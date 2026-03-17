"""
VIDEO ANIMATOR — HD Real Footage with Section-Specific Backgrounds
"""

import os, random, logging, time, tempfile, shutil
import numpy as np, cv2, requests
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, ColorClip, ImageSequenceClip, ImageClip, VideoClip
)
from moviepy.video.fx.all import crop

logger = logging.getLogger(__name__)


def cinematic_grade(frame):
    try:
        img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(l)
        img = cv2.cvtColor(cv2.merge([l,a,b]), cv2.COLOR_LAB2BGR).astype(np.float32)
        img[:,:,2] = np.clip(img[:,:,2]*1.05, 0, 255)
        img[:,:,0] = np.clip(img[:,:,0]*0.95, 0, 255)
        rows, cols = img.shape[:2]
        M = (cv2.getGaussianKernel(cols, cols*0.7) * cv2.getGaussianKernel(rows, rows*0.7).T)
        M = M / M.max()
        for i in range(3):
            img[:,:,i] = img[:,:,i] * M
        return cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_BGR2RGB)
    except Exception:
        return frame


def create_hd_background(video_path, tw, th, duration):
    try:
        clip = VideoFileClip(video_path)
        r = max(tw/clip.size[0], th/clip.size[1]) * 1.15
        clip = clip.resize(r)
        cw, ch = clip.size
        clip = crop(clip, x_center=cw/2, y_center=ch/2, width=tw, height=th)
        if clip.duration < duration:
            clip = concatenate_videoclips([clip] * (int(duration/clip.duration)+1))
        clip = clip.subclip(0, duration).fl_image(cinematic_grade)
        return clip
    except Exception:
        try:
            clip = VideoFileClip(video_path)
            frame = clip.get_frame(min(1, clip.duration-0.1))
            clip.close()
            img = Image.fromarray(frame).resize((tw, th), Image.LANCZOS)
            return ImageClip(cinematic_grade(np.array(img))).set_duration(duration)
        except Exception:
            return ColorClip(size=(tw,th), color=(15,8,40), duration=duration)


