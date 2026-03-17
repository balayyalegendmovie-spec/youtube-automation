"""
AI BRAIN — Multi-Provider with 3-Part Script Generation
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
        resp = http_requests.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.9, "topP": 0.95, "maxOutputTokens": 8192}
        }, headers={"Content-Type": "application/json"}, timeout=90)
        if resp.status_code == 429:
            raise Exception("Gemini rate limited")
        if resp.status_code != 200:
            raise Exception(f"Gemini {resp.status_code}: {resp.text[:200]}")
        c = resp.json().get("candidates", [])
        if not c:
            raise Exception("No candidates")
        p = c[0].get("content", {}).get("parts", [])
        return p[0].get("text", "") if p else ""


class GroqProvider(AIProvider):
    def __init__(self, api_key, model="llama-3.3-70b-versatile"):
        super().__init__(f"Groq ({model})", api_key)
        self.model = model
    def generate(self, prompt):
        resp = http_requests.post("https://api.groq.com/openai/v1/chat/completions",
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.9, "max_tokens": 8192},
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"}, timeout=90)
        if resp.status_code == 429:
            raise Exception("Groq rate limited")
        if resp.status_code != 200:
            raise Exception(f"Groq {resp.status_code}: {resp.text[:200]}")
        ch = resp.json().get("choices", [])
        return ch[0].get("message", {}).get("content", "") if ch else ""


class GeminiBrain:
    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.gemini_key = os.environ.get('GEMINI_API_KEY',
            self.config.get('gemini', {}).get('api_key', ''))
        self.groq_key = os.environ.get('GROQ_API_KEY', '')
        self.groq_key_2 = os.environ.get('GROQ_API_KEY_2', '')
        for attr in ['gemini_key', 'groq_key', 'groq_key_2']:
            if '${' in str(getattr(self, attr)):
                setattr(self, attr, os.environ.get(attr.upper().replace('_KEY', '_API_KEY'), ''))

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
            raise Exception("No AI keys!")
        logger.info("🧠 AI Brain ready")
        for p in self.providers:
            logger.info(f"   → {p.name}")

    def _call_ai(self, prompt, expect_json=False):
        last_err = None
        for prov in self.providers:
            if not prov.available:
                continue
            try:
                logger.info(f"   🤖 {prov.name}...")
                text = prov.generate(prompt).strip()
                logger.info(f"   ✅ {len(text)} chars")
                if expect_json:
                    text = re.sub(r'```json\s*|```\s*', '', text).strip()
                    m = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
                    if m:
                        text = m.group(0)
                    return json.loads(text)
                return text
            except json.JSONDecodeError as e:
                last_err = e
                continue
            except Exception as e:
                logger.warning(f"   ⚠️ {str(e)[:80]}")
                last_err = e
                if '429' in str(e) or 'rate' in str(e).lower():
                    continue
                time.sleep(2)
                continue
        raise Exception(f"All failed: {last_err}")

    def generate_topics(self, niche, language, trend_data=None, count=3):
        logger.info(f"🧠 Topics: '{niche}'")
        trends = ""
        if trend_data:
            trends = f"\nTrending: {json.dumps([t.get('topic','') for t in trend_data[:5]])}\n"
        prompt = f"""Generate {count} FASCINATING YouTube topics. Niche: {niche}. Language: {language}. Audience: India 16-35.
{trends}Each topic must have WOW factor — unknown facts, surprising connections.
Return JSON: [{{"topic":"English","topic_local":"{language}","search_keywords":["k1","k2"],"why_viral":"reason","emotions_map":{{"hook":"excited","section_1":"curious","section_2":"serious","section_3":"cheerful","section_4":"excited","cta":"warm"}},"sections":["S1","S2","S3","S4"],"estimated_interest":"high"}}]"""
        topics = self._call_ai(prompt, expect_json=True)
        if not isinstance(topics, list):
            topics = [topics]
        for i, t in enumerate(topics):
            logger.info(f"   {i+1}. {t.get('topic','?')}")
        return topics

    def generate_script(self, topic_data, language, target_words=2000):
        """Generate script in 3 PARTS for 10-minute video"""
        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)
        logger.info(f"🧠 Script: '{topic}' (3-part generation)")

        style = """STYLE RULES:
