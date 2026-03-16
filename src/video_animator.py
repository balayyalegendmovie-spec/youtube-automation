"""
VIDEO ANIMATOR — Creates Anime-Style Videos
Simplified version optimized for GitHub Actions.
"""

import os
import random
import logging
import time
import tempfile
import shutil
import subprocess
import math

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip, AudioFileClip, TextClip,
    CompositeVideoClip, CompositeAudioClip,
    concatenate_videoclips, ColorClip,
    ImageSequenceClip, ImageClip
)
from moviepy.video.fx.all import crop
import requests

logger = logging.getLogger(__name__)


def apply_anime_filter(frame):
    """Convert frame to anime/cartoon style"""
    try:
        img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # Smooth while keeping edges
        for _ in range(2):
            img = cv2.bilateralFilter(img, d=7, sigmaColor=50, sigmaSpace=50)

        # Edge detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        edges = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            blockSize=9, C=2
        )
        edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

        # Reduce colors (posterize)
        div = 32
        img = (img // div) * div + div // 2

        # Combine edges with posterized image
        cartoon = cv2.bitwise_and(img, edges_bgr)

        # Boost saturation
        hsv = cv2.cvtColor(cartoon, cv2.COLOR_BGR2HSV)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.3, 0, 255).astype(np.uint8)
        cartoon = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        return cv2.cvtColor(cartoon, cv2.COLOR_BGR2RGB)

    except Exception:
        return frame


def create_character_frame(width=300, height=500, mouth_open=False,
                           eyes_open=True, hair_color=(30, 30, 100),
                           eye_color=(100, 50, 200),
                           outfit_color=(200, 50, 50)):
    """Draw a simple anime character frame"""

    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = width // 2
    skin = (255, 220, 185)

    # Body
    draw.polygon([
        (cx - 60, 200), (cx + 60, 200),
        (cx + 70, height), (cx - 70, height)
    ], fill=outfit_color)

    # Collar
    draw.polygon([
        (cx - 30, 200), (cx, 230), (cx + 30, 200)
    ], fill=tuple(min(c + 40, 255) for c in outfit_color))

    # Arms
    draw.line([(cx + 55, 230), (cx + 65, 310)], fill=skin, width=12)
    draw.line([(cx - 55, 230), (cx - 65, 310)], fill=skin, width=12)

    # Neck
    draw.rectangle([(cx - 15, 180), (cx + 15, 210)], fill=skin)

    # Head
    head_cy = 120
    draw.ellipse([(cx - 55, head_cy - 65), (cx + 55, head_cy + 65)],
                 fill=skin, outline=(200, 180, 150), width=2)

    # Hair
    hair_points = [
        (cx - 60, head_cy - 10), (cx - 50, head_cy - 80),
        (cx - 20, head_cy - 90), (cx, head_cy - 95),
        (cx + 20, head_cy - 90), (cx + 50, head_cy - 80),
        (cx + 60, head_cy - 10), (cx + 55, head_cy + 10),
        (cx - 55, head_cy + 10),
    ]
    draw.polygon(hair_points, fill=hair_color)

    # Side hair
    draw.polygon([
        (cx - 58, head_cy - 10), (cx - 70, head_cy + 60),
        (cx - 50, head_cy + 50), (cx - 55, head_cy)
    ], fill=hair_color)
    draw.polygon([
        (cx + 58, head_cy - 10), (cx + 70, head_cy + 60),
        (cx + 50, head_cy + 50), (cx + 55, head_cy)
    ], fill=hair_color)

    eye_y = head_cy + 5

    if eyes_open:
        # Left eye
        draw.ellipse([(cx - 35, eye_y - 12), (cx - 10, eye_y + 12)],
                     fill='white', outline=(80, 80, 80), width=2)
        draw.ellipse([(cx - 30, eye_y - 8), (cx - 15, eye_y + 8)],
                     fill=eye_color)
        draw.ellipse([(cx - 27, eye_y - 5), (cx - 20, eye_y + 2)],
                     fill=(20, 20, 20))
        draw.ellipse([(cx - 28, eye_y - 7), (cx - 24, eye_y - 3)],
                     fill='white')
        # Right eye
        draw.ellipse([(cx + 10, eye_y - 12), (cx + 35, eye_y + 12)],
                     fill='white', outline=(80, 80, 80), width=2)
        draw.ellipse([(cx + 15, eye_y - 8), (cx + 30, eye_y + 8)],
                     fill=eye_color)
        draw.ellipse([(cx + 20, eye_y - 5), (cx + 27, eye_y + 2)],
                     fill=(20, 20, 20))
        draw.ellipse([(cx + 24, eye_y - 7), (cx + 28, eye_y - 3)],
                     fill='white')
    else:
        draw.arc([(cx - 35, eye_y - 5), (cx - 10, eye_y + 5)],
                 0, 180, fill=(80, 80, 80), width=3)
        draw.arc([(cx + 10, eye_y - 5), (cx + 35, eye_y + 5)],
                 0, 180, fill=(80, 80, 80), width=3)

    # Eyebrows
    draw.arc([(cx - 38, eye_y - 25), (cx - 8, eye_y - 10)],
             200, 340, fill=hair_color, width=3)
    draw.arc([(cx + 8, eye_y - 25), (cx + 38, eye_y - 10)],
             200, 340, fill=hair_color, width=3)

    # Nose
    draw.line([(cx, head_cy + 25), (cx - 3, head_cy + 33)],
             fill=(220, 190, 160), width=2)

    # Mouth
    mouth_y = head_cy + 40
    if mouth_open:
        draw.ellipse([(cx - 12, mouth_y - 5), (cx + 12, mouth_y + 10)],
                     fill=(200, 100, 100), outline=(180, 80, 80), width=2)
        draw.rectangle([(cx - 8, mouth_y - 3), (cx + 8, mouth_y + 1)],
                       fill='white')
    else:
        draw.arc([(cx - 15, mouth_y - 5), (cx + 15, mouth_y + 10)],
                 0, 180, fill=(200, 100, 100), width=2)

    return img


