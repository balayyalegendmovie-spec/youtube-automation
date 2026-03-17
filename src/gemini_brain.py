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
                "temperature": 0.9,
                "topP": 0.95,
                "maxOutputTokens": 8192,
            }
        }
        response = http_requests.post(url, json=payload,
                                       headers={"Content-Type": "application/json"},
                                       timeout=90)
        if response.status_code == 429:
            raise Exception("Gemini rate limited (429)")
        if response.status_code != 200:
            raise Exception(f"Gemini API error {response.status_code}: {response.text[:300]}")
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise Exception("No candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise Exception("No parts")
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
            "temperature": 0.9,
            "max_tokens": 8192,
        }
        response = http_requests.post(url, json=payload,
                                       headers={"Content-Type": "application/json",
                                                "Authorization": f"Bearer {self.api_key}"},
                                       timeout=90)
        if response.status_code == 429:
            raise Exception("Groq rate limited (429)")
        if response.status_code != 200:
            raise Exception(f"Groq API error {response.status_code}: {response.text[:300]}")
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise Exception("No choices")
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
            self.providers.append(GroqProvider(self.groq_key_2, "qwen-qwq-32b"))
        if self.gemini_key:
            self.providers.append(GeminiProvider(self.gemini_key, "gemini-2.0-flash"))

        if not self.providers:
            raise Exception("No AI API keys!")

        logger.info("🧠 AI Brain initialized:")
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
                logger.info(f"   ✅ {provider.name} ({len(text)} chars)")
                if expect_json:
                    text = re.sub(r'```json\s*', '', text)
                    text = re.sub(r'```\s*', '', text)
                    text = text.strip()
                    m = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
                    if m:
                        text = m.group(0)
                    return json.loads(text)
                return text
            except json.JSONDecodeError as e:
                last_error = e
                continue
            except Exception as e:
                logger.warning(f"   ⚠️ {provider.name}: {str(e)[:80]}")
                last_error = e
                if '429' in str(e) or 'rate' in str(e).lower():
                    continue
                time.sleep(3)
                continue
        raise Exception(f"All providers failed: {last_error}")

    def generate_topics(self, niche, language, trend_data=None, count=3):
        logger.info(f"🧠 Generating topics: '{niche}' in {language}...")
        trends = ""
        if trend_data:
            tl = [t.get('topic', '') for t in trend_data[:5]]
            trends = f"\nTrending in India: {json.dumps(tl)}\nRelate to these.\n"

        prompt = f"""YouTube strategist for Indian audience (16-35).
Generate {count} FASCINATING video topics for niche: {niche}
Language: {language}
{trends}
Rules: click-worthy, 10-min explainer, splittable into shorts, NO politics/religion
Topics should be about REAL interesting facts, science, history, technology.
NOT generic boring topics. Each topic should make someone say "WOW I didn't know that!"

Return ONLY JSON array:
[{{"topic":"English title","topic_local":"{language} title","search_keywords":["k1","k2","k3"],"why_viral":"reason","emotions_map":{{"hook":"excited","section_1":"curious","section_2":"serious","section_3":"cheerful","section_4":"excited","cta":"warm"}},"sections":["S1","S2","S3","S4"],"estimated_interest":"high"}}]"""

        topics = self._call_ai(prompt, expect_json=True)
        if not isinstance(topics, list):
            topics = [topics]
        logger.info(f"   ✅ {len(topics)} topics")
        for i, t in enumerate(topics):
            logger.info(f"      {i+1}. {t.get('topic', 'N/A')}")
        return topics

    def generate_script(self, topic_data, language, target_words=2000):
        """Generate natural Tenglish/Hinglish YouTuber-style script"""
        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)

        logger.info(f"🧠 Generating script: '{topic}'...")
        logger.info(f"   Target: {target_words} words")

        if language == "telugu":
            style_example = """
HERE IS THE EXACT WRITING STYLE YOU MUST FOLLOW:

---
Guys… ఈ రోజు topic వింటే నిజంగా మీరు shock అవుతారు!

Mahabharat lo female warriors ఎంత important role play చేశారో మీకు తెలుసా?

మనమంతా Arjuna, Bhima, Karna గురించే వింటాం…
కానీ women warriors గురించి almost ఎవరూ మాట్లాడరు!

But trust me… వాళ్లు చాలా powerful!

So… ready ah? Let's start!

---
First thing…
Mahabharat అంటే మనకు ఒక పెద్ద war story అనిపిస్తుంది కదా?

But actually… women కూడా చాలా strong ga fight చేశారు.

Example కి Draupadi…
ఆమె just queen కాదు…
ఆమె mentally చాలా strong warrior!

ఇది just beginning మాత్రమే…
ఇంకా చాలా interesting things ఉన్నాయి… wait చేయండి 👀

---
ఇప్పుడు main point కి వస్తే…

వాళ్లు direct ga sword fight చేయకపోయినా…
Strategy, support, courage…
ఇవి అన్నీ వాళ్ల వల్లే strong అయ్యాయి.

Draupadi insult scene గుర్తుందా?
అది whole war కి reason అయింది.

అంటే indirectly…
ఆమె ఒక major turning point!
---

CRITICAL STYLE RULES FROM THIS EXAMPLE:
- SHORT lines (5-12 words per line MAX)
- One thought per line, then line break
- Telugu + English mixed naturally (40% English)
- Words like: "actually", "basically", "example కి", "trust me", "right?", "కదా?"
- Dramatic "…" pauses
- NO formal Telugu — write like a 22-year-old talking
- NO subscribe/like/share ANYWHERE except the final [CTA]
- Each fact should make viewer go "WOW I didn't know that!"
"""
            lang_style = "Tenglish (Telugu + English 40%)"
        else:
            style_example = """
STYLE: Short lines, Hinglish (Hindi+English 40%), YouTuber talking.
Example: "Guys… aaj ka topic sunke shock ho jaoge! AI India mein kitni fast grow ho rahi hai? Ready ho? Let's go!"
"""
            lang_style = "Hinglish (Hindi + English 40%)"

        prompt = f"""You are India's TOP educational YouTuber with 10M subscribers.
Your videos get millions of views because every fact is MIND-BLOWING.

TOPIC: "{topic}" / "{topic_local}"
LANGUAGE: {lang_style}

{style_example}

CONTENT RULES (VERY IMPORTANT):
1. Every sentence must contain a NEW fact, statistic, or insight
2. NO repeating the same information in different words
3. NO generic filler like "ఇది చాలా interesting" without saying WHY
4. Include SPECIFIC numbers: dates, percentages, measurements
5. Tell SHORT real stories (2-3 lines each) about real people/events
6. Every section should have 3-4 UNIQUE facts the viewer probably doesn't know
7. Research-level depth — not surface-level Wikipedia summary
8. After each fact, explain WHY it matters or HOW it connects

FORMAT RULES:
1. SHORT lines — max 12 words per line
2. One thought → line break → next thought
3. Mix English 40% naturally
4. Use "…" for dramatic pauses between reveals
5. Ask viewer a question every 5-6 lines
6. NO like/subscribe/share ANYWHERE except final [CTA]
7. NO repeating phrases like "మీరు ఆశ్చర్యపోతారు" — say it ONCE max

STRUCTURE:

[HOOK]
(250+ words. 
Line 1: "Guys…" + shocking statement about the topic
Line 2-3: Ask an impossible-sounding question
Line 4-5: Give a preview fact that sounds unbelievable  
Line 6-7: Promise what they'll learn
Line 8: "Ready ah? Let's go!")

[SECTION_1: {{Short catchy Tenglish title}}]
(300+ words. "First thing…"
- 3-4 UNIQUE facts with specific numbers
- One mini story (real person/event, 3-4 lines)
- Indian context example
- End: "ఇది just beginning… next part ఇంకా crazy 👀")

[SECTION_2: {{Short catchy Tenglish title}}]  
(300+ words. "ఇప్పుడు real interesting part…"
- The SURPRISING angle nobody talks about
- Counter-intuitive fact that breaks assumptions
- "మీరు believe చేయరు కానీ…" moment
- Compare two things dramatically)

[SECTION_3: {{Short catchy Tenglish title}}]
(300+ words. "Real life connection…"
- How this connects to THEIR daily life in India
- Practical examples: phone, food, city, job
- "మీ phone లో ఇది already ఉంది… తెలుసా?"
- Make it PERSONAL to the viewer)

[SECTION_4: {{Short catchy Tenglish title}}]
(200+ words. "ఇప్పుడు biggest revelation…"
- Save the MOST mind-blowing fact for here
- Build tension: "Ready for this?… 3… 2… 1…"
- Drop the bomb fact
- Quick reaction: "Crazy right?!")

[CTA]
(100+ words. ONLY place for like/subscribe.
"So guys… ఈ video నుండి main takeaways…"
- 3 bullet point facts they learned
- "👍 Like చేయండి 🔔 Subscribe చేయండి"
- "Comment లో చెప్పండి — [specific question about topic]"
- "Next video ఇంకా mind-blowing… stay tuned!"
- "Thanks for watching ❤️")

Add [VISUAL: specific description] every 3-4 lines.
MINIMUM 1500 WORDS. Every sentence = NEW information.
Write ONLY the script. No explanations."""

        script = self._call_ai(prompt)
        word_count = len(script.split())
        logger.info(f"   ✅ Script: {word_count} words")

        if word_count < 800:
            logger.info(f"   🔄 Generating Part 2...")
            try:
                p2_prompt = f"""Continue this {lang_style} YouTube script.
Write 800+ MORE words in EXACT same style.
Short lines, Tenglish, YouTuber talking, NEW facts only.
NO subscribe/like mentions. NO repeating earlier facts.
Use markers [SECTION_3], [SECTION_4] if not already present.

EXISTING SCRIPT:
{script[:2500]}

CONTINUE with NEW content (800+ words):"""

                p2 = self._call_ai(p2_prompt)
                if len(p2.split()) > 200:
                    # Remove any duplicate CTA from part 2
                    p2 = re.sub(r'\[CTA\].*$', '', p2, flags=re.DOTALL).strip()
                    script = script + "\n\n" + p2
                    logger.info(f"   ✅ Combined: {len(script.split())} words")
            except Exception as e:
                logger.warning(f"   ⚠️ Part 2 failed: {e}")

        # Clean up: remove any mid-script like/subscribe mentions
        lines_to_remove = [
            r'.*like చేయండి.*subscribe చేయండి.*',
            r'.*like కొట్టండి.*subscribe.*',
            r'.*bell icon.*press.*',
            r'.*channel.*subscribe.*',
            r'.*share చేయండి.*',
        ]
        
        script_lines = script.split('\n')
        cleaned_lines = []
        in_cta = False
        
        for line in script_lines:
            if '[CTA]' in line:
                in_cta = True
            
            if not in_cta:
                skip = False
                for pattern in lines_to_remove:
                    if re.match(pattern, line, re.IGNORECASE):
                        skip = True
                        break
                if not skip:
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        
        script = '\n'.join(cleaned_lines)

        return script

    def review_script(self, script, language, topic):
        logger.info(f"🧠 Reviewing script...")
        prompt = f"""Review this {language} YouTube script about "{topic}".
SCRIPT: {script[:3000]}
Return JSON: {{"overall_score":8,"approved":true,"scores":{{"hook":8,"facts":9}},"improvements":["tip"],"summary":"brief"}}"""
        try:
            review = self._call_ai(prompt, expect_json=True)
        except Exception:
            review = {"overall_score": 7, "approved": True, "summary": "Skipped"}
        logger.info(f"   📊 Score: {review.get('overall_score', 7)}/10")
        return script, review

    def generate_metadata(self, topic_data, language, video_type="long"):
        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)
        logger.info(f"🧠 Generating {video_type} metadata...")

        if video_type == "long":
            prompt = f"""YouTube metadata in {language}. Topic: "{topic}"/"{topic_local}".
Return JSON: {{"title":"{language} title with emoji 50-70 chars","title_english":"English","description":"SEO description","tags":["15-20 tags"],"thumbnail_text":"2-4 bold words"}}"""
        else:
            prompt = f"""YouTube Shorts metadata in {language}. Topic: "{topic}".
Return JSON: {{"title":"catchy {language} title #shorts","description":"brief+hashtags","tags":["10 tags"],"thumbnail_text":"1-3 words"}}"""

        try:
            meta = self._call_ai(prompt, expect_json=True)
        except Exception:
            meta = {"title": topic_local or topic, "description": f"About {topic}",
                   "tags": [topic, language], "thumbnail_text": (topic_local or topic)[:20]}

        if video_type == "short":
            tags = meta.get('tags', [])
            if not any('#shorts' in str(t).lower() for t in tags):
                tags.append('#shorts')
            meta['tags'] = tags

        logger.info(f"   ✅ Title: {meta.get('title', 'N/A')[:50]}...")
        return meta

    def get_footage_keywords(self, script):
        logger.info(f"🧠 Extracting keywords...")
        prompt = f"""Extract 15 SPECIFIC English keywords for HD stock footage.
Script: {script[:2000]}
Return JSON array: ["keyword1", "keyword2"]
Keywords should be VISUAL scenes, not abstract concepts.
Example: "ancient temple ruins", "woman warrior sword", "indian marketplace busy"
NOT: "history", "culture", "importance" """

        try:
            kw = self._call_ai(prompt, expect_json=True)
            if not isinstance(kw, list):
                kw = ["technology", "science", "space", "nature"]
        except Exception:
            kw = ["technology", "science", "space", "nature", "abstract",
                  "computer", "earth", "stars", "ocean", "city",
                  "data visualization", "laboratory", "innovation",
                  "futuristic", "education"]
        logger.info(f"   ✅ {len(kw)} keywords")
        return kw

    def parse_script_sections(self, script):
        logger.info(f"🧠 Parsing sections...")
        sections = []
        current = None
        lines = []

        for line in script.split('\n'):
            line = line.strip()
            m = re.match(r'\[(HOOK|SECTION_\d+|CTA)(?::\s*(.+?))?\]', line)
            if m:
                if current:
                    sections.append({
                        'marker': current['marker'],
                        'title': current['title'],
                        'text': '\n'.join(lines).strip(),
                        'is_short_candidate': current['marker'] != 'CTA'
                    })
                current = {'marker': m.group(1), 'title': m.group(2) or m.group(1)}
                lines = []
            elif line and not line.startswith('[VISUAL'):
                lines.append(line)

        if current and lines:
            sections.append({
                'marker': current['marker'],
                'title': current['title'],
                'text': '\n'.join(lines).strip(),
                'is_short_candidate': current['marker'] != 'CTA'
            })

        if not sections:
            paras = [p.strip() for p in script.split('\n\n') if p.strip()]
            if len(paras) >= 4:
                sections = [
                    {'marker': 'HOOK', 'title': 'Hook', 'text': paras[0], 'is_short_candidate': True},
                    {'marker': 'SECTION_1', 'title': 'Part 1', 'text': '\n'.join(paras[1:3]), 'is_short_candidate': True},
                    {'marker': 'SECTION_2', 'title': 'Part 2', 'text': paras[3] if len(paras) > 3 else '', 'is_short_candidate': True},
                    {'marker': 'CTA', 'title': 'End', 'text': paras[-1], 'is_short_candidate': False},
                ]
            else:
                sections = [{'marker': 'HOOK', 'title': 'Content', 'text': script, 'is_short_candidate': True}]

        logger.info(f"   ✅ {len(sections)} sections:")
        for s in sections:
            logger.info(f"      [{s['marker']}] {s['title'][:30]} — {len(s['text'].split())} words")
        return sections
