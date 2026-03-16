"""
THUMBNAIL MAKER — Anime-Style Thumbnails (uses functions from video_animator)
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import requests
from io import BytesIO
import os
import logging
import random
import numpy as np

logger = logging.getLogger(__name__)


class ThumbnailMaker:

    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.pexels_key = os.environ.get('PEXELS_API_KEY',
            self.config.get('footage', {}).get('pexels_api_key', ''))
        if '${' in str(self.pexels_key):
            self.pexels_key = os.environ.get('PEXELS_API_KEY', '')
        logger.info("🖼️ Thumbnail Maker initialized (anime style)")

    def create_thumbnail(self, text, language, background_query,
                          output_path, channel_config=None):
        logger.info(f"🖼️ Creating thumbnail: '{text[:30]}...'")
        size = (1280, 720)

        bg = self._get_background(background_query, size)
        logger.info(f"   ✅ Background ready")

        bg = self._apply_anime_filter(bg)
        logger.info(f"   ✅ Anime filter applied")

        bg = self._apply_dark_overlay(bg)

        bg = self._add_character_reaction(bg, channel_config)
        logger.info(f"   ✅ Character added")

        font_file = ''
        if channel_config:
            font_file = channel_config.get('font_file', '')
        bg = self._add_thumbnail_text(bg, text, language, font_file)
        logger.info(f"   ✅ Text overlay added")

        bg = self._add_effects(bg)
        bg = self._boost_colors(bg)

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        bg.save(output_path, 'JPEG', quality=95)

        file_size = os.path.getsize(output_path) / 1024
        logger.info(f"   ✅ Thumbnail saved: {output_path} ({file_size:.0f} KB)")
        return output_path

    def _get_background(self, query, size):
        try:
            if not self.pexels_key:
                raise Exception("No key")
            headers = {"Authorization": self.pexels_key}
            params = {"query": query, "per_page": 5, "orientation": "landscape", "size": "medium"}
            response = requests.get("https://api.pexels.com/v1/search",
                                   headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                photos = response.json().get('photos', [])
                if photos:
                    photo = random.choice(photos)
                    img_url = photo['src']['large']
                    img_resp = requests.get(img_url, timeout=15)
                    img = Image.open(BytesIO(img_resp.content))
                    img = img.resize(size, Image.LANCZOS)
                    return img.convert('RGB')
        except Exception as e:
            logger.warning(f"   ⚠️ Background fetch failed: {e}")
        return self._create_gradient(size)

    def _create_gradient(self, size):
        img = Image.new('RGB', size)
        draw = ImageDraw.Draw(img)
        schemes = [
            [(40,0,80),(120,0,180)], [(0,30,80),(0,80,180)],
            [(80,0,20),(180,30,50)], [(10,40,60),(30,100,120)]
        ]
        c1, c2 = random.choice(schemes)
        for y in range(size[1]):
            r = y / size[1]
            color = tuple(int(c1[i]+(c2[i]-c1[i])*r) for i in range(3))
            draw.line([(0,y),(size[0],y)], fill=color)
        return img

    def _apply_anime_filter(self, img):
        try:
            from src.video_animator import apply_anime_filter_to_image
            return apply_anime_filter_to_image(img)
        except ImportError:
            # Fallback: simple posterize
            import cv2
            frame = np.array(img)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            for _ in range(2):
                frame_bgr = cv2.bilateralFilter(frame_bgr, 9, 75, 75)
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.medianBlur(gray, 5)
            edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                          cv2.THRESH_BINARY, 9, 2)
            edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            div = 32
            frame_bgr = (frame_bgr // div) * div + div // 2
            cartoon = cv2.bitwise_and(frame_bgr, edges_bgr)
            hsv = cv2.cvtColor(cartoon, cv2.COLOR_BGR2HSV)
            hsv[:,:,1] = np.clip(hsv[:,:,1]*1.3, 0, 255).astype(np.uint8)
            cartoon = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
            return Image.fromarray(cv2.cvtColor(cartoon, cv2.COLOR_BGR2RGB))

    def _apply_dark_overlay(self, img):
        overlay = Image.new('RGBA', img.size, (0,0,0,0))
        draw = ImageDraw.Draw(overlay)
        for y in range(img.size[1]):
            if y < img.size[1] * 0.3:
                alpha = int(150 - (y / (img.size[1]*0.3)) * 80)
            elif y > img.size[1] * 0.7:
                ratio = (y - img.size[1]*0.7) / (img.size[1]*0.3)
                alpha = int(70 + ratio * 100)
            else:
                alpha = 70
            draw.line([(0,y),(img.size[0],y)], fill=(0,0,0,alpha))
        img_rgba = img.convert('RGBA')
        return Image.alpha_composite(img_rgba, overlay).convert('RGB')

    def _add_character_reaction(self, img, channel_config):
        """Add anime character to thumbnail"""
        try:
            from src.video_animator import create_character_frame
        except ImportError:
            return img

        char_cfg = channel_config.get('character', {}) if channel_config else {}

        char_frame = create_character_frame(
            mouth_open=True,
            eyes_open=True,
            hair_color=tuple(char_cfg.get('hair_color', [30,30,100])),
            eye_color=tuple(char_cfg.get('eye_color', [100,50,200])),
            outfit_color=tuple(char_cfg.get('outfit_color', [200,50,50]))
        )

        char_resized = char_frame.resize((220, 370), Image.LANCZOS)

        img_rgba = img.convert('RGBA')
        x_pos = img.size[0] - 250
        y_pos = img.size[1] - 390
        img_rgba.paste(char_resized, (x_pos, y_pos), char_resized)
        return img_rgba.convert('RGB')

    def _add_thumbnail_text(self, img, text, language, font_file=''):
        draw = ImageDraw.Draw(img)

        # Clean text
        text = text.replace('*', '').strip()

        font = None
        for size in [80, 70, 60, 50, 40]:
            try:
                if font_file and os.path.exists(font_file):
                    font = ImageFont.truetype(font_file, size)
                else:
                    for fallback in [
                        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                        '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
                        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                    ]:
                        try:
                            font = ImageFont.truetype(fallback, size)
                            break
                        except:
                            continue

                if font is None:
                    font = ImageFont.load_default()

                bbox = draw.textbbox((0,0), text, font=font)
                text_width = bbox[2] - bbox[0]
                if text_width < img.size[0] - 300:
                    break
            except:
                font = ImageFont.load_default()
                break

        if font is None:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0,0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        x = 60
        y = (img.size[1] - text_h) // 2 - 20

        outline = 5
        for dx in range(-outline, outline+1):
            for dy in range(-outline, outline+1):
                if dx*dx + dy*dy <= outline*outline:
                    draw.text((x+dx, y+dy), text, font=font, fill='black')
        draw.text((x, y), text, font=font, fill='#FFD700')

        sub_text = {
            'telugu': '▶ పూర్తి వివరాలు లోపల!',
            'hindi': '▶ पूरी जानकारी अंदर!'
        }.get(language, '▶ Full Details Inside!')

        try:
            sub_font = ImageFont.truetype(
                font_file if font_file and os.path.exists(font_file)
                else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 28)
        except:
            sub_font = font
        draw.text((x, y + text_h + 15), sub_text, font=sub_font, fill='white')

        return img

    def _add_effects(self, img):
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0,0),(img.size[0],5)], fill='#FFD700')
        draw.rectangle([(0,img.size[1]-5),(img.size[0],img.size[1])], fill='#FFD700')
        cs = 40
        draw.polygon([(0,0),(cs,0),(0,cs)], fill='#FF4444')
        draw.polygon([(img.size[0],0),(img.size[0]-cs,0),(img.size[0],cs)], fill='#FF4444')
        return img

    def _boost_colors(self, img):
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = ImageEnhance.Color(img).enhance(1.3)
        img = ImageEnhance.Sharpness(img).enhance(1.2)
        return img


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("ThumbnailMaker ready")
