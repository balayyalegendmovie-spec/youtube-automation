"""
VIDEO ANIMATOR — Anime-Style with Ken Burns Zoom + Subtitles
"""

import os
import random
import logging
import time
import tempfile
import shutil
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip, AudioFileClip, TextClip,
    CompositeVideoClip, CompositeAudioClip,
    concatenate_videoclips, ColorClip,
    ImageSequenceClip, ImageClip, VideoClip
)
from moviepy.video.fx.all import crop
import requests

logger = logging.getLogger(__name__)


def apply_anime_filter_to_image(pil_image):
    try:
        frame = np.array(pil_image)
        img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        for _ in range(2):
            img = cv2.bilateralFilter(img, d=7, sigmaColor=50, sigmaSpace=50)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        edges = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY, blockSize=9, C=2
        )
        edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        div = 32
        img = (img // div) * div + div // 2
        cartoon = cv2.bitwise_and(img, edges_bgr)
        hsv = cv2.cvtColor(cartoon, cv2.COLOR_BGR2HSV)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.3, 0, 255).astype(np.uint8)
        cartoon = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        return Image.fromarray(cv2.cvtColor(cartoon, cv2.COLOR_BGR2RGB))
    except Exception:
        return pil_image


def extract_frame_from_video(video_path, time_sec=1):
    try:
        clip = VideoFileClip(video_path)
        t = min(time_sec, clip.duration - 0.1)
        frame = clip.get_frame(max(0, t))
        clip.close()
        return Image.fromarray(frame)
    except Exception:
        return None


def create_anime_background(video_path, target_w, target_h, duration):
    """Create anime background WITH slow zoom effect (Ken Burns)"""
    try:
        pil_img = extract_frame_from_video(video_path, time_sec=1)
        if pil_img is None:
            return ColorClip(size=(target_w, target_h), color=(20, 10, 50), duration=duration)

        zoom_w = int(target_w * 1.2)
        zoom_h = int(target_h * 1.2)
        pil_img = pil_img.resize((zoom_w, zoom_h), Image.LANCZOS)
        anime_img = apply_anime_filter_to_image(pil_img)
        anime_array = np.array(anime_img)

        def make_frame(t):
            progress = t / max(duration, 0.1)
            scale = 1.0 + progress * 0.15

            h, w = anime_array.shape[:2]
            new_h = int(h / scale)
            new_w = int(w / scale)

            y1 = (h - new_h) // 2
            x1 = (w - new_w) // 2
            cropped = anime_array[y1:y1 + new_h, x1:x1 + new_w]

            img = Image.fromarray(cropped)
            img = img.resize((target_w, target_h), Image.LANCZOS)
            return np.array(img)

        clip = VideoClip(make_frame, duration=duration)
        return clip

    except Exception:
        return ColorClip(size=(target_w, target_h), color=(20, 10, 50), duration=duration)


def create_gradient_bg(target_w, target_h, duration):
    colors = [
        (20, 0, 60), (0, 30, 80), (40, 0, 40),
        (10, 40, 60), (50, 0, 30), (0, 20, 50)
    ]
    c1 = random.choice(colors)
    c2 = random.choice(colors)
    img = Image.new('RGB', (target_w, target_h))
    for y in range(target_h):
        ratio = y / target_h
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        for x in range(target_w):
            img.putpixel((x, y), (r, g, b))
    return ImageClip(np.array(img)).set_duration(duration)


