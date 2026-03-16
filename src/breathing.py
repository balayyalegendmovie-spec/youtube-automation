"""
BREATHING ENGINE — Makes AI Voice Sound Natural & Emotional

This module transforms a plain script into an emotionally rich
voice script with:

1. BREATHING:
   - Short breaths between sentences
   - Longer breaths between paragraphs
   - Natural pauses at commas
   - Micro-pauses before important words

2. EMOTIONS:
   - Detects emotional context from script content
   - Maps emotions to voice parameters (rate, pitch, volume)
   - Supports: cheerful, sad, excited, serious, angry, whisper
   - Smooth transitions between emotions

3. EMPHASIS:
   - Key words spoken slower with higher pitch
   - Questions have rising intonation
   - Exclamations have energy burst
   - Numbers and facts are emphasized

4. PACING:
   - Hook section: faster, more energetic
   - Explanation: moderate, clear
   - Climax/twist: dramatic pauses
   - CTA: warm, inviting

Edge TTS SSML support is used for all of this.
"""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================
# DATA CLASSES
# =============================================

@dataclass
class EmotionSegment:
    """Represents a segment of text with a specific emotion"""
    text: str
    emotion: str = "neutral"
    intensity: float = 0.7        # 0.0 to 1.0
    rate: str = "+0%"             # Speech rate adjustment
    pitch: str = "+0Hz"           # Pitch adjustment
    volume: str = "+0%"           # Volume adjustment


@dataclass
class BreathMark:
    """Represents a breathing pause"""
    duration_ms: int = 300
    breath_type: str = "short"    # short, medium, long, dramatic


@dataclass  
class ProcessedScript:
    """Complete processed script ready for TTS"""
    ssml: str                      # SSML markup for Edge TTS
    segments: List[dict] = field(default_factory=list)
    total_estimated_duration: float = 0.0
    emotions_used: List[str] = field(default_factory=list)


# =============================================
# EMOTION DETECTOR
# =============================================

class EmotionDetector:
    """Detects emotions from text content"""
    
    # Keywords that indicate specific emotions
    EMOTION_KEYWORDS = {
        'excited': [
            'amazing', 'incredible', 'unbelievable', 'wow', 'mind-blowing',
            'extraordinary', 'fantastic', 'revolutionary', 'breakthrough',
            'అద్భుతమైన', 'ఆశ్చర్యకరమైన', 'అసాధారణమైన',
            'अद्भुत', 'अविश्वसनीय', 'शानदार', 'गजब',
            '!', 'biggest', 'fastest', 'most powerful'
        ],
        'serious': [
            'danger', 'warning', 'critical', 'important', 'serious',
            'problem', 'crisis', 'threat', 'risk', 'careful',
            'ప్రమాదకరమైన', 'హెచ్చరిక', 'ముఖ్యమైన',
            'खतरनाक', 'चेतावनी', 'गंभीर', 'महत्वपूर्ण'
        ],
        'sad': [
            'unfortunately', 'tragic', 'lost', 'died', 'destroyed',
            'sad', 'heartbreaking', 'devastating', 'painful',
            'బాధాకరమైన', 'విషాదకరమైన',
            'दुखद', 'दर्दनाक', 'विनाशकारी'
        ],
        'angry': [
            'outrageous', 'scandal', 'corruption', 'fraud', 'cheat',
            'injustice', 'exploitation', 'betrayal',
            'మోసం', 'అన్యాయం',
            'धोखा', 'अन्याय', 'भ्रष्टाचार'
        ],
        'cheerful': [
            'good news', 'great', 'wonderful', 'happy', 'celebrate',
            'success', 'achievement', 'milestone', 'congratulations',
            'శుభవార్త', 'విజయం',
            'खुशखबरी', 'सफलता', 'बधाई'
        ],
        'whisper': [
            'secret', 'hidden', 'nobody knows', 'between you and me',
            'quietly', 'mysterious', 'confidential',
            'రహస్యం', 'ఎవరికీ తెలియదు',
            'रहस्य', 'किसी को नहीं पता'
        ],
        'curious': [
            'did you know', 'what if', 'imagine', 'have you ever',
            'why does', 'how does', 'is it possible',
            'మీకు తెలుసా', 'ఊహించండి',
            'क्या आपको पता है', 'कल्पना करो', 'सोचो'
        ]
    }
    
    # Section-specific emotion defaults
    SECTION_EMOTIONS = {
        'HOOK': ('excited', 0.8),
        'SECTION_1': ('curious', 0.6),
        'SECTION_2': ('serious', 0.6),
        'SECTION_3': ('cheerful', 0.7),
        'SECTION_4': ('excited', 0.8),  # Climax section
        'CTA': ('cheerful', 0.7),
    }
    
    
    def detect_emotion(self, text, section_marker=None):
        """
        Detect the primary emotion of a text segment.
        
        Returns: (emotion_name, intensity)
        """
        
        text_lower = text.lower()
        
        # Count keyword matches for each emotion
        scores = {}
        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                scores[emotion] = score
        
        # If keywords found, use highest scoring emotion
        if scores:
            best_emotion = max(scores, key=scores.get)
            intensity = min(0.5 + scores[best_emotion] * 0.1, 1.0)
            return best_emotion, intensity
        
        # Fall back to section-based emotion
        if section_marker and section_marker in self.SECTION_EMOTIONS:
            return self.SECTION_EMOTIONS[section_marker]
        
        # Default
        return 'neutral', 0.5
    

    def detect_sentence_emotions(self, text, section_marker=None):
        """Detect emotion for each sentence in a text block"""
        
        # Split into sentences
        sentences = re.split(r'(?<=[.!?।])\s+', text)
        
        results = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            emotion, intensity = self.detect_emotion(sentence, section_marker)
            
            results.append({
                'text': sentence,
                'emotion': emotion,
                'intensity': intensity
            })
        
        return results


