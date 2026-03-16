"""
GEMINI BRAIN — AI Engine for All Content Decisions

Handles:
- Topic generation (trend-aware)
- Script writing (Telugu/Hindi with emotions)
- Script review (replaces human QA)
- Animation scene descriptions
- Metadata generation
- Footage keyword extraction

Uses Gemini 2.0 Flash (FREE tier: 15 RPM, 1500 RPD)
"""

import google.generativeai as genai
import json
import time
import logging
import re
import os

logger = logging.getLogger(__name__)


class GeminiBrain:
    
    def __init__(self, config_path="config/config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Get API key from env or config
        api_key = os.environ.get('GEMINI_API_KEY', 
                                  self.config['gemini']['api_key'])
        api_key = api_key.replace('${GEMINI_API_KEY}', 
                                   os.environ.get('GEMINI_API_KEY', ''))
        
        genai.configure(api_key=api_key)
        
        self.model = genai.GenerativeModel(
            model_name=self.config['gemini']['model'],
            generation_config={
                "temperature": self.config['gemini']['temperature'],
                "top_p": 0.95,
                "max_output_tokens": self.config['gemini']['max_output_tokens'],
            }
        )
        
        self.max_retries = self.config['gemini']['max_retries']
        self.retry_delay = self.config['gemini'].get('retry_delay', 10)
        
        logger.info("🧠 Gemini Brain initialized")
        logger.info(f"   Model: {self.config['gemini']['model']}")
    

    def _call_gemini(self, prompt, expect_json=False):
        """Call Gemini API with retry logic and detailed logging"""
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"   🤖 Calling Gemini (attempt {attempt+1}/{self.max_retries})...")
                
                response = self.model.generate_content(prompt)
                text = response.text.strip()
                
                if expect_json:
                    text = re.sub(r'```json\s*', '', text)
                    text = re.sub(r'```\s*', '', text)
                    text = text.strip()
                    
                    # Try to find JSON in the response
                    json_match = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
                    if json_match:
                        text = json_match.group(0)
                    
                    return json.loads(text)
                
                return text
                
            except json.JSONDecodeError as e:
                logger.warning(f"   ⚠️ JSON parse error: {e}")
                logger.warning(f"   Raw response: {text[:200]}...")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise
                    
            except Exception as e:
                logger.warning(f"   ⚠️ Gemini attempt {attempt+1} failed: {e}")
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (attempt + 1)
                    logger.info(f"   ⏳ Waiting {wait}s before retry...")
                    time.sleep(wait)
                else:
                    raise Exception(f"Gemini failed after {self.max_retries} attempts: {e}")


    # =============================================
    # TOPIC GENERATION
    # =============================================
    
    def generate_topics(self, niche, language, trend_data=None, count=3):
        """Generate video topics enhanced with trend data"""
        
        logger.info(f"🧠 STEP: Generating topics for '{niche}' in {language}...")
        
        trend_context = ""
        if trend_data:
            trend_topics = [t.get('topic', '') for t in trend_data[:10]]
            trend_context = f"""
Currently trending topics in India:
{json.dumps(trend_topics, indent=2)}

Try to relate your video topics to these trends where possible.
"""
        
        lang_name = "తెలుగు" if language == "telugu" else "हिंदी"
        
        prompt = f"""You are a top YouTube content strategist for Indian audience.

TASK: Generate {count} viral video topic ideas.

NICHE: {niche}
LANGUAGE: {language} ({lang_name})
TARGET AUDIENCE: Indian viewers ages 16-35

{trend_context}

REQUIREMENTS:
- Each topic must be fascinating and click-worthy
- Must work as a 10-minute explainer video
- Must be splittable into 4-5 standalone shorts (30-60 sec each)
- Include emotional hooks (surprise, curiosity, fear, excitement)
- Avoid politics, religion, controversial topics
- Consider what's searchable on YouTube India

EMOTIONAL MAPPING (important for anime-style video):
For each topic, identify which emotions should be present:
- Hook: excitement/curiosity
- Body sections: mix of serious/cheerful/curious
- Climax: surprise/excitement
- CTA: warmth/cheerful

Return ONLY valid JSON array:
[
    {{
        "topic": "Topic in English",
        "topic_local": "Topic in {language} script",
        "search_keywords": ["keyword1", "keyword2", "keyword3"],
        "why_viral": "Why this topic will get views",
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

        topics = self._call_gemini(prompt, expect_json=True)
        
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
        """Generate emotionally rich script with section markers"""
        
        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)
        emotions_map = topic_data.get('emotions_map', {})
        
        logger.info(f"🧠 STEP: Generating script for '{topic}'...")
        logger.info(f"   Language: {language}")
        logger.info(f"   Target: {target_words} words (~10 minutes)")
        
        lang_name = "తెలుగు" if language == "telugu" else "हिंदी"
        script_type = "Telugu" if language == "telugu" else "Devanagari"
        
        emotion_instructions = ""
        if emotions_map:
            emotion_instructions = f"""
