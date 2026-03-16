"""
AI BRAIN — Multi-Provider with Automatic Fallback
"""

import json
import time
import logging
import re
import os
import requests as http_requests

logger = logging.getLogger(__name__)


class AIProvider:
    def __init__(self, name, api_key):
        self.name = name
        self.api_key = api_key
        self.available = bool(api_key)

    def generate(self, prompt):
        raise NotImplementedError


class GeminiProvider(AIProvider):
    def __init__(self, api_key, model="gemini-2.0-flash-lite"):
        super().__init__(f"Gemini ({model})", api_key)
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def generate(self, prompt):
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.85,
                "topP": 0.95,
                "maxOutputTokens": 8192,
            }
        }
        response = http_requests.post(url, json=payload,
                                       headers={"Content-Type": "application/json"},
                                       timeout=60)
        if response.status_code == 429:
            raise Exception("Gemini rate limited (429)")
        if response.status_code != 200:
            raise Exception(f"Gemini API error {response.status_code}: {response.text[:300]}")
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise Exception("Gemini returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise Exception("Gemini returned no content parts")
        return parts[0].get("text", "")


class GroqProvider(AIProvider):
    def __init__(self, api_key, model="llama-3.3-70b-versatile"):
        super().__init__(f"Groq ({model})", api_key)
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"

    def generate(self, prompt):
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.85,
            "max_tokens": 8192,
        }
        response = http_requests.post(url, json=payload,
                                       headers={"Content-Type": "application/json",
                                                "Authorization": f"Bearer {self.api_key}"},
                                       timeout=60)
        if response.status_code == 429:
            raise Exception("Groq rate limited (429)")
        if response.status_code != 200:
            raise Exception(f"Groq API error {response.status_code}: {response.text[:300]}")
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise Exception("Groq returned no choices")
        return choices[0].get("message", {}).get("content", "")


