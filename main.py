"""
MAIN PIPELINE — Complete YouTube Automation Orchestrator

Runs the full pipeline with DETAILED LOGGING for GitHub Actions:
- Every step clearly shows what's happening
- Progress indicators and timing
- Error handling with screenshots
- Summary report at the end

Usage:
    python main.py --language telugu
    python main.py --language hindi  
    python main.py --language all
    python main.py --language telugu --test
"""

import os
import sys
import json
import logging
import time
import random
import glob
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import setup_pipeline_logging, github_group_start, github_group_end, github_summary


def load_config():
    """Load and process config with environment variable substitution"""
    import yaml
    
    with open("config/config.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    # Substitute environment variables
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    pexels_key = os.environ.get('PEXELS_API_KEY', '')
    
    config['gemini']['api_key'] = gemini_key
    config['footage']['pexels_api_key'] = pexels_key
    
    return config


class YouTubeAutomationPipeline:
    
    def __init__(self):
        self.config = load_config()
        self.logger = logging.getLogger('main')
        self.log_file = "output/logs/upload_history.jsonl"
        self.start_time = None
    

    def run(self, language):
        """Run complete pipeline for one language"""
        
        self.start_time = time.time()
        channel_config = self.config['channels'][language]
        run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Check if channel is enabled
        if not channel_config.get('enabled', True):
            self.logger.info(f"⏭️ {language.upper()} channel is disabled. Skipping.")
            return None
        
        self.logger.info(f"\n{'🚀'*20}")
        self.logger.info(f"   PIPELINE START: {language.upper()} CHANNEL")
        self.logger.info(f"   Run ID: {run_id}")
        self.logger.info(f"   Channel: {channel_config['channel_name']}")
        self.logger.info(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
        self.logger.info(f"{'🚀'*20}\n")
        
        output_dir = f"output/{run_id}_{language}"
        os.makedirs(output_dir, exist_ok=True)
        
        results = {
            'run_id': run_id,
            'language': language,
            'channel': channel_config['channel_name'],
            'started_at': datetime.now().isoformat(),
            'steps': {},
            'uploads': [],
            'errors': [],
        }
        
        try:
            # ════════════════════════════════════════
            # STEP 1: FIND TRENDING TOPIC
            # ════════════════════════════════════════
            github_group_start("📊 STEP 1: Finding Trending Topics")
            step_start = time.time()
            
            from src.trend_finder import TrendFinder
            trend_finder = TrendFinder()
            
            niches = channel_config.get('preferred_niches', ['technology'])
            trends = trend_finder.get_all_trends(niches)
            
            from src.gemini_brain import GeminiBrain
            brain = GeminiBrain("config/config.yaml")
            
            niche = random.choice(niches)
            self.logger.info(f"   Selected niche: {niche}")
            
            topics = brain.generate_topics(
                niche=niche,
                language=language,
                trend_data=trends[:10],
                count=3
            )
            
            if not topics:
                raise Exception("No topics generated!")
            
            topic_data = topics[0]
            trend_finder.mark_topic_used(topic_data.get('topic', ''))
            
            step_time = time.time() - step_start
            results['steps']['find_topic'] = {
                'status': 'success',
                'topic': topic_data.get('topic', ''),
                'time_seconds': round(step_time, 1)
            }
            self.logger.info(f"   ⏱️ Step 1 completed in {step_time:.1f}s")
            github_group_end()
            
            
            # ════════════════════════════════════════
            # STEP 2: GENERATE SCRIPT
            # ════════════════════════════════════════
            github_group_start("📝 STEP 2: Generating Script")
            step_start = time.time()
            
            script = brain.generate_script(
                topic_data=topic_data,
                language=language,
                target_words=self.config['content']['long_form']['target_words']
            )
            
            with open(f"{output_dir}/script_raw.txt", 'w', encoding='utf-8') as f:
                f.write(script)
            
            step_time = time.time() - step_start
            results['steps']['generate_script'] = {
                'status': 'success',
                'word_count': len(script.split()),
                'time_seconds': round(step_time, 1)
            }
            self.logger.info(f"   ⏱️ Step 2 completed in {step_time:.1f}s")
            github_group_end()
            
            
            # ════════════════════════════════════════
            # STEP 3: AI REVIEW SCRIPT
            # ════════════════════════════════════════
            github_group_start("🔍 STEP 3: AI Reviewing Script")
            step_start = time.time()
            
            reviewed_script, review = brain.review_script(
                script=script,
                language=language,
                topic=topic_data.get('topic', '')
            )
            
            with open(f"{output_dir}/script_final.txt", 'w', encoding='utf-8') as f:
                f.write(reviewed_script)
            with open(f"{output_dir}/review.json", 'w', encoding='utf-8') as f:
                json.dump(review, f, indent=2, ensure_ascii=False)
            
            step_time = time.time() - step_start
            results['steps']['review_script'] = {
                'status': 'success',
                'score': review.get('overall_score', 0),
                'approved': review.get('approved', False),
                'time_seconds': round(step_time, 1)
            }
            github_group_end()
            
            
            # ════════════════════════════════════════
            # STEP 4: PARSE SECTIONS
            # ════════════════════════════════════════
            github_group_start("📋 STEP 4: Parsing Script Sections")
            
            sections = brain.parse_script_sections(reviewed_script)
            
            results['steps']['parse_sections'] = {
                'status': 'success',
                'section_count': len(sections)
            }
            github_group_end()
            
            
            # ════════════════════════════════════════
            # STEP 5: GENERATE VOICE
            # ════════════════════════════════════════
            github_group_start("🎙️ STEP 5: Generating Voiceover")
            step_start = time.time()
            
            from src.voice_maker import VoiceMaker
            voice_maker = VoiceMaker(
                language=language,
                gender=channel_config.get('voice_gender', 'female'),
                config=self.config
            )
            
            # Full audio for long-form
            full_voice_path = f"{output_dir}/full_voice.mp3"
            full_subtitle_path = f"{output_dir}/full_subtitles.vtt"
            
            voice_maker.generate_full_audio(
                script=reviewed_script,
                output_path=full_voice_path,
                subtitle_path=full_subtitle_path
            )
            
            # Section audio for shorts
            section_audio_dir = f"{output_dir}/section_audio"
            section_audios = voice_maker.generate_section_audios(
                sections=sections,
                output_dir=section_audio_dir
            )
            
            step_time = time.time() - step_start
            results['steps']['generate_voice'] = {
                'status': 'success',
                'sections_generated': len(section_audios),
                'time_seconds': round(step_time, 1)
            }
            github_group_end()
            
            
            # ════════════════════════════════════════
            # STEP 6: GET FOOTAGE KEYWORDS
            # ════════════════════════════════════════
            github_group_start("🔑 STEP 6: Extracting Footage Keywords")
            
            footage_keywords = brain.get_footage_keywords(reviewed_script)
            
            results['steps']['footage_keywords'] = {
                'status': 'success',
                'keyword_count': len(footage_keywords)
            }
            github_group_end()
            
            
            # ════════════════════════════════════════
            # STEP 7: CREATE ANIME VIDEO
            # ════════════════════════════════════════
            github_group_start("🎬 STEP 7: Creating Anime-Style Long Video")
            step_start = time.time()
            
            from src.video_animator import VideoAnimator
            animator = VideoAnimator("config/config.yaml")
            
            long_video_path = f"{output_dir}/long_form_video.mp4"
            
            bg_music = None
            music_files = glob.glob("assets/music/*.mp3")
            if music_files:
                bg_music = random.choice(music_files)
            
            # Add duration info to sections
            for i, section in enumerate(sections):
                if i < len(section_audios):
                    section['duration'] = section_audios[i]['duration']
                else:
                    section['duration'] = 30
            
            animator.create_anime_video(
                voice_path=full_voice_path,
                subtitle_path=full_subtitle_path,
                footage_keywords=footage_keywords,
                sections=sections,
                language=language,
                channel_config=channel_config,
                output_path=long_video_path,
                bg_music_path=bg_music
            )
            
            step_time = time.time() - step_start
            results['steps']['create_long_video'] = {
                'status': 'success',
                'file_size_mb': round(os.path.getsize(long_video_path)/(1024*1024), 1),
                'time_seconds': round(step_time, 1)
            }
            github_group_end()
            
            
            # ════════════════════════════════════════
            # STEP 8: CUT SHORTS
            # ════════════════════════════════════════
            github_group_start("✂️ STEP 8: Cutting Anime Shorts")
            step_start = time.time()
            
            from src.shorts_cutter import ShortsCutter
            cutter = ShortsCutter("config/config.yaml")
            
            shorts_dir = f"{output_dir}/shorts"
            
            # Get footage file paths for shorts
            footage_paths = []
            footage_cache = f"{output_dir}/footage_cache"
            if os.path.exists(footage_cache):
                footage_paths = glob.glob(f"{footage_cache}/*.mp4")
            
            shorts = cutter.cut_shorts(
                section_audios=section_audios,
                footage_clips=footage_paths if footage_paths else footage_keywords[:5],
                language=language,
                channel_config=channel_config,
                output_dir=shorts_dir
            )
            
            step_time = time.time() - step_start
            results['steps']['cut_shorts'] = {
                'status': 'success',
                'shorts_created': len(shorts),
                'time_seconds': round(step_time, 1)
            }
            github_group_end()
            
            
            # ════════════════════════════════════════
            # STEP 9: GENERATE THUMBNAILS
            # ════════════════════════════════════════
            github_group_start("🖼️ STEP 9: Generating Anime Thumbnails")
            step_start = time.time()
            
            from src.thumbnail_maker import ThumbnailMaker
            thumb_maker = ThumbnailMaker("config/config.yaml")
            
            # Long-form metadata + thumbnail
            long_metadata = brain.generate_metadata(topic_data, language, "long")
            
            long_thumb_path = f"{output_dir}/thumbnail_long.jpg"
            thumb_maker.create_thumbnail(
                text=long_metadata.get('thumbnail_text', topic_data.get('topic_local', '')),
                language=language,
                background_query=topic_data.get('topic', 'technology'),
                output_path=long_thumb_path,
                channel_config=channel_config
            )
            
            # Shorts metadata + thumbnails
            shorts_metadata = []
            for j, short_info in enumerate(shorts):
                short_topic = {
                    **topic_data,
                    'topic': short_info.get('section_title', ''),
                    'topic_local': short_info.get('section_title', '')
                }
                
                short_meta = brain.generate_metadata(short_topic, language, "short")
                
                short_thumb = f"{output_dir}/thumbnail_short_{j}.jpg"
                thumb_maker.create_thumbnail(
                    text=short_meta.get('thumbnail_text', ''),
                    language=language,
                    background_query=topic_data.get('topic', ''),
                    output_path=short_thumb,
                    channel_config=channel_config
                )
                
                short_meta['thumbnail_path'] = short_thumb
                short_meta['video_path'] = short_info['path']
                shorts_metadata.append(short_meta)
            
            step_time = time.time() - step_start
            results['steps']['thumbnails'] = {
                'status': 'success',
                'thumbnails_created': 1 + len(shorts),
                'time_seconds': round(step_time, 1)
            }
            github_group_end()
            
            
            # ════════════════════════════════════════
            # STEP 10: UPLOAD TO YOUTUBE
            # ════════════════════════════════════════
            github_group_start("📤 STEP 10: Uploading to YouTube")
            step_start = time.time()
            
            from src.uploader import YouTubeUploader
            uploader = YouTubeUploader(
                cookie_file=channel_config['cookie_file'],
                channel_name=channel_config['channel_name']
            )
            
            uploaded = []
            
            # Upload long-form
            self.logger.info(f"\n   📤 Uploading long-form video...")
            try:
                long_url = uploader.upload(
                    video_path=long_video_path,
                    title=long_metadata.get('title', f'{topic_data["topic"]}'),
                    description=long_metadata.get('description', ''),
                    tags=long_metadata.get('tags', []),
                    thumbnail_path=long_thumb_path,
                    is_short=False
                )
                
                uploaded.append({
                    'type': 'long_form',
                    'url': long_url,
                    'title': long_metadata.get('title', '')
                })
                
            except Exception as e:
                self.logger.error(f"   ❌ Long-form upload failed: {e}")
                results['errors'].append(f"Long-form upload: {str(e)}")
            
            # Upload shorts with gaps
            for j, (short_meta, short_info) in enumerate(zip(shorts_metadata, shorts)):
                self.logger.info(f"\n   📤 Uploading short {j+1}/{len(shorts)}...")
                
                # Wait between uploads
                wait_time = random.randint(30, 90)
                self.logger.info(f"   ⏳ Waiting {wait_time}s before next upload...")
                time.sleep(wait_time)
                
                try:
                    desc = short_meta.get('description', '')
                    if uploaded:
                        desc += f"\n\n▶ Full video: {uploaded[0].get('url', '')}"
                    
                    short_url = uploader.upload(
                        video_path=short_meta['video_path'],
                        title=short_meta.get('title', f'Short {j+1}'),
                        description=desc,
                        tags=short_meta.get('tags', []),
                        thumbnail_path=short_meta.get('thumbnail_path'),
                        is_short=True
                    )
                    
                    uploaded.append({
                        'type': 'short',
                        'url': short_url,
                        'title': short_meta.get('title', '')
                    })
                    
                except Exception as e:
                    self.logger.error(f"   ❌ Short {j+1} upload failed: {e}")
                    results['errors'].append(f"Short {j+1}: {str(e)}")
            
            step_time = time.time() - step_start
            results['steps']['upload'] = {
                'status': 'success',
                'long_uploaded': len([u for u in uploaded if u['type'] == 'long_form']),
                'shorts_uploaded': len([u for u in uploaded if u['type'] == 'short']),
                'time_seconds': round(step_time, 1)
            }
            results['uploads'] = uploaded
            github_group_end()
            
            
            # ════════════════════════════════════════
            # SUMMARY
            # ════════════════════════════════════════
            total_time = time.time() - self.start_time
            results['completed_at'] = datetime.now().isoformat()
            results['total_time_seconds'] = round(total_time, 1)
            results['status'] = 'success'
            
            # Save log
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(results, ensure_ascii=False) + '\n')
            
            # Print summary
            self._print_summary(results, language)
            
            # GitHub Actions summary
            self._write_github_summary(results, language)
            
            # Cleanup temp files
            if not self.config['output'].get('keep_temp_files', False):
                self._cleanup(output_dir)
            
            return results
            
        except Exception as e:
            total_time = time.time() - self.start_time
            self.logger.error(f"\n{'❌'*20}")
            self.logger.error(f"   PIPELINE FAILED: {e}")
            self.logger.error(f"   Time elapsed: {total_time:.0f}s")
            self.logger.error(f"{'❌'*20}")
            
            results['status'] = 'failed'
            results['error'] = str(e)
            results['total_time_seconds'] = round(total_time, 1)
            
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(results) + '\n')
            
            return results
    

    def _print_summary(self, results, language):
        """Print beautiful summary"""
        
        total_time = results.get('total_time_seconds', 0)
        minutes = int(total_time // 60)
        seconds = int(total_time % 60)
        
        self.logger.info(f"\n{'═'*60}")
        self.logger.info(f"   📊 PIPELINE SUMMARY — {language.upper()}")
        self.logger.info(f"{'═'*60}")
        self.logger.info(f"   🎯 Topic: {results['steps'].get('find_topic', {}).get('topic', 'N/A')}")
        self.logger.info(f"   📝 Script: {results['steps'].get('generate_script', {}).get('word_count', 0)} words")
        self.logger.info(f"   🔍 Review: {results['steps'].get('review_script', {}).get('score', 0)}/10")
        self.logger.info(f"   🎬 Long video: {'✅' if results['steps'].get('create_long_video', {}).get('status') == 'success' else '❌'}")
        self.logger.info(f"   ✂️ Shorts: {results['steps'].get('cut_shorts', {}).get('shorts_created', 0)} created")
        self.logger.info(f"   📤 Uploaded: {len(results.get('uploads', []))} videos")
        
        if results.get('errors'):
            self.logger.info(f"   ⚠️ Errors: {len(results['errors'])}")
            for err in results['errors']:
                self.logger.info(f"      → {err[:80]}")
        
        self.logger.info(f"   ⏱️ Total time: {minutes}m {seconds}s")
        self.logger.info(f"   ✅ Status: {results.get('status', 'unknown').upper()}")
        self.logger.info(f"{'═'*60}\n")
    

    def _write_github_summary(self, results, language):
        """Write GitHub Actions job summary"""
        
        uploads = results.get('uploads', [])
        long_vids = [u for u in uploads if u['type'] == 'long_form']
        short_vids = [u for u in uploads if u['type'] == 'short']
        
        summary = f"""
## 🎬 YouTube Automation — {language.upper()} Channel

| Metric | Value |
|--------|-------|
| Topic | {results['steps'].get('find_topic', {}).get('topic', 'N/A')} |
| Script Quality | {results['steps'].get('review_script', {}).get('score', 0)}/10 |
| Long Videos | {len(long_vids)} uploaded |
| Shorts | {len(short_vids)} uploaded |
| Total Time | {results.get('total_time_seconds', 0):.0f}s |
| Status | {'✅ Success' if results.get('status') == 'success' else '❌ Failed'} |

### Uploaded Videos
"""
        for u in uploads:
            emoji = '🎥' if u['type'] == 'long_form' else '📱'
            summary += f"- {emoji} [{u.get('title', 'Video')[:50]}]({u.get('url', '#')})\n"
        
        if results.get('errors'):
            summary += "\n### ⚠️ Errors\n"
            for err in results['errors']:
                summary += f"- {err[:100]}\n"
        
        github_summary(summary)
    

    def _cleanup(self, output_dir):
        """Clean up temporary files"""
        
        import shutil
        
        dirs_to_clean = [
            os.path.join(output_dir, 'section_audio'),
            os.path.join(output_dir, 'footage_cache'),
        ]
        
        for d in dirs_to_clean:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d)
                except Exception:
                    pass
        
        self.logger.info("   🧹 Temp files cleaned")
    

    def run_all(self):
        """Run pipeline for all enabled channels"""
        
        all_results = []
        
        for language in self.config['channels']:
            if self.config['channels'][language].get('enabled', True):
                self.logger.info(f"\n{'🚀'*5} Starting {language.upper()} channel {'🚀'*5}")
                
                result = self.run(language)
                all_results.append(result)
                
                # Wait between channels
                wait = random.randint(60, 180)
                self.logger.info(f"\n⏳ Waiting {wait}s before next channel...\n")
                time.sleep(wait)
        
        return all_results


# ════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='YouTube Automation Pipeline')
    parser.add_argument('--language', '-l', choices=['telugu', 'hindi', 'all'],
                        default='all', help='Language to process')
    parser.add_argument('--test', action='store_true',
                        help='Test mode (skip upload)')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_pipeline_logging()
    logger = logging.getLogger('main')
    
    logger.info(f"\n{'='*60}")
    logger.info(f"   🤖 YOUTUBE AUTOMATION BOT v2.0")
    logger.info(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"   Language: {args.language}")
    logger.info(f"   Mode: {'TEST' if args.test else 'PRODUCTION'}")
    logger.info(f"{'='*60}\n")
    
    pipeline = YouTubeAutomationPipeline()
    
    if args.language == 'all':
        pipeline.run_all()
    else:
        pipeline.run(args.language)