def create_character_frame(width=400, height=650, mouth_open=False,
                           eyes_open=True, hair_color=(20,20,60),
                           eye_color=(80,40,180), outfit_color=(180,40,40)):
    img = Image.new('RGBA', (width, height), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx, skin, sc = width//2, (255,218,185), 1.3

    d.polygon([(cx-int(60*sc),int(200*sc)),(cx+int(60*sc),int(200*sc)),
               (cx+int(70*sc),height),(cx-int(70*sc),height)], fill=outfit_color)
    d.polygon([(cx-int(30*sc),int(200*sc)),(cx,int(230*sc)),
               (cx+int(30*sc),int(200*sc))], fill=tuple(min(c+40,255) for c in outfit_color))
    for s in [1,-1]:
        d.line([(cx+s*int(55*sc),int(230*sc)),(cx+s*int(65*sc),int(310*sc))], fill=skin, width=int(14*sc))
    d.rectangle([(cx-int(15*sc),int(180*sc)),(cx+int(15*sc),int(210*sc))], fill=skin)

    hcy = int(120*sc)
    d.ellipse([(cx-int(55*sc),hcy-int(65*sc)),(cx+int(55*sc),hcy+int(65*sc))], fill=skin, outline=(200,180,150), width=2)
    pts = [(cx-int(60*sc),hcy-int(10*sc)),(cx-int(50*sc),hcy-int(80*sc)),
           (cx-int(20*sc),hcy-int(90*sc)),(cx,hcy-int(95*sc)),
           (cx+int(20*sc),hcy-int(90*sc)),(cx+int(50*sc),hcy-int(80*sc)),
           (cx+int(60*sc),hcy-int(10*sc)),(cx+int(55*sc),hcy+int(10*sc)),
           (cx-int(55*sc),hcy+int(10*sc))]
    d.polygon(pts, fill=hair_color)
    for s in [-1,1]:
        d.polygon([(cx+s*int(58*sc),hcy-int(10*sc)),(cx+s*int(70*sc),hcy+int(60*sc)),
                   (cx+s*int(50*sc),hcy+int(50*sc)),(cx+s*int(55*sc),hcy)], fill=hair_color)

    ey = hcy+int(5*sc)
    if eyes_open:
        for s in [-1,1]:
            ox = cx+s*int(22*sc)
            d.ellipse([(ox-int(14*sc),ey-int(14*sc)),(ox+int(14*sc),ey+int(14*sc))], fill='white', outline=(60,60,60), width=2)
            d.ellipse([(ox-int(9*sc),ey-int(9*sc)),(ox+int(9*sc),ey+int(9*sc))], fill=eye_color)
            d.ellipse([(ox-int(5*sc),ey-int(5*sc)),(ox+int(3*sc),ey+int(3*sc))], fill=(15,15,15))
            d.ellipse([(ox-int(6*sc),ey-int(8*sc)),(ox-int(2*sc),ey-int(4*sc))], fill='white')
    else:
        for s in [-1,1]:
            ox = cx+s*int(22*sc)
            d.arc([(ox-int(14*sc),ey-int(5*sc)),(ox+int(14*sc),ey+int(5*sc))], 0, 180, fill=(60,60,60), width=3)

    d.arc([(cx-int(40*sc),ey-int(28*sc)),(cx-int(5*sc),ey-int(10*sc))], 200, 340, fill=hair_color, width=3)
    d.arc([(cx+int(5*sc),ey-int(28*sc)),(cx+int(40*sc),ey-int(10*sc))], 200, 340, fill=hair_color, width=3)
    d.line([(cx,hcy+int(25*sc)),(cx-int(3*sc),hcy+int(35*sc))], fill=(220,190,160), width=2)

    my = hcy+int(45*sc)
    if mouth_open:
        d.ellipse([(cx-int(14*sc),my-int(6*sc)),(cx+int(14*sc),my+int(12*sc))], fill=(200,90,90), outline=(170,70,70), width=2)
        d.rectangle([(cx-int(10*sc),my-int(4*sc)),(cx+int(10*sc),my+int(1*sc))], fill='white')
    else:
        d.arc([(cx-int(16*sc),my-int(5*sc)),(cx+int(16*sc),my+int(12*sc))], 0, 180, fill=(200,90,90), width=2)
    return img


def gen_char_clip(dur, fps=10, **kw):
    frames = []
    for f in range(int(dur*fps)):
        frames.append(np.array(create_character_frame(
            mouth_open=(f%(max(1,fps//3)))<(max(1,fps//3)//2),
            eyes_open=(f%(fps*4))>3, **kw)))
    return ImageSequenceClip(frames, fps=fps)


def dl_footage(kw, outdir, key, count=1):
    if not key: return []
    dl = []
    try:
        r = requests.get("https://api.pexels.com/videos/search",
            headers={"Authorization": key},
            params={"query": kw, "per_page": 3, "size": "large", "orientation": "landscape"}, timeout=15)
        if r.status_code != 200: return []
        for i, v in enumerate(r.json().get('videos', [])[:count]):
            sel = None
            for vf in v.get('video_files', []):
                if 720 <= vf.get('height', 0) <= 1080:
                    sel = vf; break
            if not sel:
                for vf in v.get('video_files', []):
                    if vf.get('height', 0) >= 480:
                        sel = vf; break
            if sel:
                fp = os.path.join(outdir, f"c_{kw[:15].replace(' ','_')}_{i}.mp4")
                with open(fp, 'wb') as f:
                    f.write(requests.get(sel['link'], timeout=60).content)
                dl.append(fp)
            time.sleep(0.5)
    except Exception as e:
        logger.warning(f"   ⚠️ DL '{kw}': {e}")
    return dl


class VideoAnimator:
    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.pkey = os.environ.get('PEXELS_API_KEY',
            self.config.get('footage',{}).get('pexels_api_key',''))
        if '${' in str(self.pkey): self.pkey = os.environ.get('PEXELS_API_KEY','')
        logger.info("🎬 Animator ready")

    def create_anime_video(self, voice_path, subtitle_path, footage_keywords,
                            sections, language, channel_config, output_path, bg_music_path=None):
        logger.info("🎬 Creating HD video...")
        voice = AudioFileClip(voice_path)
        td = voice.duration
        logger.info(f"   Duration: {td:.1f}s")

        rw = self.config.get('content',{}).get('long_form',{}).get('resolution_w', 1920)
        rh = self.config.get('content',{}).get('long_form',{}).get('resolution_h', 1080)
        fps = self.config.get('content',{}).get('long_form',{}).get('fps', 24)
        tmp = tempfile.mkdtemp(prefix='yt_')
        fd = os.path.join(tmp, 'f'); os.makedirs(fd, exist_ok=True)

        # Download section-specific footage
        logger.info(f"   📥 Downloading section-specific footage...")
        sec_footage = {}
        kw_per = max(2, len(footage_keywords) // max(len(sections), 1))

        for si in range(len(sections)):
            skw = footage_keywords[si*kw_per:(si+1)*kw_per] or footage_keywords[:2]
            clips = []
            for k in skw[:2]:
                c = dl_footage(k, fd, self.pkey)
                clips.extend(c)
                if clips: break
                time.sleep(0.5)
            sec_footage[si] = clips
            if clips:
                logger.info(f"   ✅ S{si+1}: {skw[0][:25]}")

        cc = channel_config.get('character', {})
        ckw = {k: tuple(cc.get(k, v)) for k, v in
               [('hair_color',[20,20,60]),('eye_color',[80,40,180]),('outfit_color',[180,40,40])]}

        logger.info(f"   🎨 {len(sections)} scenes...")
        scenes = []
        for si, sec in enumerate(sections):
            sd = sec.get('duration', td/max(len(sections),1))
            logger.info(f"   🎨 {si+1}/{len(sections)}: [{sec.get('marker','?')}] {sd:.1f}s")

            # Use section-specific footage
            if sec_footage.get(si):
                bg = create_hd_background(sec_footage[si][0], rw, rh, sd)
            else:
                all_f = [c for clips in sec_footage.values() for c in clips]
                bg = create_hd_background(all_f[si%len(all_f)], rw, rh, sd) if all_f else ColorClip(size=(rw,rh), color=(15,8,40), duration=sd)

            try:
                ch = gen_char_clip(min(sd,25), fps=8, **ckw)
                if ch.duration < sd:
                    ch = concatenate_videoclips([ch]*(int(sd/ch.duration)+1))
                ch = ch.subclip(0, min(sd, ch.duration)).set_position((rw-450, rh-680))
                scene = CompositeVideoClip([bg, ch], size=(rw, rh))
            except Exception:
                scene = bg

            title = sec.get('title', '')
            if title and title != sec.get('marker',''):
                try:
                    txt = TextClip(title, fontsize=42, color='#FFFFFF', stroke_color='black',
                                   stroke_width=3, size=(rw-500,None), method='caption'
                                   ).set_duration(min(5,sd)).set_position((50,35))
                    tbg = ColorClip(size=(rw-450,80), color=(0,0,0)).set_opacity(0.5
                          ).set_duration(min(5,sd)).set_position((30,25))
                    scene = CompositeVideoClip([scene, tbg, txt], size=(rw,rh))
                except Exception: pass

            st = sec.get('text', '')
            if st:
                try:
                    import re as rem
                    sents = rem.split(r'[.!?।]', st)
                    sub = '. '.join(s.strip() for s in sents[:2] if s.strip())[:90]
                    if sub:
                        stxt = TextClip(sub+'...', fontsize=30, color='white', stroke_color='black',
                                        stroke_width=2, size=(rw-250,None), method='caption', align='center'
                                        ).set_duration(min(8,sd)).set_start(2).set_position(('center',rh-120))
                        sbg = ColorClip(size=(rw-200,80), color=(0,0,0)).set_opacity(0.4
                              ).set_duration(min(8,sd)).set_start(2).set_position(('center',rh-130))
                        scene = CompositeVideoClip([scene, sbg, stxt], size=(rw,rh))
                except Exception: pass

            scenes.append(scene.set_duration(sd))

        final = concatenate_videoclips(scenes, method="compose") if scenes else ColorClip(size=(rw,rh), color=(15,8,40), duration=td)
        final = final.subclip(0, min(td, final.duration)).set_audio(voice)

        logger.info(f"   💾 Exporting...")
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        final.write_videofile(output_path, fps=fps, codec='libx264', audio_codec='aac',
                             bitrate=self.config.get('content',{}).get('long_form',{}).get('bitrate','4000k'),
                             preset='medium', threads=2, logger=None)
        final.close(); voice.close()
        for s in scenes:
            try: s.close()
            except: pass
        try: shutil.rmtree(tmp)
        except: pass
        logger.info(f"   ✅ {os.path.getsize(output_path)/(1024*1024):.1f} MB")
        return output_path

    def create_anime_short(self, voice_path, section_text, footage_keywords,
                            language, channel_config, output_path):
        logger.info(f"   ✂️ {os.path.basename(output_path)}")
        voice = AudioFileClip(voice_path)
        dur = min(voice.duration, 58)
        sw = self.config.get('content',{}).get('shorts',{}).get('resolution_w', 1080)
        sh = self.config.get('content',{}).get('shorts',{}).get('resolution_h', 1920)
        fps = self.config.get('content',{}).get('shorts',{}).get('fps', 24)
        tmp = tempfile.mkdtemp(prefix='yt_s_')
        fd = os.path.join(tmp, 'f'); os.makedirs(fd, exist_ok=True)

        footage = []
        for kw in footage_keywords[:2]:
            footage.extend(dl_footage(kw, fd, self.pkey))
            if footage: break
            time.sleep(1)

        bg = create_hd_background(footage[0], sw, sh, dur) if footage else ColorClip(size=(sw,sh), color=(15,8,40), duration=dur)

        cc = channel_config.get('character', {})
        try:
            ch = gen_char_clip(min(dur,20), fps=6,
                hair_color=tuple(cc.get('hair_color',[20,20,60])),
                eye_color=tuple(cc.get('eye_color',[80,40,180])),
                outfit_color=tuple(cc.get('outfit_color',[180,40,40])))
            if ch.duration < dur:
                ch = concatenate_videoclips([ch]*(int(dur/ch.duration)+1))
            ch = ch.subclip(0,dur).set_position((sw-430, sh-700))
            scene = CompositeVideoClip([bg, ch], size=(sw,sh))
        except: scene = bg

        cta = {'telugu': 'Subscribe చేయండి! 🔔', 'hindi': 'Subscribe करें! 🔔'}
        try:
            bar = ColorClip(size=(sw,90), color=(0,0,0)).set_opacity(0.6).set_duration(dur).set_position(('center',sh-140))
            ct = TextClip(cta.get(language,'Subscribe!'), fontsize=30, color='#FFD700',
                         stroke_color='black', stroke_width=2, size=(sw-80,None), method='caption'
                         ).set_duration(dur).set_position(('center',sh-130))
            scene = CompositeVideoClip([scene, bar, ct], size=(sw,sh)).set_duration(dur)
        except: pass

        scene = scene.set_audio(voice.subclip(0,dur)).set_duration(dur)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        scene.write_videofile(output_path, fps=fps, codec='libx264', audio_codec='aac',
                             bitrate=self.config.get('content',{}).get('shorts',{}).get('bitrate','3000k'),
                             preset='medium', threads=2, logger=None)
        scene.close(); voice.close()
        try: shutil.rmtree(tmp)
        except: pass
        logger.info(f"   ✅ {os.path.getsize(output_path)/(1024*1024):.1f} MB")
        return output_path
