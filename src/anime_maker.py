"""
═══════════════════════════════════════════════════════════════
  ANIME MAKER — AI Anime Character & Scene Generation
  
  Uses Hugging Face Inference API (FREE)
  
  Generates:
  • Consistent anime character with different expressions
  • Background scenes matching script content  
  • Composited character-on-background images
  • Multiple expression variants for animation
  
  Character consistency via:
  • Fixed detailed character prompt
  • Same seed value
  • Same model
═══════════════════════════════════════════════════════════════
"""

import requests
import os
import io
import time
import logging
import yaml
import random
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

logger = logging.getLogger(__name__)


class AnimeMaker:
    """Generate anime character images for video scenes"""
    
    HF_API_URL = "https://api-inference.huggingface.co/models/"
    
    def __init__(self, config_path="config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.hf_token = os.environ.get('HF_API_TOKEN', '')
        self.headers = {"Authorization": f"Bearer {self.hf_token}"} if self.hf_token else {}
        
        anime_config = self.config.get('anime', {})
        self.model = anime_config.get('model', 'cagliostrolab/animagine-xl-3.1')
        self.fallback_model = anime_config.get('fallback_model', 
                               'stabilityai/stable-diffusion-xl-base-1.0')
        self.image_size = anime_config.get('image_size', 1024)


    def load_character(self, character_config_path):
        """Load character configuration"""
        
        with open(character_config_path, 'r') as f:
            self.character = yaml.safe_load(f)
        
        logger.info(f"Character loaded: {self.character['name']}")
        return self.character


    def generate_scene_images(self, scenes, character_config_path, 
                                output_dir, log_fn=None):
        """Generate all scene images for a video"""
        
        self.load_character(character_config_path)
        os.makedirs(output_dir, exist_ok=True)
        
        generated = []
        
        for i, scene in enumerate(scenes):
            if log_fn:
                log_fn(f"Generating anime scene {i+1}/{len(scenes)}: "
                       f"{scene.get('section', 'scene')} [{scene.get('emotion', 'neutral')}]")
            
            scene_dir = os.path.join(output_dir, f"scene_{i:02d}")
            os.makedirs(scene_dir, exist_ok=True)
            
            emotion = scene.get('emotion', scene.get('character_expression', 'neutral'))
            bg_type = self._determine_bg_type(scene.get('scene_description', ''))
            
            # Generate character with expression
            char_path = os.path.join(scene_dir, "character.png")
            self._generate_character_image(
                expression=emotion,
                background_type=bg_type,
                scene_desc=scene.get('scene_description', ''),
                output_path=char_path,
                log_fn=log_fn
            )
            
            # Generate alternate expression for animation variety
            alt_emotions = self._get_alt_emotions(emotion)
            alt_paths = []
            
            for j, alt_emotion in enumerate(alt_emotions[:2]):
                alt_path = os.path.join(scene_dir, f"character_alt_{j}.png")
                self._generate_character_image(
                    expression=alt_emotion,
                    background_type=bg_type,
                    scene_desc=scene.get('scene_description', ''),
                    output_path=alt_path,
                    log_fn=log_fn
                )
                alt_paths.append(alt_path)
            
            generated.append({
                'scene_index': i,
                'main_image': char_path,
                'alt_images': alt_paths,
                'emotion': emotion,
                'scene_dir': scene_dir
            })
        
        return generated


    def _generate_character_image(self, expression, background_type,
                                    scene_desc, output_path, log_fn=None):
        """Generate a single character image via Hugging Face API"""
        
        # Build prompt
        base = self.character['base_prompt']
        expr = self.character['expressions'].get(expression, 
                self.character['expressions'].get('neutral', ''))
        bg = self.character['backgrounds'].get(background_type,
              self.character['backgrounds'].get('default', ''))
        
        if scene_desc:
            bg = f"{bg}, {scene_desc}"
        
        full_prompt = f"{base}, {expr}, {bg}"
        negative = self.character.get('negative_prompt', '')
        seed = self.character.get('seed', 42)
        
        # Try primary model, then fallback
        models = [self.model, self.fallback_model]
        
        for model in models:
            try:
                image = self._call_hf_api(
                    model=model,
                    prompt=full_prompt,
                    negative_prompt=negative,
                    seed=seed
                )
                
                if image:
                    # Post-process: enhance and resize
                    image = self._post_process_image(image)
                    image.save(output_path, 'PNG', quality=95)
                    
                    if log_fn:
                        log_fn(f"    Generated: {expression} ({model.split('/')[-1]})")
                    return output_path
                    
            except Exception as e:
                logger.warning(f"Model {model} failed: {e}")
                continue
        
        # Ultimate fallback: create a styled gradient placeholder
        if log_fn:
            log_fn(f"    Using fallback gradient for: {expression}")
        
        self._create_fallback_image(expression, background_type, output_path)
        return output_path


    def _call_hf_api(self, model, prompt, negative_prompt="", seed=42):
        """Call Hugging Face Inference API"""
        
        url = f"{self.HF_API_URL}{model}"
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt": negative_prompt,
                "seed": seed,
                "width": self.image_size,
                "height": self.image_size,
                "num_inference_steps": 25,
                "guidance_scale": 7.0
            }
        }
        
        # Retry logic (model might be loading)
        for attempt in range(3):
            response = requests.post(
                url, 
                headers=self.headers, 
                json=payload, 
                timeout=120
            )
            
            if response.status_code == 200:
                image = Image.open(io.BytesIO(response.content))
                return image
            
            elif response.status_code == 503:
                # Model is loading
                wait_time = response.json().get('estimated_time', 30)
                logger.info(f"Model loading, waiting {wait_time:.0f}s...")
                time.sleep(min(wait_time, 60))
                continue
            
            elif response.status_code == 429:
                # Rate limited
                time.sleep(15 * (attempt + 1))
                continue
            
            else:
                error_msg = response.text[:200]
                raise Exception(f"HF API error {response.status_code}: {error_msg}")
        
        raise Exception(f"HF API failed after 3 attempts for model {model}")


    def _post_process_image(self, image):
        """Enhance the generated image"""
        
        # Resize to standard resolution
        image = image.resize((1920, 1080), Image.LANCZOS)
        
        # Enhance contrast slightly
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.1)
        
        # Enhance color vibrancy
        enhancer = ImageEnhance.Color(image)
        image = enhancer.enhance(1.15)
        
        # Slight sharpening
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.2)
        
        return image


    def _create_fallback_image(self, expression, bg_type, output_path):
        """Create a gradient background as fallback if API fails"""
        
        img = Image.new('RGB', (1920, 1080))
        draw = ImageDraw.Draw(img)
        
        # Color schemes per background type
        schemes = {
            'technology': [(20, 30, 80), (60, 100, 200)],
            'space': [(5, 5, 30), (30, 20, 80)],
            'history': [(60, 40, 20), (150, 100, 50)],
            'science': [(10, 50, 50), (30, 130, 130)],
            'nature': [(20, 60, 20), (80, 160, 80)],
            'finance': [(30, 30, 50), (80, 80, 140)],
            'default': [(20, 15, 40), (60, 40, 100)]
        }
        
        colors = schemes.get(bg_type, schemes['default'])
        start_c, end_c = colors
        
        for y in range(1080):
            ratio = y / 1080
            r = int(start_c[0] + (end_c[0] - start_c[0]) * ratio)
            g = int(start_c[1] + (end_c[1] - start_c[1]) * ratio)
            b = int(start_c[2] + (end_c[2] - start_c[2]) * ratio)
            draw.line([(0, y), (1920, y)], fill=(r, g, b))
        
        # Add some abstract shapes for visual interest
        for _ in range(5):
            x = random.randint(0, 1920)
            y = random.randint(0, 1080)
            r = random.randint(50, 200)
            opacity_color = tuple(
                min(255, c + random.randint(20, 60)) for c in end_c
            )
            draw.ellipse(
                [x - r, y - r, x + r, y + r],
                fill=opacity_color
            )
        
        # Blur for smooth gradient effect
        img = img.filter(ImageFilter.GaussianBlur(radius=40))
        
        img.save(output_path, 'PNG')


    def _determine_bg_type(self, scene_desc):
        """Determine background type from scene description"""
        
        scene_lower = scene_desc.lower()
        
        type_keywords = {
            'technology': ['tech', 'computer', 'ai', 'robot', 'digital', 'cyber', 'code'],
            'space': ['space', 'star', 'planet', 'galaxy', 'astronaut', 'cosmos', 'orbit'],
            'history': ['ancient', 'temple', 'historical', 'palace', 'tradition', 'era'],
            'science': ['lab', 'science', 'experiment', 'atom', 'molecule', 'research'],
            'nature': ['nature', 'forest', 'mountain', 'ocean', 'animal', 'tree'],
            'finance': ['money', 'finance', 'bank', 'stock', 'investment', 'economy'],
        }
        
        for bg_type, keywords in type_keywords.items():
            if any(kw in scene_lower for kw in keywords):
                return bg_type
        
        return 'default'


    def _get_alt_emotions(self, primary_emotion):
        """Get complementary emotions for animation variety"""
        
        emotion_transitions = {
            'neutral': ['thinking', 'explaining'],
            'happy': ['excited', 'neutral'],
            'excited': ['happy', 'surprised'],
            'serious': ['thinking', 'explaining'],
            'thinking': ['explaining', 'curious'],
            'surprised': ['excited', 'amazed'],
            'sad': ['thinking', 'neutral'],
            'explaining': ['thinking', 'serious'],
            'curious': ['thinking', 'surprised'],
            'amazed': ['excited', 'happy'],
            'inspired': ['happy', 'excited'],
        }
        
        return emotion_transitions.get(primary_emotion, ['neutral', 'thinking'])