def create_character_frame(width=300, height=500, mouth_open=False,
                           eyes_open=True, hair_color=(30, 30, 100),
                           eye_color=(100, 50, 200),
                           outfit_color=(200, 50, 50)):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = width // 2
    skin = (255, 220, 185)

    draw.polygon([(cx-60,200),(cx+60,200),(cx+70,height),(cx-70,height)], fill=outfit_color)
    draw.polygon([(cx-30,200),(cx,230),(cx+30,200)],
                 fill=tuple(min(c+40,255) for c in outfit_color))
    draw.line([(cx+55,230),(cx+65,310)], fill=skin, width=12)
    draw.line([(cx-55,230),(cx-65,310)], fill=skin, width=12)
    draw.rectangle([(cx-15,180),(cx+15,210)], fill=skin)

    head_cy = 120
    draw.ellipse([(cx-55,head_cy-65),(cx+55,head_cy+65)],
                 fill=skin, outline=(200,180,150), width=2)

    hair_pts = [(cx-60,head_cy-10),(cx-50,head_cy-80),(cx-20,head_cy-90),
                (cx,head_cy-95),(cx+20,head_cy-90),(cx+50,head_cy-80),
                (cx+60,head_cy-10),(cx+55,head_cy+10),(cx-55,head_cy+10)]
    draw.polygon(hair_pts, fill=hair_color)
    draw.polygon([(cx-58,head_cy-10),(cx-70,head_cy+60),(cx-50,head_cy+50),(cx-55,head_cy)], fill=hair_color)
    draw.polygon([(cx+58,head_cy-10),(cx+70,head_cy+60),(cx+50,head_cy+50),(cx+55,head_cy)], fill=hair_color)

    ey = head_cy + 5
    if eyes_open:
        draw.ellipse([(cx-35,ey-12),(cx-10,ey+12)], fill='white', outline=(80,80,80), width=2)
        draw.ellipse([(cx-30,ey-8),(cx-15,ey+8)], fill=eye_color)
        draw.ellipse([(cx-27,ey-5),(cx-20,ey+2)], fill=(20,20,20))
        draw.ellipse([(cx-28,ey-7),(cx-24,ey-3)], fill='white')
        draw.ellipse([(cx+10,ey-12),(cx+35,ey+12)], fill='white', outline=(80,80,80), width=2)
        draw.ellipse([(cx+15,ey-8),(cx+30,ey+8)], fill=eye_color)
        draw.ellipse([(cx+20,ey-5),(cx+27,ey+2)], fill=(20,20,20))
        draw.ellipse([(cx+24,ey-7),(cx+28,ey-3)], fill='white')
    else:
        draw.arc([(cx-35,ey-5),(cx-10,ey+5)], 0, 180, fill=(80,80,80), width=3)
        draw.arc([(cx+10,ey-5),(cx+35,ey+5)], 0, 180, fill=(80,80,80), width=3)

    draw.arc([(cx-38,ey-25),(cx-8,ey-10)], 200, 340, fill=hair_color, width=3)
    draw.arc([(cx+8,ey-25),(cx+38,ey-10)], 200, 340, fill=hair_color, width=3)
    draw.line([(cx,head_cy+25),(cx-3,head_cy+33)], fill=(220,190,160), width=2)

    my = head_cy + 40
    if mouth_open:
        draw.ellipse([(cx-12,my-5),(cx+12,my+10)], fill=(200,100,100), outline=(180,80,80), width=2)
        draw.rectangle([(cx-8,my-3),(cx+8,my+1)], fill='white')
    else:
        draw.arc([(cx-15,my-5),(cx+15,my+10)], 0, 180, fill=(200,100,100), width=2)

    return img


