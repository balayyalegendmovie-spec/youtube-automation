"""
VOICE MAKER — Natural TTS with Breathing & Emotions
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
        cleaned = text
        cleaned = re.sub(r'\[HOOK\]|\[SECTION_\d+:.*?\]|\[CTA\]', '', cleaned)
        cleaned = re.sub(r'\[VISUAL:.*?\]', '', cleaned)
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = cleaned.strip()
        return cleaned

    async def _generate_audio_with_timestamps(self, text, output_path,
                                                subtitle_path=None,
                                                rate="+2%", pitch="+1Hz"):
        cleaned_text = self._clean_for_tts(text)
        if not cleaned_text:
            logger.warning("   ⚠️ Empty text after cleaning")
            return None

        communicate = edge_tts.Communicate(
            text=cleaned_text,
            voice=self.voice,
            rate=rate,
            pitch=pitch
        )

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

        logger.info(f"   📁 Audio saved: {output_path} ({len(audio_data)} bytes)")

        if subtitle_path and word_boundaries:
            self._create_srt_from_boundaries(word_boundaries, subtitle_path)
            logger.info(f"   📝 Subtitles saved: {subtitle_path}")

        return output_path

    def _create_srt_from_boundaries(self, boundaries, output_path):
        if not boundaries:
            return
        srt_content = []
        subtitle_index = 1
        words_per_line = 6
        current_words = []
        current_start = None
        current_end = None

        for boundary in boundaries:
            word = boundary["text"]
            start_time = boundary["offset"] / 10_000_000
            end_time = start_time + boundary["duration"] / 10_000_000

            if current_start is None:
                current_start = start_time
            current_words.append(word)
            current_end = end_time

            if len(current_words) >= words_per_line:
                srt_content.append(
                    f"{subtitle_index}\n"
                    f"{self._format_srt_time(current_start)} --> "
                    f"{self._format_srt_time(current_end)}\n"
                    f"{' '.join(current_words)}\n"
                )
                subtitle_index += 1
                current_words = []
                current_start = None
                current_end = None

        if current_words:
            srt_content.append(
                f"{subtitle_index}\n"
                f"{self._format_srt_time(current_start)} --> "
                f"{self._format_srt_time(current_end)}\n"
                f"{' '.join(current_words)}\n"
            )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_content))

    def _format_srt_time(self, seconds):
        if seconds is None:
            seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def generate_full_audio(self, script, output_path, subtitle_path=None):
        logger.info(f"🎙️ STEP: Generating full voiceover...")
        logger.info(f"   Script length: {len(script.split())} words")

        logger.info(f"   🫁 Processing breathing and emotions...")
        processed = self.breathing_processor.process_script(
            script, self.language
        )
        logger.info(f"   ✅ Estimated duration: {processed.total_estimated_duration:.0f}s")
        logger.info(f"   ✅ Emotions: {', '.join(processed.emotions_used)}")

        logger.info(f"   🔊 Generating audio with Edge TTS...")

        if subtitle_path:
            if subtitle_path.endswith('.vtt'):
                subtitle_path = subtitle_path.replace('.vtt', '.srt')

        asyncio.run(
            self._generate_audio_with_timestamps(
                text=script,
                output_path=output_path,
                subtitle_path=subtitle_path,
                rate="+2%",
                pitch="+1Hz"
            )
        )

        logger.info(f"   🎛️ Post-processing audio...")
        self._post_process(output_path)

        duration = self._get_duration(output_path)
        file_size = os.path.getsize(output_path) / (1024 * 1024)

        logger.info(f"   ✅ Full audio complete:")
        logger.info(f"      Duration: {duration:.1f}s")
        logger.info(f"      File size: {file_size:.1f} MB")

        return output_path

    def generate_section_audios(self, sections, output_dir):
        logger.info(f"🎙️ STEP: Generating section audio ({len(sections)} sections)...")

        os.makedirs(output_dir, exist_ok=True)
        section_audios = []

        for i, section in enumerate(sections):
            marker = section.get('marker', f'SECTION_{i}')
            text = section.get('text', '')
            title = section.get('title', marker)

            if not text.strip():
                logger.info(f"   ⏭️ [{marker}] Empty text, skipping")
                continue

            word_count = len(text.split())
            logger.info(f"   🎤 [{marker}] Generating audio ({word_count} words)...")

            audio_path = os.path.join(output_dir, f"section_{i:02d}_{marker.lower()}.mp3")
            subtitle_path = os.path.join(output_dir, f"section_{i:02d}_{marker.lower()}.srt")

            rate, pitch = self._get_section_voice_params(marker)

            try:
                asyncio.run(
                    self._generate_audio_with_timestamps(
                        text=text,
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
                    'word_count': word_count
                })

                logger.info(f"   ✅ [{marker}] {duration:.1f}s audio generated")

            except Exception as e:
                logger.error(f"   ❌ [{marker}] Audio failed: {e}")

                try:
                    logger.info(f"   🔄 [{marker}] Retrying without subtitles...")
                    communicate = edge_tts.Communicate(
                        text=self._clean_for_tts(text),
                        voice=self.voice, rate=rate, pitch=pitch
                    )
                    asyncio.run(communicate.save(audio_path))

                    self._post_process(audio_path)
                    duration = self._get_duration(audio_path)

                    section_audios.append({
                        'section_marker': marker,
                        'section_title': title,
                        'audio_path': audio_path,
                        'subtitle_path': None,
                        'duration': duration,
                        'text': text,
                        'word_count': word_count
                    })
                    logger.info(f"   ✅ [{marker}] {duration:.1f}s (no subtitles)")
                except Exception as e2:
                    logger.error(f"   ❌ [{marker}] Fallback failed: {e2}")

        total_duration = sum(s['duration'] for s in section_audios)
        logger.info(f"   ✅ Section audio complete: {len(section_audios)} sections, "
                    f"{total_duration:.0f}s total")

        return section_audios

    def _get_section_voice_params(self, marker):
        """Natural-sounding voice parameters per section"""
        params = {
            'HOOK': ('+8%', '+3Hz'),
            'SECTION_1': ('+3%', '+0Hz'),
            'SECTION_2': ('+0%', '-2Hz'),
            'SECTION_3': ('+3%', '+2Hz'),
            'SECTION_4': ('+5%', '+3Hz'),
            'CTA': ('+0%', '+1Hz'),
        }
        return params.get(marker, ('+3%', '+0Hz'))

    def _post_process(self, audio_path):
        if not os.path.exists(audio_path):
            return
        file_size = os.path.getsize(audio_path)
        if file_size < 100:
            return

        processed_path = audio_path + '.tmp.mp3'
        try:
            cmd = [
                'ffmpeg', '-y', '-i', audio_path,
                '-af', 'loudnorm=I=-16:LRA=11:TP=-1.5',
                '-ar', '44100', '-ac', '1', '-b:a', '128k',
                processed_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and os.path.exists(processed_path):
                if os.path.getsize(processed_path) > 100:
                    os.replace(processed_path, audio_path)
                else:
                    os.remove(processed_path)
            else:
                if os.path.exists(processed_path):
                    os.remove(processed_path)
        except Exception as e:
            logger.warning(f"   ⚠️ Post-processing skipped: {e}")
            if os.path.exists(processed_path):
                os.remove(processed_path)

    def _get_duration(self, audio_path):
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0', audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return float(result.stdout.strip())
        except Exception:
            try:
                size = os.path.getsize(audio_path)
                return size / 16000
            except Exception:
                return 30.0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    vm = VoiceMaker('telugu', 'female')
    vm.generate_full_audio(
        "నమస్కారం! ఈ వీడియోలో మనం తెలుసుకుందాం.",
        "output/test_voice.mp3",
        "output/test_voice.srt"
    )
    print("Done!")
