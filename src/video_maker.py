"""
═══════════════════════════════════════════════════════════════
  VIDEO MAKER — Animated Video Assembly Engine
  
  Creates videos that look alive with:
  • Subtle character breathing animation
  • Expression changes synced with emotions
  • Ken Burns camera movement
  • Smooth transitions between scenes
  • Subtitle overlays
  • Background music mixing
═══════════════════════════════════════════════════════════════
"""

import os
import subprocess
import logging
import math
import random
import numpy as np
from moviepy.editor import (
    VideoFileClip, AudioFileClip, ImageClip, TextClip,
    CompositeVideoClip, CompositeAudioClip, ColorClip,
    concatenate_videoclips
)
from moviepy.video.fx.all import resize, fadein, fadeout
from PIL import Image

logger = logging.getLogger(__name__)


class AnimatedVideoMaker:
    """Create animated videos from anime images + audio"""
    
    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.anim_config = self.config.get('anime', {}).get('animation', {})
        self.long_size = tuple(self.config['content']['long_form']['resolution'])
        self.short_size = tuple(self.config['content']['shorts']['resolution'])
        self.fps = self.config['content']['long_form']['fps']


    def create_long_video(self, section_audios, scene_images, 
                           bg_music_path, output_path, language,
                           font_path=None, log_fn=None):
        """Create the full long-form video"""
        
        if log_fn:
            log_fn("Starting long-form video assembly...")
        
        section_clips = []
        
        for i, (audio_info, scene_info) in enumerate(
            zip(section_audios, scene_images)
        ):
            if log_fn:
                log_fn(f"Assembling section {i+1}/{len(section_audios)}: "
                       f"{audio_info['section_marker']}")
            
            # Create animated section clip
            section_clip = self._create_animated_section(
                main_image_path=scene_info['main_image'],
                alt_image_paths=scene_info.get('alt_images', []),
                audio_path=audio_info['audio_path'],
                duration=audio_info['duration'],
                emotion=audio_info['emotion'],
                size=self.long_size
            )
            
            # Add transition
            if i > 0:
                section_clip = fadein(section_clip, 0.5)
            if i < len(section_audios) - 1:
                section_clip = fadeout(section_clip, 0.3)
            
            section_clips.append(section_clip)
        
        if log_fn:
            log_fn("Concatenating all sections...")
        
        # Concatenate all sections
        final = concatenate_videoclips(section_clips, method="compose")
        
        # Mix audio
        voice_clips = []
        for audio_info in section_audios:
            voice_clips.append(AudioFileClip(audio_info['audio_path']))
        
        from moviepy.audio.AudioClip import concatenate_audioclips
        full_voice = concatenate_audioclips(voice_clips)
        
        # Add background music
        audio_tracks = [full_voice]
        
        if bg_music_path and os.path.exists(bg_music_path):
            try:
                bg = AudioFileClip(bg_music_path)
                total_dur = full_voice.duration
                
                if bg.duration < total_dur:
                    loops = int(total_dur / bg.duration) + 1
                    bg_parts = [AudioFileClip(bg_music_path) for _ in range(loops)]
                    bg = concatenate_audioclips(bg_parts)
                
                bg = bg.subclip(0, total_dur)
                bg = bg.volumex(0.06)  # Very quiet
                audio_tracks.append(bg)
                
                if log_fn:
                    log_fn("Background music added")
                    
            except Exception as e:
                if log_fn:
                    log_fn(f"Background music skipped: {e}")
        
        mixed_audio = CompositeAudioClip(audio_tracks)
        final = final.set_audio(mixed_audio)
        
        if log_fn:
            log_fn(f"Exporting video ({final.duration:.0f}s)...")
        
        # Export
        final.write_videofile(
            output_path,
            fps=self.fps,
            codec='libx264',
            audio_codec='aac',
            bitrate='4000k',
            preset='faster',
            threads=2,
            logger=None
        )
        
        # Cleanup
        final.close()
        for c in section_clips:
            try: c.close()
            except: pass
        for a in voice_clips:
            try: a.close()
            except: pass
        
        if log_fn:
            log_fn(f"Long-form video exported: {output_path}")
        
        return output_path


    def _create_animated_section(self, main_image_path, alt_image_paths,
                                   audio_path, duration, emotion, size):
        """Create an animated clip from anime images"""
        
        W, H = size
        
        # Load main image
        main_img = ImageClip(main_image_path).resize(newsize=(W, H))
        main_img = main_img.set_duration(duration)
        
        # Apply breathing animation (subtle zoom in/out)
        breathing_speed = self.anim_config.get('breathing_speed', 0.3)
        
        def breathing_zoom(get_frame, t):
            """Subtle breathing zoom effect"""
            frame = get_frame(t)
            h, w = frame.shape[:2]
            
            # Sine wave zoom: 1.00 to 1.02
            scale = 1.0 + 0.015 * math.sin(2 * math.pi * breathing_speed * t)
            
            new_h = int(h * scale)
            new_w = int(w * scale)
            
            # Crop center after zoom
            y_off = (new_h - h) // 2
            x_off = (new_w - w) // 2
            
            img_pil = Image.fromarray(frame)
            img_pil = img_pil.resize((new_w, new_h), Image.LANCZOS)
            img_pil = img_pil.crop((x_off, y_off, x_off + w, y_off + h))
            
            return np.array(img_pil)
        
        animated = main_img.fl(breathing_zoom)
        
        # Apply slow camera pan (Ken Burns)
        pan_direction = random.choice(['left', 'right', 'up', 'down'])
        pan_speed = 15  # pixels over full duration
        
        def camera_pan(get_frame, t):
            """Slow camera pan effect"""
            frame = get_frame(t)
            h, w = frame.shape[:2]
            progress = t / max(duration, 0.1)
            
            offset = int(pan_speed * progress)
            
            img_pil = Image.fromarray(frame)
            
            # Slightly enlarge to allow pan room
            enlarge = 1.05
            ew, eh = int(w * enlarge), int(h * enlarge)
            img_pil = img_pil.resize((ew, eh), Image.LANCZOS)
            
            if pan_direction == 'left':
                x = offset
                y = (eh - h) // 2
            elif pan_direction == 'right':
                x = (ew - w) - offset
                y = (eh - h) // 2
            elif pan_direction == 'up':
                x = (ew - w) // 2
                y = offset
            else:
                x = (ew - w) // 2
                y = (eh - h) - offset
            
            x = max(0, min(x, ew - w))
            y = max(0, min(y, eh - h))
            
            img_pil = img_pil.crop((x, y, x + w, y + h))
            return np.array(img_pil)
        
        animated = animated.fl(camera_pan)
        
        # Add expression changes if alternate images available
        if alt_image_paths:
            animated = self._add_expression_changes(
                animated, alt_image_paths, duration, size
            )
        
        return animated


    def _add_expression_changes(self, base_clip, alt_image_paths, 
                                  duration, size):
        """Overlay expression changes at intervals"""
        
        W, H = size
        interval = self.anim_config.get('expression_change_interval', 6.0)
        
        layers = [base_clip]
        
        for i, alt_path in enumerate(alt_image_paths):
            if not os.path.exists(alt_path):
                continue
            
            # Calculate when this expression appears
            start_time = interval * (i + 1)
            if start_time >= duration - 1:
                break
            
            expr_duration = min(interval, duration - start_time)
            
            try:
                alt_clip = (ImageClip(alt_path)
                           .resize(newsize=(W, H))
                           .set_duration(expr_duration)
                           .set_start(start_time))
                
                # Crossfade
                alt_clip = fadein(alt_clip, 0.4)
                alt_clip = fadeout(alt_clip, 0.4)
                
                layers.append(alt_clip)
            except Exception:
                pass
        
        if len(layers) > 1:
            return CompositeVideoClip(layers, size=(W, H)).set_duration(duration)
        return base_clip


    def create_short_video(self, audio_path, main_image_path, alt_images,
                            duration, emotion, language, section_title,
                            channel_name, output_path, font_path=None,
                            log_fn=None):
        """Create a single vertical short"""
        
        W, H = self.short_size  # 1080 x 1920
        
        if log_fn:
            log_fn(f"Creating short: {section_title[:40]}...")
        
        # Load and crop image to vertical
        img = Image.open(main_image_path)
        
        # For vertical: crop center portion and resize
        iw, ih = img.size
        target_ratio = W / H  # 0.5625 (9:16)
        current_ratio = iw / ih
        
        if current_ratio > target_ratio:
            # Image is wider — crop sides
            new_w = int(ih * target_ratio)
            left = (iw - new_w) // 2
            img = img.crop((left, 0, left + new_w, ih))
        else:
            # Image is taller — crop top/bottom
            new_h = int(iw / target_ratio)
            top = (ih - new_h) // 2
            img = img.crop((0, top, iw, top + new_h))
        
        img = img.resize((W, H), Image.LANCZOS)
        
        # Save cropped version
        vert_path = output_path.replace('.mp4', '_bg.png')
        img.save(vert_path)
        
        # Create animated vertical clip
        section_clip = self._create_animated_section(
            main_image_path=vert_path,
            alt_image_paths=[],  # Simpler for shorts
            audio_path=audio_path,
            duration=min(duration, 58),
            emotion=emotion,
            size=self.short_size
        )
        
        # Add title overlay at top
        try:
            title_bar = ColorClip(
                size=(W, 100), color=(0, 0, 0)
            ).set_opacity(0.5).set_duration(section_clip.duration)
            
            title_txt = TextClip(
                section_title[:50],
                fontsize=32, color='white',
                size=(W - 40, None), method='caption'
            ).set_duration(section_clip.duration).set_position(('center', 30))
            
            title_overlay = CompositeVideoClip(
                [title_bar, title_txt], size=(W, 100)
            ).set_position(('center', 80))
            
        except Exception:
            title_overlay = None
        
        # Add CTA overlay at bottom
        cta_text = {
            'telugu': 'పూర్తి వీడియో చూడండి 👆',
            'hindi': 'पूरा वीडियो देखें 👆'
        }.get(language, 'Watch Full Video 👆')
        
        try:
            cta = TextClip(
                cta_text, fontsize=28, color='#FFD700',
                stroke_color='black', stroke_width=2
            ).set_duration(section_clip.duration).set_position(('center', H - 120))
        except Exception:
            cta = None
        
        # Compose
        layers = [section_clip]
        if title_overlay:
            layers.append(title_overlay)
        if cta:
            layers.append(cta)
        
        final = CompositeVideoClip(layers, size=self.short_size)
        
        # Set audio
        audio = AudioFileClip(audio_path)
        clip_dur = min(audio.duration, 58)
        final = final.subclip(0, clip_dur)
        audio = audio.subclip(0, clip_dur)
        final = final.set_audio(audio)
        
        # Export
        final.write_videofile(
            output_path,
            fps=self.fps,
            codec='libx264',
            audio_codec='aac',
            bitrate='3000k',
            preset='faster',
            threads=2,
            logger=None
        )
        
        # Cleanup
        final.close()
        audio.close()
        section_clip.close()
        
        if os.path.exists(vert_path):
            os.remove(vert_path)
        
        if log_fn:
            log_fn(f"Short exported: {output_path}")
        
        return output_path
