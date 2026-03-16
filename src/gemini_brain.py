"""
AI BRAIN — Multi-Provider with Automatic Fallback

Providers (all FREE):
1. Gemini (google-generativeai) — multiple models
2. Groq (groq) — very generous free tier
3. Direct HTTP to Gemini REST API — avoids SDK quota issues

If one provider fails → automatically tries next one.
"""

import json
import time
import logging
import re
import os
import requests as http_requests

logger = logging.getLogger(__name__)


class AIProvider:
    """Base class for AI providers"""
    
    def __init__(self, name, api_key):
        self.name = name
        self.api_key = api_key
        self.available = bool(api_key)
    
    def generate(self, prompt):
        raise NotImplementedError


class GeminiProvider(AIProvider):
    """Google Gemini via REST API (avoids deprecated SDK issues)"""
    
    def __init__(self, api_key, model="gemini-2.0-flash-lite"):
        super().__init__(f"Gemini ({model})", api_key)
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
    
    def generate(self, prompt):
        url = (
            f"{self.base_url}/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.85,
                "topP": 0.95,
                "maxOutputTokens": 8192,
            }
        }
        
        response = http_requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        if response.status_code == 429:
            raise Exception(f"Gemini rate limited (429)")
        
        if response.status_code != 200:
            error_msg = response.text[:300]
            raise Exception(f"Gemini API error {response.status_code}: {error_msg}")
        
        data = response.json()
        
        # Extract text from response
        candidates = data.get("candidates", [])
        if not candidates:
            raise Exception("Gemini returned no candidates")
        
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise Exception("Gemini returned no content parts")
        
        return parts[0].get("text", "")


class GroqProvider(AIProvider):
    """Groq API — FREE tier: 30 RPM, 14400 RPD"""
    
    def __init__(self, api_key, model="llama-3.3-70b-versatile"):
        super().__init__(f"Groq ({model})", api_key)
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"
    
    def generate(self, prompt):
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.85,
            "max_tokens": 8192,
        }
        
        response = http_requests.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            },
            timeout=60
        )
        
        if response.status_code == 429:
            raise Exception(f"Groq rate limited (429)")
        
        if response.status_code != 200:
            error_msg = response.text[:300]
            raise Exception(f"Groq API error {response.status_code}: {error_msg}")
        
        data = response.json()
        
        choices = data.get("choices", [])
        if not choices:
            raise Exception("Groq returned no choices")
        
        return choices[0].get("message", {}).get("content", "")