EMOTION GUIDE (the voice actor will use these emotions):
- Hook: {emotions_map.get('hook', 'excited')} — Start with HIGH energy
- Section 1: {emotions_map.get('section_1', 'curious')} — Build curiosity
- Section 2: {emotions_map.get('section_2', 'serious')} — Get serious/deep
- Section 3: {emotions_map.get('section_3', 'cheerful')} — Lighten the mood
- Section 4: {emotions_map.get('section_4', 'excited')} — CLIMAX — most exciting part
- CTA: {emotions_map.get('cta', 'warm')} — Warm and inviting
"""

        prompt = f"""Write a complete YouTube video script in {language} ({lang_name}).

TOPIC: "{topic}" / "{topic_local}"

{emotion_instructions}

CRITICAL REQUIREMENTS:

1. LANGUAGE:
   - Write ENTIRELY in {language} using {script_type} script
   - Natural conversational style (like talking to a friend)
   - Mix common English tech terms naturally
   - A 15-year-old should understand everything
   - Use rhetorical questions to keep engagement

2. LENGTH: {target_words} words (approximately 10 minutes spoken)

3. STRUCTURE — EXACTLY this format with markers:

[HOOK]
(30-45 seconds — MOST IMPORTANT)
- Start with a SHOCKING fact or mind-blowing question
- Create irresistible curiosity in first 5 seconds
- Tell viewer what they'll learn
- Use phrases like "మీకు తెలుసా?" / "क्या आपको पता है?"
- THIS section determines if viewer stays or leaves

[SECTION_1: {{Title in {language}}}]
(90-120 seconds)
- First main point with real-world examples
- Reference something Indian audience relates to
- End with a mini-cliffhanger for next section
- Must work as STANDALONE 30-60 sec short

[SECTION_2: {{Title in {language}}}]
(90-120 seconds)
- Second main point — go deeper
- Include a surprising twist or counter-intuitive fact
- Use comparison ("this is bigger than..." / "imagine if...")
- Must work as STANDALONE short

[SECTION_3: {{Title in {language}}}]
(90-120 seconds)
- Third point — the human/emotional angle
- How does this affect regular people in India?
- Make it personal and relatable
- Must work as STANDALONE short

[SECTION_4: {{Title in {language}}}]
(90-120 seconds)
- THE CLIMAX — most mind-blowing fact/revelation
- Save the BEST for this section
- This is the "wow" moment
- Must work as STANDALONE short (this one goes viral)

[CTA]
(30-45 seconds)
- Quick summary (3 bullet points)
- Warm call to subscribe
- Tease next video topic
- End with memorable one-liner

4. VISUAL CUES — Add [VISUAL: description] tags:
   Example: [VISUAL: satellite orbiting earth with glowing trail]
   These help our animator create matching visuals.
   Add 2-3 visual cues per section.

5. ENGAGEMENT TECHNIQUES:
   - Ask questions every 2-3 sentences
   - Use "but wait..." / "here's the crazy part..." style reveals
   - Include at least 3 specific numbers/statistics
   - Reference popular Indian context (cricket, Bollywood, cities, food)

