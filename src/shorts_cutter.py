"""
SHORTS CUTTER — Cuts long video sections into vertical shorts
Uses functions from video_animator (not class imports)
"""

import os
import logging
from moviepy.editor import (
    VideoFileClip, AudioFileClip, TextClip,
    CompositeVideoClip, concatenate_videoclips, ColorClip,
    ImageSequenceClip, ImageClip
)
import numpy as np

logger = logging.getLogger(__name__)


class ShortsCutter:

    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.max_dur = self.config.get('content',{}).get('shorts',{}).get('max_duration_seconds', 58)
        self.min_dur = self.config.get('content',{}).get('shorts',{}).get('min_duration_seconds', 25)
        logger.info("✂️ Shorts Cutter initialized")

    def cut_shorts(self, section_audios, footage_clips, language,
                    channel_config, output_dir, long_video_url=""):
        logger.info(f"✂️ STEP: Cutting shorts from {len(section_audios)} sections...")
        os.makedirs(output_dir, exist_ok=True)

        from src.video_animator import VideoAnimator
        animator = VideoAnimator("config/config.yaml")

        created = []
        skipped = 0

        for i, section in enumerate(section_audios):
            marker = section.get('section_marker', f'SECTION_{i}')
            duration = section.get('duration', 0)

            if marker == 'CTA':
                logger.info(f"   ⏭️ [{marker}] Skipping CTA")
                skipped += 1
                continue

            if duration > self.max_dur:
                duration = self.max_dur
            elif duration < self.min_dur:
                logger.info(f"   ⏭️ [{marker}] Too short ({duration:.0f}s)")
                skipped += 1
                continue

            output_path = os.path.join(output_dir, f"short_{i:02d}_{marker.lower()}.mp4")
            logger.info(f"   🎬 Short {i+1}: [{marker}] ({duration:.0f}s)")

            try:
                # Get a few keywords from footage_clips
                kw_list = []
                if isinstance(footage_clips, list):
                    for fc in footage_clips[:3]:
                        if isinstance(fc, str):
                            kw_list.append(os.path.basename(fc).replace('.mp4','').replace('clip_','').replace('_',' '))
                        elif isinstance(fc, dict):
                            kw_list.append(fc.get('keyword', 'technology'))

                if not kw_list:
                    kw_list = ['technology', 'science', 'space']

                animator.create_anime_short(
                    voice_path=section['audio_path'],
                    section_text=section.get('text', ''),
                    footage_keywords=kw_list,
                    language=language,
                    channel_config=channel_config,
                    output_path=output_path
                )

                file_size = os.path.getsize(output_path) / (1024*1024)
                created.append({
                    'path': output_path,
                    'duration': duration,
                    'section_marker': marker,
                    'section_title': section.get('section_title', marker),
                    'text': section.get('text', ''),
                    'file_size_mb': round(file_size, 1)
                })
                logger.info(f"   ✅ Short {i+1}: {file_size:.1f} MB")

            except Exception as e:
                logger.error(f"   ❌ Short {i+1} failed: {e}")

        logger.info(f"✂️ Done: {len(created)} created, {skipped} skipped")
        return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("ShortsCutter ready")