class GeminiBrain:

    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.gemini_key = os.environ.get('GEMINI_API_KEY',
                                          self.config.get('gemini', {}).get('api_key', ''))
        self.groq_key = os.environ.get('GROQ_API_KEY', '')
        self.groq_key_2 = os.environ.get('GROQ_API_KEY_2', '')

        if '${' in str(self.gemini_key):
            self.gemini_key = os.environ.get('GEMINI_API_KEY', '')
        if '${' in str(self.groq_key):
            self.groq_key = os.environ.get('GROQ_API_KEY', '')
        if '${' in str(self.groq_key_2):
            self.groq_key_2 = os.environ.get('GROQ_API_KEY_2', '')

        self.providers = []

        if self.gemini_key:
            self.providers.append(GeminiProvider(self.gemini_key, "gemini-2.0-flash-lite"))

        if self.groq_key:
            self.providers.append(GroqProvider(self.groq_key, "llama-3.3-70b-versatile"))

        if self.groq_key_2:
            self.providers.append(GroqProvider(self.groq_key_2, "mistral-saba-24b"))

        if self.gemini_key:
            self.providers.append(GeminiProvider(self.gemini_key, "gemini-2.0-flash"))

        if self.groq_key:
            self.providers.append(GroqProvider(self.groq_key, "deepseek-r1-distill-llama-70b"))

        if not self.providers:
            raise Exception("No AI API keys! Set GEMINI_API_KEY or GROQ_API_KEY")

        logger.info("🧠 AI Brain initialized with providers:")
        for p in self.providers:
            logger.info(f"   → {p.name}: {'READY' if p.available else 'NO KEY'}")

    def _call_ai(self, prompt, expect_json=False):
        last_error = None
        for provider in self.providers:
            if not provider.available:
                continue
            try:
                logger.info(f"   🤖 Trying {provider.name}...")
                text = provider.generate(prompt).strip()
                logger.info(f"   ✅ {provider.name} responded ({len(text)} chars)")
                if expect_json:
                    text = re.sub(r'```json\s*', '', text)
                    text = re.sub(r'```\s*', '', text)
                    text = text.strip()
                    json_match = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
                    if json_match:
                        text = json_match.group(0)
                    return json.loads(text)
                return text
            except json.JSONDecodeError as e:
                logger.warning(f"   ⚠️ {provider.name} JSON error: {e}")
                last_error = e
                continue
            except Exception as e:
                logger.warning(f"   ⚠️ {provider.name} failed: {str(e)[:100]}")
                last_error = e
                if '429' in str(e) or 'rate' in str(e).lower() or 'quota' in str(e).lower():
                    logger.info(f"   ↪️ Switching...")
                    continue
                time.sleep(3)
                continue
        raise Exception(f"All providers failed. Last: {last_error}")

    def generate_topics(self, niche, language, trend_data=None, count=3):
        logger.info(f"🧠 STEP: Generating topics for '{niche}' in {language}...")
        trend_context = ""
        if trend_data:
            topics_list = [t.get('topic', '') for t in trend_data[:5]]
            trend_context = f"\nTrending in India:\n{json.dumps(topics_list, indent=2)}\nRelate to these.\n"

        lang_name = "తెలుగు" if language == "telugu" else "हिंदी"
        prompt = f"""YouTube content strategist for Indian audience.
Generate {count} video topics.
NICHE: {niche}, LANGUAGE: {language} ({lang_name}), AUDIENCE: 16-35 India
{trend_context}
Requirements: fascinating, 10-min explainer, splittable into shorts, avoid politics/religion
Return ONLY JSON array:
[{{"topic":"English","topic_local":"{language}","search_keywords":["k1","k2"],"why_viral":"reason","emotions_map":{{"hook":"excited","section_1":"curious","section_2":"serious","section_3":"cheerful","section_4":"excited","cta":"warm"}},"sections":["S1","S2","S3","S4"],"estimated_interest":"high"}}]"""

        topics = self._call_ai(prompt, expect_json=True)
        if not isinstance(topics, list):
            topics = [topics]
        logger.info(f"   ✅ {len(topics)} topics:")
        for i, t in enumerate(topics):
            logger.info(f"      {i+1}. {t.get('topic', 'N/A')}")
        return topics

    def generate_script(self, topic_data, language, target_words=2000):
        """Generate natural Tenglish/Hinglish conversational script"""
        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)

        logger.info(f"🧠 STEP: Generating script for '{topic}'...")
        logger.info(f"   Language: {language}, Target: {target_words} words")

        if language == "telugu":
            lang_instruction = """LANGUAGE STYLE — "Tenglish" (Telugu + English mix):
- Write in Telugu script (తెలుగు) BUT mix English words naturally (30-40%)
- Example: "AI technology అనేది చాలా powerful గా develop అవుతోంది"
- Example: "ఈ concept ని simple గా explain చేస్తాను"
- Example: "India లో almost 50 million students ఈ technology use చేస్తున్నారు"
- Talk like a young Telugu YouTuber, NOT a textbook
- Use "guys", "OK so", "basically", "actually" naturally in between"""
        else:
            lang_instruction = """LANGUAGE STYLE — "Hinglish" (Hindi + English mix):
- Write in Hindi/Devanagari BUT mix English words naturally (30-40%)
- Example: "AI technology बहुत powerful तरीके से develop हो रही है"
- Talk like a young Hindi YouTuber, NOT formal news reader"""

        prompt = f"""You are a TOP Indian YouTuber making complex topics EXCITING.
Style: energetic, funny, relatable, like talking to your best friend.

TOPIC: "{topic}" / "{topic_local}"

{lang_instruction}

CRITICAL: MINIMUM 1800 WORDS. This is a 10-minute video.
Write like you're TALKING to camera, not reading.
Use "guys", excitement, reactions, audience questions.

STRUCTURE:

[HOOK]
(250+ words. MOST IMPORTANT section.
Start SHOCKING: "Guys... ఈ రోజు topic వింటే మీరు shock అవుతారు!"
Or start with impossible question: "Wait... మీకు తెలుసా ..."
Create INTENSE curiosity. Tell them WHY they MUST watch.
Use dramatic language. Make a PROMISE about what they'll learn.
Ask them to comment their guess: "comment లో చెప్పండి మీ answer!")

[SECTION_1: {{Catchy title in Telugu+English}}]
(300+ words. First main point.
"OK so first thing..." casual opener.
REAL examples from India with specific numbers.
Tell a mini STORY about a real person/place.
Compare to relatable things from daily Indian life.
React: "Seriously, ఇది crazy right?!"
End with teaser: "కానీ wait... next part even more interesting!")

[SECTION_2: {{Catchy title in Telugu+English}}]
(300+ words. Go DEEPER.
"ఇప్పుడు real interesting part కి వచ్చాం..."
Reveal something SURPRISING or counter-intuitive.
"మీరు believe చేయరు కానీ..." style reveals.
Include a dramatic "plot twist" moment.
React: "నేను first time విన్నప్పుడు కూడా shock అయ్యాను!")

[SECTION_3: {{Catchy title in Telugu+English}}]
(300+ words. PERSONAL and RELATABLE.
"ఇది మన daily life ని ఎలా affect చేస్తుందంటే..."
Connect to everyday Indian life — phone, food, family, work.
Give PRACTICAL examples anyone can relate to.
Use humor: "మీ mom కి చెప్పండి — she'll be like WHAT?!"
Ask audience: "మీరు ఇలా experience చేశారా? comment చేయండి!")

[SECTION_4: {{Catchy title in Telugu+English}}]
(300+ words. CLIMAX — most MIND-BLOWING part.
"OK guys... ఇప్పుడు BIGGEST revelation..."
Build tension: "Ready? ... 3... 2... 1..."
DROP the most amazing fact.
React emotionally: "Crazy right?! Mind = blown!"
Make viewers feel WOW.)

[CTA]
(150+ words. Warm friendly ending.
"So guys, ఈ రోజు main points ఏంటంటే..."
3 bullet point takeaways.
"ఈ video నచ్చితే like కొట్టండి, subscribe చేయండి, bell icon press చేయండి!"
Tease next video: "Next video లో even MORE mind-blowing topic..."
Memorable one-liner ending.)

Add [VISUAL: description] tags every 3-4 sentences.
Ask viewer questions every 5 sentences.
Use reactions: "Whoa!", "Seriously?!", "Mind blown!"
Reference: cricket, Bollywood, Indian cities, festivals, food.

MINIMUM 1800 WORDS. Write MORE. Tell STORIES. Be DETAILED.
Write ONLY the script."""

        script = self._call_ai(prompt)
        word_count = len(script.split())
        logger.info(f"   ✅ Script: {word_count} words")

        if word_count < 800:
            logger.info(f"   🔄 Expanding ({word_count} words)...")
            try:
                expand = f"""Expand this {language} script to 1800+ words. Add stories, examples, reactions, audience interaction. Keep markers.

SCRIPT:
{script[:3000]}

EXPANDED (1800+ words):"""
                expanded = self._call_ai(expand)
                if len(expanded.split()) > word_count:
                    script = expanded
                    logger.info(f"   ✅ Expanded to {len(expanded.split())} words")
            except Exception as e:
                logger.warning(f"   ⚠️ Expansion failed: {e}")

        return script

    def review_script(self, script, language, topic):
        logger.info(f"🧠 STEP: Reviewing script...")
        prompt = f"""Review this {language} YouTube script about "{topic}".
SCRIPT:
---
{script[:3000]}
---
Return JSON:
{{"overall_score":8,"approved":true,"scores":{{"hook":8,"facts":9,"engagement":7,"language":8}},"improvements":["tip1"],"summary":"brief"}}"""

        try:
            review = self._call_ai(prompt, expect_json=True)
        except Exception:
            review = {"overall_score": 7, "approved": True, "scores": {},
                      "improvements": [], "summary": "Review skipped"}

        logger.info(f"   📊 Score: {review.get('overall_score', 7)}/10")
        final = script
        if review.get('revised_script') and review.get('overall_score', 7) < 6:
            final = review['revised_script']
        return final, review

    def generate_metadata(self, topic_data, language, video_type="long"):
        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)
        logger.info(f"🧠 Generating {video_type} metadata...")

        if video_type == "long":
            prompt = f"""YouTube metadata in {language}. Topic: "{topic}"/"{topic_local}". Long-form, Indian audience.
Return JSON: {{"title":"{language} title with emoji (50-70 chars)","title_english":"English","description":"300-word SEO description","tags":["15-20 tags"],"thumbnail_text":"2-4 bold words"}}"""
        else:
            prompt = f"""YouTube Shorts metadata in {language}. Topic: "{topic}".
Return JSON: {{"title":"catchy {language} title #shorts","description":"brief + hashtags","tags":["10 tags + #shorts"],"thumbnail_text":"1-3 words"}}"""

        try:
            metadata = self._call_ai(prompt, expect_json=True)
        except Exception:
            metadata = {"title": topic_local or topic, "description": f"About {topic}",
                       "tags": [topic, language, "facts"], "thumbnail_text": (topic_local or topic)[:20]}

        if video_type == "short":
            tags = metadata.get('tags', [])
            if not any('#shorts' in str(t).lower() for t in tags):
                tags.append('#shorts')
            metadata['tags'] = tags

        logger.info(f"   ✅ Title: {metadata.get('title', 'N/A')[:50]}...")
        return metadata

    def get_footage_keywords(self, script):
        logger.info(f"🧠 Extracting footage keywords...")
        prompt = f"""From this script, extract 15 ENGLISH keywords for HD stock footage.
SCRIPT: {script[:2000]}
Return ONLY JSON array: ["keyword1", "keyword2"]"""

        try:
            kw = self._call_ai(prompt, expect_json=True)
            if not isinstance(kw, list):
                kw = ["technology", "science", "space", "nature", "abstract"]
        except Exception:
            kw = ["technology", "science", "space", "nature", "abstract",
                  "computer", "earth", "stars", "ocean", "city", "data",
                  "laboratory", "innovation", "futuristic", "education"]

        logger.info(f"   ✅ {len(kw)} keywords")
        return kw

    def parse_script_sections(self, script):
        logger.info(f"🧠 Parsing sections...")
        sections = []
        current = None
        text_lines = []

        for line in script.split('\n'):
            line = line.strip()
            m = re.match(r'\[(HOOK|SECTION_\d+|CTA)(?::\s*(.+?))?\]', line)
            if m:
                if current:
                    sections.append({
                        'marker': current['marker'], 'title': current['title'],
                        'text': '\n'.join(text_lines).strip(),
                        'is_short_candidate': current['marker'] != 'CTA'
                    })
                current = {'marker': m.group(1), 'title': m.group(2) or m.group(1)}
                text_lines = []
            elif line and not line.startswith('[VISUAL'):
                text_lines.append(line)

        if current and text_lines:
            sections.append({
                'marker': current['marker'], 'title': current['title'],
                'text': '\n'.join(text_lines).strip(),
                'is_short_candidate': current['marker'] != 'CTA'
            })

        if not sections:
            paragraphs = [p.strip() for p in script.split('\n\n') if p.strip()]
            if len(paragraphs) >= 4:
                sections = [
                    {'marker': 'HOOK', 'title': 'Hook', 'text': paragraphs[0], 'is_short_candidate': True},
                    {'marker': 'SECTION_1', 'title': 'Part 1', 'text': '\n'.join(paragraphs[1:3]), 'is_short_candidate': True},
                    {'marker': 'SECTION_2', 'title': 'Part 2', 'text': paragraphs[3] if len(paragraphs) > 3 else '', 'is_short_candidate': True},
                    {'marker': 'CTA', 'title': 'Ending', 'text': paragraphs[-1], 'is_short_candidate': False},
                ]
            else:
                sections = [{'marker': 'HOOK', 'title': 'Content', 'text': script, 'is_short_candidate': True}]

        logger.info(f"   ✅ {len(sections)} sections:")
        for s in sections:
            logger.info(f"      [{s['marker']}] {s['title'][:30]} — {len(s['text'].split())} words")
        return sections