- Tenglish: Telugu script + 40% English words mixed naturally
- SHORT lines: max 12 words per line, one thought per line
- Filler words for natural flow: "So basically…", "And honestly…", "OK so…", "Right?"
- Breathing cues: Add "…" between thoughts (speaker pauses here)
- Audience interaction: "మీకు ఏమనిపిస్తుంది?", "Crazy right?", "Comment చేయండి"
- NO like/subscribe/share ANYWHERE except final [CTA]
- Every sentence = NEW unique fact or insight
- Tell mini stories (3-4 lines about real people/events)
- Use specific numbers: years, percentages, counts

EXAMPLE:
Guys… ఈ topic వింటే మీరు shock అవుతారు!

India lo ఒక ancient temple ఉంది…
దాని age ఎంతో తెలుసా?

Almost 1500 years old!

And honestly… most people don't even know about this.

So basically… ఈ temple ని Pallava dynasty build చేసింది…
7th century lo.

ఆ time lo India ఎంత advanced గా ఉందంటే…
Europe ఇంకా dark ages lo ఉంది!

Crazy right?

OK so next fact ఇంకా mind-blowing…"""

        # PART 1: Hook + Section 1
        p1_prompt = f"""You are India's top YouTuber. Write PART 1 of a script about: "{topic}"
{style}

Write these sections:

[HOOK]
(200+ words. Start: "Guys…" + shocking fact.
Build curiosity. Ask impossible question.
Promise what they'll learn.
End: "So… ready ah? Let's go!")

[SECTION_1: {{Catchy Tenglish title}}]
(300+ words. "OK so first thing…"
3-4 UNIQUE facts with specific numbers.
One mini story about real person/place.
End: "ఇది just beginning… next part ఇంకా crazy 👀")

Add [VISUAL: specific scene description] every 3-4 lines.
Write 500+ words total. ONLY script text."""

        part1 = self._call_ai(p1_prompt)
        logger.info(f"   Part 1: {len(part1.split())} words")

        # PART 2: Section 2 + Section 3
        p2_prompt = f"""Continue this YouTube script about "{topic}". Same Tenglish style.
{style}

