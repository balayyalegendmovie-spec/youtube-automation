"""
VIDEO QUALITY BUILDER — Generates high-quality video and uploads to Drive.
No YouTube upload. Focus on quality only.
"""

import os
import sys
import json
import logging
import time
import random
import glob
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src import setup_pipeline_logging, github_group_start, github_group_end, github_summary


def load_config():
    import yaml
    with open("config/config.yaml", 'r') as f:
        config = yaml.safe_load(f)
    config['gemini']['api_key'] = os.environ.get('GEMINI_API_KEY', '')
    config['footage']['pexels_api_key'] = os.environ.get('PEXELS_API_KEY', '')
    return config


def run_pipeline(language):
    config = load_config()
    channel_config = config['channels'][language]
    run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = f"output/{run_id}_{language}"
    os.makedirs(output_dir, exist_ok=True)

    logger = logging.getLogger('main')
    start_time = time.time()

    logger.info(f"\n{'🎬'*20}")
    logger.info(f"   VIDEO QUALITY BUILDER")
    logger.info(f"   Language: {language.upper()}")
    logger.info(f"   Channel: {channel_config['channel_name']}")
    logger.info(f"{'🎬'*20}\n")

    results = {'run_id': run_id, 'language': language, 'steps': {},
               'uploads': [], 'errors': [], 'status': 'running'}

    long_video_path = None
    long_thumb_path = None
    shorts = []
    reviewed_script = ""
    topic_data = {}

    try:
        # STEP 1: Topics
        github_group_start("📊 STEP 1: Finding Topics")
        from src.trend_finder import TrendFinder
        from src.gemini_brain import GeminiBrain

        trends = TrendFinder().get_all_trends(
            channel_config.get('preferred_niches', ['technology'])
        )
        brain = GeminiBrain("config/config.yaml")
        niche = random.choice(channel_config.get('preferred_niches', ['technology']))
        logger.info(f"   Niche: {niche}")

        topics = brain.generate_topics(niche, language, trends[:10], count=3)
        if not topics:
            raise Exception("No topics!")

        topic_data = topics[0]
        TrendFinder().mark_topic_used(topic_data.get('topic', ''))
        logger.info(f"   ✅ Topic: {topic_data.get('topic', '')}")
        github_group_end()

        # STEP 2: Script
        github_group_start("📝 STEP 2: Writing Script")
        script = brain.generate_script(topic_data, language,
                                        config['content']['long_form']['target_words'])
        with open(f"{output_dir}/script_raw.txt", 'w', encoding='utf-8') as f:
            f.write(script)
        logger.info(f"   ✅ Script: {len(script.split())} words")
        github_group_end()

        # STEP 3: Review
        github_group_start("🔍 STEP 3: Reviewing")
        reviewed_script, review = brain.review_script(script, language,
                                                        topic_data.get('topic', ''))
        with open(f"{output_dir}/script_final.txt", 'w', encoding='utf-8') as f:
            f.write(reviewed_script)
        logger.info(f"   ✅ Score: {review.get('overall_score', 7)}/10")
        github_group_end()

        # STEP 4: Parse
        github_group_start("📋 STEP 4: Parsing Sections")
        sections = brain.parse_script_sections(reviewed_script)
        logger.info(f"   ✅ {len(sections)} sections")
        github_group_end()

        # STEP 5: Voice
        github_group_start("🎙️ STEP 5: Generating Voice")
        from src.voice_maker import VoiceMaker
        vm = VoiceMaker(language, channel_config.get('voice_gender', 'female'), config)

        full_voice = f"{output_dir}/full_voice.mp3"
        full_subs = f"{output_dir}/full_subtitles.srt"
        vm.generate_full_audio(reviewed_script, full_voice, full_subs)

        section_dir = f"{output_dir}/section_audio"
        section_audios = vm.generate_section_audios(sections, section_dir)
        logger.info(f"   ✅ {len(section_audios)} section audios")
        github_group_end()

        # STEP 6: Footage Keywords
        github_group_start("🔑 STEP 6: Footage Keywords")
        footage_kw = brain.get_footage_keywords(reviewed_script)
        logger.info(f"   ✅ {len(footage_kw)} keywords")
        github_group_end()

        # STEP 7: Video
        github_group_start("🎬 STEP 7: Creating Video")
        from src.video_animator import VideoAnimator
        animator = VideoAnimator("config/config.yaml")

        long_video_path = f"{output_dir}/long_form_video.mp4"

        bg_music = None
        music_files = glob.glob("assets/music/*.mp3")
        if music_files:
            bg_music = random.choice(music_files)

        for i, sec in enumerate(sections):
            if i < len(section_audios):
                sec['duration'] = section_audios[i]['duration']
            else:
                sec['duration'] = 30

        animator.create_anime_video(
            voice_path=full_voice, subtitle_path=full_subs,
            footage_keywords=footage_kw, sections=sections,
            language=language, channel_config=channel_config,
            output_path=long_video_path, bg_music_path=bg_music
        )

        vid_size = os.path.getsize(long_video_path) / (1024*1024)
        logger.info(f"   ✅ Video: {vid_size:.1f} MB")
        github_group_end()

        # STEP 8: Shorts
        github_group_start("✂️ STEP 8: Cutting Shorts")
        from src.shorts_cutter import ShortsCutter
        cutter = ShortsCutter("config/config.yaml")
        shorts = cutter.cut_shorts(
            section_audios, footage_kw[:5], language,
            channel_config, f"{output_dir}/shorts"
        )
        logger.info(f"   ✅ {len(shorts)} shorts")
        github_group_end()

        # STEP 9: Thumbnails
        github_group_start("🖼️ STEP 9: Thumbnails")
        from src.thumbnail_maker import ThumbnailMaker
        tm = ThumbnailMaker("config/config.yaml")

        long_meta = brain.generate_metadata(topic_data, language, "long")
        long_thumb_path = f"{output_dir}/thumbnail_long.jpg"
        tm.create_thumbnail(
            long_meta.get('thumbnail_text', topic_data.get('topic_local', '')),
            language, topic_data.get('topic', ''),
            long_thumb_path, channel_config
        )

        shorts_metadata = []
        for j, si in enumerate(shorts):
            try:
                sm = brain.generate_metadata(
                    {**topic_data, 'topic': si.get('section_title', ''),
                     'topic_local': si.get('section_title', '')},
                    language, "short"
                )
            except Exception:
                sm = {'title': si.get('section_title', f'Short {j+1}'),
                      'thumbnail_text': si.get('section_title', '')[:20],
                      'description': '', 'tags': ['#shorts']}

            st = f"{output_dir}/thumbnail_short_{j}.jpg"
            tm.create_thumbnail(
                sm.get('thumbnail_text', ''), language,
                topic_data.get('topic', ''), st, channel_config
            )
            sm['thumbnail_path'] = st
            sm['video_path'] = si['path']
            shorts_metadata.append(sm)

        logger.info(f"   ✅ {1 + len(shorts)} thumbnails")
        github_group_end()

        # STEP 10: Upload to Drive
        github_group_start("☁️ STEP 10: Uploading to Drive")
        from src.drive_uploader import DriveUploader
        drive = DriveUploader()

        short_thumbs = [f"{output_dir}/thumbnail_short_{j}.jpg"
                       for j in range(len(shorts))
                       if os.path.exists(f"{output_dir}/thumbnail_short_{j}.jpg")]

        drive_result = drive.upload_pipeline_output(
            run_id=run_id, language=language,
            topic=topic_data.get('topic', ''),
            long_video_path=long_video_path,
            shorts=shorts,
            thumbnail_long_path=long_thumb_path,
            short_thumbnails=short_thumbs,
            script_text=reviewed_script,
            output_dir=output_dir
        )

        if drive_result:
            results['drive'] = drive_result
            logger.info(f"   ☁️ {drive_result.get('folder_link', '')}")
        github_group_end()

        # SUMMARY
        total_time = time.time() - start_time
        mins = int(total_time // 60)
        secs = int(total_time % 60)

        logger.info(f"\n{'═'*60}")
        logger.info(f"   📊 VIDEO QUALITY BUILDER — SUMMARY")
        logger.info(f"{'═'*60}")
        logger.info(f"   🎯 Topic: {topic_data.get('topic', '')}")
        logger.info(f"   📝 Script: {len(reviewed_script.split())} words")
        logger.info(f"   🔍 Review: {review.get('overall_score', 7)}/10")
        logger.info(f"   🎬 Long video: {vid_size:.1f} MB")
        logger.info(f"   ✂️ Shorts: {len(shorts)}")
        logger.info(f"   🖼️ Thumbnails: {1 + len(shorts)}")

        if drive_result:
            logger.info(f"   ☁️ Drive: {drive_result.get('total_size_mb', 0):.1f} MB")
            logger.info(f"   🔗 {drive_result.get('folder_link', 'N/A')}")

        logger.info(f"   ⏱️ Time: {mins}m {secs}s")
        logger.info(f"   ✅ Status: SUCCESS")
        logger.info(f"{'═'*60}\n")

        # GitHub summary
        summary = f"""
## 🎬 Video Quality Builder — {language.upper()}

| Metric | Value |
|--------|-------|
| Topic | {topic_data.get('topic', 'N/A')} |
| Script | {len(reviewed_script.split())} words |
| Review | {review.get('overall_score', 7)}/10 |
| Video | {vid_size:.1f} MB |
| Shorts | {len(shorts)} |
| Time | {mins}m {secs}s |
"""
        if drive_result:
            summary += f"\n🔗 [Download from Drive]({drive_result.get('folder_link', '')})\n"

        github_summary(summary)

    except Exception as e:
        logger.error(f"\n❌ FAILED: {e}")

        # Try Drive backup even on failure
        try:
            from src.drive_uploader import DriveUploader
            drive = DriveUploader()
            if drive.enabled and long_video_path and os.path.exists(str(long_video_path)):
                drive.upload_pipeline_output(
                    run_id, language, topic_data.get('topic', 'failed'),
                    long_video_path=long_video_path if os.path.exists(str(long_video_path)) else None,
                    shorts=shorts, script_text=reviewed_script, output_dir=output_dir
                )
        except Exception:
            pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--language', '-l', default='telugu')
    args = parser.parse_args()

    setup_pipeline_logging()
    logger = logging.getLogger('main')
    logger.info(f"🎬 Video Quality Builder v1.0")

    run_pipeline(args.language)
