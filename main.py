"""
═══════════════════════════════════════════════════════════════
  YOUTUBE AUTOMATION — MAIN PIPELINE
  
  Complete flow:
  1.  Find trending topics
  2.  Generate topic with Gemini
  3.  Write emotional script
  4.  AI review & fix script
  5.  Generate emotional voiceover
  6.  Generate anime character images
  7.  Assemble animated long-form video
  8.  Cut into shorts
  9.  Generate thumbnails
  10. Generate metadata
  11. Upload long-form video
  12. Upload shorts
  
  Each step logged in detail for GitHub Actions visibility
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import time
import glob
import random
import shutil
import argparse
import yaml
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline_logger import PipelineLogger
from src.gemini_brain import GeminiBrain
from src.trend_finder import TrendFinder
from src.voice_maker import EmotionalVoiceMaker
from src.anime_maker import AnimeMaker
from src.video_maker import AnimatedVideoMaker
from src.thumbnail_maker import ThumbnailMaker
from src.uploader import YouTubeUploader


def run_pipeline(language: str, config_path: str = "config/config.yaml"):
    """Run complete pipeline for one language/channel"""
    
    # ─── Load Config ───
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    channel = config['channels'][language]
    run_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    output_dir = f"output/{language}_{run_id}"
    os.makedirs(output_dir, exist_ok=True)
    
    # ─── Initialize Logger ───
    log = PipelineLogger("YouTube Automation")
    log.pipeline_start(language, run_id)
    
    results = {'uploaded': [], 'errors': []}
    
    try:
        # ─── Initialize Engines ───
        brain = GeminiBrain(config_path)
        trend_finder = TrendFinder()
        voice_maker = EmotionalVoiceMaker(
            voice_id=channel['voice_id'],
            config_path=config_path
        )
        anime_maker = AnimeMaker(config_path)
        video_maker = AnimatedVideoMaker(config_path)
        thumb_maker = ThumbnailMaker(config_path)
        
        uploader = YouTubeUploader(
            channel_name=language,
            cookie_env_var=channel['cookie_env_var']
        )
        

        # ════════════════════════════════════════
        #  STEP 1: FIND TRENDING TOPICS
        # ════════════════════════════════════════
        
        with log.step(1, "Find Trending Topics", "topic"):
            trends = trend_finder.get_all_trends()
            log.detail("Sources checked", "Google Trends + Reddit + YouTube India")
            log.detail("Topics found", len(trends))
            
            for t in trends[:5]:
                log.sub_step(f"[{t['source']}] {t['topic'][:60]}")
        

        # ════════════════════════════════════════
        #  STEP 2: GENERATE VIDEO TOPIC
        # ════════════════════════════════════════
        
        with log.step(2, "Generate Video Topic (Gemini)", "topic"):
            niche = random.choice(config['content']['niches'])
            log.detail("Selected niche", niche)
            
            topics = brain.generate_topics(
                niche=niche,
                language=language,
                trending_data=trends,
                count=3
            )
            
            topic = topics[0]
            log.detail("Topic (EN)", topic['topic'])
            log.detail("Topic (Local)", topic.get('topic_local', 'N/A'))
            log.detail("Hook", topic.get('hook', 'N/A'))
            log.detail("Sections", len(topic.get('sections', [])))
            
            for s in topic.get('sections', []):
                log.sub_step(f"[{s.get('emotion', '?')}] {s.get('title', '')}")
        

        # ════════════════════════════════════════
        #  STEP 3: GENERATE EMOTIONAL SCRIPT
        # ════════════════════════════════════════
        
        with log.step(3, "Generate Emotional Script (Gemini)", "script"):
            script = brain.generate_emotional_script(
                topic_data=topic,
                language=language,
                target_words=config['content']['long_form']['target_words']
            )
            
            word_count = len(script.split())
            log.detail("Word count", word_count)
            log.detail("Est. duration", f"{word_count / 150:.1f} min")
            
            # Count markers
            emotions = len(re.findall(r'\[EMOTION:\w+\]', script))
            breaths = len(re.findall(r'\[BREATH\]', script))
            pauses = len(re.findall(r'\[PAUSE:\w+\]', script))
            scenes = len(re.findall(r'\[SCENE:.+?\]', script))
            
            log.detail("Emotion markers", emotions)
            log.detail("Breathing pauses", breaths)
            log.detail("Dramatic pauses", pauses)
            log.detail("Scene changes", scenes)
            
            # Save script
            with open(f"{output_dir}/script_raw.txt", 'w', encoding='utf-8') as f:
                f.write(script)
            
            log.sub_step(f"Script saved: {output_dir}/script_raw.txt")
        

        # ════════════════════════════════════════
        #  STEP 4: AI REVIEW & FIX SCRIPT
        # ════════════════════════════════════════
        
        import re  # ensure imported
        
        with log.step(4, "AI Review & Fix Script (Gemini)", "review"):
            reviewed_script, review = brain.review_and_fix_script(
                script=script,
                language=language,
                topic=topic['topic']
            )
            
            log.detail("Review score", f"{review.get('overall_score', '?')}/10")
            log.detail("Approved", review.get('approved', False))
            
            changes = review.get('changes_made', [])
            log.detail("Changes made", len(changes))
            for change in changes[:5]:
                log.sub_step(f"Fix: {change[:80]}")
            
            with open(f"{output_dir}/script_final.txt", 'w', encoding='utf-8') as f:
                f.write(reviewed_script)
            
            log.sub_step("Final script saved")
        

        # ════════════════════════════════════════
        #  STEP 5: PARSE SCRIPT INTO SECTIONS
        # ════════════════════════════════════════
        
        with log.step(5, "Parse Script Sections", "script"):
            sections = brain.parse_script_to_sections(reviewed_script)
            
            log.detail("Total sections", len(sections))
            
            for s in sections:
                log.sub_step(
                    f"[{s['marker']}] {s['title'][:40]} "
                    f"— emotion:{s['emotion']} — "
                    f"words:{len(s['text'].split())}"
                )
        

        # ════════════════════════════════════════
        #  STEP 6: GENERATE EMOTIONAL VOICE
        # ════════════════════════════════════════
        
        with log.step(6, "Generate Emotional Voice", "voice"):
            voice_dir = f"{output_dir}/voice"
            
            section_audios = voice_maker.generate_full_audio(
                sections=sections,
                output_path=f"{output_dir}/full_voice.mp3",
                subtitle_path=f"{output_dir}/full_subtitles.vtt",
                log_fn=log.sub_step
            )
            
            total_audio = sum(s['duration'] for s in section_audios)
            log.detail("Total audio duration", f"{total_audio:.1f}s ({total_audio/60:.1f}min)")
            log.detail("Sections generated", len(section_audios))
            
            for sa in section_audios:
                log.sub_step(
                    f"Section {sa['section_marker']}: "
                    f"{sa['duration']:.1f}s [{sa['emotion']}]"
                )
        

        # ════════════════════════════════════════
        #  STEP 7: GENERATE ANIME IMAGES
        # ════════════════════════════════════════
        
        with log.step(7, "Generate Anime Character Images", "anime"):
            # Get scene descriptions from Gemini
            log.sub_step("Getting scene descriptions from Gemini...")
            scene_descs = brain.get_scene_descriptions(reviewed_script)
            log.detail("Scene descriptions", len(scene_descs))
            
            # Generate anime images
            anime_dir = f"{output_dir}/anime"
            scene_images = anime_maker.generate_scene_images(
                scenes=scene_descs,
                character_config_path=channel['character_config'],
                output_dir=anime_dir,
                log_fn=log.sub_step
            )
            
            log.detail("Images generated", len(scene_images))
            total_images = sum(
                1 + len(s.get('alt_images', [])) for s in scene_images
            )
            log.detail("Total image files", total_images)
        

        # ════════════════════════════════════════
        #  STEP 8: ASSEMBLE LONG-FORM VIDEO
        # ════════════════════════════════════════
        
        with log.step(8, "Assemble Long-form Video", "video"):
            long_video_path = f"{output_dir}/long_video.mp4"
            
            # Find background music
            bg_music = None
            music_files = glob.glob("assets/music/*.mp3")
            if music_files:
                bg_music = random.choice(music_files)
                log.detail("Background music", os.path.basename(bg_music))
            
            # Ensure we have enough scene images for sections
            while len(scene_images) < len(section_audios):
                scene_images.append(scene_images[-1] if scene_images else {
                    'main_image': None,
                    'alt_images': []
                })
            
            video_maker.create_long_video(
                section_audios=section_audios,
                scene_images=scene_images[:len(section_audios)],
                bg_music_path=bg_music,
                output_path=long_video_path,
                language=language,
                font_path=channel.get('font'),
                log_fn=log.sub_step
            )
            
            # Get file size
            size_mb = os.path.getsize(long_video_path) / (1024 * 1024)
            log.detail("Video file size", f"{size_mb:.1f} MB")
            log.detail("Output", long_video_path)
        

        # ════════════════════════════════════════
        #  STEP 9: CUT SHORTS FROM SECTIONS
        # ════════════════════════════════════════
        
        with log.step(9, "Cut Shorts from Sections", "shorts"):
            shorts_dir = f"{output_dir}/shorts"
            os.makedirs(shorts_dir, exist_ok=True)
            
            shorts = []
            short_count = 0
            
            for i, (audio, scene) in enumerate(
                zip(section_audios, scene_images[:len(section_audios)])
            ):
                if not audio.get('is_short', True):
                    log.sub_step(f"Skipping {audio['section_marker']} (CTA)")
                    continue
                
                if audio['duration'] < config['content']['shorts']['min_duration_seconds']:
                    log.sub_step(f"Skipping {audio['section_marker']} (too short: {audio['duration']:.0f}s)")
                    continue
                
                short_path = f"{shorts_dir}/short_{short_count:02d}.mp4"
                
                try:
                    video_maker.create_short_video(
                        audio_path=audio['audio_path'],
                        main_image_path=scene['main_image'],
                        alt_images=scene.get('alt_images', []),
                        duration=audio['duration'],
                        emotion=audio['emotion'],
                        language=language,
                        section_title=audio['section_title'],
                        channel_name=channel['name'],
                        output_path=short_path,
                        log_fn=log.sub_step
                    )
                    
                    shorts.append({
                        'path': short_path,
                        'title': audio['section_title'],
                        'duration': audio['duration'],
                        'emotion': audio['emotion'],
                        'text': audio.get('text', '')
                    })
                    short_count += 1
                    
                    log.progress(short_count, len(section_audios) - 1, audio['section_title'][:30])
                    
                except Exception as e:
                    log.log(f"Short {i} failed: {e}", 'warning')
            
            log.detail("Shorts created", len(shorts))
        

        # ════════════════════════════════════════
        #  STEP 10: GENERATE THUMBNAILS + METADATA
        # ════════════════════════════════════════
        
        with log.step(10, "Generate Thumbnails & Metadata", "thumbnail"):
            # Long-form metadata
            log.sub_step("Generating long-form metadata...")
            long_meta = brain.generate_metadata(
                topic_data=topic,
                language=language,
                video_type="long"
            )
            log.detail("Long title", long_meta.get('title', 'N/A')[:60])
            
            # Long-form thumbnail
            thumb_bg = scene_images[0]['main_image'] if scene_images else None
            long_thumb = f"{output_dir}/thumbnail_long.jpg"
            
            thumb_maker.create_thumbnail(
                text=long_meta.get('thumbnail_text', topic.get('topic_local', topic['topic'])),
                scene_image_path=thumb_bg,
                output_path=long_thumb,
                log_fn=log.sub_step
            )
            
            # Shorts metadata
            shorts_meta = []
            for i, short in enumerate(shorts):
                s_meta = brain.generate_metadata(
                    topic_data={**topic, 'topic': short['title'], 'topic_local': short['title']},
                    language=language,
                    video_type="short"
                )
                s_meta['video_path'] = short['path']
                shorts_meta.append(s_meta)
                log.sub_step(f"Short {i+1} metadata: {s_meta.get('title', '?')[:50]}")
            
            log.detail("Thumbnails created", 1)
            log.detail("Metadata generated", 1 + len(shorts_meta))
        

        # ════════════════════════════════════════
        #  STEP 11: UPLOAD LONG-FORM VIDEO
        # ════════════════════════════════════════
        
        with log.step(11, f"Upload Long Video ({language.upper()})", "upload"):
            try:
                long_url = uploader.upload(
                    video_path=long_video_path,
                    title=long_meta['title'],
                    description=long_meta.get('description', ''),
                    tags=long_meta.get('tags', []),
                    thumbnail_path=long_thumb,
                    log_fn=log.sub_step
                )
                
                results['uploaded'].append({
                    'type': 'long_form',
                    'url': long_url,
                    'title': long_meta['title']
                })
                
                log.detail("Video URL", long_url)
                
            except Exception as e:
                log.log(f"Long video upload failed: {e}", 'error')
                results['errors'].append(f"Long upload: {e}")
            
            # Delay before shorts
            log.sub_step("Waiting 30s before shorts upload...")
            time.sleep(30)
        

        # ════════════════════════════════════════
        #  STEP 12: UPLOAD SHORTS
        # ════════════════════════════════════════
        
        with log.step(12, f"Upload Shorts ({language.upper()})", "upload"):
            long_url = results['uploaded'][0]['url'] if results['uploaded'] else ''
            
            for i, s_meta in enumerate(shorts_meta):
                log.progress(i + 1, len(shorts_meta), f"Short {i+1}")
                
                try:
                    # Add long video reference
                    desc = s_meta.get('description', '')
                    if long_url:
                        full_vid_text = {
                            'telugu': 'పూర్తి వీడియో',
                            'hindi': 'पूरा वीडियो'
                        }.get(language, 'Full video')
                        desc += f"\n\n{full_vid_text}: {long_url}"
                    
                    short_url = uploader.upload(
                        video_path=s_meta['video_path'],
                        title=s_meta['title'],
                        description=desc,
                        tags=s_meta.get('tags', []),
                        log_fn=log.sub_step
                    )
                    
                    results['uploaded'].append({
                        'type': 'short',
                        'url': short_url,
                        'title': s_meta['title']
                    })
                    
                    log.sub_step(f"Short {i+1} uploaded: {short_url}")
                    
                    # Delay between shorts (avoid spam detection)
                    if i < len(shorts_meta) - 1:
                        wait = random.randint(45, 90)
                        log.sub_step(f"Waiting {wait}s before next upload...")
                        time.sleep(wait)
                    
                except Exception as e:
                    log.log(f"Short {i+1} upload failed: {e}", 'warning')
                    results['errors'].append(f"Short {i+1}: {e}")
            
            log.detail("Shorts uploaded", 
                       len([v for v in results['uploaded'] if v['type'] == 'short']))
        

        # ════════════════════════════════════════
        #  CLEANUP & SUMMARY
        # ════════════════════════════════════════
        
        if not config['output'].get('keep_temp', False):
            try:
                for d in ['voice', 'anime']:
                    path = os.path.join(output_dir, d)
                    if os.path.exists(path):
                        shutil.rmtree(path)
            except Exception:
                pass
        
        # Save results log
        results_log = {
            'run_id': run_id,
            'timestamp': datetime.utcnow().isoformat(),
            'language': language,
            'topic': topic['topic'],
            'topic_local': topic.get('topic_local', ''),
            'review_score': review.get('overall_score', 0),
            'uploaded': results['uploaded'],
            'errors': results['errors'],
            'status': 'success' if results['uploaded'] else 'partial'
        }
        
        log_dir = "output/logs"
        os.makedirs(log_dir, exist_ok=True)
        with open(f"{log_dir}/history.jsonl", 'a', encoding='utf-8') as f:
            f.write(json.dumps(results_log, ensure_ascii=False) + '\n')
        
        log.pipeline_end(results)
        return results_log
        
    except Exception as e:
        log.pipeline_error(e)
        
        # Save error log
        error_log = {
            'run_id': run_id,
            'timestamp': datetime.utcnow().isoformat(),
            'language': language,
            'status': 'failed',
            'error': str(e)
        }
        
        log_dir = "output/logs"
        os.makedirs(log_dir, exist_ok=True)
        with open(f"{log_dir}/history.jsonl", 'a') as f:
            f.write(json.dumps(error_log) + '\n')
        
        raise


# ════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='YouTube Automation Pipeline')
    parser.add_argument('--language', '-l', required=True,
                       choices=['telugu', 'hindi'],
                       help='Channel language to process')
    parser.add_argument('--config', '-c', default='config/config.yaml',
                       help='Config file path')
    
    args = parser.parse_args()
    
    result = run_pipeline(args.language, args.config)
    
    # Exit code
    if result.get('status') == 'failed':
        sys.exit(1)
    else:
        sys.exit(0)