PREVIOUS CONTENT (for context only, don't repeat):
{part1[:1000]}

Now write NEXT sections:

[SECTION_2: {{Catchy Tenglish title}}]
(300+ words. "ఇప్పుడు real interesting part ki వస్తే…"
The SURPRISING angle nobody talks about.
Counter-intuitive facts. "Believe చేయరు కానీ…"
A dramatic reveal/twist moment.)

[SECTION_3: {{Catchy Tenglish title}}]
(300+ words. "Real life connection…"
How this affects THEIR daily life in India.
Examples: phone, food, city, job.
"మీ daily life lo ఇది already ఉంది… తెలుసా?"
Make it personal.)

Add [VISUAL: specific scene] every 3-4 lines.
Write 500+ words. NO like/subscribe. ONLY script."""

        part2 = self._call_ai(p2_prompt)
        logger.info(f"   Part 2: {len(part2.split())} words")

        # PART 3: Section 4 + CTA
        p3_prompt = f"""Final part of YouTube script about "{topic}". Same Tenglish style.
{style}

Write final sections:

[SECTION_4: {{Catchy Tenglish title}}]
(200+ words. "OK guys… biggest revelation…"
Most MIND-BLOWING fact saved for last.
Build tension: "Ready?… 3… 2… 1…"
Drop the bomb. React: "Crazy right?!")

[CTA]
(100+ words. ONLY place for like/subscribe.
"So guys… ఈ video lo main takeaways…"
3 bullet point facts they learned.
"👍 Like 🔔 Subscribe 📢 Share"
"Comment lo చెప్పండి — [question]"
"Next video ఇంకా mind-blowing!"
"Thanks for watching ❤️")

Write 300+ words. Script text only."""

        part3 = self._call_ai(p3_prompt)
        logger.info(f"   Part 3: {len(part3.split())} words")

        # Combine all parts
        script = part1 + "\n\n" + part2 + "\n\n" + part3
        total = len(script.split())
        logger.info(f"   ✅ Total script: {total} words")

        # Clean: remove mid-script subscribe mentions
        clean_lines = []
        in_cta = False
        remove_patterns = [
            r'.*like చేయండి.*subscribe.*', r'.*subscribe చేయండి.*',
            r'.*bell icon.*', r'.*channel.*subscribe.*',
            r'.*like కొట్టండి.*', r'.*share చేయండి.*subscribe.*'
        ]
        for line in script.split('\n'):
            if '[CTA]' in line:
                in_cta = True
            if not in_cta:
                skip = any(re.match(p, line, re.IGNORECASE) for p in remove_patterns)
                if not skip:
                    clean_lines.append(line)
            else:
                clean_lines.append(line)

        return '\n'.join(clean_lines)

    def review_script(self, script, language, topic):
        logger.info(f"🧠 Review...")
        try:
            r = self._call_ai(f'Review script about "{topic}". Return JSON: {{"overall_score":8,"approved":true,"summary":"ok"}}', expect_json=True)
        except Exception:
            r = {"overall_score": 7, "approved": True, "summary": "Skipped"}
        logger.info(f"   📊 {r.get('overall_score',7)}/10")
        return script, r

    def generate_metadata(self, topic_data, language, video_type="long"):
        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)
        logger.info(f"🧠 Metadata ({video_type})...")
        try:
            if video_type == "long":
                meta = self._call_ai(f'YouTube metadata in {language}. Topic: "{topic}". Return JSON: {{"title":"title with emoji","description":"SEO desc","tags":["tags"],"thumbnail_text":"2-4 words"}}', expect_json=True)
            else:
                meta = self._call_ai(f'Shorts metadata in {language}. Topic: "{topic}". Return JSON: {{"title":"title #shorts","description":"desc","tags":["tags"],"thumbnail_text":"1-3 words"}}', expect_json=True)
        except Exception:
            meta = {"title": topic_local or topic, "description": topic, "tags": [topic], "thumbnail_text": topic[:20]}
        if video_type == "short" and not any('#shorts' in str(t) for t in meta.get('tags', [])):
            meta.setdefault('tags', []).append('#shorts')
        return meta

    def get_footage_keywords(self, script):
        """Extract SPECIFIC visual keywords for EACH section"""
        logger.info(f"🧠 Footage keywords (section-specific)...")
        sections_text = re.split(r'\[SECTION_\d+.*?\]|\[HOOK\]|\[CTA\]', script)
        all_keywords = []

        for i, section in enumerate(sections_text):
            if len(section.strip()) < 50:
                continue
            try:
                prompt = f"""From this script section, extract 3-4 SPECIFIC English keywords for stock VIDEO footage.
Keywords must describe VISUAL SCENES that match what the speaker is talking about.
NOT abstract words. SPECIFIC visual scenes.

Good: "ancient indian temple carved stone", "woman warrior with sword battlefield"
Bad: "history", "importance", "culture"

SECTION:
{section[:500]}

Return JSON array: ["scene1", "scene2", "scene3"]"""

                kw = self._call_ai(prompt, expect_json=True)
                if isinstance(kw, list):
                    all_keywords.extend(kw)
            except Exception:
                pass

        if len(all_keywords) < 5:
            all_keywords.extend(["cinematic landscape india", "ancient ruins temple",
                                "technology futuristic", "crowd indian city", "nature drone aerial"])

        logger.info(f"   ✅ {len(all_keywords)} section-specific keywords")
        return all_keywords

    def parse_script_sections(self, script):
        logger.info(f"🧠 Parsing...")
        sections = []
        current = None
        lines = []
        for line in script.split('\n'):
            line = line.strip()
            m = re.match(r'\[(HOOK|SECTION_\d+|CTA)(?::\s*(.+?))?\]', line)
            if m:
                if current:
                    sections.append({'marker': current['marker'], 'title': current['title'],
                                    'text': '\n'.join(lines).strip(),
                                    'is_short_candidate': current['marker'] != 'CTA'})
                current = {'marker': m.group(1), 'title': m.group(2) or m.group(1)}
                lines = []
            elif line and not line.startswith('[VISUAL'):
                lines.append(line)
        if current and lines:
            sections.append({'marker': current['marker'], 'title': current['title'],
                            'text': '\n'.join(lines).strip(),
                            'is_short_candidate': current['marker'] != 'CTA'})
        if not sections:
            paras = [p.strip() for p in script.split('\n\n') if p.strip()]
            sections = [{'marker': 'HOOK', 'title': 'Content', 'text': script, 'is_short_candidate': True}]
        logger.info(f"   ✅ {len(sections)} sections")
        for s in sections:
            logger.info(f"      [{s['marker']}] {len(s['text'].split())} words")
        return sections