# =============================================
# VOICE PARAMETER MAPPER
# =============================================

class VoiceParameterMapper:
    """Maps emotions to Edge TTS voice parameters"""
    
    EMOTION_PARAMS = {
        'neutral': {
            'rate': '+0%',
            'pitch': '+0Hz',
            'volume': '+0%',
            'style': 'general',
        },
        'excited': {
            'rate': '+15%',
            'pitch': '+30Hz',
            'volume': '+10%',
            'style': 'cheerful',
        },
        'serious': {
            'rate': '-10%',
            'pitch': '-15Hz',
            'volume': '+5%',
            'style': 'serious',
        },
        'sad': {
            'rate': '-15%',
            'pitch': '-25Hz',
            'volume': '-10%',
            'style': 'sad',
        },
        'angry': {
            'rate': '+10%',
            'pitch': '+10Hz',
            'volume': '+20%',
            'style': 'angry',
        },
        'cheerful': {
            'rate': '+8%',
            'pitch': '+20Hz',
            'volume': '+5%',
            'style': 'cheerful',
        },
        'whisper': {
            'rate': '-20%',
            'pitch': '-10Hz',
            'volume': '-30%',
            'style': 'whispering',
        },
        'curious': {
            'rate': '+5%',
            'pitch': '+15Hz',
            'volume': '+0%',
            'style': 'curious',
        },
    }
    
    
    def get_params(self, emotion, intensity=0.7):
        """Get voice parameters for an emotion with intensity scaling"""
        
        params = self.EMOTION_PARAMS.get(emotion, self.EMOTION_PARAMS['neutral']).copy()
        
        # Scale parameters by intensity
        for key in ['rate', 'pitch', 'volume']:
            value = params[key]
            # Parse the value
            match = re.match(r'([+-]?)(\d+)(.*)', value)
            if match:
                sign = -1 if match.group(1) == '-' else 1
                num = int(match.group(2))
                unit = match.group(3)
                
                # Scale by intensity
                scaled = int(num * intensity)
                params[key] = f"{'+' if sign > 0 else '-'}{scaled}{unit}"
        
        return params


# =============================================
# BREATHING ENGINE
# =============================================