class GeminiBrain:
    """
    Multi-provider AI brain with automatic fallback.
    
    Tries providers in order:
    1. Gemini flash-lite (separate quota from flash)
    2. Groq llama-3.3-70b (FREE, very generous)
    3. Gemini 1.5-flash (another quota pool)
    4. Gemini 2.0-flash (original, might be rate limited)
    """
    
    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Get API keys
        self.gemini_key = os.environ.get(
            'GEMINI_API_KEY',
            self.config.get('gemini', {}).get('api_key', '')
        )
        self.groq_key = os.environ.get('GROQ_API_KEY', '')
        self.groq_key_2 = os.environ.get('GROQ_API_KEY_2', '')

        # Clean placeholders
        if '${' in str(self.gemini_key):
            self.gemini_key = os.environ.get('GEMINI_API_KEY', '')
        if '${' in str(self.groq_key):
            self.groq_key = os.environ.get('GROQ_API_KEY', '')
        if '${' in str(self.groq_key_2):
            self.groq_key_2 = os.environ.get('GROQ_API_KEY_2', '')

        # Build providers (order = priority)
        self.providers = []

        if self.gemini_key:
            self.providers.append(
                GeminiProvider(self.gemini_key, "gemini-2.0-flash-lite")
            )

        if self.groq_key:
            self.providers.append(
                GroqProvider(self.groq_key, "llama-3.3-70b-versatile")
            )

        if self.groq_key_2:
            self.providers.append(
                GroqProvider(self.groq_key_2, "llama-3.1-70b-versatile")
            )

        if self.gemini_key:
            self.providers.append(
                GeminiProvider(self.gemini_key, "gemini-1.5-flash")
            )
            self.providers.append(
                GeminiProvider(self.gemini_key, "gemini-2.0-flash")
            )

        if self.groq_key:
            # Groq also has other free models as fallback
            self.providers.append(
                GroqProvider(self.groq_key, "llama-3.1-8b-instant")
            )

        if not self.providers:
            raise Exception("No AI API keys! Set GEMINI_API_KEY or GROQ_API_KEY")

        logger.info("🧠 AI Brain initialized with providers:")
        for p in self.providers:
            status = "READY" if p.available else "NO KEY"
            logger.info(f"   → {p.name}: {status}")
    

    def _call_ai(self, prompt, expect_json=False):
        """Call AI with automatic fallback between providers"""
        
        last_error = None
        
        for provider in self.providers:
            if not provider.available:
                continue
            
            try:
                logger.info(f"   🤖 Trying {provider.name}...")
                
                text = provider.generate(prompt)
                text = text.strip()
                
                logger.info(f"   ✅ {provider.name} responded ({len(text)} chars)")
                
                if expect_json:
                    text = re.sub(r'```json\s*', '', text)
                    text = re.sub(r'```\s*', '', text)
                    text = text.strip()
                    
                    # Find JSON in response
                    json_match = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
                    if json_match:
                        text = json_match.group(0)
                    
                    return json.loads(text)
                
                return text
                
            except json.JSONDecodeError as e:
                logger.warning(f"   ⚠️ {provider.name} JSON parse error: {e}")
                last_error = e
                # Try next provider
                continue
                
            except Exception as e:
                error_str = str(e)
                logger.warning(f"   ⚠️ {provider.name} failed: {error_str[:100]}")
                last_error = e
                
                # If rate limited, try next provider immediately
                if '429' in error_str or 'rate' in error_str.lower() or 'quota' in error_str.lower():
                    logger.info(f"   ↪️ Switching to next provider...")
                    continue
                
                # For other errors, wait briefly then try next
                time.sleep(3)
                continue
        
        # All providers failed
        raise Exception(
            f"All AI providers failed. Last error: {last_error}"
        )


    # =============================================
    # TOPIC GENERATION
    # =============================================
    
    def generate_topics(self, niche, language, trend_data=None, count=3):
        """Generate video topics"""
        
        logger.info(f"🧠 STEP: Generating topics for '{niche}' in {language}...")
        
        trend_context = ""
        if trend_data:
            trend_topics = [t.get('topic', '') for t in trend_data[:10]]
            trend_context = f"""
Currently trending in India:
{json.dumps(trend_topics[:5], indent=2)}
Try to relate topics to these trends.
"""
        
        lang_name = "తెలుగు" if language == "telugu" else "हिंदी"
        
        prompt = f"""You are a YouTube content strategist for Indian audience.

Generate {count} video topic ideas.

NICHE: {niche}
LANGUAGE: {language} ({lang_name})
AUDIENCE: Indian viewers ages 16-35

{trend_context}

Requirements:
- Topics must be fascinating and click-worthy
- Must work as 10-minute explainer videos
- Each must be splittable into 4-5 standalone shorts
- Avoid politics, religion, controversy
- Include emotional hooks

Return ONLY valid JSON array:
[
    {{
        "topic": "Topic in English",
        "topic_local": "Topic in {language}",
        "search_keywords": ["keyword1", "keyword2", "keyword3"],
        "why_viral": "Why this will get views",
        "emotions_map": {{
            "hook": "excited",
            "section_1": "curious",
            "section_2": "serious",
            "section_3": "cheerful",
            "section_4": "excited",
            "cta": "warm"
        }},
        "sections": [
            "Section 1 title",
            "Section 2 title",
            "Section 3 title",
            "Section 4 title"
        ],
        "estimated_interest": "high"
    }}
]"""

        topics = self._call_ai(prompt, expect_json=True)
        
        if not isinstance(topics, list):
            topics = [topics]
        
        logger.info(f"   ✅ Generated {len(topics)} topics:")
        for i, t in enumerate(topics):
            logger.info(f"      {i+1}. {t.get('topic', 'N/A')}")
        
        return topics


    # =============================================
    # SCRIPT GENERATION
    # =============================================
    
    def generate_script(self, topic_data, language, target_words=1500):
        """Generate emotionally rich script"""
        
        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)
        emotions_map = topic_data.get('emotions_map', {})
        
        logger.info(f"🧠 STEP: Generating script for '{topic}'...")
        logger.info(f"   Language: {language}, Target: {target_words} words")
        
        lang_name = "తెలుగు" if language == "telugu" else "हिंदी"
        script_type = "Telugu" if language == "telugu" else "Devanagari"
        
        emotion_instructions = ""
        if emotions_map:
            emotion_instructions = f"""
EMOTIONS:
- Hook: {emotions_map.get('hook', 'excited')}
- Section 1: {emotions_map.get('section_1', 'curious')}
- Section 2: {emotions_map.get('section_2', 'serious')}
- Section 3: {emotions_map.get('section_3', 'cheerful')}
- Section 4: {emotions_map.get('section_4', 'excited')}
- CTA: {emotions_map.get('cta', 'warm')}
"""

        prompt = f"""Write a COMPLETE and DETAILED YouTube video script in {language} ({lang_name}).

TOPIC: "{topic}" / "{topic_local}"

{emotion_instructions}

CRITICAL — LENGTH REQUIREMENT:
You MUST write AT LEAST {target_words} words. This is a 10-MINUTE video.
Current target: {target_words} words MINIMUM.
If your script is under {target_words} words, it will be REJECTED.
Each section should be 150-250 words.
Count your words carefully.

WRITE IN: {language} using {script_type} script only.
Style: Natural, conversational, like talking to a friend.
Mix common English technical terms naturally.

STRUCTURE — Use these EXACT markers:

[HOOK]
Write 100-150 words here. Start with a SHOCKING fact. Create curiosity. 
Ask "మీకు తెలుసా?" or "क्या आपको पता है?" style questions.

[SECTION_1: Title in {language}]
Write 200-250 words. First main point. Real examples.
Reference something Indian audience relates to.
End with a teaser for next section.

[SECTION_2: Title in {language}]
Write 200-250 words. Go deeper. Include surprising twist.
Use comparisons. Must work as standalone short.

[SECTION_3: Title in {language}]
Write 200-250 words. Human/emotional angle.
How does this affect people in India?

[SECTION_4: Title in {language}]
Write 200-250 words. CLIMAX — most mind-blowing revelation.
Save the BEST fact for this section.

[CTA]
Write 100-150 words. Summary + subscribe call.
Tease next video. End with memorable line.

Add [VISUAL: description] tags (2-3 per section).
Use rhetorical questions every 2-3 sentences.
Include at least 5 specific numbers/statistics.

REMEMBER: MINIMUM {target_words} WORDS TOTAL. This is very important.

Return ONLY the script text."""

        script = self._call_ai(prompt)
        
        word_count = len(script.split())
        logger.info(f"   ✅ Script generated: {word_count} words")
        
        return script


    # =============================================
    # SCRIPT REVIEW
    # =============================================
    
    def review_script(self, script, language, topic):
        """AI reviews and improves the script"""
        
        logger.info(f"🧠 STEP: AI reviewing script quality...")
        
        prompt = f"""Review this {language} YouTube script about "{topic}".

SCRIPT:
---
{script[:3000]}
---

Score each category 1-10 and provide fixes.

Return JSON:
{{
    "overall_score": 8,
    "approved": true,
    "scores": {{
        "hook": 8,
        "facts": 9,
        "engagement": 7,
        "language": 8,
        "emotions": 8,
        "safety": 10
    }},
    "factual_issues": [],
    "improvements": ["improvement 1"],
    "revised_hook": null,
    "revised_script": null,
    "summary": "Brief summary"
}}

If overall_score < 7, include revised_script with fixes."""

        try:
            review = self._call_ai(prompt, expect_json=True)
        except Exception as e:
            logger.warning(f"   ⚠️ Review failed: {e}")
            logger.info(f"   ↪️ Using script without review")
            review = {
                "overall_score": 7,
                "approved": True,
                "scores": {},
                "improvements": [],
                "summary": "Review skipped due to API error"
            }
        
        score = review.get('overall_score', 7)
        logger.info(f"   📊 Review score: {score}/10")
        
        final_script = script
        
        if review.get('revised_script') and score < 6:
            logger.info(f"   🔄 Using revised script")
            final_script = review['revised_script']
        
        return final_script, review


    # =============================================
    # METADATA GENERATION
    # =============================================
    
    def generate_metadata(self, topic_data, language, video_type="long"):
        """Generate title, description, tags"""
        
        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)
        
        logger.info(f"🧠 Generating {video_type} metadata...")
        
        if video_type == "long":
            prompt = f"""Generate YouTube video metadata in {language}.

Topic: "{topic}" / "{topic_local}"
Type: Long-form (8-12 min), Indian audience

Return JSON:
{{
    "title": "Compelling title in {language} with emoji (50-70 chars)",
    "title_english": "Same in English",
    "description": "300-word SEO description in {language} with hashtags and subscribe CTA",
    "tags": ["15-20 mixed {language} and English tags"],
    "thumbnail_text": "2-4 bold words in {language} for thumbnail"
}}"""
        else:
            prompt = f"""Generate YouTube Shorts metadata in {language}.

Topic: "{topic}"
Type: Short (30-60 sec)

Return JSON:
{{
    "title": "Catchy title in {language} (40-60 chars) #shorts",
    "description": "Brief description with hashtags",
    "tags": ["10-15 tags including #shorts"],
    "thumbnail_text": "1-3 words in {language}"
}}"""

        try:
            metadata = self._call_ai(prompt, expect_json=True)
        except Exception as e:
            logger.warning(f"   ⚠️ Metadata generation failed: {e}")
            # Fallback metadata
            metadata = {
                "title": topic_local or topic,
                "title_english": topic,
                "description": f"Video about {topic}",
                "tags": [topic, language, "facts", "shorts"],
                "thumbnail_text": topic_local[:20] if topic_local else topic[:20]
            }
        
        if video_type == "short":
            tags = metadata.get('tags', [])
            if not any('#shorts' in str(t).lower() for t in tags):
                tags.append('#shorts')
            metadata['tags'] = tags
        
        logger.info(f"   ✅ Title: {metadata.get('title', 'N/A')[:50]}...")
        return metadata


    # =============================================
    # FOOTAGE KEYWORDS
    # =============================================
    
    def get_footage_keywords(self, script):
        """Extract visual keywords for stock footage"""
        
        logger.info(f"🧠 Extracting footage keywords...")
        
        prompt = f"""From this script, extract 15 ENGLISH keywords for stock footage search.

SCRIPT (first 2000 chars):
{script[:2000]}

Focus on visual scenes: nature, technology, space, abstract.
Return ONLY a JSON array of strings.
Example: ["satellite orbiting earth", "neural network", "ocean waves"]"""

        try:
            keywords = self._call_ai(prompt, expect_json=True)
            if not isinstance(keywords, list):
                keywords = ["technology", "science", "space", "nature", "abstract"]
        except Exception:
            keywords = [
                "technology", "science", "space", "nature", "abstract",
                "computer", "earth", "stars", "ocean", "city lights",
                "data visualization", "laboratory", "innovation",
                "futuristic", "education"
            ]
        
        logger.info(f"   ✅ {len(keywords)} footage keywords")
        return keywords


    # =============================================
    # SECTION PARSER
    # =============================================
    
    def parse_script_sections(self, script):
        """Parse script into sections"""
        
        logger.info(f"🧠 Parsing script sections...")
        
        sections = []
        current_section = None
        current_text = []
        
        for line in script.split('\n'):
            line = line.strip()
            
            section_match = re.match(
                r'\[(HOOK|SECTION_\d+|CTA)(?::\s*(.+?))?\]',
                line
            )
            
            if section_match:
                if current_section is not None:
                    sections.append({
                        'marker': current_section['marker'],
                        'title': current_section['title'],
                        'text': '\n'.join(current_text).strip(),
                        'is_short_candidate': current_section['marker'] not in ['CTA']
                    })
                
                current_section = {
                    'marker': section_match.group(1),
                    'title': section_match.group(2) or section_match.group(1)
                }
                current_text = []
            elif line and not line.startswith('[VISUAL'):
                current_text.append(line)
        
        if current_section and current_text:
            sections.append({
                'marker': current_section['marker'],
                'title': current_section['title'],
                'text': '\n'.join(current_text).strip(),
                'is_short_candidate': current_section['marker'] not in ['CTA']
            })
        
        # If no sections found (script didn't have markers),
        # split into chunks
        if not sections:
            logger.warning("   ⚠️ No section markers found, splitting by paragraphs")
            paragraphs = [p.strip() for p in script.split('\n\n') if p.strip()]
            
            if len(paragraphs) >= 4:
                sections = [
                    {'marker': 'HOOK', 'title': 'Hook',
                     'text': paragraphs[0], 'is_short_candidate': True},
                    {'marker': 'SECTION_1', 'title': 'Part 1',
                     'text': '\n'.join(paragraphs[1:3]), 'is_short_candidate': True},
                    {'marker': 'SECTION_2', 'title': 'Part 2',
                     'text': '\n'.join(paragraphs[3:5]) if len(paragraphs) > 4 else paragraphs[3] if len(paragraphs) > 3 else '',
                     'is_short_candidate': True},
                    {'marker': 'CTA', 'title': 'Ending',
                     'text': paragraphs[-1], 'is_short_candidate': False},
                ]
            else:
                sections = [
                    {'marker': 'HOOK', 'title': 'Content',
                     'text': script, 'is_short_candidate': True}
                ]
        
        logger.info(f"   ✅ Found {len(sections)} sections:")
        for s in sections:
            wc = len(s['text'].split())
            logger.info(f"      [{s['marker']}] {s['title'][:30]} — {wc} words")
        
        return sections


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    brain = GeminiBrain()
    topics = brain.generate_topics("space and science", "telugu", count=2)
    print(json.dumps(topics, indent=2, ensure_ascii=False))
