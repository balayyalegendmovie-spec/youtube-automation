"""
THUMBNAIL MAKER — Anime-Style Thumbnails

Creates eye-catching anime-style thumbnails:
- Stock image background with anime filter
- Bold text overlay (Telugu/Hindi)
- Anime character face
- Vibrant colors and effects
- YouTube-optimized 1280x720

Design formula:
- Dark/vibrant background
- Large text (2-4 words max)
- Character reaction face
- Bright accent colors (yellow/red text on dark bg)
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
        
        self.pexels_key = os.environ.get(
            'PEXELS_API_KEY',
            self.config['footage'].get('pexels_api_key', '')
        )
        if '${' in str(self.pexels_key):
            self.pexels_key = os.environ.get('PEXELS_API_KEY', '')
        
        logger.info("🖼️ Thumbnail Maker initialized (anime style)")
    

    def create_thumbnail(self, text, language, background_query, 
                          output_path, channel_config=None):
        """Create anime-style thumbnail"""
        
        logger.info(f"🖼️ Creating thumbnail: '{text[:30]}...'")
        
        size = (1280, 720)
        
        # Step 1: Background
        bg = self._get_background(background_query, size)
        logger.info(f"   ✅ Background ready")
        
        # Step 2: Apply anime filter to background
        bg = self._apply_anime_filter(bg)
        logger.info(f"   ✅ Anime filter applied")
        
        # Step 3: Dark gradient overlay
        bg = self._apply_dark_overlay(bg)
        
        # Step 4: Add anime character face (reaction)
        bg = self._add_character_reaction(bg, channel_config)
        logger.info(f"   ✅ Character added")
        
        # Step 5: Add text
        font_file = ''
        if channel_config:
            font_file = channel_config.get('font_file', '')
        bg = self._add_thumbnail_text(bg, text, language, font_file)
        logger.info(f"   ✅ Text overlay added")
        
        # Step 6: Add decorative effects
        bg = self._add_effects(bg)
        
        # Step 7: Final color boost
        bg = self._boost_colors(bg)
        
        # Save
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        bg.save(output_path, 'JPEG', quality=95)
        
        file_size = os.path.getsize(output_path) / 1024
        logger.info(f"   ✅ Thumbnail saved: {output_path} ({file_size:.0f} KB)")
        
        return output_path
    

    def _get_background(self, query, size):
        """Get background image from Pexels"""
        
        try:
            if not self.pexels_key:
                raise Exception("No Pexels API key")
            
            headers = {"Authorization": self.pexels_key}
            params = {
                "query": query,
                "per_page": 5,
                "orientation": "landscape",
                "size": "medium"
            }
            
            response = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers, params=params, timeout=10
            )
            
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
        
        return self._create_anime_gradient(size)
    

    def _create_anime_gradient(self, size):
        """Create anime-style gradient background"""
        
        img = Image.new('RGB', size)
        draw = ImageDraw.Draw(img)
        
        schemes = [
            [(40, 0, 80), (120, 0, 180), (200, 50, 100)],
            [(0, 30, 80), (0, 80, 180), (50, 150, 200)],
            [(80, 0, 20), (180, 30, 50), (220, 100, 50)],
            [(10, 40, 60), (30, 100, 120), (60, 180, 180)],
        ]
        
        colors = random.choice(schemes)
        
        for y in range(size[1]):
            ratio = y / size[1]
            
            if ratio < 0.5:
                r2 = ratio * 2
                r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * r2)
                g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * r2)
                b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * r2)
            else:
                r2 = (ratio - 0.5) * 2
                r = int(colors[1][0] + (colors[2][0] - colors[1][0]) * r2)
                g = int(colors[1][1] + (colors[2][1] - colors[1][1]) * r2)
                b = int(colors[1][2] + (colors[2][2] - colors[1][2]) * r2)
            
            draw.line([(0, y), (size[0], y)], fill=(r, g, b))
        
        return img
    

    def _apply_anime_filter(self, img):
        """Apply anime/cartoon filter to background image"""
        
        import cv2
        
        frame = np.array(img)
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        # Bilateral filter for smooth areas
        for _ in range(2):
            frame_bgr = cv2.bilateralFilter(frame_bgr, 9, 75, 75)
        
        # Edge detection
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        edges = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY, 9, 2
        )
        edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        
        # Color reduction
        div = 40
        frame_bgr = (frame_bgr // div) * div + div // 2
        
        # Combine
        cartoon = cv2.bitwise_and(frame_bgr, edges_bgr)
        
        # Boost saturation
        hsv = cv2.cvtColor(cartoon, cv2.COLOR_BGR2HSV)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.5, 0, 255).astype(np.uint8)
        cartoon = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        result_rgb = cv2.cvtColor(cartoon, cv2.COLOR_BGR2RGB)
        return Image.fromarray(result_rgb)
    

    def _apply_dark_overlay(self, img):
        """Dark gradient for text readability"""
        
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        for y in range(img.size[1]):
            # Darker at bottom and top, lighter in middle
            if y < img.size[1] * 0.3:
                alpha = int(150 - (y / (img.size[1] * 0.3)) * 80)
            elif y > img.size[1] * 0.7:
                ratio = (y - img.size[1] * 0.7) / (img.size[1] * 0.3)
                alpha = int(70 + ratio * 100)
            else:
                alpha = 70
            
            draw.line([(0, y), (img.size[0], y)], fill=(0, 0, 0, alpha))
        
        img_rgba = img.convert('RGBA')
        return Image.alpha_composite(img_rgba, overlay).convert('RGB')
    

    def _add_character_reaction(self, img, channel_config):
        """Add anime character reaction face to thumbnail"""
        
        from src.video_animator import AnimeCharacterGenerator
        
        char_config = channel_config.get('character', {}) if channel_config else {}
        character = AnimeCharacterGenerator(char_config)
        
        # Generate surprised/excited character
        char_frame = character.generate_character_frame(
            state='talking',
            mouth_open=True,
            eyes_open=True,
            hand_gesture='pointing'
        )
        
        # Resize character for thumbnail
        char_resized = char_frame.resize((220, 370), Image.LANCZOS)
        
        # Position in bottom-right
        img_rgba = img.convert('RGBA')
        x_pos = img.size[0] - 250
        y_pos = img.size[1] - 390
        
        img_rgba.paste(char_resized, (x_pos, y_pos), char_resized)
        
        return img_rgba.convert('RGB')
    

    def _add_thumbnail_text(self, img, text, language, font_file=''):
        """Add bold text to thumbnail"""
        
        draw = ImageDraw.Draw(img)
        
        # Try to load appropriate font
        font = None
        for size in [85, 75, 65, 55, 45]:
            try:
                if font_file and os.path.exists(font_file):
                    font = ImageFont.truetype(font_file, size)
                else:
                    for fallback in [
                        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                        'Arial Bold'
                    ]:
                        try:
                            font = ImageFont.truetype(fallback, size)
                            break
                        except Exception:
                            continue
                
                if font is None:
                    font = ImageFont.load_default()
                
                # Check text fits (leave room for character on right)
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                
                if text_width < img.size[0] - 300:
                    break
                    
            except Exception:
                font = ImageFont.load_default()
                break
        
        if font is None:
            font = ImageFont.load_default()
        
        # Position text (left-center area, leaving right side for character)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        x = 60
        y = (img.size[1] - text_h) // 2 - 20
        
        # Draw text with thick outline
        outline_size = 5
        outline_color = 'black'
        
        for dx in range(-outline_size, outline_size + 1):
            for dy in range(-outline_size, outline_size + 1):
                if dx * dx + dy * dy <= outline_size * outline_size:
                    draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
        
        # Main text in bright yellow
        draw.text((x, y), text, font=font, fill='#FFD700')
        
        # Add subtitle line below
        sub_text = {
            'telugu': '▶ పూర్తి వివరాలు లోపల!',
            'hindi': '▶ पूरी जानकारी अंदर!'
        }.get(language, '▶ Full Details Inside!')
        
        try:
            sub_font_size = max(20, (font.size if hasattr(font, 'size') else 30) // 2)
            sub_font = ImageFont.truetype(
                font_file if font_file and os.path.exists(font_file) else 
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                sub_font_size
            )
        except Exception:
            sub_font = font
        
        draw.text((x, y + text_h + 15), sub_text, font=sub_font, fill='white')
        
        return img
    

    def _add_effects(self, img):
        """Add sparkle/glow effects"""
        
        draw = ImageDraw.Draw(img)
        
        # Top accent line
        draw.rectangle([(0, 0), (img.size[0], 5)], fill='#FFD700')
        # Bottom accent line
        draw.rectangle([(0, img.size[1]-5), (img.size[0], img.size[1])], fill='#FFD700')
        
        # Corner accents
        corner_size = 40
        draw.polygon([(0, 0), (corner_size, 0), (0, corner_size)], fill='#FF4444')
        draw.polygon([
            (img.size[0], 0), (img.size[0]-corner_size, 0), (img.size[0], corner_size)
        ], fill='#FF4444')
        
        return img
    

    def _boost_colors(self, img):
        """Final color enhancement"""
        
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.3)
        
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.3)
        
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.2)
        
        return img


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    tm = ThumbnailMaker()
    tm.create_thumbnail(
        text="అంతరిక్ష రహస్యాలు",
        language="telugu",
        background_query="space galaxy",
        output_path="output/thumbnails/test_thumb.jpg",
        channel_config={'character': {'hair_color': [30,30,100], 'eye_color': [100,50,200], 'outfit_color': [200,50,50]}}
    )