class BreathingEngine:
    """
    Adds natural breathing patterns to scripts.
    
    Breathing rules:
    1. Short breath (200-300ms) after every sentence
    2. Medium breath (400-500ms) at paragraph breaks
    3. Long breath (600-800ms) between sections
    4. Micro-pause (100-150ms) at commas
    5. Dramatic pause (800-1200ms) before reveals
    6. No breath in the middle of a phrase
    """
    
    def __init__(self, config=None):
        self.config = config or {}
        
        # Default breath durations (ms)
        self.SHORT_BREATH = self.config.get('short_breath_ms', 300)
        self.MEDIUM_BREATH = self.config.get('long_breath_ms', 500)
        self.LONG_BREATH = 800
        self.COMMA_PAUSE = self.config.get('comma_pause_ms', 200)
        self.DRAMATIC_PAUSE = 1000
        self.SENTENCE_PAUSE = self.config.get('sentence_pause_ms', 400)
    
    
    def add_breathing(self, text, section_marker=None):
        """
        Add breathing marks to text.
        Returns text with SSML break tags.
        """
        
        processed = text
        
        # 1. Add pauses at sentence endings (.!?।)
        processed = re.sub(
            r'([.!?।])\s+',
            f'\\1 <break time="{self.SENTENCE_PAUSE}ms"/> ',
            processed
        )
        
        # 2. Add shorter pauses at commas
        processed = re.sub(
            r',\s+',
            f', <break time="{self.COMMA_PAUSE}ms"/> ',
            processed
        )
        
        # 3. Add pauses at ellipsis (...)
        processed = re.sub(
            r'\.\.\.\s*',
            f'... <break time="{self.DRAMATIC_PAUSE}ms"/> ',
            processed
        )
        
        # 4. Add pauses at em-dashes (—)
        processed = re.sub(
            r'\s*[—–]\s*',
            f' <break time="{self.SHORT_BREATH}ms"/> ',
            processed
        )
        
        # 5. Add longer pauses between paragraphs
        processed = re.sub(
            r'\n\s*\n',
            f'\n<break time="{self.MEDIUM_BREATH}ms"/>\n',
            processed
        )
        
        # 6. Add dramatic pause before "but", "however", "actually"
        dramatic_words = [
            'but', 'however', 'actually', 'surprisingly',
            'in fact', 'the truth is', 'interestingly',
            'కానీ', 'నిజానికి', 'ఆశ్చర్యకరంగా',
            'लेकिन', 'असल में', 'हैरानी की बात',
            'मगर', 'वास्तव में', 'दरअसल'
        ]
        
        for word in dramatic_words:
            pattern = re.compile(
                rf'([.!?।,]\s*)<break[^/]*/>\s*({re.escape(word)})',
                re.IGNORECASE
            )
            processed = pattern.sub(
                f'\\1 <break time="{self.DRAMATIC_PAUSE}ms"/> \\2',
                processed
            )
        
        # 7. Add emphasis on numbers and statistics
        processed = re.sub(
            r'(\d+(?:\.\d+)?(?:\s*(?:million|billion|crore|lakh|percent|%|thousand'
            r'|కోట్లు|లక్షలు|करोड़|लाख)))',
            r'<emphasis level="strong">\1</emphasis>',
            processed,
            flags=re.IGNORECASE
        )
        
        # 8. Section-specific breathing
        if section_marker == 'HOOK':
            # Hook: shorter pauses, more energy
            processed = processed.replace(
                f'time="{self.SENTENCE_PAUSE}ms"',
                f'time="{int(self.SENTENCE_PAUSE * 0.7)}ms"'
            )
        elif section_marker == 'CTA':
            # CTA: warm pauses
            processed = processed.replace(
                f'time="{self.SENTENCE_PAUSE}ms"',
                f'time="{int(self.SENTENCE_PAUSE * 1.3)}ms"'
            )
        
        return processed


# =============================================
# SSML BUILDER
# =============================================

