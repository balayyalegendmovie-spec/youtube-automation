"""
VIDEO ANIMATOR — HD Anime-Style with Ken Burns Zoom + Subtitles
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
        for _ in range(3):
            img = cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 7)
        edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                       cv2.THRESH_BINARY, blockSize=9, C=2)
        edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        div = 24
        img = (img // div) * div + div // 2
        cartoon = cv2.bitwise_and(img, edges_bgr)
        hsv = cv2.cvtColor(cartoon, cv2.COLOR_BGR2HSV)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.4, 0, 255).astype(np.uint8)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] * 1.1, 0, 255).astype(np.uint8)
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
    try:
        pil_img = extract_frame_from_video(video_path, time_sec=1)
        if pil_img is None:
            return ColorClip(size=(target_w, target_h), color=(15, 8, 40), duration=duration)

        zoom_w = int(target_w * 1.25)
        zoom_h = int(target_h * 1.25)
        pil_img = pil_img.resize((zoom_w, zoom_h), Image.LANCZOS)
        anime_img = apply_anime_filter_to_image(pil_img)
        arr = np.array(anime_img)

        def make_frame(t):
            progress = t / max(duration, 0.1)
            scale = 1.0 + progress * 0.18
            h, w = arr.shape[:2]
            nh, nw = int(h / scale), int(w / scale)
            y1, x1 = (h - nh) // 2, (w - nw) // 2
            cropped = arr[y1:y1+nh, x1:x1+nw]
            img = Image.fromarray(cropped).resize((target_w, target_h), Image.LANCZOS)
            return np.array(img)

        return VideoClip(make_frame, duration=duration)
    except Exception:
        return ColorClip(size=(target_w, target_h), color=(15, 8, 40), duration=duration)


def create_character_frame(width=400, height=650, mouth_open=False,
                           eyes_open=True, hair_color=(20, 20, 60),
                           eye_color=(80, 40, 180), outfit_color=(180, 40, 40)):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = width // 2
    skin = (255, 218, 185)
    sc = 1.3

    # Body
    draw.polygon([(cx-int(60*sc),int(200*sc)),(cx+int(60*sc),int(200*sc)),
                  (cx+int(70*sc),height),(cx-int(70*sc),height)], fill=outfit_color)
    draw.polygon([(cx-int(30*sc),int(200*sc)),(cx,int(230*sc)),
                  (cx+int(30*sc),int(200*sc))],
                 fill=tuple(min(c+40,255) for c in outfit_color))

    # Arms
    draw.line([(cx+int(55*sc),int(230*sc)),(cx+int(65*sc),int(310*sc))], fill=skin, width=int(14*sc))
    draw.line([(cx-int(55*sc),int(230*sc)),(cx-int(65*sc),int(310*sc))], fill=skin, width=int(14*sc))

    # Neck
    draw.rectangle([(cx-int(15*sc),int(180*sc)),(cx+int(15*sc),int(210*sc))], fill=skin)

    # Head
    hcy = int(120*sc)
    draw.ellipse([(cx-int(55*sc),hcy-int(65*sc)),(cx+int(55*sc),hcy+int(65*sc))],
                 fill=skin, outline=(200,180,150), width=2)

    # Hair
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

    # Eyes
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

    # Eyebrows
    draw.arc([(cx-int(40*sc),ey-int(28*sc)),(cx-int(5*sc),ey-int(10*sc))],
             200, 340, fill=hair_color, width=3)
    draw.arc([(cx+int(5*sc),ey-int(28*sc)),(cx+int(40*sc),ey-int(10*sc))],
             200, 340, fill=hair_color, width=3)

    # Nose
    draw.line([(cx,hcy+int(25*sc)),(cx-int(3*sc),hcy+int(35*sc))], fill=(220,190,160), width=2)

    # Mouth
    my = hcy + int(45*sc)
    if mouth_open:
        draw.ellipse([(cx-int(14*sc),my-int(6*sc)),(cx+int(14*sc),my+int(12*sc))],
                     fill=(200,90,90), outline=(170,70,70), width=2)
        draw.rectangle([(cx-int(10*sc),my-int(4*sc)),(cx+int(10*sc),my+int(1*sc))], fill='white')
    else:
        draw.arc([(cx-int(16*sc),my-int(5*sc)),(cx+int(16*sc),my+int(12*sc))],
                 0, 180, fill=(200,90,90), width=2)

    return img


def generate_character_clip(duration, fps=10, hair_color=(20,20,60),
                             eye_color=(80,40,180), outfit_color=(180,40,40)):
    frames = []
    total = int(duration * fps)
    blink = fps * 4
    mouth = max(1, fps // 3)

    for f in range(total):
        mo = (f % mouth) < (mouth // 2)
        eo = (f % blink) > 3
        img = create_character_frame(mouth_open=mo, eyes_open=eo,
                                      hair_color=hair_color, eye_color=eye_color,
                                      outfit_color=outfit_color)
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
        logger.info("🎬 STEP: Creating HD anime video...")
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
        for kw in footage_keywords[:10]:
            clips = download_stock_footage(kw, fd, self.pexels_key)
            footage.extend(clips)
            if len(footage) >= 8:
                break
            time.sleep(1)
        logger.info(f"   ✅ {len(footage)} clips")

        cc = channel_config.get('character', {})
        hair = tuple(cc.get('hair_color', [20,20,60]))
        eyes = tuple(cc.get('eye_color', [80,40,180]))
        outfit = tuple(cc.get('outfit_color', [180,40,40]))

        logger.info(f"   🎨 Building {len(sections)} scenes...")
        scenes = []
        ci = 0

        for si, sec in enumerate(sections):
            sd = sec.get('duration', total_dur / max(len(sections), 1))
            mk = sec.get('marker', '?')
            title = sec.get('title', '')
            logger.info(f"   🎨 Scene {si+1}/{len(sections)}: [{mk}] {sd:.1f}s")

            if footage:
                bg = create_anime_background(footage[ci % len(footage)], rw, rh, sd)
                ci += 1
            else:
                bg = ColorClip(size=(rw, rh), color=(15, 8, 40), duration=sd)

            try:
                ch = generate_character_clip(min(sd, 25), fps=8,
                                              hair_color=hair, eye_color=eyes, outfit_color=outfit)
                if ch.duration < sd:
                    ch = concatenate_videoclips([ch] * (int(sd/ch.duration)+1))
                ch = ch.subclip(0, min(sd, ch.duration))
                ch = ch.set_position((rw - 450, rh - 680))
                scene = CompositeVideoClip([bg, ch], size=(rw, rh))
            except Exception:
                scene = bg

            if title and title != mk:
                try:
                    txt = TextClip(title, fontsize=40, color='#FFD700',
                                   stroke_color='black', stroke_width=3,
                                   size=(rw-500, None), method='caption'
                                   ).set_duration(min(5, sd)).set_position((50, 35))
                    tbg = ColorClip(size=(rw-450, 80), color=(0,0,0)
                                    ).set_opacity(0.6).set_duration(min(5, sd)).set_position((30, 25))
                    scene = CompositeVideoClip([scene, tbg, txt], size=(rw, rh))
                except Exception:
                    pass

            st = sec.get('text', '')
            if st:
                try:
                    import re as rem
                    sents = rem.split(r'[.!?।]', st)
                    sub = '. '.join(s.strip() for s in sents[:2] if s.strip())
                    if len(sub) > 90:
                        sub = sub[:90] + '...'
                    if sub:
                        stxt = TextClip(sub, fontsize=28, color='white',
                                        stroke_color='black', stroke_width=2,
                                        size=(rw-250, None), method='caption', align='center'
                                        ).set_duration(min(8, sd)).set_start(2
                                        ).set_position(('center', rh-110))
                        sbg = ColorClip(size=(rw-200, 70), color=(0,0,0)
                                        ).set_opacity(0.5).set_duration(min(8, sd)
                                        ).set_start(2).set_position(('center', rh-120))
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
                             preset='fast', threads=2, logger=None)

        final.close()
        voice.close()
        for s in scenes:
            try: s.close()
            except: pass
        try: shutil.rmtree(tmp)
        except: pass

        fs = os.path.getsize(output_path) / (1024*1024)
        logger.info(f"   ✅ Video: {fs:.1f} MB")
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

        bg = create_anime_background(footage[0], sw, sh, dur) if footage else ColorClip(
            size=(sw, sh), color=(15,8,40), duration=dur)

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
            bar = ColorClip(size=(sw,90), color=(0,0,0)).set_opacity(0.7
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
                             preset='fast', threads=2, logger=None)

        scene.close()
        voice.close()
        try: shutil.rmtree(tmp)
        except: pass

        logger.info(f"   ✅ Short: {os.path.getsize(output_path)/(1024*1024):.1f} MB")
        return output_path
