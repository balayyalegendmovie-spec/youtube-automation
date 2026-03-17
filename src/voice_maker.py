"""
VOICE MAKER — Natural sounding with breathing pauses
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
        'telugu': {'female': 'te-IN-ShrutiNeural', 'male': 'te-IN-MohanNeural'},
        'hindi': {'female': 'hi-IN-SwaraNeural', 'male': 'hi-IN-MadhurNeural'}
    }

    def __init__(self, language='telugu', gender='female', config=None):
        self.language = language
        self.voice = self.VOICES[language][gender]
        self.config = config or {}
        from src.breathing import BreathingProcessor
        self.breathing_processor = BreathingProcessor(
            voice_id=self.voice,
            config=self.config.get('voice', {}).get('breathing', {}))
        logger.info(f"🎙️ Voice: {self.voice}")

    def _clean_for_tts(self, text):
        cleaned = re.sub(r'\[HOOK\]|\[SECTION_\d+:.*?\]|\[CTA\]', '', text)
        cleaned = re.sub(r'\[VISUAL:.*?\]', '', cleaned)
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        cleaned = re.sub(r'\(.*?\)', '', cleaned)

        # Natural pauses — the KEY to realistic voice
        # Triple dots = long pause (like thinking)
        cleaned = cleaned.replace('...', ' ,,, ')
        cleaned = cleaned.replace('…', ' ,,, ')
        # Dash = medium pause
        cleaned = cleaned.replace(' — ', ' ,, ')
        cleaned = cleaned.replace(' - ', ' , ')
        # After question mark = pause for effect
        cleaned = re.sub(r'\?\s+', '? ,,, ', cleaned)
        # After exclamation = brief pause
        cleaned = re.sub(r'!\s+', '! ,, ', cleaned)
        # Between paragraphs = breathing pause
        cleaned = re.sub(r'\n\s*\n', ' ,,,, ', cleaned)
        # Single newlines = brief pause
        cleaned = re.sub(r'\n', ' , ', cleaned)

        # Add filler sounds for naturalness
        cleaned = re.sub(r'So basically', 'So,,, basically', cleaned)
        cleaned = re.sub(r'OK so', 'OK,, so', cleaned)
        cleaned = re.sub(r'And honestly', 'And,, honestly', cleaned)
        cleaned = re.sub(r'But trust me', 'But,, trust me', cleaned)
        cleaned = re.sub(r'First thing', 'First thing,,', cleaned)

        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = re.sub(r',{5,}', ',,,,', cleaned)
        return cleaned.strip()

    async def _generate_audio(self, text, output_path, subtitle_path=None,
                                rate="+5%", pitch="+1Hz"):
        cleaned = self._clean_for_tts(text)
        if not cleaned:
            return None

        communicate = edge_tts.Communicate(text=cleaned, voice=self.voice,
                                            rate=rate, pitch=pitch)
        audio_data = bytearray()
        word_boundaries = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_boundaries.append({
                    "text": chunk["text"],
                    "offset": chunk["offset"],
                    "duration": chunk["duration"]
                })

        with open(output_path, "wb") as f:
            f.write(bytes(audio_data))
        logger.info(f"   📁 {output_path} ({len(audio_data)} bytes)")

        if subtitle_path and word_boundaries:
            self._write_srt(word_boundaries, subtitle_path)
        return output_path

    def _write_srt(self, boundaries, path):
        srt = []
        idx = 1
        words = []
        start = None
        for b in boundaries:
            s = b["offset"] / 10_000_000
            e = s + b["duration"] / 10_000_000
            if b["text"].strip() in [',', ',,', ',,,', ',,,,', '']:
                continue
            if start is None:
                start = s
            words.append(b["text"])
            if len(words) >= 5:
                srt.append(f"{idx}\n{self._ts(start)} --> {self._ts(e)}\n{' '.join(words)}\n")
                idx += 1
                words = []
                start = None
        if words:
            srt.append(f"{idx}\n{self._ts(start)} --> {self._ts(e)}\n{' '.join(words)}\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt))

    def _ts(self, s):
        s = s or 0
        return f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{int(s%60):02d},{int((s%1)*1000):03d}"

    def generate_full_audio(self, script, output_path, subtitle_path=None):
        logger.info(f"🎙️ Full audio ({len(script.split())} words)...")
        processed = self.breathing_processor.process_script(script, self.language)
        logger.info(f"   Est: {processed.total_estimated_duration:.0f}s")

        if subtitle_path and subtitle_path.endswith('.vtt'):
            subtitle_path = subtitle_path.replace('.vtt', '.srt')

        # SLOWER rate for natural sound
        asyncio.run(self._generate_audio(script, output_path, subtitle_path,
                                          rate="+5%", pitch="+1Hz"))
        self._post_process(output_path)
        dur = self._get_duration(output_path)
        logger.info(f"   ✅ {dur:.1f}s, {os.path.getsize(output_path)/(1024*1024):.1f} MB")
        return output_path

    def generate_section_audios(self, sections, output_dir):
        logger.info(f"🎙️ {len(sections)} sections...")
        os.makedirs(output_dir, exist_ok=True)
        results = []
        section_speeds = {
            'HOOK': ('+8%', '+2Hz'),
            'SECTION_1': ('+5%', '+1Hz'),
            'SECTION_2': ('+3%', '+0Hz'),
            'SECTION_3': ('+5%', '+1Hz'),
            'SECTION_4': ('+8%', '+2Hz'),
            'CTA': ('+3%', '+1Hz'),
        }
        for i, sec in enumerate(sections):
            mk = sec.get('marker', f'S{i}')
            text = sec.get('text', '')
            if not text.strip():
                continue
            ap = os.path.join(output_dir, f"section_{i:02d}_{mk.lower()}.mp3")
            sp = os.path.join(output_dir, f"section_{i:02d}_{mk.lower()}.srt")
            rate, pitch = section_speeds.get(mk, ('+5%', '+1Hz'))
            try:
                asyncio.run(self._generate_audio(text, ap, sp, rate, pitch))
                self._post_process(ap)
                dur = self._get_duration(ap)
                results.append({'section_marker': mk, 'section_title': sec.get('title', mk),
                               'audio_path': ap, 'subtitle_path': sp, 'duration': dur,
                               'text': text, 'word_count': len(text.split())})
                logger.info(f"   ✅ [{mk}] {dur:.1f}s")
            except Exception as e:
                logger.error(f"   ❌ [{mk}] {e}")
                try:
                    asyncio.run(edge_tts.Communicate(
                        text=self._clean_for_tts(text), voice=self.voice,
                        rate=rate, pitch=pitch).save(ap))
                    self._post_process(ap)
                    dur = self._get_duration(ap)
                    results.append({'section_marker': mk, 'section_title': sec.get('title', mk),
                                   'audio_path': ap, 'subtitle_path': None, 'duration': dur,
                                   'text': text, 'word_count': len(text.split())})
                except Exception:
                    pass
        logger.info(f"   ✅ {len(results)} audios, {sum(r['duration'] for r in results):.0f}s total")
        return results

    def _post_process(self, path):
        if not os.path.exists(path) or os.path.getsize(path) < 100:
            return
        tmp = path + '.tmp.mp3'
        try:
            subprocess.run([
                'ffmpeg', '-y', '-i', path,
                '-af', 'loudnorm=I=-16:LRA=11:TP=-1.5,equalizer=f=3000:width_type=h:width=1000:g=1',
                '-ar', '44100', '-ac', '1', '-b:a', '192k', tmp
            ], capture_output=True, timeout=120)
            if os.path.exists(tmp) and os.path.getsize(tmp) > 100:
                os.replace(tmp, path)
            elif os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)

    def _get_duration(self, path):
        try:
            r = subprocess.run(['ffprobe', '-v', 'quiet', '-show_entries',
                               'format=duration', '-of', 'csv=p=0', path],
                              capture_output=True, text=True, timeout=30)
            return float(r.stdout.strip())
        except Exception:
            return os.path.getsize(path) / 24000 if os.path.exists(path) else 30
