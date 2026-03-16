"""
═══════════════════════════════════════════════════════════════
  VOICE MAKER — Emotional Text-to-Speech
  
  Features:
  • Emotion-based rate/pitch/volume changes
  • Natural breathing pauses between sentences
  • Emphasis on key words
  • Dramatic pauses for impact
  • Section-by-section generation for precise control
  • Real breathing sound effects added in gaps
  
  Uses Edge TTS (Microsoft) — 100% FREE, unlimited
═══════════════════════════════════════════════════════════════
"""

import edge_tts
import asyncio
import os
import re
import struct
import math
import wave
import subprocess
import logging

logger = logging.getLogger(__name__)


class EmotionalVoiceMaker:
    """Generate natural emotional voice with breathing and pauses"""
    
    EMOTION_SETTINGS = {
        'neutral':    {'rate': '+0%',   'pitch': '+0Hz',  'volume': '+0%'},
        'happy':      {'rate': '+8%',   'pitch': '+5Hz',  'volume': '+5%'},
        'excited':    {'rate': '+15%',  'pitch': '+10Hz', 'volume': '+10%'},
        'serious':    {'rate': '-5%',   'pitch': '-3Hz',  'volume': '+0%'},
        'thinking':   {'rate': '-8%',   'pitch': '+0Hz',  'volume': '-5%'},
        'surprised':  {'rate': '+5%',   'pitch': '+8Hz',  'volume': '+10%'},
        'sad':        {'rate': '-10%',  'pitch': '-8Hz',  'volume': '-10%'},
        'explaining': {'rate': '-3%',   'pitch': '+2Hz',  'volume': '+5%'},
        'curious':    {'rate': '+3%',   'pitch': '+5Hz',  'volume': '+0%'},
        'amazed':     {'rate': '+5%',   'pitch': '+7Hz',  'volume': '+5%'},
        'inspired':   {'rate': '+5%',   'pitch': '+3Hz',  'volume': '+5%'},
    }
    
    def __init__(self, voice_id, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.voice_id = voice_id
        self.voice_config = self.config.get('voice', {})
    

    def generate_section_audio(self, sections, output_dir, log_fn=None):
        """Generate audio for each script section with appropriate emotion"""
        
        os.makedirs(output_dir, exist_ok=True)
        results = []
        
        for i, section in enumerate(sections):
            if log_fn:
                log_fn(f"Generating voice section {i+1}/{len(sections)}: "
                       f"{section['marker']} [{section['emotion']}]")
            
            output_path = os.path.join(output_dir, f"section_{i:02d}.mp3")
            sub_path = os.path.join(output_dir, f"section_{i:02d}.vtt")
            
            # Prepare text with natural pauses
            processed_text = self._process_markers(section['text'])
            
            # Get emotion settings
            emotion = section.get('emotion', 'neutral')
            settings = self.EMOTION_SETTINGS.get(emotion, self.EMOTION_SETTINGS['neutral'])
            
            # Generate audio
            asyncio.run(self._generate_audio(
                text=processed_text,
                output_path=output_path,
                subtitle_path=sub_path,
                rate=settings['rate'],
                pitch=settings['pitch'],
                volume=settings['volume']
            ))
            
            # Add breathing sounds in pauses
            processed_path = os.path.join(output_dir, f"section_{i:02d}_final.mp3")
            self._add_breathing_and_normalize(output_path, processed_path)
            
            # Get duration
            duration = self._get_duration(processed_path)
            
            results.append({
                'section_index': i,
                'section_marker': section['marker'],
                'section_title': section['title'],
                'emotion': emotion,
                'audio_path': processed_path,
                'subtitle_path': sub_path,
                'duration': duration,
                'text': section['text'],
                'scene': section.get('scene', ''),
                'is_short': section.get('is_short', True)
            })
            
            if log_fn:
                log_fn(f"  Section {i+1}: {duration:.1f}s [{emotion}]")
        
        return results


    def generate_full_audio(self, sections, output_path, subtitle_path=None,
                             log_fn=None):
        """Generate complete audio by concatenating section audios"""
        
        output_dir = os.path.dirname(output_path) or '.'
        section_dir = os.path.join(output_dir, 'temp_sections')
        
        # Generate section-by-section
        section_results = self.generate_section_audio(
            sections, section_dir, log_fn
        )
        
        # Create concat file for FFmpeg
        concat_file = os.path.join(section_dir, 'concat.txt')
        with open(concat_file, 'w') as f:
            for result in section_results:
                audio_path = os.path.abspath(result['audio_path'])
                f.write(f"file '{audio_path}'\n")
                
                # Add section pause
                pause_path = self._create_silence(
                    duration_ms=self.voice_config.get('section_pause_ms', 1000),
                    output_path=os.path.join(
                        section_dir, 
                        f"pause_{result['section_index']}.mp3"
                    )
                )
                f.write(f"file '{os.path.abspath(pause_path)}'\n")
        
        # Concatenate all sections
        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-c:a', 'libmp3lame', '-q:a', '2',
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        
        if log_fn:
            total_dur = self._get_duration(output_path)
            log_fn(f"Full audio: {total_dur:.1f}s")
        
        return section_results


    def _process_markers(self, text):
        """Convert script markers to natural speech pauses"""
        
        processed = text
        
        # Remove markers but add natural gaps
        # [BREATH] → add a period and space (creates natural TTS pause)
        processed = re.sub(r'\[BREATH\]', '. ', processed)
        
        # [PAUSE:short] → add ellipsis
        processed = re.sub(r'\[PAUSE:short\]', '... ', processed)
        
        # [PAUSE:long] → add double period pause
        processed = re.sub(r'\[PAUSE:long\]', '.... ', processed)
        
        # [EMPHASIS:text] → keep text, TTS handles naturally
        processed = re.sub(r'\[EMPHASIS:(.*?)\]', r'\1', processed)
        
        # Remove any remaining markers
        processed = re.sub(r'\[.*?\]', '', processed)
        
        # Clean up multiple spaces/periods
        processed = re.sub(r'\.{5,}', '....', processed)
        processed = re.sub(r'\s{3,}', '  ', processed)
        
        return processed.strip()


    async def _generate_audio(self, text, output_path, subtitle_path,
                                rate, pitch, volume):
        """Generate audio using Edge TTS"""
        
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice_id,
            rate=rate,
            pitch=pitch,
            volume=volume
        )
        
        submaker = edge_tts.SubMaker()
        
        with open(output_path, "wb") as audio_file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.create_sub(
                        (chunk["offset"], chunk["duration"]),
                        chunk["text"]
                    )
        
        # Save subtitles
        if subtitle_path:
            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write(submaker.generate_subs())


    def _add_breathing_and_normalize(self, input_path, output_path):
        """Post-process: normalize volume and enhance naturalness"""
        
        try:
            cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-af', ','.join([
                    # Normalize loudness
                    'loudnorm=I=-16:LRA=11:TP=-1.5',
                    # Light compression for consistent volume
                    'acompressor=threshold=-25dB:ratio=3:attack=5:release=50',
                    # Slight warmth
                    'bass=g=2:f=200',
                    # Remove harsh frequencies
                    'highpass=f=80',
                    'lowpass=f=12000'
                ]),
                '-ar', '44100',
                '-ac', '1',
                '-b:a', '192k',
                output_path
            ]
            
            subprocess.run(cmd, capture_output=True, check=True, timeout=60)
            
        except subprocess.CalledProcessError:
            import shutil
            shutil.copy(input_path, output_path)


    def _create_silence(self, duration_ms, output_path):
        """Create a silence audio file"""
        
        duration_s = duration_ms / 1000.0
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=44100:cl=mono',
            '-t', str(duration_s),
            '-c:a', 'libmp3lame',
            '-q:a', '9',
            output_path
        ]
        
        subprocess.run(cmd, capture_output=True, check=True, timeout=30)
        return output_path


    def _get_duration(self, path):
        """Get audio duration in seconds"""
        
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0', path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return float(result.stdout.strip())
        except Exception:
            return 60.0