class SSMLBuilder:
    """
    Builds complete SSML for Edge TTS with emotions and breathing.
    
    Edge TTS supported SSML elements:
    - <speak> root
    - <voice> voice selection
    - <prosody rate="" pitch="" volume=""> 
    - <break time="Xms"/>
    - <emphasis level="strong|moderate|reduced">
    - <p> paragraph
    - <s> sentence
    """
    
    def __init__(self, voice_id="te-IN-ShrutiNeural"):
        self.voice_id = voice_id
        self.emotion_detector = EmotionDetector()
        self.param_mapper = VoiceParameterMapper()
        self.breathing_engine = BreathingEngine()
    

    def build_ssml(self, script, sections=None):
        """
        Build complete SSML from script text.
        
        Args:
            script: Full script text with section markers
            sections: Parsed sections (optional)
        
        Returns:
            ProcessedScript with SSML and metadata
        """
        
        logger.info("🫁 STEP: Building natural voice SSML with breathing & emotions...")
        
        if sections is None:
            sections = self._parse_sections(script)
        
        ssml_parts = []
        all_emotions = set()
        total_words = 0
        
        for section in sections:
            logger.info(f"  Processing section: [{section['marker']}] "
                       f"({len(section['text'].split())} words)")
            
            # Detect emotions for each sentence
            sentence_emotions = self.emotion_detector.detect_sentence_emotions(
                section['text'],
                section['marker']
            )
            
            # Build SSML for this section
            section_ssml = self._build_section_ssml(
                sentence_emotions,
                section['marker']
            )
            
            ssml_parts.append(section_ssml)
            
            # Track emotions used
            for se in sentence_emotions:
                all_emotions.add(se['emotion'])
                total_words += len(se['text'].split())
        
        # Combine all parts
        full_ssml = '\n'.join(ssml_parts)
        
        # Estimate duration (avg 2.5 words/second for Indian languages)
        estimated_duration = total_words / 2.5
        
        emotions_list = list(all_emotions)
        
        logger.info(f"  ✅ SSML built: {total_words} words, "
                    f"~{estimated_duration:.0f}s estimated, "
                    f"emotions: {', '.join(emotions_list)}")
        
        return ProcessedScript(
            ssml=full_ssml,
            segments=[{'marker': s['marker'], 'word_count': len(s['text'].split())} 
                     for s in sections],
            total_estimated_duration=estimated_duration,
            emotions_used=emotions_list
        )


    def _build_section_ssml(self, sentence_emotions, section_marker):
        """Build SSML for one section"""
        
        parts = []
        prev_emotion = None
        
        for i, sent_data in enumerate(sentence_emotions):
            text = sent_data['text']
            emotion = sent_data['emotion']
            intensity = sent_data['intensity']
            
            # Get voice parameters for this emotion
            params = self.param_mapper.get_params(emotion, intensity)
            
            # Add breathing
            text_with_breathing = self.breathing_engine.add_breathing(
                text, section_marker
            )
            
            # Add prosody wrapper if emotion changed
            if emotion != prev_emotion:
                # Close previous prosody if exists
                if prev_emotion is not None:
                    parts.append('</prosody>')
                    # Add transition breath between emotion changes
                    parts.append(f'<break time="400ms"/>')
                
                # Open new prosody
                parts.append(
                    f'<prosody rate="{params["rate"]}" '
                    f'pitch="{params["pitch"]}" '
                    f'volume="{params["volume"]}">'
                )
            
            # Handle question intonation
            if text.rstrip().endswith('?') or text.rstrip().endswith('?'):
                # Questions: rising pitch at end
                text_with_breathing = (
                    f'<prosody pitch="+20Hz">{text_with_breathing}</prosody>'
                )
            
            # Handle exclamations
            elif text.rstrip().endswith('!'):
                text_with_breathing = (
                    f'<prosody rate="+10%" volume="+10%">'
                    f'{text_with_breathing}</prosody>'
                )
            
            parts.append(f'<s>{text_with_breathing}</s>')
            prev_emotion = emotion
        
        # Close last prosody tag
        if prev_emotion is not None:
            parts.append('</prosody>')
        
        # Add section break
        parts.append('<break time="800ms"/>')
        
        return '\n'.join(parts)


    def _parse_sections(self, script):
        """Parse script into sections if not provided"""
        
        sections = []
        current = None
        current_text = []
        
        for line in script.split('\n'):
            line = line.strip()
            
            section_match = re.match(
                r'\[(HOOK|SECTION_\d+|CTA)(?::\s*(.+?))?\]',
                line
            )
            
            if section_match:
                if current is not None and current_text:
                    sections.append({
                        'marker': current['marker'],
                        'title': current['title'],
                        'text': '\n'.join(current_text).strip()
                    })
                
                current = {
                    'marker': section_match.group(1),
                    'title': section_match.group(2) or section_match.group(1)
                }
                current_text = []
            
            elif line and not line.startswith('[VISUAL'):
                current_text.append(line)
        
        if current and current_text:
            sections.append({
                'marker': current['marker'],
                'title': current['title'],
                'text': '\n'.join(current_text).strip()
            })
        
        return sections


    def build_section_ssml(self, section_text, section_marker, emotion_override=None):
        """
        Build SSML for a single section (used for shorts).
        
        Returns just the SSML text string that can be passed to Edge TTS.
        """
        
        sentence_emotions = self.emotion_detector.detect_sentence_emotions(
            section_text,
            section_marker
        )
        
        # Override emotion if specified
        if emotion_override:
            for se in sentence_emotions:
                se['emotion'] = emotion_override
        
        ssml = self._build_section_ssml(sentence_emotions, section_marker)
        
        return ssml


