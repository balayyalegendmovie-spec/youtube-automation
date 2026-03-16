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
            self.providers.append(GroqProvider(self.groq_key_2, "llama3-70b-8192"))

        if self.gemini_key:
            self.providers.append(GeminiProvider(self.gemini_key, "gemini-2.0-flash"))

        if self.groq_key:
            self.providers.append(GroqProvider(self.groq_key, "llama-3.3-70b-specdec"))

        if not self.providers:
            raise Exception("No AI API keys! Set GEMINI_API_KEY or GROQ_API_KEY")

        logger.info("🧠 AI Brain initialized with providers:")
        for p in self.providers:
            status = "READY" if p.available else "NO KEY"
            logger.info(f"   → {p.name}: {status}")

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
                logger.warning(f"   ⚠️ {provider.name} JSON parse error: {e}")
                last_error = e
                continue
            except Exception as e:
                error_str = str(e)
                logger.warning(f"   ⚠️ {provider.name} failed: {error_str[:100]}")
                last_error = e
                if '429' in error_str or 'rate' in error_str.lower() or 'quota' in error_str.lower():
                    logger.info(f"   ↪️ Switching to next provider...")
                    continue
                time.sleep(3)
                continue

        raise Exception(f"All AI providers failed. Last error: {last_error}")

    def generate_topics(self, niche, language, trend_data=None, count=3):
        logger.info(f"🧠 STEP: Generating topics for '{niche}' in {language}...")

        trend_context = ""
        if trend_data:
            trend_topics = [t.get('topic', '') for t in trend_data[:10]]
            trend_context = f"\nCurrently trending in India:\n{json.dumps(trend_topics[:5], indent=2)}\nTry to relate topics to these trends.\n"

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

    def generate_script(self, topic_data, language, target_words=1500):
        """Generate emotionally rich script — ENFORCES minimum length"""

        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)

        logger.info(f"🧠 STEP: Generating script for '{topic}'...")
        logger.info(f"   Language: {language}, Target: {target_words} words")

        lang_name = "తెలుగు" if language == "telugu" else "हिंदी"
        script_type = "Telugu" if language == "telugu" else "Devanagari"

        prompt = f"""You are a professional YouTube scriptwriter. Write a LONG, DETAILED video script.

TOPIC: "{topic}" / "{topic_local}"
LANGUAGE: {language} ({lang_name}) using {script_type} script

ABSOLUTE REQUIREMENT: Write MINIMUM 1200 words. Count carefully.
Each section MUST be 150-200 words minimum.
Short scripts will be rejected. Write MORE not less.

Write naturally like you're explaining to a friend. Mix English technical words.

STRUCTURE (use these EXACT markers):

[HOOK]
(Write 150+ words. Start with a shocking question or fact. Create intense curiosity.
Ask "మీకు తెలుసా?" or "क्या आपको पता है?" to hook the viewer.
Explain WHY this topic matters to them personally.
Tease what they'll learn. Make them NEED to keep watching.)

[SECTION_1: {{Interesting title in {language}}}]
(Write 200+ words. First main point explained in detail.
Give a specific real-world EXAMPLE from India.
Use numbers and statistics. Compare to something relatable.
End with curiosity for next section.)

[SECTION_2: {{Interesting title in {language}}}]
(Write 200+ words. Second point — go DEEPER.
Reveal something surprising or counter-intuitive.
Tell a mini-story or case study. Make it dramatic.
Include a "but here's the twist" moment.)

[SECTION_3: {{Interesting title in {language}}}]
(Write 200+ words. The HUMAN angle.
How does this affect normal people in India?
Give a relatable everyday example.
Connect to Indian culture, daily life, cities.)

[SECTION_4: {{Interesting title in {language}}}]
(Write 200+ words. THE CLIMAX — most mind-blowing revelation.
Save the absolute BEST fact or insight for here.
Build tension, then reveal. Make viewers say "WOW!")

[CTA]
(Write 100+ words. Summarize 3 key takeaways.
Warm call to subscribe. Tease next video topic.
End with a memorable one-liner.)

RULES:
- Add [VISUAL: description] tags (2-3 per section)
- Ask rhetorical questions every 3-4 sentences
- Include at least 8 specific numbers/facts
- Reference Indian context
- Total MUST be over 1200 words

Write ONLY the script."""

        script = self._call_ai(prompt)
        word_count = len(script.split())
        logger.info(f"   ✅ Script generated: {word_count} words")

        if word_count < 800:
            logger.info(f"   🔄 Script too short ({word_count} words), requesting expansion...")

            expand_prompt = f"""Expand this {language} script to 1200+ words. Add more details, examples, statistics, and engagement to each section. Keep [HOOK], [SECTION_1] etc markers.

SCRIPT:
{script[:3000]}

Write expanded version:"""

            try:
                expanded = self._call_ai(expand_prompt)
                expanded_count = len(expanded.split())
                if expanded_count > word_count:
                    script = expanded
                    logger.info(f"   ✅ Expanded to {expanded_count} words")
                else:
                    logger.info(f"   ⚠️ Expansion didn't help ({expanded_count} words)")
            except Exception as e:
                logger.warning(f"   ⚠️ Expansion failed: {e}")
                logger.info(f"   Using original {word_count}-word script")

        return script

    def review_script(self, script, language, topic):
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
            review = {
                "overall_score": 7, "approved": True,
                "scores": {}, "improvements": [],
                "summary": "Review skipped due to API error"
            }

        score = review.get('overall_score', 7)
        logger.info(f"   📊 Review score: {score}/10")

        final_script = script
        if review.get('revised_script') and score < 6:
            logger.info(f"   🔄 Using revised script")
            final_script = review['revised_script']

        return final_script, review

    def generate_metadata(self, topic_data, language, video_type="long"):
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
            metadata = {
                "title": topic_local or topic,
                "title_english": topic,
                "description": f"Video about {topic}",
                "tags": [topic, language, "facts", "shorts"],
                "thumbnail_text": (topic_local or topic)[:20]
            }

        if video_type == "short":
            tags = metadata.get('tags', [])
            if not any('#shorts' in str(t).lower() for t in tags):
                tags.append('#shorts')
            metadata['tags'] = tags

        logger.info(f"   ✅ Title: {metadata.get('title', 'N/A')[:50]}...")
        return metadata

    def get_footage_keywords(self, script):
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

    def parse_script_sections(self, script):
        logger.info(f"🧠 Parsing script sections...")

        sections = []
        current_section = None
        current_text = []

        for line in script.split('\n'):
            line = line.strip()
            section_match = re.match(
                r'\[(HOOK|SECTION_\d+|CTA)(?::\s*(.+?))?\]', line
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
                     'text': '\n'.join(paragraphs[3:5]) if len(paragraphs) > 4 else paragraphs[3],
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