def generate_character_animation(duration_seconds, fps=10,
                                  hair_color=(30, 30, 100),
                                  eye_color=(100, 50, 200),
                                  outfit_color=(200, 50, 50)):
    """Generate character animation frames"""

    total_frames = int(duration_seconds * fps)
    frames = []
    blink_interval = fps * 4
    mouth_interval = max(1, fps // 4)

    for f in range(total_frames):
        mouth_open = (f % mouth_interval) < (mouth_interval // 2)
        eyes_open = (f % blink_interval) > 3

        char_img = create_character_frame(
            mouth_open=mouth_open,
            eyes_open=eyes_open,
            hair_color=hair_color,
            eye_color=eye_color,
            outfit_color=outfit_color
        )
        frames.append(np.array(char_img))

    return frames


def download_stock_footage(keyword, output_dir, pexels_key, count=1):
    """Download stock footage from Pexels"""

    downloaded = []

    if not pexels_key:
        return downloaded

    try:
        headers = {"Authorization": pexels_key}
        params = {
            "query": keyword,
            "per_page": 3,
            "size": "medium",
            "orientation": "landscape"
        }

        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers, params=params, timeout=15
        )

        if response.status_code != 200:
            return downloaded

        videos = response.json().get('videos', [])

        for i, video in enumerate(videos[:count]):
            video_files = video.get('video_files', [])

            selected = None
            for vf in video_files:
                h = vf.get('height', 0)
                if 360 <= h <= 720:
                    selected = vf
                    break

            if not selected and video_files:
                selected = video_files[0]

            if selected:
                file_path = os.path.join(
                    output_dir, f"clip_{keyword[:15].replace(' ', '_')}_{i}.mp4"
                )
                vid_resp = requests.get(selected['link'], timeout=60)
                with open(file_path, 'wb') as f:
                    f.write(vid_resp.content)
                downloaded.append(file_path)

            time.sleep(0.5)

    except Exception as e:
        logger.warning(f"   ⚠️ Footage download failed for '{keyword}': {e}")

    return downloaded


def resize_and_crop(clip, target_w, target_h):
    """Resize clip to fit target, cropping excess"""

    cw, ch = clip.size
    target_ratio = target_w / target_h
    clip_ratio = cw / ch

    if clip_ratio > target_ratio:
        new_h = target_h
        new_w = int(clip_ratio * target_h)
    else:
        new_w = target_w
        new_h = int(target_w / clip_ratio)

    clip = clip.resize((new_w, new_h))
    clip = crop(clip, x_center=new_w / 2, y_center=new_h / 2,
                width=target_w, height=target_h)
    return clip


class VideoAnimator:
    """Main video creation engine"""

    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.pexels_key = os.environ.get(
            'PEXELS_API_KEY',
            self.config.get('footage', {}).get('pexels_api_key', '')
        )
        if '${' in str(self.pexels_key):
            self.pexels_key = os.environ.get('PEXELS_API_KEY', '')

        logger.info("🎬 Video Animator initialized")

    def create_anime_video(self, voice_path, subtitle_path,
                            footage_keywords, sections, language,
                            channel_config, output_path,
                            bg_music_path=None):
        """Create long-form anime-style video"""

        logger.info("🎬 STEP: Creating anime-style video...")
        logger.info(f"   Voice: {voice_path}")
        logger.info(f"   Sections: {len(sections)}")

        # Load voice
        voice_audio = AudioFileClip(voice_path)
        total_duration = voice_audio.duration
        logger.info(f"   Total duration: {total_duration:.1f}s")

        # Resolution
        res_w = self.config.get('content', {}).get('long_form', {}).get('resolution_w', 1920)
        res_h = self.config.get('content', {}).get('long_form', {}).get('resolution_h', 1080)
        fps = self.config.get('content', {}).get('long_form', {}).get('fps', 24)

        # Download footage
        temp_dir = tempfile.mkdtemp(prefix='yt_video_')
        footage_dir = os.path.join(temp_dir, 'footage')
        os.makedirs(footage_dir, exist_ok=True)

        logger.info(f"   📥 Downloading stock footage...")
        all_footage = []
        for kw in footage_keywords[:10]:
            clips = download_stock_footage(kw, footage_dir, self.pexels_key)
            all_footage.extend(clips)
            if len(all_footage) >= 8:
                break
            time.sleep(1)

        logger.info(f"   ✅ Downloaded {len(all_footage)} clips")

        # Character config
        char_config = channel_config.get('character', {})
        hair_color = tuple(char_config.get('hair_color', [30, 30, 100]))
        eye_color = tuple(char_config.get('eye_color', [100, 50, 200]))
        outfit_color = tuple(char_config.get('outfit_color', [200, 50, 50]))

        # Build scenes
        logger.info(f"   🎨 Building video scenes...")
        scene_clips = []
        clip_idx = 0
        bg_change = 5  # seconds per background clip

        for sec_i, section in enumerate(sections):
            sec_duration = section.get('duration', total_duration / max(len(sections), 1))

            logger.info(f"   🎨 Scene {sec_i + 1}/{len(sections)}: "
                       f"[{section.get('marker', '?')}] {sec_duration:.1f}s")

            # Build background
            num_bg = max(1, int(sec_duration / bg_change))
            bg_clips = []

            for j in range(num_bg):
                bg_dur = min(bg_change, sec_duration - j * bg_change)
                if bg_dur <= 0:
                    break

                if all_footage:
                    fp = all_footage[(clip_idx + j) % len(all_footage)]
                    try:
                        bgc = VideoFileClip(fp)
                        bgc = bgc.subclip(0, min(bgc.duration, bg_dur))
                        bgc = resize_and_crop(bgc, res_w, res_h)
                        bgc = bgc.fl_image(apply_anime_filter)
                        bg_clips.append(bgc)
                        continue
                    except Exception:
                        pass

                # Fallback gradient
                bg_clips.append(
                    ColorClip(size=(res_w, res_h), color=(20, 10, 50),
                              duration=bg_dur)
                )

            clip_idx += num_bg

            if bg_clips:
                scene_bg = concatenate_videoclips(bg_clips, method="compose")
                scene_bg = scene_bg.subclip(0, min(sec_duration, scene_bg.duration))
            else:
                scene_bg = ColorClip(size=(res_w, res_h), color=(20, 10, 50),
                                     duration=sec_duration)

            # Character overlay
            try:
                char_fps = min(fps, 10)
                char_frames = generate_character_animation(
                    min(sec_duration, 30), char_fps,
                    hair_color, eye_color, outfit_color
                )

                if char_frames:
                    char_clip = ImageSequenceClip(char_frames, fps=char_fps)
                    if char_clip.duration < sec_duration:
                        loops = int(sec_duration / char_clip.duration) + 1
                        char_clip = concatenate_videoclips([char_clip] * loops)
                    char_clip = char_clip.subclip(0, min(sec_duration, char_clip.duration))
                    char_clip = char_clip.set_position((res_w - 350, res_h - 520))

                    scene = CompositeVideoClip(
                        [scene_bg, char_clip], size=(res_w, res_h)
                    )
                else:
                    scene = scene_bg
            except Exception as e:
                logger.warning(f"   ⚠️ Character failed: {e}")
                scene = scene_bg

            # Section title
            sec_title = section.get('title', '')
            if sec_title:
                try:
                    font_file = channel_config.get('font_file', '')
                    font_to_use = font_file if font_file and os.path.exists(font_file) else 'DejaVu-Sans-Bold'

                    txt = TextClip(
                        sec_title, fontsize=36, color='white',
                        font=font_to_use, stroke_color='black',
                        stroke_width=2, size=(res_w - 400, None),
                        method='caption', align='West'
                    ).set_duration(min(5, sec_duration)).set_position((40, 40))

                    txt_bg = ColorClip(
                        size=(res_w - 350, 70), color=(0, 0, 0)
                    ).set_opacity(0.5).set_duration(min(5, sec_duration)).set_position((20, 30))

                    scene = CompositeVideoClip(
                        [scene, txt_bg, txt], size=(res_w, res_h)
                    )
                except Exception:
                    pass

            scene = scene.set_duration(sec_duration)
            scene_clips.append(scene)

        # Concatenate all scenes
        logger.info(f"   🔗 Concatenating {len(scene_clips)} scenes...")

        if scene_clips:
            final_video = concatenate_videoclips(scene_clips, method="compose")
        else:
            final_video = ColorClip(
                size=(res_w, res_h), color=(20, 10, 40),
                duration=total_duration
            )

        final_video = final_video.subclip(
            0, min(total_duration, final_video.duration)
        )

        # Audio
        logger.info(f"   🎵 Adding audio...")
        audio_tracks = [voice_audio]

        if bg_music_path and os.path.exists(bg_music_path):
            try:
                bg_music = AudioFileClip(bg_music_path)
                if bg_music.duration < total_duration:
                    from moviepy.audio.AudioClip import concatenate_audioclips
                    loops = int(total_duration / bg_music.duration) + 1
                    bg_music = concatenate_audioclips([bg_music] * loops)
                bg_music = bg_music.subclip(0, total_duration)
                bg_music = bg_music.volumex(0.06)
                audio_tracks.append(bg_music)
            except Exception as e:
                logger.warning(f"   ⚠️ Background music failed: {e}")

        final_audio = CompositeAudioClip(audio_tracks)
        final_video = final_video.set_audio(final_audio)

        # Export
        logger.info(f"   💾 Exporting video...")
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        final_video.write_videofile(
            output_path, fps=fps, codec='libx264',
            audio_codec='aac', bitrate='4000k',
            preset='ultrafast', threads=2, logger=None
        )

        # Cleanup
        final_video.close()
        voice_audio.close()
        for sc in scene_clips:
            try:
                sc.close()
            except Exception:
                pass

        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

        file_size = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"   ✅ Video created: {output_path} ({file_size:.1f} MB)")
        return output_path

    def create_anime_short(self, voice_path, section_text,
                            footage_keywords, language, channel_config,
                            output_path):
        """Create a single vertical short"""

        logger.info(f"   ✂️ Creating short: {os.path.basename(output_path)}")

        voice_audio = AudioFileClip(voice_path)
        duration = min(voice_audio.duration, 58)

        sw = self.config.get('content', {}).get('shorts', {}).get('resolution_w', 1080)
        sh = self.config.get('content', {}).get('shorts', {}).get('resolution_h', 1920)
        fps = self.config.get('content', {}).get('shorts', {}).get('fps', 24)

        temp_dir = tempfile.mkdtemp(prefix='yt_short_')
        footage_dir = os.path.join(temp_dir, 'footage')
        os.makedirs(footage_dir, exist_ok=True)

        # Download one clip
        all_footage = []
        for kw in footage_keywords[:3]:
            clips = download_stock_footage(kw, footage_dir, self.pexels_key)
            all_footage.extend(clips)
            if clips:
                break
            time.sleep(1)

        # Background
        if all_footage:
            try:
                bg = VideoFileClip(all_footage[0])
                bg = bg.subclip(0, min(bg.duration, duration))
                bg = resize_and_crop(bg, sw, sh)
                bg = bg.fl_image(apply_anime_filter)

                if bg.duration < duration:
                    loops = int(duration / bg.duration) + 1
                    bg = concatenate_videoclips([bg] * loops)
                bg = bg.subclip(0, duration)
            except Exception:
                bg = ColorClip(size=(sw, sh), color=(20, 10, 50), duration=duration)
        else:
            bg = ColorClip(size=(sw, sh), color=(20, 10, 50), duration=duration)

        # Character
        char_config = channel_config.get('character', {})
        try:
            char_frames = generate_character_animation(
                min(duration, 30), min(fps, 8),
                tuple(char_config.get('hair_color', [30, 30, 100])),
                tuple(char_config.get('eye_color', [100, 50, 200])),
                tuple(char_config.get('outfit_color', [200, 50, 50]))
            )
            if char_frames:
                cc = ImageSequenceClip(char_frames, fps=min(fps, 8))
                if cc.duration < duration:
                    cc = concatenate_videoclips([cc] * (int(duration / cc.duration) + 1))
                cc = cc.subclip(0, duration).set_position((sw - 330, sh - 550))
                scene = CompositeVideoClip([bg, cc], size=(sw, sh))
            else:
                scene = bg
        except Exception:
            scene = bg

        # CTA overlay
        cta_texts = {
            'telugu': 'పూర్తి వీడియో చానెల్ లో! 👆',
            'hindi': 'पूरा वीडियो चैनल पर! 👆'
        }
        try:
            cta_bar = ColorClip(
                size=(sw, 80), color=(0, 0, 0)
            ).set_opacity(0.7).set_duration(duration).set_position(('center', sh - 130))

            cta_txt = TextClip(
                cta_texts.get(language, 'Full Video on Channel! 👆'),
                fontsize=26, color='#FFD700',
                stroke_color='black', stroke_width=2,
                size=(sw - 60, None), method='caption'
            ).set_duration(duration).set_position(('center', sh - 120))

            scene = CompositeVideoClip(
                [scene, cta_bar, cta_txt], size=(sw, sh)
            ).set_duration(duration)
        except Exception:
            pass

        # Audio
        audio_trimmed = voice_audio.subclip(0, duration)
        scene = scene.set_audio(audio_trimmed)
        scene = scene.set_duration(duration)

        # Export
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        scene.write_videofile(
            output_path, fps=fps, codec='libx264',
            audio_codec='aac', bitrate='3000k',
            preset='ultrafast', threads=2, logger=None
        )

        scene.close()
        voice_audio.close()

        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

        file_size = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"   ✅ Short: {file_size:.1f} MB")
        return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("VideoAnimator ready")