# =============================================
# SCRIPT PRE-PROCESSOR
# =============================================

class ScriptPreProcessor:
    """
    Pre-processes script BEFORE sending to TTS.
    
    Tasks:
    1. Clean up formatting artifacts
    2. Convert numbers to words (for better pronunciation)
    3. Add pronunciation hints for technical terms
    4. Normalize punctuation
    5. Add reading instructions
    """
    
    # Number words in Telugu and Hindi
    TELUGU_NUMBERS = {
        0: 'సున్న', 1: 'ఒకటి', 2: 'రెండు', 3: 'మూడు', 4: 'నాలుగు',
        5: 'ఐదు', 6: 'ఆరు', 7: 'ఏడు', 8: 'ఎనిమిది', 9: 'తొమ్మిది',
        10: 'పది', 100: 'వంద', 1000: 'వెయ్యి'
    }
    
    HINDI_NUMBERS = {
        0: 'शून्य', 1: 'एक', 2: 'दो', 3: 'तीन', 4: 'चार',
        5: 'पाँच', 6: 'छह', 7: 'सात', 8: 'आठ', 9: 'नौ',
        10: 'दस', 100: 'सौ', 1000: 'हज़ार'
    }
    
    
    def preprocess(self, script, language='telugu'):
        """Full preprocessing pipeline"""
        
        logger.info(f"  Pre-processing script for {language}...")
        
        processed = script
        
        # 1. Remove visual cues (not for voice)
        processed = re.sub(r'\[VISUAL:.*?\]', '', processed)
        
        # 2. Clean section markers (keep for parsing but make invisible to TTS)
        # Don't remove them — we need them for section splitting
        
        # 3. Normalize whitespace
        processed = re.sub(r'[ \t]+', ' ', processed)
        processed = re.sub(r'\n{3,}', '\n\n', processed)
        
        # 4. Fix punctuation
        processed = processed.replace('..', '.')
        processed = processed.replace(',,', ',')
        
        # 5. Add pronunciation hints for abbreviations
        abbreviations = {
            'AI': 'ए आई' if language == 'hindi' else 'ఏ ఐ',
            'NASA': 'नासा' if language == 'hindi' else 'నాసా',
            'ISS': 'आई एस एस' if language == 'hindi' else 'ఐ ఎస్ ఎస్',
            'DNA': 'डी एन ए' if language == 'hindi' else 'డీ ఎన్ ఏ',
            'API': 'ए पी आई' if language == 'hindi' else 'ఏ పీ ఐ',
            'CPU': 'सी पी यू' if language == 'hindi' else 'సీ పీ యూ',
            'GPU': 'जी पी यू' if language == 'hindi' else 'జీ పీ యూ',
            'km': 'किलोमीटर' if language == 'hindi' else 'కిలోమీటర్లు',
            'kg': 'किलोग्राम' if language == 'hindi' else 'కిలోగ్రాములు',
        }
        
        for abbr, expansion in abbreviations.items():
            # Only replace standalone abbreviations
            processed = re.sub(
                rf'\b{re.escape(abbr)}\b',
                expansion,
                processed
            )
        
        # 6. Add reading flow markers
        # Before listing items, add a slight pause
        list_markers = ['1.', '2.', '3.', '4.', '5.',
                       'First', 'Second', 'Third',
                       'మొదట', 'రెండవ', 'మూడవ',
                       'पहला', 'दूसरा', 'तीसरा']
        
        for marker in list_markers:
            processed = processed.replace(
                marker,
                f'<break time="300ms"/> {marker}'
            )
        
        return processed


