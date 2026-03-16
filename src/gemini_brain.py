"""
═══════════════════════════════════════════════════════════════
  GEMINI BRAIN — Central AI Engine
  
  Handles:
  • Topic generation with trend awareness
  • Script writing with EMOTION MARKERS for voice/animation
  • Script quality review (replaces human judgment)
  • Metadata generation (title, description, tags)
  • Footage/scene keyword extraction
  
  Emotion markers in scripts:
  [EMOTION:happy] [EMOTION:sad] [EMOTION:excited]
  [EMOTION:serious] [EMOTION:thinking] [EMOTION:surprised]
  [PAUSE:short] [PAUSE:long] [BREATH]
═══════════════════════════════════════════════════════════════
"""

import google.generativeai as genai
import json
import time
import re
import os
import yaml


class GeminiBrain:
    
    def __init__(self, config_path="config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        api_key = os.environ.get('GEMINI_API_KEY', 
                    self.config.get('gemini', {}).get('api_key', ''))
        
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment or config!")
        
        genai.configure(api_key=api_key)
        
        self.model = genai.GenerativeModel(
            model_name=self.config['gemini']['model'],
            generation_config={
                "temperature": self.config['gemini']['temperature'],
                "top_p": 0.95,
                "max_output_tokens": 8192,
            }
        )
        
        self.max_retries = self.config['gemini']['max_retries']


    def _call(self, prompt, expect_json=False):
        """Call Gemini API with retries"""
        
        for attempt in range(self.max_retries):
            try:
                response = self.model.generate_content(prompt)
                text = response.text.strip()
                
                if expect_json:
                    text = re.sub(r'```json\s*', '', text)
                    text = re.sub(r'```\s*', '', text)
                    return json.loads(text)
                
                return text
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait = 5 * (attempt + 1)
                    time.sleep(wait)
                else:
                    raise Exception(f"Gemini failed after {self.max_retries} attempts: {e}")


    def generate_topics(self, niche, language, trending_data=None, count=3):
        """Generate video topics enhanced with trending data"""
        
        channel_conf = self.config['channels'][language]
        
        trend_context = ""
        if trending_data:
            trend_items = [t.get('topic', '') for t in trending_data[:10]]
            trend_context = f"""
Currently trending in India:
{json.dumps(trend_items, indent=2)}

Try to connect your topics with these trends where naturally possible."""

        prompt = f"""You are a top YouTube content strategist for Indian {channel_conf['native_name']} audience.

Generate {count} compelling video topics for niche: "{niche}"

{trend_context}

REQUIREMENTS:
- Target audience: {channel_conf['target_audience']}
- Topics must be FASCINATING and create curiosity
- Each topic should support a 10-minute deep explainer video
- Each topic must be divisible into 5 standalone short clips
- Avoid controversial politics or religion
- Mix evergreen + trending topics

Return ONLY this JSON:
[
    {{
        "topic": "Topic in English",
        "topic_local": "Topic in {channel_conf['native_name']}",
        "hook": "A one-line hook that creates instant curiosity",
        "search_keywords": ["keyword1", "keyword2", "keyword3"],
        "trend_connection": "How this connects to current trends (or 'evergreen')",
        "emotion_arc": ["curious", "surprised", "amazed", "thoughtful", "inspired"],
        "sections": [
            {{"title": "Section title", "emotion": "curious", "key_fact": "One amazing fact"}},
            {{"title": "Section title", "emotion": "surprised", "key_fact": "One amazing fact"}},
            {{"title": "Section title", "emotion": "amazed", "key_fact": "One amazing fact"}},
            {{"title": "Section title", "emotion": "thoughtful", "key_fact": "One amazing fact"}},
            {{"title": "Section title", "emotion": "inspired", "key_fact": "One amazing fact"}}
        ],
        "thumbnail_idea": "2-3 word thumbnail text in {channel_conf['native_name']}",
        "estimated_interest": "high"
    }}
]"""

        return self._call(prompt, expect_json=True)


    def generate_emotional_script(self, topic_data, language, target_words=1500):
        """Generate script WITH emotion markers and voice direction"""
        
        channel = self.config['channels'][language]
        emotion_arc = topic_data.get('emotion_arc', 
                        ['curious', 'surprised', 'amazed', 'thoughtful', 'inspired'])
        
        prompt = f"""Write a YouTube video script in {channel['native_name']} about:
"{topic_data['topic']}"

═══════════════════════════════════════════════
CRITICAL: EMOTION & VOICE DIRECTION MARKERS
═══════════════════════════════════════════════

You MUST include these markers throughout the script for voice and animation:

EMOTION MARKERS (controls character expression + voice tone):
  [EMOTION:happy] — cheerful, upbeat delivery
  [EMOTION:excited] — high energy, fast pace, raised pitch
  [EMOTION:serious] — calm, authoritative, slower pace
  [EMOTION:thinking] — contemplative, questioning tone
  [EMOTION:surprised] — wide-eyed amazement
  [EMOTION:sad] — empathetic, softer voice
  [EMOTION:explaining] — teacher mode, clear and measured

PAUSE MARKERS (for natural speech rhythm):
  [BREATH] — natural breathing pause (300ms)
  [PAUSE:short] — brief dramatic pause (500ms)
  [PAUSE:long] — dramatic silence for impact (1000ms)
  [EMPHASIS:text here] — stress/emphasize these words

SCENE MARKERS (for anime background changes):
  [SCENE:description] — change background scene

═══════════════════════════════════════════════
SCRIPT STRUCTURE
═══════════════════════════════════════════════

[SECTION:HOOK]
[EMOTION:excited]
[SCENE:eye-catching scene related to topic]
(30-45 seconds — THE MOST IMPORTANT PART)
- Start with a SHOCKING statement or impossible question
- Create a knowledge gap the viewer MUST fill
- Say "ఈ వీడియో చివరిలో..."/"इस वीडियो के अंत तक..." to promise value
[PAUSE:long]

[SECTION:PART1:{topic_data.get('sections', [{{}}])[0].get('title', 'Point 1')}]
[EMOTION:{emotion_arc[0] if len(emotion_arc) > 0 else 'curious'}]
[SCENE:relevant background]
(90-120 seconds — standalone short-worthy)
- Start with its own mini-hook
- Include real-world example relevant to India
- End with teaser for next section
[BREATH]

[SECTION:PART2:{topic_data.get('sections', [{{}}]*2)[1].get('title', 'Point 2')}]
[EMOTION:{emotion_arc[1] if len(emotion_arc) > 1 else 'surprised'}]
[SCENE:relevant background]
(90-120 seconds — standalone short-worthy)
- Build on previous section
- Include a surprising fact or statistic
- Use rhetorical questions
[BREATH]

[SECTION:PART3:{topic_data.get('sections', [{{}}]*3)[2].get('title', 'Point 3')}]
[EMOTION:{emotion_arc[2] if len(emotion_arc) > 2 else 'amazed'}]
[SCENE:relevant background]
(90-120 seconds — standalone short-worthy)
- The most interesting/surprising point
- This should be the "WOW" moment
[PAUSE:short]

[SECTION:PART4:{topic_data.get('sections', [{{}}]*4)[3].get('title', 'Point 4')}]
[EMOTION:{emotion_arc[3] if len(emotion_arc) > 3 else 'thinking'}]
[SCENE:relevant background]
(90-120 seconds — standalone short-worthy)
- Deeper analysis or real-world implications
- Connect to viewer's daily life
[BREATH]

[SECTION:PART5:{topic_data.get('sections', [{{}}]*5)[4].get('title', 'Point 5')}]
[EMOTION:{emotion_arc[4] if len(emotion_arc) > 4 else 'inspired'}]
[SCENE:relevant background]
(60-90 seconds — standalone short-worthy)
- Future implications or call to thought
- Inspiring or thought-provoking conclusion
[PAUSE:long]

[SECTION:CTA]
[EMOTION:happy]
[SCENE:channel branding background]
(30 seconds)
- Summarize key takeaway
- Ask viewers to subscribe in {channel['native_name']}
- Tease next video topic

═══════════════════════════════════════════════
LANGUAGE RULES
═══════════════════════════════════════════════

- Write in {channel['native_name']} using {channel['script_name']} script
- Use NATURAL conversational {channel['language']} (like talking to a friend)
- Mix English technical terms where natural (like {channel['language']} YouTubers do)
- A 15-year-old should understand everything
- Use "మీకు తెలుసా?"/"क्या आप जानते हैं?" style engagement
- Include India-specific examples and references

TARGET LENGTH: ~{target_words} words (~10 minutes spoken)

Write the complete script now:"""

        return self._call(prompt)


    def review_and_fix_script(self, script, language, topic):
        """AI reviews AND fixes the script — zero human needed"""
        
        channel = self.config['channels'][language]
        
        prompt = f"""You are a senior YouTube content editor.

Review this {channel['native_name']} script and FIX any issues:

SCRIPT:
{script}

TOPIC: {topic}

CHECK AND FIX:
1. FACTUAL ACCURACY — Fix any wrong facts/dates/numbers
2. EMOTION MARKERS — Ensure [EMOTION:X] markers are present at natural points
3. PAUSE MARKERS — Add [BREATH] and [PAUSE:short/long] at natural speech points
4. EMPHASIS — Add [EMPHASIS:key words] for important terms
5. ENGAGEMENT — Is the hook compelling? Fix if weak.
6. EACH SECTION should work as standalone 30-60sec short
7. LANGUAGE — Fix any unnatural {channel['native_name']} phrasing
8. SCENE MARKERS — Add [SCENE:description] for background changes
9. Remove any harmful, offensive, or copyrighted content

IMPORTANT: 
- Add [BREATH] after every 2-3 sentences (humans breathe!)
- Add [PAUSE:short] before surprising reveals
- Add [PAUSE:long] after shocking facts (let it sink in)
- Vary emotions throughout — don't keep same emotion too long

Return this JSON:
{{
    "overall_score": 8,
    "approved": true,
    "changes_made": ["list of changes"],
    "fixed_script": "THE COMPLETE FIXED SCRIPT with all markers"
}}"""

        result = self._call(prompt, expect_json=True)
        
        fixed_script = result.get('fixed_script', script)
        return fixed_script, result


    def generate_metadata(self, topic_data, language, video_type="long",
                           long_video_url=None):
        """Generate optimized title, description, tags"""
        
        channel = self.config['channels'][language]
        topic = topic_data['topic']
        topic_local = topic_data.get('topic_local', topic)
        
        url_ref = ""
        if long_video_url and video_type == "short":
            url_ref = f"\nFull video URL to reference: {long_video_url}"
        
        if video_type == "long":
            prompt = f"""Generate YouTube metadata in {channel['native_name']} for:
Topic: "{topic}"

Return JSON:
{{
    "title": "{channel['native_name']} title (50-70 chars, include emoji, create curiosity)",
    "description": "Full {channel['native_name']} description (300+ words) with:\\n- Compelling summary\\n- Timestamps for each section\\n- 3 relevant hashtags\\n- 'Subscribe' CTA in {channel['native_name']}\\n- Mix {channel['native_name']} and English keywords for SEO",
    "tags": ["15-20 tags mixing {channel['native_name']} and English"],
    "thumbnail_text": "2-4 word {channel['native_name']} text for thumbnail (BOLD, CATCHY)"
}}"""
        else:
            prompt = f"""Generate YouTube Shorts metadata in {channel['native_name']}:
Topic: "{topic_local}"
{url_ref}

Return JSON:
{{
    "title": "Short catchy {channel['native_name']} title (under 60 chars) ending with #shorts",
    "description": "{channel['native_name']} description + 'పూర్తి వీడియో చూడండి'/'पूरा वीडियो देखें' + link + hashtags",
    "tags": ["10-15 relevant tags"]
}}"""

        return self._call(prompt, expect_json=True)


    def get_scene_descriptions(self, script):
        """Extract scene descriptions for anime image generation"""
        
        prompt = f"""From this video script, extract visual scene descriptions for anime-style illustration.

SCRIPT:
{script[:4000]}

For each [SECTION] in the script, provide an anime scene description.

Return JSON array:
[
    {{
        "section": "HOOK",
        "emotion": "excited",
        "scene_description": "Detailed description for anime background art (in English)",
        "character_expression": "excited",
        "key_visual_element": "Main visual element to show",
        "camera_angle": "close-up / medium shot / wide shot",
        "lighting": "dramatic / warm / cool / neutral"
    }},
    ...
]

Make scenes VISUALLY INTERESTING and VARIED.
Each scene should be distinct from the others."""

        return self._call(prompt, expect_json=True)


    def parse_script_to_sections(self, script):
        """Parse script into sections with emotion data"""
        
        sections = []
        current = {
            'marker': '', 'title': '', 'text': '',
            'emotion': 'neutral', 'scene': '', 'is_short': True
        }
        
        for line in script.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Section marker
            section_match = re.match(
                r'\[SECTION:(\w+)(?::(.+?))?\]', line
            )
            if section_match:
                if current['text'].strip():
                    sections.append(current.copy())
                
                marker = section_match.group(1)
                title = section_match.group(2) or marker
                current = {
                    'marker': marker,
                    'title': title,
                    'text': '',
                    'emotion': 'neutral',
                    'scene': '',
                    'is_short': marker not in ['CTA']
                }
                continue
            
            # Emotion marker
            emotion_match = re.match(r'\[EMOTION:(\w+)\]', line)
            if emotion_match:
                current['emotion'] = emotion_match.group(1)
                continue
            
            # Scene marker
            scene_match = re.match(r'\[SCENE:(.+?)\]', line)
            if scene_match:
                current['scene'] = scene_match.group(1)
                continue
            
            # Regular text (keep pause/breath/emphasis markers in text)
            if not line.startswith('[SECTION') and not line.startswith('[EMOTION') \
               and not line.startswith('[SCENE'):
                current['text'] += line + '\n'
        
        # Last section
        if current['text'].strip():
            sections.append(current.copy())
        
        return sections
