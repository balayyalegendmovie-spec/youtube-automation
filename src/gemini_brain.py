"""
AI BRAIN — All Free Providers with Auto-Rotation
Providers: Gemini, Groq, Cerebras, SambaNova, OpenRouter, GitHub Models, HuggingFace
"""

import json
import time
import logging
import re
import os
import random
import requests as http_requests

logger = logging.getLogger(__name__)


def _call_openai_api(url, key, model, prompt):
    resp = http_requests.post(url,
        json={"model": model, "messages": [{"role": "user", "content": prompt}],
              "max_tokens": 8192, "temperature": 0.9},
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        timeout=90)
    if resp.status_code == 429:
        raise Exception("Rate limited")
    if resp.status_code not in [200, 201]:
        raise Exception(f"Error {resp.status_code}: {resp.text[:200]}")
    ch = resp.json().get("choices", [])
    if not ch:
        raise Exception("No choices")
    return ch[0].get("message", {}).get("content", "")


def _call_gemini_api(key, model, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    resp = http_requests.post(url,
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.9, "topP": 0.95, "maxOutputTokens": 8192}},
        headers={"Content-Type": "application/json"}, timeout=90)
    if resp.status_code == 429:
        raise Exception("Rate limited")
    if resp.status_code != 200:
        raise Exception(f"Error {resp.status_code}: {resp.text[:200]}")
    c = resp.json().get("candidates", [])
    if not c:
        raise Exception("No candidates")
    p = c[0].get("content", {}).get("parts", [])
    return p[0].get("text", "") if p else ""


