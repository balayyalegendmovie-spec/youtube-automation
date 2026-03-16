"""
VOICE MAKER — Fast Natural TTS with Breathing & Emotions
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
        self.gender = gender
        self.voice = self.VOICES[language][gender]
        self.config = config or {}

        from src.breathing import BreathingProcessor
        self.breathing_processor = BreathingProcessor(
            voice_id=self.voice,
            config=self.config.get('voice', {}).get('breathing', {})
        )

        logger.info(f"🎙️ Voice Maker initialized")
        logger.info(f"   Language: {language}, Voice: {self.voice}")

    def _clean_for_tts(self, text):
        cleaned = re.sub(r'\[HOOK\]|\[SECTION_\d+:.*?\]|\[CTA\]', '', text)
        cleaned = re.sub(r'\[VISUAL:.*?\]', '', cleaned)
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        cleaned = re.sub(r'\(.*?\)', '', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        return cleaned.strip()

    async def _generate_audio_with_timestamps(self, text, output_path,
                                                subtitle_path=None,
                                                rate="+15%", pitch="+2Hz"):
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

        logger.info(f"   📁 Audio: {output_path} ({len(audio_data)} bytes)")

        if subtitle_path and word_boundaries:
            self._create_srt(word_boundaries, subtitle_path)

        return output_path

    def _create_srt(self, boundaries, output_path):
        srt = []
        idx = 1
        words = []
        start = None
        end = None

        for b in boundaries:
            s = b["offset"] / 10_000_000
            e = s + b["duration"] / 10_000_000
            if start is None:
                start = s
            words.append(b["text"])
            end = e

            if len(words) >= 6:
                srt.append(f"{idx}\n{self._fmt(start)} --> {self._fmt(end)}\n{' '.join(words)}\n")
                idx += 1
                words = []
                start = None

        if words:
            srt.append(f"{idx}\n{self._fmt(start)} --> {self._fmt(end)}\n{' '.join(words)}\n")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt))

    def _fmt(self, s):
        if s is None:
            s = 0
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        ms = int((s % 1) * 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    def generate_full_audio(self, script, output_path, subtitle_path=None):
        logger.info(f"🎙️ STEP: Generating voiceover...")
        logger.info(f"   Words: {len(script.split())}")

        processed = self.breathing_processor.process_script(script, self.language)
        logger.info(f"   ✅ Duration est: {processed.total_estimated_duration:.0f}s")
        logger.info(f"   ✅ Emotions: {', '.join(processed.emotions_used)}")

        if subtitle_path and subtitle_path.endswith('.vtt'):
            subtitle_path = subtitle_path.replace('.vtt', '.srt')

        asyncio.run(self._generate_audio_with_timestamps(
            text=script, output_path=output_path,
            subtitle_path=subtitle_path,
            rate="+15%", pitch="+2Hz"
        ))

        self._post_process(output_path)
        duration = self._get_duration(output_path)
        size = os.path.getsize(output_path) / (1024 * 1024)

        logger.info(f"   ✅ Audio: {duration:.1f}s, {size:.1f} MB")
        return output_path

    def generate_section_audios(self, sections, output_dir):
        logger.info(f"🎙️ Generating {len(sections)} section audios...")
        os.makedirs(output_dir, exist_ok=True)
        results = []

        for i, sec in enumerate(sections):
            marker = sec.get('marker', f'S{i}')
            text = sec.get('text', '')
            if not text.strip():
                continue

            wc = len(text.split())
            logger.info(f"   🎤 [{marker}] {wc} words...")

            ap = os.path.join(output_dir, f"section_{i:02d}_{marker.lower()}.mp3")
            sp = os.path.join(output_dir, f"section_{i:02d}_{marker.lower()}.srt")

            rate, pitch = self._section_params(marker)

            try:
                asyncio.run(self._generate_audio_with_timestamps(
                    text=text, output_path=ap, subtitle_path=sp,
                    rate=rate, pitch=pitch
                ))
                self._post_process(ap)
                dur = self._get_duration(ap)

                results.append({
                    'section_marker': marker, 'section_title': sec.get('title', marker),
                    'audio_path': ap, 'subtitle_path': sp,
                    'duration': dur, 'text': text, 'word_count': wc
                })
                logger.info(f"   ✅ [{marker}] {dur:.1f}s")

            except Exception as e:
                logger.error(f"   ❌ [{marker}] Failed: {e}")
                try:
                    comm = edge_tts.Communicate(text=self._clean_for_tts(text),
                                                 voice=self.voice, rate=rate, pitch=pitch)
                    asyncio.run(comm.save(ap))
                    self._post_process(ap)
                    dur = self._get_duration(ap)
                    results.append({
                        'section_marker': marker, 'section_title': sec.get('title', marker),
                        'audio_path': ap, 'subtitle_path': None,
                        'duration': dur, 'text': text, 'word_count': wc
                    })
                    logger.info(f"   ✅ [{marker}] {dur:.1f}s (no subs)")
                except Exception as e2:
                    logger.error(f"   ❌ [{marker}] Retry failed: {e2}")

        total = sum(r['duration'] for r in results)
        logger.info(f"   ✅ Total: {len(results)} sections, {total:.0f}s")
        return results

    def _section_params(self, marker):
        """Fast energetic voice per section type"""
        return {
            'HOOK': ('+18%', '+4Hz'),
            'SECTION_1': ('+15%', '+2Hz'),
            'SECTION_2': ('+12%', '+0Hz'),
            'SECTION_3': ('+15%', '+3Hz'),
            'SECTION_4': ('+18%', '+4Hz'),
            'CTA': ('+12%', '+2Hz'),
        }.get(marker, ('+15%', '+2Hz'))

    def _post_process(self, path):
        if not os.path.exists(path) or os.path.getsize(path) < 100:
            return
        tmp = path + '.tmp.mp3'
        try:
            subprocess.run([
                'ffmpeg', '-y', '-i', path,
                '-af', 'loudnorm=I=-16:LRA=11:TP=-1.5',
                '-ar', '44100', '-ac', '1', '-b:a', '192k', tmp
            ], capture_output=True, text=True, timeout=120)
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
            try:
                return os.path.getsize(path) / 24000
            except Exception:
                return 30.0