def generate_character_clip(duration, fps=8, hair_color=(30,30,100),
                             eye_color=(100,50,200), outfit_color=(200,50,50)):
    total_frames = int(duration * fps)
    frames = []
    blink_interval = fps * 4
    mouth_interval = max(1, fps // 3)

    for f in range(total_frames):
        mouth_open = (f % mouth_interval) < (mouth_interval // 2)
        eyes_open = (f % blink_interval) > 3
        char_img = create_character_frame(
            mouth_open=mouth_open, eyes_open=eyes_open,
            hair_color=hair_color, eye_color=eye_color,
            outfit_color=outfit_color
        )
        frames.append(np.array(char_img))

    return ImageSequenceClip(frames, fps=fps)


def download_stock_footage(keyword, output_dir, pexels_key, count=1):
    downloaded = []
    if not pexels_key:
        return downloaded
    try:
        headers = {"Authorization": pexels_key}
        params = {"query": keyword, "per_page": 3, "size": "small", "orientation": "landscape"}
        resp = requests.get("https://api.pexels.com/videos/search",
                           headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            return downloaded
        videos = resp.json().get('videos', [])
        for i, video in enumerate(videos[:count]):
            vfiles = video.get('video_files', [])
            sel = None
            for vf in vfiles:
                if 360 <= vf.get('height', 0) <= 720:
                    sel = vf
                    break
            if not sel and vfiles:
                sel = vfiles[0]
            if sel:
                fp = os.path.join(output_dir, f"clip_{keyword[:15].replace(' ','_')}_{i}.mp4")
                vr = requests.get(sel['link'], timeout=60)
                with open(fp, 'wb') as f:
                    f.write(vr.content)
                downloaded.append(fp)
            time.sleep(0.5)
    except Exception as e:
        logger.warning(f"   ⚠️ Download failed '{keyword}': {e}")
    return downloaded


class VideoAnimator:

    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.pexels_key = os.environ.get('PEXELS_API_KEY',
            self.config.get('footage', {}).get('pexels_api_key', ''))
        if '${' in str(self.pexels_key):
            self.pexels_key = os.environ.get('PEXELS_API_KEY', '')
        logger.info("🎬 Video Animator initialized")

    def create_anime_video(self, voice_path, subtitle_path, footage_keywords,
                            sections, language, channel_config, output_path,
                            bg_music_path=None):
        logger.info("🎬 STEP: Creating anime-style video...")

        voice_audio = AudioFileClip(voice_path)
        total_duration = voice_audio.duration
        logger.info(f"   Total duration: {total_duration:.1f}s")

        res_w = self.config.get('content',{}).get('long_form',{}).get('resolution_w', 1280)
        res_h = self.config.get('content',{}).get('long_form',{}).get('resolution_h', 720)
        fps = 15

        temp_dir = tempfile.mkdtemp(prefix='yt_vid_')
        footage_dir = os.path.join(temp_dir, 'footage')
        os.makedirs(footage_dir, exist_ok=True)

        logger.info(f"   📥 Downloading stock footage...")
        all_footage = []
        for kw in footage_keywords[:8]:
            clips = download_stock_footage(kw, footage_dir, self.pexels_key)
            all_footage.extend(clips)
            if len(all_footage) >= 6:
                break
            time.sleep(1)
        logger.info(f"   ✅ Downloaded {len(all_footage)} clips")

        char_cfg = channel_config.get('character', {})
        hair = tuple(char_cfg.get('hair_color', [30,30,100]))
        eyes = tuple(char_cfg.get('eye_color', [100,50,200]))
        outfit = tuple(char_cfg.get('outfit_color', [200,50,50]))

        logger.info(f"   🎨 Building {len(sections)} scenes...")
        scene_clips = []
        clip_idx = 0

        for sec_i, section in enumerate(sections):
            sec_dur = section.get('duration', total_duration / max(len(sections), 1))
            marker = section.get('marker', '?')
            title = section.get('title', '')
            logger.info(f"   🎨 Scene {sec_i+1}/{len(sections)}: [{marker}] {sec_dur:.1f}s")

            # Background with Ken Burns zoom
            if all_footage:
                fp = all_footage[clip_idx % len(all_footage)]
                clip_idx += 1
                bg = create_anime_background(fp, res_w, res_h, sec_dur)
            else:
                bg = create_gradient_bg(res_w, res_h, sec_dur)

            # Character
            try:
                char_clip = generate_character_clip(
                    min(sec_dur, 20), fps=6,
                    hair_color=hair, eye_color=eyes, outfit_color=outfit
                )
                if char_clip.duration < sec_dur:
                    loops = int(sec_dur / char_clip.duration) + 1
                    char_clip = concatenate_videoclips([char_clip] * loops)
                char_clip = char_clip.subclip(0, min(sec_dur, char_clip.duration))
                char_clip = char_clip.set_position((res_w - 350, res_h - 520))
                scene = CompositeVideoClip([bg, char_clip], size=(res_w, res_h))
            except Exception as e:
                logger.warning(f"   ⚠️ Character failed: {e}")
                scene = bg

            # Section title (first 5 seconds)
            if title and title != marker:
                try:
                    txt = TextClip(
                        title, fontsize=36, color='#FFD700',
                        stroke_color='black', stroke_width=3,
                        size=(res_w - 400, None), method='caption'
                    ).set_duration(min(5, sec_dur)).set_position((40, 30))

                    txt_bg = ColorClip(
                        size=(res_w - 350, 70), color=(0, 0, 0)
                    ).set_opacity(0.6).set_duration(min(5, sec_dur)).set_position((20, 20))

                    scene = CompositeVideoClip(
                        [scene, txt_bg, txt], size=(res_w, res_h)
                    )
                except Exception:
                    pass

            # Subtitle text at bottom
            section_text = section.get('text', '')
            if section_text:
                try:
                    import re as re_module
                    sentences = re_module.split(r'[.!?।]', section_text)
                    subtitle = '. '.join(s.strip() for s in sentences[:2] if s.strip())
                    if len(subtitle) > 80:
                        subtitle = subtitle[:80] + '...'

                    if subtitle:
                        sub_txt = TextClip(
                            subtitle, fontsize=24, color='white',
                            stroke_color='black', stroke_width=2,
                            size=(res_w - 200, None), method='caption',
                            align='center'
                        ).set_duration(min(8, sec_dur)).set_start(2).set_position(('center', res_h - 100))

                        sub_bg = ColorClip(
                            size=(res_w - 150, 60), color=(0, 0, 0)
                        ).set_opacity(0.5).set_duration(min(8, sec_dur)).set_start(2).set_position(('center', res_h - 110))

                        scene = CompositeVideoClip(
                            [scene, sub_bg, sub_txt], size=(res_w, res_h)
                        )
                except Exception:
                    pass

            scene = scene.set_duration(sec_dur)
            scene_clips.append(scene)

        logger.info(f"   🔗 Joining {len(scene_clips)} scenes...")
        if scene_clips:
            final_video = concatenate_videoclips(scene_clips, method="compose")
        else:
            final_video = ColorClip(size=(res_w, res_h), color=(20, 10, 40), duration=total_duration)

        final_video = final_video.subclip(0, min(total_duration, final_video.duration))

        logger.info(f"   🎵 Adding voiceover...")
        final_video = final_video.set_audio(voice_audio)

        logger.info(f"   💾 Exporting video (this takes 2-4 minutes)...")
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        final_video.write_videofile(
            output_path, fps=fps, codec='libx264',
            audio_codec='aac', bitrate='2000k',
            preset='ultrafast', threads=2, logger=None
        )

        final_video.close()
        voice_audio.close()
        for sc in scene_clips:
            try: sc.close()
            except: pass

        try: shutil.rmtree(temp_dir)
        except: pass

        file_size = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"   ✅ Video created: {file_size:.1f} MB")
        return output_path

    def create_anime_short(self, voice_path, section_text, footage_keywords,
                            language, channel_config, output_path):
        logger.info(f"   ✂️ Creating short: {os.path.basename(output_path)}")

        voice_audio = AudioFileClip(voice_path)
        duration = min(voice_audio.duration, 58)

        sw = 1080
        sh = 1920
        fps = 15

        temp_dir = tempfile.mkdtemp(prefix='yt_short_')
        fd = os.path.join(temp_dir, 'footage')
        os.makedirs(fd, exist_ok=True)

        all_footage = []
        for kw in footage_keywords[:2]:
            clips = download_stock_footage(kw, fd, self.pexels_key)
            all_footage.extend(clips)
            if clips: break
            time.sleep(1)

        if all_footage:
            bg = create_anime_background(all_footage[0], sw, sh, duration)
        else:
            bg = ColorClip(size=(sw, sh), color=(20, 10, 50), duration=duration)

        char_cfg = channel_config.get('character', {})
        try:
            cc = generate_character_clip(
                min(duration, 15), fps=6,
                hair_color=tuple(char_cfg.get('hair_color', [30,30,100])),
                eye_color=tuple(char_cfg.get('eye_color', [100,50,200])),
                outfit_color=tuple(char_cfg.get('outfit_color', [200,50,50]))
            )
            if cc.duration < duration:
                cc = concatenate_videoclips([cc] * (int(duration/cc.duration)+1))
            cc = cc.subclip(0, duration).set_position((sw-330, sh-550))
            scene = CompositeVideoClip([bg, cc], size=(sw, sh))
        except:
            scene = bg

        cta_map = {'telugu': 'పూర్తి వీడియో చానెల్ లో! 👆', 'hindi': 'पूरा वीडियो चैनल पर! 👆'}
        try:
            cta_bar = ColorClip(size=(sw,80), color=(0,0,0)).set_opacity(0.7).set_duration(duration).set_position(('center', sh-130))
            cta_txt = TextClip(cta_map.get(language, 'Full Video!'), fontsize=26,
                              color='#FFD700', stroke_color='black', stroke_width=2,
                              size=(sw-60, None), method='caption'
                              ).set_duration(duration).set_position(('center', sh-120))
            scene = CompositeVideoClip([scene, cta_bar, cta_txt], size=(sw, sh)).set_duration(duration)
        except: pass

        audio_trimmed = voice_audio.subclip(0, duration)
        scene = scene.set_audio(audio_trimmed).set_duration(duration)

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        scene.write_videofile(output_path, fps=fps, codec='libx264',
                             audio_codec='aac', bitrate='2000k',
                             preset='ultrafast', threads=2, logger=None)

        scene.close()
        voice_audio.close()
        try: shutil.rmtree(temp_dir)
        except: pass

        fs = os.path.getsize(output_path) / (1024*1024)
        logger.info(f"   ✅ Short: {fs:.1f} MB")
        return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("VideoAnimator ready")