Return ONLY the script text. No explanations before or after."""

        script = self._call_gemini(prompt)
        
        word_count = len(script.split())
        logger.info(f"   ✅ Script generated: {word_count} words")
        logger.info(f"   📊 Target was {target_words}, got {word_count} "
                    f"({'✅ Good' if abs(word_count - target_words) < 300 else '⚠️ Needs adjustment'})")
        
        return script


    # =============================================
    # SCRIPT REVIEW (Replaces Human)
    # =============================================
    
    def review_script(self, script, language, topic):
        """AI reviews and improves the script — zero human needed"""
        
        logger.info(f"🧠 STEP: AI reviewing script quality...")
        
        prompt = f"""You are a senior YouTube content editor with 10 years experience
reviewing {language} educational content for Indian audience.

SCRIPT TO REVIEW:
---
{script}
---

TOPIC: {topic}

REVIEW CHECKLIST — Score each 1-10:

1. HOOK QUALITY (most important):
   - Does it grab attention in first 5 seconds?
   - Is there a clear curiosity gap?
   - Would YOU stop scrolling for this?

2. FACTUAL ACCURACY:
   - Are all facts, dates, numbers correct?
   - Any misleading or false claims?
   - Anything that could get the channel flagged?

3. ENGAGEMENT FLOW:
   - Does each section maintain interest?
   - Are there enough questions and reveals?
   - Would viewer watch till the end?

4. LANGUAGE QUALITY:
   - Is the {language} natural and conversational?
   - Any grammatical errors?
   - Is technical jargon explained simply?

5. STANDALONE SECTIONS:
   - Does each section work as a 30-60 sec short?
   - Does each have its own mini-hook?

6. EMOTIONAL VARIETY:
   - Are different emotions present throughout?
   - Is there excitement, curiosity, surprise?
   - Does the climax (Section 4) deliver?

7. SAFETY:
   - Any offensive content?
   - Any copyright issues?
   - Anything YouTube would flag?

RESPOND IN JSON:
{{
    "overall_score": 8,
    "approved": true,
    "scores": {{
        "hook": 8,
        "facts": 9,
        "engagement": 7,
        "language": 8,
        "sections": 7,
        "emotions": 8,
        "safety": 10
    }},
    "factual_issues": [],
    "improvements": ["improvement 1", "improvement 2"],
    "revised_hook": "Better hook if score < 7, otherwise null",
    "revised_script": null,
    "summary": "Brief review summary"
}}

If overall_score < 7, provide revised_script with fixes.
If only hook needs work, provide just revised_hook."""

        review = self._call_gemini(prompt, expect_json=True)
        
        score = review.get('overall_score', 0)
        approved = review.get('approved', False)
        
        logger.info(f"   📊 Review Results:")
        logger.info(f"      Overall: {score}/10 {'✅ Approved' if approved else '❌ Needs revision'}")
        
        scores = review.get('scores', {})
        for metric, val in scores.items():
            emoji = '✅' if val >= 7 else '⚠️' if val >= 5 else '❌'
            logger.info(f"      {emoji} {metric}: {val}/10")
        
        if review.get('improvements'):
            logger.info(f"   📝 Suggested improvements:")
            for imp in review['improvements'][:3]:
                logger.info(f"      → {imp}")
        
        # Apply fixes if needed
        final_script = script
        
        if not approved or score < 6:
            if review.get('revised_script'):
                logger.info(f"   🔄 Using AI-revised script")
                final_script = review['revised_script']
            else:
                logger.info(f"   🔄 Requesting script fixes...")
                final_script = self._fix_script(script, review, language)
        elif review.get('revised_hook') and scores.get('hook', 10) < 7:
            # Just fix the hook
            logger.info(f"   🔄 Replacing weak hook with improved version")
            final_script = self._replace_hook(script, review['revised_hook'])
        
        return final_script, review


    def _fix_script(self, script, review, language):
        """Fix script based on review feedback"""
        
        issues = review.get('improvements', [])
        issues.extend(review.get('factual_issues', []))
        
        if not issues:
            return script
        
        prompt = f"""Fix this {language} YouTube script based on reviewer feedback.

ISSUES TO FIX:
{json.dumps(issues, indent=2, ensure_ascii=False)}

