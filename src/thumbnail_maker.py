"""
═══════════════════════════════════════════════════════════════
  THUMBNAIL MAKER — Eye-catching anime style thumbnails
═══════════════════════════════════════════════════════════════
"""

import os
import logging
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

logger = logging.getLogger(__name__)


class ThumbnailMaker:
    
    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)


    def create_thumbnail(self, text, scene_image_path, output_path,
                          font_path=None, log_fn=None):
        """Create a YouTube thumbnail (1280x720)"""
        
        SIZE = (1280, 720)
        
        # Load scene image as background
        try:
            bg = Image.open(scene_image_path)
            bg = bg.resize(SIZE, Image.LANCZOS)
        except Exception:
            bg = self._gradient_bg(SIZE)
        
        # Darken background slightly for text readability
        enhancer = ImageEnhance.Brightness(bg)
        bg = enhancer.enhance(0.7)
        
        # Increase contrast
        enhancer = ImageEnhance.Contrast(bg)
        bg = enhancer.enhance(1.3)
        
        # Add vignette effect
        bg = self._add_vignette(bg)
        
        draw = ImageDraw.Draw(bg)
        
        # Load font
        font = self._load_font(font_path, size=85)
        font_small = self._load_font(font_path, size=35)
        
        # Draw main text with heavy outline
        self._draw_outlined_text(
            draw, text, font, 
            position=(SIZE[0]//2, SIZE[1]//2 - 30),
            fill='#FFD700',
            outline_color='black',
            outline_width=5
        )
        
        # Add accent lines
        draw.rectangle([(40, 10), (SIZE[0]-40, 14)], fill='#FF4444')
        draw.rectangle([(40, SIZE[1]-14), (SIZE[0]-40, SIZE[1]-10)], fill='#FF4444')
        
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        bg.save(output_path, 'JPEG', quality=95)
        
        if log_fn:
            log_fn(f"Thumbnail created: {output_path}")
        
        return output_path


    def _load_font(self, font_path, size):
        paths_to_try = [
            font_path,
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "assets/fonts/NotoSansTelugu-Bold.ttf",
            "assets/fonts/NotoSansDevanagari-Bold.ttf",
        ]
        
        for p in paths_to_try:
            if p and os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
        
        return ImageFont.load_default()


    def _draw_outlined_text(self, draw, text, font, position,
                              fill='white', outline_color='black',
                              outline_width=4):
        x, y = position
        
        # Get text size
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        
        # Center
        x = x - tw // 2
        y = y - th // 2
        
        # Outline
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx*dx + dy*dy <= outline_width*outline_width:
                    draw.text((x+dx, y+dy), text, font=font, fill=outline_color)
        
        # Main text
        draw.text((x, y), text, font=font, fill=fill)


    def _add_vignette(self, img):
        w, h = img.size
        vignette = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(vignette)
        
        for i in range(min(w, h) // 4):
            alpha = int((i / (min(w, h) // 4)) * 120)
            draw.rectangle(
                [i, i, w - i, h - i],
                outline=(0, 0, 0, 120 - alpha)
            )
        
        img = img.convert('RGBA')
        img = Image.alpha_composite(img, vignette)
        return img.convert('RGB')


    def _gradient_bg(self, size):
        img = Image.new('RGB', size)
        draw = ImageDraw.Draw(img)
        
        c1 = (random.randint(10, 40), random.randint(10, 30), random.randint(40, 80))
        c2 = (random.randint(60, 120), random.randint(30, 80), random.randint(80, 160))
        
        for y in range(size[1]):
            r = y / size[1]
            color = tuple(int(c1[i] + (c2[i] - c1[i]) * r) for i in range(3))
            draw.line([(0, y), (size[0], y)], fill=color)
        
        return img