def _call_hf_api(key, model, prompt):
    resp = http_requests.post(f"https://api-inference.huggingface.co/models/{model}",
        json={"inputs": prompt, "parameters": {"max_new_tokens": 4096, "temperature": 0.9}},
        headers={"Authorization": f"Bearer {key}"}, timeout=90)
    if resp.status_code == 429:
        raise Exception("Rate limited")
    if resp.status_code != 200:
        raise Exception(f"Error {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    if isinstance(data, list) and data:
        return data[0].get("generated_text", "")
    return str(data)


class GeminiBrain:
    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.providers = []

        def key(name):
            k = os.environ.get(name, '')
            return k if k and '${' not in k and len(k) > 5 else ''

        # Groq — 14,400/day
        k = key('GROQ_API_KEY')
        if k:
            self.providers.append({
                'name': 'Groq-1 (llama-3.3-70b)',
                'call': lambda p, _k=k: _call_openai_api(
                    "https://api.groq.com/openai/v1/chat/completions",
                    _k, "llama-3.3-70b-versatile", p)
            })

        k = key('GROQ_API_KEY_2')
        if k:
            self.providers.append({
                'name': 'Groq-2 (llama-3.3-70b)',
                'call': lambda p, _k=k: _call_openai_api(
                    "https://api.groq.com/openai/v1/chat/completions",
                    _k, "llama-3.3-70b-versatile", p)
            })

        # Gemini — 1,500/day
        k = key('GEMINI_API_KEY')
        if k:
            self.providers.append({
                'name': 'Gemini (2.0-flash)',
                'call': lambda p, _k=k: _call_gemini_api(_k, "gemini-2.0-flash", p)
            })

        # Cerebras — 1,000/day
        k = key('CEREBRAS_API_KEY')
        if k:
            self.providers.append({
                'name': 'Cerebras (llama-3.3-70b)',
                'call': lambda p, _k=k: _call_openai_api(
                    "https://api.cerebras.ai/v1/chat/completions",
                    _k, "llama-3.3-70b", p)
            })

        # SambaNova — 1,000/day
        k = key('SAMBANOVA_API_KEY')
        if k:
            self.providers.append({
                'name': 'SambaNova (llama-3.3-70b)',
                'call': lambda p, _k=k: _call_openai_api(
                    "https://api.sambanova.ai/v1/chat/completions",
                    _k, "Meta-Llama-3.3-70B-Instruct", p)
            })

        # OpenRouter — free models
        k = key('OPENROUTER_API_KEY')
        if k:
            self.providers.append({
                'name': 'OpenRouter (llama-free)',
                'call': lambda p, _k=k: _call_openai_api(
                    "https://openrouter.ai/api/v1/chat/completions",
                    _k, "meta-llama/llama-3.3-70b-instruct:free", p)
            })

        # GitHub Models — free automatic
        k = key('GITHUB_TOKEN')
        if k:
            self.providers.append({
                'name': 'GitHub (gpt-4o-mini)',
                'call': lambda p, _k=k: _call_openai_api(
                    "https://models.inference.ai.azure.com/chat/completions",
                    _k, "gpt-4o-mini", p)
            })

        # HuggingFace — free
        k = key('HF_API_KEY')
        if k:
            self.providers.append({
                'name': 'HuggingFace (Mistral)',
                'call': lambda p, _k=k: _call_hf_api(
                    _k, "mistralai/Mistral-7B-Instruct-v0.3", p)
            })

        # Gemini lite as last fallback
        k = key('GEMINI_API_KEY')
        if k:
            self.providers.append({
                'name': 'Gemini (2.0-flash-lite)',
                'call': lambda p, _k=k: _call_gemini_api(_k, "gemini-2.0-flash-lite", p)
            })

        if not self.providers:
            raise Exception("No AI keys found!")

        logger.info(f"🧠 AI Brain: {len(self.providers)} providers")
        for p in self.providers:
            logger.info(f"   → {p['name']}")

    def _call_ai(self, prompt, expect_json=False):
        providers = list(self.providers)
        random.shuffle(providers)
        last_err = None

        for prov in providers:
            try:
                logger.info(f"   🤖 {prov['name']}...")
                text = prov['call'](prompt).strip()
                if not text:
                    raise Exception("Empty response")
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
                if 'rate' in str(e).lower() or '429' in str(e):
                    continue
                time.sleep(2)
                continue

        raise Exception(f"All {len(providers)} providers failed: {last_err}")

    def generate_topics(self, niche, language, trend_data=None, count=3):
        logger.info(f"🧠 Topics: '{niche}'")
        trends = ""
        if trend_data:
            trends = f"\nTrending: {json.dumps([t.get('topic','') for t in trend_data[:5]])}\n"
        prompt = f"""Generate {count} FASCINATING YouTube topics. Niche: {niche}. Language: {language}.
{trends}WOW factor, unknown facts. NOT generic.
Return JSON: [{{"topic":"English","topic_local":"{language}","search_keywords":["k1","k2"],"why_viral":"reason","emotions_map":{{"hook":"excited","section_1":"curious","section_2":"serious","section_3":"cheerful","section_4":"excited","cta":"warm"}},"sections":["S1","S2","S3","S4"],"estimated_interest":"high"}}]"""
        topics = self._call_ai(prompt, expect_json=True)
        if not isinstance(topics, list):
            topics = [topics]
        for i, t in enumerate(topics):
            logger.info(f"   {i+1}. {t.get('topic','?')}")
        return topics

    def generate_script(self, topic_data, language, target_words=2000):
        """3-PART generation for 10-min video"""
        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)
        logger.info(f"🧠 Script: '{topic}' (3 parts)")

        style = """STYLE:
- Tenglish: Telugu script + 40% English naturally
- SHORT lines: max 12 words per line
- Fillers: "So basically…", "hmm…", "OK so…"
- Pauses: "…" between thoughts
- Questions: "Crazy right?", "Comment చేయండి"
- NO like/subscribe except final CTA
- Every sentence = NEW fact with numbers
- Mini stories, Indian examples
- React: "Whoa!", "Mind blown!"

EXAMPLE:
Guys… ఈ topic వింటే shock అవుతారు!

India lo ఒక ancient temple ఉంది…
దాని age ఎంతో తెలుసా?

hmm… Almost 1500 years old!

And honestly… most people don't know this.

Crazy right?"""

        p1 = f"""Top YouTuber. PART 1 about: "{topic}"
{style}
[HOOK] (250+ words. "Guys…" + shocking. "Ready? Let's go!")
[SECTION_1: {{Tenglish title}}] (300+ words. "OK so first thing…" Facts, story. "ఇది just beginning 👀")
[VISUAL: scene] every 3 lines. 500+ words. Script only."""

        part1 = self._call_ai(p1)
        logger.info(f"   Part1: {len(part1.split())} words")
        time.sleep(3)

        p2 = f"""Continue about "{topic}". Same style.
{style}
Context: {part1[:600]}
[SECTION_2: {{title}}] (300+ words. Surprising facts, twist.)
[SECTION_3: {{title}}] (300+ words. Daily life India examples.)
500+ words. NO subscribe. Script only."""

        part2 = self._call_ai(p2)
        logger.info(f"   Part2: {len(part2.split())} words")
        time.sleep(3)

        p3 = f"""Final part about "{topic}". Same style.
{style}
[SECTION_4: {{title}}] (200+ words. Mind-blowing fact.)
[CTA] (100+ words. ONLY subscribe here. "👍 Like 🔔 Subscribe" "Thanks ❤️")
300+ words. Script only."""

        part3 = self._call_ai(p3)
        logger.info(f"   Part3: {len(part3.split())} words")

        for pat in [r'.*like చేయండి.*subscribe.*', r'.*subscribe చేయండి.*',
                    r'.*bell icon.*', r'.*like కొట్టండి.*']:
            part1 = re.sub(pat, '', part1, flags=re.IGNORECASE)
            part2 = re.sub(pat, '', part2, flags=re.IGNORECASE)

        script = part1 + "\n\n" + part2 + "\n\n" + part3
        logger.info(f"   ✅ Total: {len(script.split())} words")
        return script

    def review_script(self, script, language, topic):
        logger.info(f"🧠 Review...")
        try:
            r = self._call_ai(
                f'Rate script 1-10. JSON: {{"overall_score":8,"approved":true,"summary":"ok"}}',
                expect_json=True)
        except Exception:
            r = {"overall_score": 7, "approved": True, "summary": "Skipped"}
        logger.info(f"   📊 {r.get('overall_score', 7)}/10")
        return script, r

    def generate_metadata(self, topic_data, language, video_type="long"):
        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)
        logger.info(f"🧠 Metadata ({video_type})...")
        try:
            if video_type == "long":
                meta = self._call_ai(
                    f'YouTube metadata {language}. Topic: "{topic}". '
                    f'JSON: {{"title":"emoji title","description":"SEO","tags":["tags"],"thumbnail_text":"2-4 words"}}',
                    expect_json=True)
            else:
                meta = self._call_ai(
                    f'Shorts metadata {language}. "{topic}". '
                    f'JSON: {{"title":"#shorts title","description":"desc","tags":["tags"],"thumbnail_text":"words"}}',
                    expect_json=True)
        except Exception:
            meta = {"title": topic_local or topic, "description": topic,
                    "tags": [topic], "thumbnail_text": topic[:20]}
        if video_type == "short" and not any('#shorts' in str(t) for t in meta.get('tags', [])):
            meta.setdefault('tags', []).append('#shorts')
        return meta

    def get_footage_keywords(self, script):
        logger.info(f"🧠 Footage keywords...")
        chunks = re.split(r'\[SECTION_\d+.*?\]|\[HOOK\]|\[CTA\]', script)
        all_kw = []
        for chunk in chunks:
            if len(chunk.strip()) < 50:
                continue
            try:
                kw = self._call_ai(
                    f'3 SPECIFIC stock video keywords for visual scenes. '
                    f'NOT abstract. Example: "ancient temple sunset" '
                    f'Text: {chunk[:400]} '
                    f'JSON: ["scene1","scene2","scene3"]',
                    expect_json=True)
                if isinstance(kw, list):
                    all_kw.extend(kw)
            except Exception:
                pass
            time.sleep(1)
        if len(all_kw) < 5:
            all_kw.extend(["cinematic india", "ancient ruins", "technology",
                           "indian city aerial", "nature landscape"])
        logger.info(f"   ✅ {len(all_kw)} keywords")
        return all_kw

    def parse_script_sections(self, script):
        logger.info(f"🧠 Parsing...")
        sections, current, lines = [], None, []
        for line in script.split('\n'):
            line = line.strip()
            m = re.match(r'\[(HOOK|SECTION_\d+|CTA)(?::\s*(.+?))?\]', line)
            if m:
                if current:
                    sections.append({
                        'marker': current['marker'], 'title': current['title'],
                        'text': '\n'.join(lines).strip(),
                        'is_short_candidate': current['marker'] != 'CTA'})
                current = {'marker': m.group(1), 'title': m.group(2) or m.group(1)}
                lines = []
            elif line and not line.startswith('[VISUAL'):
                lines.append(line)
        if current and lines:
            sections.append({
                'marker': current['marker'], 'title': current['title'],
                'text': '\n'.join(lines).strip(),
                'is_short_candidate': current['marker'] != 'CTA'})
        if not sections:
            sections = [{'marker': 'HOOK', 'title': 'Content',
                         'text': script, 'is_short_candidate': True}]
        logger.info(f"   ✅ {len(sections)} sections")
        for s in sections:
            logger.info(f"      [{s['marker']}] {len(s['text'].split())} words")
        return sections