SCORES:
{json.dumps(review.get('scores', {}), indent=2)}

ORIGINAL SCRIPT:
{script}

Fix ALL issues while keeping:
- Same section markers [HOOK], [SECTION_1], etc.
- Same overall structure and topic
- Same approximate length
- [VISUAL: ] tags

Return ONLY the fixed script."""

        fixed = self._call_gemini(prompt)
        logger.info(f"   ✅ Script fixed ({len(fixed.split())} words)")
        return fixed


    def _replace_hook(self, script, new_hook):
        """Replace just the hook section"""
        
        # Find and replace hook section
        hook_pattern = re.compile(
            r'\[HOOK\].*?(?=\[SECTION_1)',
            re.DOTALL
        )
        
        if hook_pattern.search(script):
            return hook_pattern.sub(f'[HOOK]\n{new_hook}\n\n', script)
        return script


    # =============================================
    # METADATA GENERATION
    # =============================================
    
    def generate_metadata(self, topic_data, language, video_type="long"):
        """Generate title, description, tags"""
        
        topic = topic_data.get('topic', '')
        topic_local = topic_data.get('topic_local', topic)
        
        logger.info(f"🧠 Generating {video_type} metadata for: {topic[:40]}...")
        
        if video_type == "long":
            prompt = f"""Generate YouTube video metadata in {language}.

Topic: "{topic}" / "{topic_local}"
Type: Long-form educational video (8-12 minutes)
Audience: Indian {language} speakers

Return JSON:
{{
    "title": "Compelling clickbait-style title in {language} (50-70 chars) — use emoji — create curiosity",
    "title_english": "Same title in English",
    "description": "SEO-optimized description in {language} (300+ words):\\n- Hook paragraph\\n- Key points covered\\n- Timestamps placeholder\\n- 5+ hashtags in both {language} and English\\n- Subscribe CTA in {language}\\n- Related search terms",
    "tags": ["15-20 tags mixing {language} and English for maximum reach"],
    "thumbnail_text": "2-4 words in {language} — BOLD and SHOCKING for thumbnail"
}}"""
        else:
            prompt = f"""Generate YouTube Shorts metadata in {language}.

Topic: "{topic}" / "{topic_local}"
Type: YouTube Short (30-60 seconds)
Audience: Indian {language} speakers

Return JSON:
{{
    "title": "Catchy short title in {language} (40-60 chars) #shorts",
    "description": "Brief description + hashtags + Full video link placeholder",
    "tags": ["10-15 tags including #shorts"],
    "thumbnail_text": "1-3 words in {language}"
}}"""

        metadata = self._call_gemini(prompt, expect_json=True)
        
        # Ensure shorts have #shorts
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
        """Extract visual search keywords for stock footage"""
        
        logger.info(f"🧠 Extracting footage keywords from script...")
        
        prompt = f"""From this video script, extract keywords for finding stock footage on Pexels.

SCRIPT (first 3000 chars):
{script[:3000]}

Return a JSON array of 15-20 ENGLISH keywords/phrases.
Focus on VISUAL scenes that would look cinematic:
- Natural phenomena
- Technology visuals
- Space/science imagery
- Abstract backgrounds
- City/nature scenes

Example: ["satellite orbiting earth", "neural network visualization", "deep ocean creatures"]

Return ONLY the JSON array."""

        keywords = self._call_gemini(prompt, expect_json=True)
        
        if not isinstance(keywords, list):
            keywords = ["technology", "science", "space", "nature", "abstract"]
        
        logger.info(f"   ✅ Extracted {len(keywords)} footage keywords")
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
        
        logger.info(f"   ✅ Found {len(sections)} sections:")
        for s in sections:
            word_count = len(s['text'].split())
            short_status = "📱 Short candidate" if s['is_short_candidate'] else "⏭️ Skip for shorts"
            logger.info(f"      [{s['marker']}] {s['title'][:30]} — {word_count} words — {short_status}")
        
        return sections


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    brain = GeminiBrain()
    topics = brain.generate_topics("space and science", "telugu", count=2)
    print(json.dumps(topics, indent=2, ensure_ascii=False))
