"""
SHORTS CUTTER — Cuts Long-Form Video Into Vertical Anime Shorts

Pipeline:
1. Takes section audio files (from voice_maker)
2. Downloads fresh footage per short (or reuses)
3. Applies anime filter
4. Renders in 9:16 vertical format
5. Adds animated character
6. Adds CTA overlay ("Full video on channel")
7. Each short is standalone — works WITHOUT watching the long video

Output: 4-6 shorts per long video, each 25-58 seconds
"""

import os
import logging
import random
import tempfile
import shutil
from moviepy.editor import (
    VideoFileClip, AudioFileClip, TextClip,
    CompositeVideoClip, CompositeAudioClip,
    concatenate_videoclips, ColorClip, ImageClip,
    ImageSequenceClip
)
from moviepy.video.fx.all import crop, resize
import numpy as np

logger = logging.getLogger(__name__)


class ShortsCutter:
    """Cuts long-form content into vertical anime shorts"""
    
    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.shorts_w = self.config['content']['shorts']['resolution_w']
        self.shorts_h = self.config['content']['shorts']['resolution_h']
        self.shorts_size = (self.shorts_w, self.shorts_h)
        self.max_duration = self.config['content']['shorts']['max_duration_seconds']
        self.min_duration = self.config['content']['shorts']['min_duration_seconds']
        self.fps = self.config['content']['shorts']['fps']
        self.bitrate = self.config['content']['shorts']['bitrate']
        
        logger.info("✂️ Shorts Cutter initialized")
        logger.info(f"   Resolution: {self.shorts_w}x{self.shorts_h}")
        logger.info(f"   Duration range: {self.min_duration}-{self.max_duration}s")
    

    def cut_shorts(self, section_audios, footage_clips, language,
                    channel_config, output_dir, long_video_url=""):
        """
        Create shorts from section audio files.
        
        Args:
            section_audios: List of dicts with audio_path, duration, section_marker, text
            footage_clips: List of downloaded footage file paths
            language: 'telugu' or 'hindi'
            channel_config: Channel configuration dict
            output_dir: Where to save shorts
            long_video_url: URL of long video (for CTA)
        
        Returns:
            List of created short info dicts
        """
        
        logger.info(f"✂️ STEP: Cutting shorts from {len(section_audios)} sections...")
        
        os.makedirs(output_dir, exist_ok=True)
        created_shorts = []
        skipped = 0
        failed = 0
        
        for i, section in enumerate(section_audios):
            marker = section.get('section_marker', f'SECTION_{i}')
            duration = section.get('duration', 0)
            
            # Skip CTA section — not good as standalone short
            if marker == 'CTA':
                logger.info(f"   ⏭️ Skipping [{marker}] — CTA not suitable for short")
                skipped += 1
                continue
            
            # Check duration bounds
            if duration > self.max_duration:
                logger.info(f"   ⚠️ [{marker}] {duration:.0f}s > {self.max_duration}s — will trim")
                duration = self.max_duration
            elif duration < self.min_duration:
                logger.info(f"   ⏭️ Skipping [{marker}] — too short ({duration:.0f}s < {self.min_duration}s)")
                skipped += 1
                continue
            
            output_path = os.path.join(output_dir, f"short_{i:02d}_{marker.lower()}.mp4")
            
            logger.info(f"   🎬 Creating short {i+1}: [{marker}] ({duration:.0f}s)")
            
            try:
                self._create_single_short(
                    audio_path=section['audio_path'],
                    subtitle_path=section.get('subtitle_path'),
                    footage_clips=footage_clips,
                    duration=duration,
                    section_title=section.get('section_title', marker),
                    section_text=section.get('text', ''),
                    language=language,
                    channel_config=channel_config,
                    long_video_url=long_video_url,
                    output_path=output_path
                )
                
                file_size = os.path.getsize(output_path) / (1024 * 1024)
                
                created_shorts.append({
                    'path': output_path,
                    'duration': duration,
                    'section_marker': marker,
                    'section_title': section.get('section_title', marker),
                    'text': section.get('text', ''),
                    'file_size_mb': round(file_size, 1)
                })
                
                logger.info(f"   ✅ Short {i+1} created: {file_size:.1f} MB")
                
            except Exception as e:
                logger.error(f"   ❌ Short {i+1} failed: {e}")
                failed += 1
        
        logger.info(f"✂️ Shorts cutting complete:")
        logger.info(f"   ✅ Created: {len(created_shorts)}")
        logger.info(f"   ⏭️ Skipped: {skipped}")
        logger.info(f"   ❌ Failed: {failed}")
        
        return created_shorts
    

    def _create_single_short(self, audio_path, subtitle_path, footage_clips,
                               duration, section_title, section_text, language,
                               channel_config, long_video_url, output_path):
        """Create one vertical anime short"""
        
        from src.video_animator import AnimeFilter, AnimeCharacterGenerator
        
        # Load audio
        audio = AudioFileClip(audio_path)
        actual_duration = min(audio.duration, self.max_duration)
        
        # ── Background ──
        bg_clip = self._create_vertical_background(
            footage_clips, actual_duration
        )
        
        # ── Character Animation ──
        char_config = channel_config.get('character', {})
        character = AnimeCharacterGenerator(char_config)
        
        try:
            char_frames = character.generate_animation_frames(
                duration_seconds=min(actual_duration, 30),
                fps=min(self.fps, 12),
                is_talking=True
            )
            
            if char_frames:
                char_clip = ImageSequenceClip(char_frames, fps=min(self.fps, 12))
                
                if char_clip.duration < actual_duration:
                    loops = int(actual_duration / char_clip.duration) + 1
                    char_clip = concatenate_videoclips([char_clip] * loops)
                
                char_clip = char_clip.subclip(0, actual_duration)
                char_clip = char_clip.set_position(
                    (self.shorts_w - 330, self.shorts_h - 550)
                )
                
                scene = CompositeVideoClip(
                    [bg_clip, char_clip],
                    size=self.shorts_size
                )
            else:
                scene = bg_clip
        except Exception as e:
            logger.warning(f"     Character animation failed: {e}")
            scene = bg_clip
        
        # ── Title Overlay (top) ──
        scene = self._add_title_bar(scene, section_title, language,
                                     channel_config, actual_duration)
        
        # ── CTA Overlay (bottom) ──
        scene = self._add_cta_bar(scene, language, long_video_url,
                                   actual_duration)
        
        # ── Subscribe Animation (last 3 seconds) ──
        scene = self._add_subscribe_prompt(scene, language, actual_duration)
        
        # ── Set Audio ──
        audio_trimmed = audio.subclip(0, actual_duration)
        scene = scene.set_audio(audio_trimmed)
        scene = scene.set_duration(actual_duration)
        
        # ── Export ──
        scene.write_videofile(
            output_path,
            fps=self.fps,
            codec='libx264',
            audio_codec='aac',
            bitrate=self.bitrate,
            preset='fast',
            threads=2,
            logger=None
        )
        
        # Cleanup
        scene.close()
        audio.close()
    

    def _create_vertical_background(self, footage_clips, duration):
        """Create vertical background from footage with anime filter"""
        
        from src.video_animator import AnimeFilter
        
        clip_change_interval = 4  # seconds
        num_clips_needed = int(duration / clip_change_interval) + 1
        
        bg_clips = []
        
        for j in range(num_clips_needed):
            if footage_clips:
                footage_path = footage_clips[j % len(footage_clips)]
                
                if isinstance(footage_path, dict):
                    footage_path = footage_path.get('path', '')
                
                try:
                    clip = VideoFileClip(footage_path)
                    clip_dur = min(clip.duration, clip_change_interval)
                    clip = clip.subclip(0, clip_dur)
                    
                    # Convert to vertical
                    clip = self._make_vertical(clip)
                    
                    # Apply anime filter
                    clip = clip.fl_image(
                        lambda frame: AnimeFilter.apply_quick_anime(frame, 0.7)
                    )
                    
                    bg_clips.append(clip)
                    continue
                except Exception:
                    pass
            
            # Fallback: animated gradient
            gradient = self._create_animated_gradient(
                clip_change_interval
            )
            bg_clips.append(gradient)
        
        if bg_clips:
            bg = concatenate_videoclips(bg_clips, method="compose")
            bg = bg.subclip(0, min(duration, bg.duration))
        else:
            bg = ColorClip(
                size=self.shorts_size,
                color=(15, 10, 40),
                duration=duration
            )
        
        return bg
    

    def _make_vertical(self, clip):
        """Convert horizontal clip to vertical 9:16"""
        
        tw, th = self.shorts_size
        cw, ch = clip.size
        
        target_ratio = tw / th
        clip_ratio = cw / ch
        
        if clip_ratio > target_ratio:
            new_h = th
            new_w = int(clip_ratio * th)
        else:
            new_w = tw
            new_h = int(tw / clip_ratio)
        
        clip = clip.resize((new_w, new_h))
        clip = crop(clip, x_center=new_w/2, y_center=new_h/2,
                    width=tw, height=th)
        
        return clip
    

    def _create_animated_gradient(self, duration):
        """Create animated gradient background as fallback"""
        
        from PIL import Image as PILImage
        
        frames = []
        fps = 10
        total_frames = int(duration * fps)
        
        colors = [
            [(20, 0, 60), (60, 0, 120)],
            [(0, 20, 60), (0, 60, 140)],
            [(40, 0, 40), (100, 0, 80)],
        ]
        
        color_pair = random.choice(colors)
        
        for f in range(total_frames):
            img = PILImage.new('RGB', self.shorts_size)
            draw = ImageDraw.Draw(img) if hasattr(PILImage, 'ImageDraw') else None
            
            # Simple gradient
            for y in range(self.shorts_h):
                ratio = y / self.shorts_h
                # Add subtle animation
                shift = np.sin(f * 0.1 + ratio * 3) * 10
                
                r = int(color_pair[0][0] + (color_pair[1][0] - color_pair[0][0]) * ratio + shift)
                g = int(color_pair[0][1] + (color_pair[1][1] - color_pair[0][1]) * ratio)
                b = int(color_pair[0][2] + (color_pair[1][2] - color_pair[0][2]) * ratio + shift)
                
                r = max(0, min(255, r))
                g = max(0, min(255, g))
                b = max(0, min(255, b))
                
                for x in range(self.shorts_w):
                    img.putpixel((x, y), (r, g, b))
            
            frames.append(np.array(img))
        
        return ImageSequenceClip(frames, fps=fps)
    

    def _add_title_bar(self, scene, title, language, channel_config, duration):
        """Add semi-transparent title bar at top of short"""
        
        try:
            font_file = channel_config.get('font_file', '')
            font_to_use = font_file if os.path.exists(font_file) else 'Arial-Bold'
            
            # Background bar
            bar = ColorClip(
                size=(self.shorts_w, 140),
                color=(0, 0, 0)
            ).set_opacity(0.65).set_duration(min(6, duration))
            bar = bar.set_position(('center', 60))
            
            # Title text
            txt = TextClip(
                title,
                fontsize=32,
                color='white',
                font=font_to_use,
                stroke_color='black',
                stroke_width=2,
                size=(self.shorts_w - 80, None),
                method='caption',
                align='center'
            ).set_duration(min(6, duration))
            txt = txt.set_position(('center', 80))
            
            scene = CompositeVideoClip(
                [scene, bar, txt],
                size=self.shorts_size
            ).set_duration(duration)
            
        except Exception as e:
            logger.warning(f"     Title bar failed: {e}")
        
        return scene
    

    def _add_cta_bar(self, scene, language, long_video_url, duration):
        """Add CTA bar at bottom"""
        
        cta_texts = {
            'telugu': 'పూర్తి వీడియో చానెల్ లో చూడండి! 👆',
            'hindi': 'पूरा वीडियो चैनल पर देखें! 👆'
        }
        cta_text = cta_texts.get(language, 'Watch Full Video! 👆')
        
        try:
            bar = ColorClip(
                size=(self.shorts_w, 90),
                color=(0, 0, 0)
            ).set_opacity(0.7).set_duration(duration)
            bar = bar.set_position(('center', self.shorts_h - 140))
            
            txt = TextClip(
                cta_text,
                fontsize=26,
                color='#FFD700',
                stroke_color='black',
                stroke_width=2,
                size=(self.shorts_w - 60, None),
                method='caption',
                align='center'
            ).set_duration(duration)
            txt = txt.set_position(('center', self.shorts_h - 125))
            
            scene = CompositeVideoClip(
                [scene, bar, txt],
                size=self.shorts_size
            ).set_duration(duration)
            
        except Exception as e:
            logger.warning(f"     CTA bar failed: {e}")
        
        return scene
    

    def _add_subscribe_prompt(self, scene, language, duration):
        """Add subscribe animation in last 3 seconds"""
        
        sub_texts = {
            'telugu': '🔔 Subscribe చేయండి!',
            'hindi': '🔔 Subscribe करें!'
        }
        sub_text = sub_texts.get(language, '🔔 Subscribe!')
        
        if duration <= 5:
            return scene
        
        try:
            prompt_duration = 3
            start_time = duration - prompt_duration
            
            sub_txt = TextClip(
                sub_text,
                fontsize=36,
                color='#FF0000',
                stroke_color='white',
                stroke_width=3,
                method='label'
            ).set_duration(prompt_duration).set_start(start_time)
            sub_txt = sub_txt.set_position(('center', self.shorts_h // 2))
            
            # Pulsing background
            sub_bg = ColorClip(
                size=(self.shorts_w - 100, 70),
                color=(255, 255, 255)
            ).set_opacity(0.85).set_duration(prompt_duration).set_start(start_time)
            sub_bg = sub_bg.set_position(('center', self.shorts_h // 2 - 10))
            
            scene = CompositeVideoClip(
                [scene, sub_bg, sub_txt],
                size=self.shorts_size
            ).set_duration(duration)
            
        except Exception as e:
            logger.warning(f"     Subscribe prompt failed: {e}")
        
        return scene


# Need this import for gradient fallback
from PIL import ImageDraw


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("✂️ Shorts Cutter ready for use")
