"""
VOICE MAKER — Natural Emotional TTS using Edge TTS + Breathing Engine

Pipeline:
1. Script text comes in
2. breathing.py processes it (adds pauses, emotions, SSML)
3. Edge TTS generates audio with SSML
4. Post-processing normalizes volume
5. Word-level timestamps generated for subtitles

Voices used:
- Telugu: te-IN-ShrutiNeural (female) / te-IN-MohanNeural (male)
- Hindi: hi-IN-SwaraNeural (female) / hi-IN-MadhurNeural (male)
"""

import edge_tts
import asyncio
import os
import subprocess
import logging
import re

logger = logging.getLogger(__name__)


class VoiceMaker:
    
    VOICES = {
        'telugu': {
            'female': 'te-IN-ShrutiNeural',
            'male': 'te-IN-MohanNeural'
        },
        'hindi': {
            'female': 'hi-IN-SwaraNeural',
            'male': 'hi-IN-MadhurNeural'
        }
    }
    
    def __init__(self, language='telugu', gender='female', config=None):
        self.language = language
        self.gender = gender
        self.voice = self.VOICES[language][gender]
        self.config = config or {}
        
        # Import breathing processor
        from src.breathing import BreathingProcessor
        self.breathing_processor = BreathingProcessor(
            voice_id=self.voice,
            config=self.config.get('voice', {}).get('breathing', {})
        )
        
        logger.info(f"🎙️ Voice Maker initialized")
        logger.info(f"   Language: {language}")
        logger.info(f"   Voice: {self.voice}")
        logger.info(f"   Breathing: enabled")
    

    def _clean_for_tts(self, text):
        """Clean text for TTS — remove markers, visual cues"""
        
        cleaned = text
        cleaned = re.sub(r'\[HOOK\]|\[SECTION_\d+:.*?\]|\[CTA\]', '', cleaned)
        cleaned = re.sub(r'\[VISUAL:.*?\]', '', cleaned)
        
        # Remove SSML tags that Edge TTS doesn't support well
        # Keep only: break, prosody, emphasis
        # Remove nested prosody (Edge TTS doesn't like it)
        cleaned = re.sub(r'<speak>|</speak>', '', cleaned)
        cleaned = re.sub(r'<voice[^>]*>|</voice>', '', cleaned)
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned
    

    async def _generate_with_emotion(self, text, output_path, 
                                       subtitle_path=None, rate="+5%", 
                                       pitch="+0Hz"):
        """Generate audio using Edge TTS with emotion parameters"""
        
        cleaned_text = self._clean_for_tts(text)
        
        if not cleaned_text:
            logger.warning("   ⚠️ Empty text after cleaning, skipping")
            return None
        
        communicate = edge_tts.Communicate(
            text=cleaned_text,
            voice=self.voice,
            rate=rate,
            pitch=pitch
        )
        
        if subtitle_path:
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
            
            with open(subtitle_path, "w", encoding="utf-8") as sub_file:
                sub_content = submaker.generate_subs()
                sub_file.write(sub_content)
            
            logger.info(f"   📝 Subtitles saved: {subtitle_path}")
        else:
            await communicate.save(output_path)
        
        return output_path
    

    def generate_full_audio(self, script, output_path, subtitle_path=None):
        """
        Generate complete audio for full script with emotions.
        
        Flow:
        1. Process through breathing engine
        2. Generate audio with Edge TTS
        3. Post-process for quality
        """
        
        logger.info(f"🎙️ STEP: Generating full voiceover...")
        logger.info(f"   Script length: {len(script.split())} words")
        
        # Step 1: Process through breathing engine
        logger.info(f"   🫁 Processing breathing and emotions...")
        processed = self.breathing_processor.process_script(
            script, self.language
        )
        logger.info(f"   ✅ Estimated duration: {processed.total_estimated_duration:.0f}s")
        logger.info(f"   ✅ Emotions: {', '.join(processed.emotions_used)}")
        
        # Step 2: Generate audio
        logger.info(f"   🔊 Generating audio with Edge TTS...")
        
        # Use cleaned version (TTS sometimes struggles with complex SSML)
        clean_script = self._clean_for_tts(script)
        
        asyncio.run(
            self._generate_with_emotion(
                text=clean_script,
                output_path=output_path,
                subtitle_path=subtitle_path,
                rate="+5%",
                pitch="+0Hz"
            )
        )
        
        # Step 3: Post-process
        logger.info(f"   🎛️ Post-processing audio...")
        self._post_process(output_path)
        
        # Get final duration
        duration = self._get_duration(output_path)
        file_size = os.path.getsize(output_path) / (1024 * 1024)
        
        logger.info(f"   ✅ Full audio complete:")
        logger.info(f"      Duration: {duration:.1f}s")
        logger.info(f"      File size: {file_size:.1f} MB")
        
        return output_path
    

    def generate_section_audios(self, sections, output_dir):
        """
        Generate separate audio for each section (for shorts).
        Returns list of section audio info.
        """
        
        logger.info(f"🎙️ STEP: Generating section-wise audio ({len(sections)} sections)...")
        
        os.makedirs(output_dir, exist_ok=True)
        section_audios = []
        
        for i, section in enumerate(sections):
            marker = section.get('marker', f'SECTION_{i}')
            text = section.get('text', '')
            title = section.get('title', marker)
            
            if not text.strip():
                logger.info(f"   ⏭️ [{marker}] Empty text, skipping")
                continue
            
            logger.info(f"   🎤 [{marker}] Generating audio ({len(text.split())} words)...")
            
            audio_path = os.path.join(output_dir, f"section_{i:02d}_{marker.lower()}.mp3")
            subtitle_path = os.path.join(output_dir, f"section_{i:02d}_{marker.lower()}.vtt")
            
            # Process section through breathing engine
            section_ssml = self.breathing_processor.process_section(
                text, marker, self.language
            )
            
            # Determine emotion-based voice parameters
            rate, pitch = self._get_section_voice_params(marker)
            
            # Generate audio
            try:
                clean_text = self._clean_for_tts(text)
                
                asyncio.run(
                    self._generate_with_emotion(
                        text=clean_text,
                        output_path=audio_path,
                        subtitle_path=subtitle_path,
                        rate=rate,
                        pitch=pitch
                    )
                )
                
                self._post_process(audio_path)
                duration = self._get_duration(audio_path)
                
                section_audios.append({
                    'section_marker': marker,
                    'section_title': title,
                    'audio_path': audio_path,
                    'subtitle_path': subtitle_path,
                    'duration': duration,
                    'text': text,
                    'word_count': len(text.split())
                })
                
                logger.info(f"   ✅ [{marker}] {duration:.1f}s audio generated")
                
            except Exception as e:
                logger.error(f"   ❌ [{marker}] Audio generation failed: {e}")
        
        total_duration = sum(s['duration'] for s in section_audios)
        logger.info(f"   ✅ Section audio complete: {len(section_audios)} sections, "
                    f"{total_duration:.0f}s total")
        
        return section_audios
    

    def _get_section_voice_params(self, marker):
        """Get voice rate/pitch based on section type"""
        
        params = {
            'HOOK': ('+10%', '+5Hz'),
            'SECTION_1': ('+5%', '+0Hz'),
            'SECTION_2': ('+3%', '-2Hz'),
            'SECTION_3': ('+5%', '+3Hz'),
            'SECTION_4': ('+8%', '+5Hz'),
            'CTA': ('+3%', '+2Hz'),
        }
        
        return params.get(marker, ('+5%', '+0Hz'))
    

    def _post_process(self, audio_path):
        """Normalize audio volume and improve quality"""
        
        processed_path = audio_path + '.processed.mp3'
        
        try:
            cmd = [
                'ffmpeg', '-y', '-i', audio_path,
                '-af', (
                    'loudnorm=I=-16:LRA=11:TP=-1.5,'
                    'acompressor=threshold=-20dB:ratio=3:attack=5:release=50,'
                    'equalizer=f=200:width_type=h:width=100:g=2,'
                    'equalizer=f=3000:width_type=h:width=1000:g=1.5'
                ),
                '-ar', '44100',
                '-ac', '1',
                '-b:a', '128k',
                processed_path
            ]
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            
            if result.returncode == 0:
                os.replace(processed_path, audio_path)
            else:
                logger.warning(f"   ⚠️ Post-processing returned non-zero, using original")
                if os.path.exists(processed_path):
                    os.remove(processed_path)
                    
        except Exception as e:
            logger.warning(f"   ⚠️ Post-processing failed: {e}")
            if os.path.exists(processed_path):
                os.remove(processed_path)
    

    def _get_duration(self, audio_path):
        """Get audio duration in seconds"""
        
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return float(result.stdout.strip())
        except Exception:
            return 60.0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    vm = VoiceMaker('telugu', 'female')
    vm.generate_full_audio(
        "నమస్కారం! ఈ వీడియోలో మనం అంతరిక్షం గురించి తెలుసుకుందాం.",
        "output/test_voice.mp3",
        "output/test_voice.vtt"
    )
