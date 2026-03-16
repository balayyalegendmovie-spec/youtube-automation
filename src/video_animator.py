"""
VIDEO ANIMATOR — HD Cinematic Style with Real Footage
No anime filter (it causes blur). Uses color grading instead.
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
    CompositeVideoClip, concatenate_videoclips, ColorClip,
    ImageSequenceClip, ImageClip, VideoClip
)
from moviepy.video.fx.all import crop
import requests

logger = logging.getLogger(__name__)


def cinematic_grade(frame):
    """Apply cinematic color grading — NOT blurry anime filter"""
    try:
        img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        # Increase contrast slightly
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        img = cv2.merge([l, a, b])
        img = cv2.cvtColor(img, cv2.COLOR_LAB2BGR)
        # Slight warm tint
        img = img.astype(np.float32)
        img[:, :, 2] = np.clip(img[:, :, 2] * 1.05, 0, 255)  # Red +5%
        img[:, :, 0] = np.clip(img[:, :, 0] * 0.95, 0, 255)  # Blue -5%
        img = img.astype(np.uint8)
        # Slight vignette
        rows, cols = img.shape[:2]
        X = cv2.getGaussianKernel(cols, cols * 0.7)
        Y = cv2.getGaussianKernel(rows, rows * 0.7)
        M = Y * X.T
        M = M / M.max()
        for i in range(3):
            img[:, :, i] = (img[:, :, i] * M).astype(np.uint8)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception:
        return frame


def extract_frame_from_video(video_path, time_sec=1):
    try:
        clip = VideoFileClip(video_path)
        t = min(time_sec, clip.duration - 0.1)
        frame = clip.get_frame(max(0, t))
        clip.close()
        return Image.fromarray(frame)
    except Exception:
        return None


def create_hd_background(video_path, target_w, target_h, duration):
    """Use REAL video clip as background with Ken Burns zoom — NO blur filter"""
    try:
        clip = VideoFileClip(video_path)
        clip_dur = min(clip.duration, duration)

        # Resize to fill target
        cw, ch = clip.size
        ratio = max(target_w / cw, target_h / ch) * 1.15  # Slightly larger for zoom
        clip = clip.resize(ratio)

        # Center crop
        cw, ch = clip.size
        clip = crop(clip, x_center=cw/2, y_center=ch/2,
                    width=target_w, height=target_h)

        # Loop if needed
        if clip_dur < duration:
            loops = int(duration / clip_dur) + 1
            clip = concatenate_videoclips([clip] * loops)

        clip = clip.subclip(0, duration)

        # Apply cinematic color grading (NOT anime filter)
        clip = clip.fl_image(cinematic_grade)

        return clip

    except Exception:
        # Fallback: static graded image
        try:
            pil_img = extract_frame_from_video(video_path)
            if pil_img:
                pil_img = pil_img.resize((target_w, target_h), Image.LANCZOS)
                arr = np.array(pil_img)
                arr = cinematic_grade(arr)
                return ImageClip(arr).set_duration(duration)
        except Exception:
            pass
        return ColorClip(size=(target_w, target_h), color=(15, 8, 40), duration=duration)


def create_character_frame(width=400, height=650, mouth_open=False,
                           eyes_open=True, hair_color=(20, 20, 60),
                           eye_color=(80, 40, 180), outfit_color=(180, 40, 40)):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = width // 2
    skin = (255, 218, 185)
    sc = 1.3

    draw.polygon([(cx-int(60*sc),int(200*sc)),(cx+int(60*sc),int(200*sc)),
                  (cx+int(70*sc),height),(cx-int(70*sc),height)], fill=outfit_color)
    draw.polygon([(cx-int(30*sc),int(200*sc)),(cx,int(230*sc)),
                  (cx+int(30*sc),int(200*sc))],
                 fill=tuple(min(c+40,255) for c in outfit_color))
    draw.line([(cx+int(55*sc),int(230*sc)),(cx+int(65*sc),int(310*sc))], fill=skin, width=int(14*sc))
    draw.line([(cx-int(55*sc),int(230*sc)),(cx-int(65*sc),int(310*sc))], fill=skin, width=int(14*sc))
    draw.rectangle([(cx-int(15*sc),int(180*sc)),(cx+int(15*sc),int(210*sc))], fill=skin)

    hcy = int(120*sc)
    draw.ellipse([(cx-int(55*sc),hcy-int(65*sc)),(cx+int(55*sc),hcy+int(65*sc))],
                 fill=skin, outline=(200,180,150), width=2)

    pts = [(cx-int(60*sc),hcy-int(10*sc)),(cx-int(50*sc),hcy-int(80*sc)),
           (cx-int(20*sc),hcy-int(90*sc)),(cx,hcy-int(95*sc)),
           (cx+int(20*sc),hcy-int(90*sc)),(cx+int(50*sc),hcy-int(80*sc)),
           (cx+int(60*sc),hcy-int(10*sc)),(cx+int(55*sc),hcy+int(10*sc)),
           (cx-int(55*sc),hcy+int(10*sc))]
    draw.polygon(pts, fill=hair_color)
    draw.polygon([(cx-int(58*sc),hcy-int(10*sc)),(cx-int(70*sc),hcy+int(60*sc)),
                  (cx-int(50*sc),hcy+int(50*sc)),(cx-int(55*sc),hcy)], fill=hair_color)
    draw.polygon([(cx+int(58*sc),hcy-int(10*sc)),(cx+int(70*sc),hcy+int(60*sc)),
                  (cx+int(50*sc),hcy+int(50*sc)),(cx+int(55*sc),hcy)], fill=hair_color)

    ey = hcy + int(5*sc)
    if eyes_open:
        for side in [-1, 1]:
            ox = cx + side * int(22*sc)
            draw.ellipse([(ox-int(14*sc),ey-int(14*sc)),(ox+int(14*sc),ey+int(14*sc))],
                         fill='white', outline=(60,60,60), width=2)
            draw.ellipse([(ox-int(9*sc),ey-int(9*sc)),(ox+int(9*sc),ey+int(9*sc))], fill=eye_color)
            draw.ellipse([(ox-int(5*sc),ey-int(5*sc)),(ox+int(3*sc),ey+int(3*sc))], fill=(15,15,15))
            draw.ellipse([(ox-int(6*sc),ey-int(8*sc)),(ox-int(2*sc),ey-int(4*sc))], fill='white')
    else:
        for side in [-1, 1]:
            ox = cx + side * int(22*sc)
            draw.arc([(ox-int(14*sc),ey-int(5*sc)),(ox+int(14*sc),ey+int(5*sc))],
                     0, 180, fill=(60,60,60), width=3)

    draw.arc([(cx-int(40*sc),ey-int(28*sc)),(cx-int(5*sc),ey-int(10*sc))], 200, 340, fill=hair_color, width=3)
    draw.arc([(cx+int(5*sc),ey-int(28*sc)),(cx+int(40*sc),ey-int(10*sc))], 200, 340, fill=hair_color, width=3)
    draw.line([(cx,hcy+int(25*sc)),(cx-int(3*sc),hcy+int(35*sc))], fill=(220,190,160), width=2)

    my = hcy + int(45*sc)
    if mouth_open:
        draw.ellipse([(cx-int(14*sc),my-int(6*sc)),(cx+int(14*sc),my+int(12*sc))],
                     fill=(200,90,90), outline=(170,70,70), width=2)
        draw.rectangle([(cx-int(10*sc),my-int(4*sc)),(cx+int(10*sc),my+int(1*sc))], fill='white')
    else:
        draw.arc([(cx-int(16*sc),my-int(5*sc)),(cx+int(16*sc),my+int(12*sc))],
                 0, 180, fill=(200,90,90), width=2)
    return img


def generate_character_clip(duration, fps=10, **kwargs):
    frames = []
    total = int(duration * fps)
    blink = fps * 4
    mouth = max(1, fps // 3)
    for f in range(total):
        img = create_character_frame(
            mouth_open=(f % mouth) < (mouth // 2),
            eyes_open=(f % blink) > 3, **kwargs)
        frames.append(np.array(img))
    return ImageSequenceClip(frames, fps=fps)


def download_stock_footage(keyword, output_dir, pexels_key, count=1):
    downloaded = []
    if not pexels_key:
        return downloaded
    try:
        resp = requests.get("https://api.pexels.com/videos/search",
                           headers={"Authorization": pexels_key},
                           params={"query": keyword, "per_page": 3,
                                   "size": "large", "orientation": "landscape"},
                           timeout=15)
        if resp.status_code != 200:
            return downloaded
        for i, video in enumerate(resp.json().get('videos', [])[:count]):
            sel = None
            for vf in video.get('video_files', []):
                if 720 <= vf.get('height', 0) <= 1080:
                    sel = vf
                    break
            if not sel:
                for vf in video.get('video_files', []):
                    if vf.get('height', 0) >= 480:
                        sel = vf
                        break
            if sel:
                fp = os.path.join(output_dir, f"clip_{keyword[:15].replace(' ','_')}_{i}.mp4")
                with open(fp, 'wb') as f:
                    f.write(requests.get(sel['link'], timeout=60).content)
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
        logger.info("🎬 STEP: Creating HD cinematic video...")
        voice = AudioFileClip(voice_path)
        total_dur = voice.duration
        logger.info(f"   Duration: {total_dur:.1f}s")

        rw = self.config.get('content',{}).get('long_form',{}).get('resolution_w', 1920)
        rh = self.config.get('content',{}).get('long_form',{}).get('resolution_h', 1080)
        fps = self.config.get('content',{}).get('long_form',{}).get('fps', 24)

        tmp = tempfile.mkdtemp(prefix='yt_')
        fd = os.path.join(tmp, 'footage')
        os.makedirs(fd, exist_ok=True)

        logger.info(f"   📥 Downloading HD footage...")
        footage = []
        for kw in footage_keywords[:12]:
            clips = download_stock_footage(kw, fd, self.pexels_key)
            footage.extend(clips)
            if len(footage) >= 10:
                break
            time.sleep(0.5)
        logger.info(f"   ✅ {len(footage)} HD clips")

        cc = channel_config.get('character', {})
        char_kw = {
            'hair_color': tuple(cc.get('hair_color', [20,20,60])),
            'eye_color': tuple(cc.get('eye_color', [80,40,180])),
            'outfit_color': tuple(cc.get('outfit_color', [180,40,40]))
        }

        logger.info(f"   🎨 Building {len(sections)} scenes (HD real footage)...")
        scenes = []
        ci = 0

        for si, sec in enumerate(sections):
            sd = sec.get('duration', total_dur / max(len(sections), 1))
            mk = sec.get('marker', '?')
            title = sec.get('title', '')
            logger.info(f"   🎨 Scene {si+1}/{len(sections)}: [{mk}] {sd:.1f}s")

            # Use REAL video clip (not static filtered image)
            if footage:
                bg = create_hd_background(footage[ci % len(footage)], rw, rh, sd)
                ci += 1
            else:
                bg = ColorClip(size=(rw, rh), color=(15, 8, 40), duration=sd)

            # Character overlay
            try:
                ch = generate_character_clip(min(sd, 25), fps=8, **char_kw)
                if ch.duration < sd:
                    ch = concatenate_videoclips([ch] * (int(sd/ch.duration)+1))
                ch = ch.subclip(0, min(sd, ch.duration))
                ch = ch.set_position((rw - 450, rh - 680))
                scene = CompositeVideoClip([bg, ch], size=(rw, rh))
            except Exception:
                scene = bg

            # Section title
            if title and title != mk:
                try:
                    txt = TextClip(title, fontsize=42, color='#FFFFFF',
                                   stroke_color='black', stroke_width=3,
                                   size=(rw-500, None), method='caption'
                                   ).set_duration(min(5, sd)).set_position((50, 35))
                    tbg = ColorClip(size=(rw-450, 80), color=(0,0,0)
                                    ).set_opacity(0.5).set_duration(min(5, sd)).set_position((30, 25))
                    scene = CompositeVideoClip([scene, tbg, txt], size=(rw, rh))
                except Exception:
                    pass

            # Subtitles
            st = sec.get('text', '')
            if st:
                try:
                    import re as rem
                    sents = rem.split(r'[.!?।]', st)
                    sub = '. '.join(s.strip() for s in sents[:2] if s.strip())
                    if len(sub) > 90:
                        sub = sub[:90] + '...'
                    if sub:
                        stxt = TextClip(sub, fontsize=30, color='white',
                                        stroke_color='black', stroke_width=2,
                                        size=(rw-250, None), method='caption', align='center'
                                        ).set_duration(min(8, sd)).set_start(2
                                        ).set_position(('center', rh-120))
                        sbg = ColorClip(size=(rw-200, 80), color=(0,0,0)
                                        ).set_opacity(0.4).set_duration(min(8, sd)
                                        ).set_start(2).set_position(('center', rh-130))
                        scene = CompositeVideoClip([scene, sbg, stxt], size=(rw, rh))
                except Exception:
                    pass

            scene = scene.set_duration(sd)
            scenes.append(scene)

        logger.info(f"   🔗 Joining {len(scenes)} scenes...")
        final = concatenate_videoclips(scenes, method="compose") if scenes else ColorClip(
            size=(rw, rh), color=(15,8,40), duration=total_dur)
        final = final.subclip(0, min(total_dur, final.duration))
        final = final.set_audio(voice)

        logger.info(f"   💾 Exporting HD video...")
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        br = self.config.get('content',{}).get('long_form',{}).get('bitrate', '4000k')
        final.write_videofile(output_path, fps=fps, codec='libx264',
                             audio_codec='aac', bitrate=br,
                             preset='medium', threads=2, logger=None)

        final.close()
        voice.close()
        for s in scenes:
            try: s.close()
            except: pass
        try: shutil.rmtree(tmp)
        except: pass

        logger.info(f"   ✅ Video: {os.path.getsize(output_path)/(1024*1024):.1f} MB")
        return output_path

    def create_anime_short(self, voice_path, section_text, footage_keywords,
                            language, channel_config, output_path):
        logger.info(f"   ✂️ Short: {os.path.basename(output_path)}")
        voice = AudioFileClip(voice_path)
        dur = min(voice.duration, 58)

        sw = self.config.get('content',{}).get('shorts',{}).get('resolution_w', 1080)
        sh = self.config.get('content',{}).get('shorts',{}).get('resolution_h', 1920)
        fps = self.config.get('content',{}).get('shorts',{}).get('fps', 24)

        tmp = tempfile.mkdtemp(prefix='yt_s_')
        fd = os.path.join(tmp, 'f')
        os.makedirs(fd, exist_ok=True)

        footage = []
        for kw in footage_keywords[:2]:
            clips = download_stock_footage(kw, fd, self.pexels_key)
            footage.extend(clips)
            if clips: break
            time.sleep(1)

        if footage:
            bg = create_hd_background(footage[0], sw, sh, dur)
        else:
            bg = ColorClip(size=(sw, sh), color=(15,8,40), duration=dur)

        cc = channel_config.get('character', {})
        try:
            ch = generate_character_clip(min(dur, 20), fps=6,
                hair_color=tuple(cc.get('hair_color', [20,20,60])),
                eye_color=tuple(cc.get('eye_color', [80,40,180])),
                outfit_color=tuple(cc.get('outfit_color', [180,40,40])))
            if ch.duration < dur:
                ch = concatenate_videoclips([ch] * (int(dur/ch.duration)+1))
            ch = ch.subclip(0, dur).set_position((sw-430, sh-700))
            scene = CompositeVideoClip([bg, ch], size=(sw, sh))
        except:
            scene = bg

        cta_map = {'telugu': 'Subscribe చేయండి! 🔔', 'hindi': 'Subscribe करें! 🔔'}
        try:
            bar = ColorClip(size=(sw,90), color=(0,0,0)).set_opacity(0.6
                  ).set_duration(dur).set_position(('center', sh-140))
            ctxt = TextClip(cta_map.get(language, 'Subscribe!'), fontsize=30,
                           color='#FFD700', stroke_color='black', stroke_width=2,
                           size=(sw-80, None), method='caption'
                           ).set_duration(dur).set_position(('center', sh-130))
            scene = CompositeVideoClip([scene, bar, ctxt], size=(sw, sh)).set_duration(dur)
        except: pass

        scene = scene.set_audio(voice.subclip(0, dur)).set_duration(dur)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        br = self.config.get('content',{}).get('shorts',{}).get('bitrate', '3000k')
        scene.write_videofile(output_path, fps=fps, codec='libx264',
                             audio_codec='aac', bitrate=br,
                             preset='medium', threads=2, logger=None)
        scene.close()
        voice.close()
        try: shutil.rmtree(tmp)
        except: pass
        logger.info(f"   ✅ Short: {os.path.getsize(output_path)/(1024*1024):.1f} MB")
        return output_path