# =============================================
# MAIN BREATHING PROCESSOR
# =============================================

class BreathingProcessor:
    """
    Main class that combines all breathing/emotion processing.
    
    Usage:
        processor = BreathingProcessor(voice_id="te-IN-ShrutiNeural")
        result = processor.process_script(script, language="telugu")
        # result.ssml contains ready-to-speak SSML
    """
    
    def __init__(self, voice_id, config=None):
        self.voice_id = voice_id
        self.config = config or {}
        
        # Initialize components
        self.preprocessor = ScriptPreProcessor()
        self.ssml_builder = SSMLBuilder(voice_id)
        
        logger.info(f"🫁 Breathing processor initialized for voice: {voice_id}")
    

    def process_script(self, script, language='telugu', sections=None):
        """
        Complete processing pipeline:
        1. Pre-process text
        2. Detect emotions
        3. Add breathing
        4. Build SSML
        
        Returns: ProcessedScript
        """
        
        logger.info("🫁 STEP: Processing script for natural voice...")
        logger.info(f"  Language: {language}")
        logger.info(f"  Voice: {self.voice_id}")
        
        # Step 1: Pre-process
        cleaned_script = self.preprocessor.preprocess(script, language)
        logger.info(f"  ✅ Pre-processing complete")
        
        # Step 2: Build SSML with emotions and breathing
        result = self.ssml_builder.build_ssml(cleaned_script, sections)
        
        logger.info(f"  ✅ Voice processing complete:")
        logger.info(f"     Estimated duration: {result.total_estimated_duration:.0f}s")
        logger.info(f"     Emotions detected: {', '.join(result.emotions_used)}")
        logger.info(f"     Sections: {len(result.segments)}")
        
        return result
    

    def process_section(self, section_text, section_marker, 
                        language='telugu', emotion_override=None):
        """
        Process a single section (for shorts).
        Returns SSML string.
        """
        
        # Pre-process
        cleaned = self.preprocessor.preprocess(section_text, language)
        
        # Build SSML
        ssml = self.ssml_builder.build_section_ssml(
            cleaned, section_marker, emotion_override
        )
        
        return ssml


# =============================================
# QUICK TEST
# =============================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test with Telugu text
    test_script = """
[HOOK]
మీకు తెలుసా? మన సూర్యుడు ప్రతి సెకనుకు 4 మిలియన్ టన్నుల పదార్థాన్ని శక్తిగా మారుస్తుంది!

ఇది నిజంగా అద్భుతమైన విషయం. ఈ వీడియోలో మనం అంతరిక్షం గురించి 3 ఆశ్చర్యకరమైన నిజాలు తెలుసుకుందాం.

[SECTION_1: సూర్యుడి శక్తి]
సూర్యుడు ఒక భారీ న్యూక్లియర్ రియాక్టర్. ప్రతి సెకనుకు, 600 మిలియన్ టన్నుల హైడ్రోజన్ హీలియంగా మారుతుంది.

కానీ ఆశ్చర్యకరంగా, ఈ ప్రక్రియలో 4 మిలియన్ టన్నుల పదార్థం పూర్తిగా అదృశ్యమవుతుంది!

[CTA]
ఈ విషయాలు మీకు నచ్చితే, subscribe చేయండి. ప్రతిరోజూ ఇలాంటి అద్భుతమైన facts తెస్తాం!
    """
    
    processor = BreathingProcessor(
        voice_id="te-IN-ShrutiNeural"
    )
    
    result = processor.process_script(test_script, language='telugu')
    
    print("\n" + "="*60)
    print("PROCESSED SSML (first 500 chars):")
    print("="*60)
    print(result.ssml[:500])
    print(f"\nEstimated duration: {result.total_estimated_duration:.0f}s")
    print(f"Emotions: {result.emotions_used}")
