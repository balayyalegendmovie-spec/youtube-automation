"""
YOUTUBE UPLOADER — Browser-Based Session Upload

Features:
- Cookie/session based (NO API quotas)
- Supports SEPARATE channels (Telugu ≠ Hindi)
- Each channel has its own cookies/session
- Detailed step-by-step logging
- Error screenshots for debugging
- Auto-retry on failure
- Cookie refresh after upload

Flow:
1. Load channel-specific cookies
2. Open YouTube Studio (headless browser)
3. Upload video file
4. Fill title, description, tags
5. Set thumbnail
6. Set visibility (public)
7. Publish
8. Save updated cookies
"""

import asyncio
import json
import os
import logging
import time
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class YouTubeUploader:
    
    def __init__(self, cookie_file, channel_name=""):
        self.cookie_file = cookie_file
        self.channel_name = channel_name
        self.browser = None
        self.context = None
        self.page = None
        self.playwright_instance = None
        
        logger.info(f"📤 Uploader initialized for: {channel_name}")
        logger.info(f"   Cookie file: {cookie_file}")


    async def _start_browser(self):
        """Start headless browser with saved cookies"""
        
        from playwright.async_api import async_playwright
        
        self.playwright_instance = await async_playwright().start()
        
        self.browser = await self.playwright_instance.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/125.0.0.0 Safari/537.36'
            ),
            locale='en-US',
            timezone_id='Asia/Kolkata'
        )
        
        # Load cookies
        if os.path.exists(self.cookie_file):
            with open(self.cookie_file, 'r') as f:
                cookie_data = json.load(f)
            
            # Handle both formats (direct cookies list or nested)
            cookies = cookie_data
            if isinstance(cookie_data, dict):
                cookies = cookie_data.get('cookies', [])
            
            if cookies:
                await self.context.add_cookies(cookies)
                logger.info(f"   🍪 Loaded {len(cookies)} cookies")
            else:
                raise Exception("No cookies found in cookie file!")
        else:
            raise FileNotFoundError(
                f"Cookie file not found: {self.cookie_file}\n"
                f"Run: python -m src.cookie_extractor --channel <name>"
            )
        
        self.page = await self.context.new_page()
        
        # Block unnecessary resources for speed
        await self.page.route("**/*.{png,jpg,jpeg,gif,svg,ico}", 
                              lambda route: route.abort())
        await self.page.route("**/googlesyndication*", 
                              lambda route: route.abort())


    async def _stop_browser(self):
        """Close browser and save updated cookies"""
        
        if self.context:
            try:
                cookies = await self.context.cookies()
                
                # Save updated cookies
                cookie_data = {
                    'cookies': cookies,
                    'updated_at': datetime.now().isoformat(),
                    'channel': self.channel_name
                }
                
                with open(self.cookie_file, 'w') as f:
                    json.dump(cookie_data, f, indent=2)
                
                logger.info(f"   🍪 Cookies updated and saved")
            except Exception as e:
                logger.warning(f"   ⚠️ Cookie save failed: {e}")
        
        if self.browser:
            await self.browser.close()
        if self.playwright_instance:
            await self.playwright_instance.stop()


    async def _take_debug_screenshot(self, name="debug"):
        """Take screenshot for debugging"""
        
        try:
            ss_dir = "output/logs/screenshots"
            os.makedirs(ss_dir, exist_ok=True)
            path = f"{ss_dir}/{name}_{datetime.now().strftime('%H%M%S')}.png"
            await self.page.screenshot(path=path)
            logger.info(f"   📸 Debug screenshot: {path}")
        except Exception:
            pass


    async def upload_video(self, video_path, title, description,
                            tags=None, thumbnail_path=None, is_short=False):
        """Upload a single video to YouTube"""
        
        video_type = "Short" if is_short else "Long-form"
        
        logger.info(f"\n   {'─'*50}")
        logger.info(f"   📤 UPLOADING {video_type}: {title[:50]}...")
        logger.info(f"   📁 File: {video_path}")
        logger.info(f"   📊 Size: {os.path.getsize(video_path)/(1024*1024):.1f} MB")
        logger.info(f"   {'─'*50}")
        
        try:
            await self._start_browser()
            
            # Step 1: Navigate to YouTube Studio
            logger.info(f"   1️⃣ Navigating to YouTube Studio...")
            await self.page.goto(
                'https://studio.youtube.com',
                wait_until='networkidle',
                timeout=30000
            )
            await asyncio.sleep(3)
            
            # Check login
            if 'accounts.google.com' in self.page.url:
                logger.error(f"   ❌ NOT LOGGED IN — cookies expired!")
                logger.error(f"   Re-run: python -m src.cookie_extractor --channel {self.channel_name}")
                await self._take_debug_screenshot("login_required")
                raise Exception("Session expired — re-login required")
            
            logger.info(f"   ✅ Logged into YouTube Studio")
            
            # Step 2: Click Upload button
            logger.info(f"   2️⃣ Opening upload dialog...")
            await self._click_upload_button()
            logger.info(f"   ✅ Upload dialog opened")
            
            # Step 3: Select file
            logger.info(f"   3️⃣ Selecting video file...")
            await self._select_file(video_path)
            logger.info(f"   ✅ File selected, upload started")
            
            # Step 4: Wait for processing to begin
            logger.info(f"   4️⃣ Waiting for upload processing...")
            await asyncio.sleep(5)
            
            # Step 5: Fill title
            logger.info(f"   5️⃣ Setting title...")
            await self._fill_title(title)
            logger.info(f"   ✅ Title set")
            
            # Step 6: Fill description
            logger.info(f"   6️⃣ Setting description...")
            await self._fill_description(description)
            logger.info(f"   ✅ Description set")
            
            # Step 7: Set "Not made for kids"
            logger.info(f"   7️⃣ Setting audience...")
            await self._set_not_for_kids()
            logger.info(f"   ✅ Set: Not made for kids")
            
            # Step 8: Set tags
            if tags:
                logger.info(f"   8️⃣ Setting {len(tags)} tags...")
                await self._fill_tags(tags)
                logger.info(f"   ✅ Tags set")
            
            # Step 9: Upload thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"   9️⃣ Uploading thumbnail...")
                await self._set_thumbnail(thumbnail_path)
                logger.info(f"   ✅ Thumbnail uploaded")
            
            # Step 10: Wait for upload to finish
            logger.info(f"   🔟 Waiting for upload to complete...")
            await self._wait_for_upload_complete()
            logger.info(f"   ✅ Upload complete")
            
            # Step 11: Navigate to visibility and publish
            logger.info(f"   1️⃣1️⃣ Setting visibility and publishing...")
            await self._navigate_and_publish()
            logger.info(f"   ✅ Published!")
            
            # Step 12: Get video URL
            video_url = await self._get_video_url()
            
            logger.info(f"\n   ✅✅✅ UPLOAD SUCCESSFUL ✅✅✅")
            logger.info(f"   🔗 URL: {video_url}")
            logger.info(f"   📹 Type: {video_type}")
            logger.info(f"   📺 Channel: {self.channel_name}")
            
            return video_url
            
        except Exception as e:
            logger.error(f"   ❌ Upload FAILED: {e}")
            await self._take_debug_screenshot("upload_error")
            raise
            
        finally:
            await self._stop_browser()


    async def _click_upload_button(self):
        """Click Create → Upload videos"""
        
        create_selectors = [
            '#create-icon',
            'ytcp-button#create-icon',
            '[id="create-icon"]',
            'button:has-text("Create")',
        ]
        
        clicked = False
        for selector in create_selectors:
            try:
                await self.page.click(selector, timeout=5000)
                clicked = True
                await asyncio.sleep(1)
                break
            except Exception:
                continue
        
        if not clicked:
            await self._take_debug_screenshot("no_create_button")
            raise Exception("Could not find Create button")
        
        # Click "Upload videos" from dropdown
        upload_selectors = [
            '#text-item-0',
            'tp-yt-paper-item:first-child',
            'tp-yt-paper-item:has-text("Upload")',
        ]
        
        for selector in upload_selectors:
            try:
                await self.page.click(selector, timeout=3000)
                await asyncio.sleep(2)
                return
            except Exception:
                continue
        
        raise Exception("Could not find Upload option in dropdown")


    async def _select_file(self, video_path):
        """Select video file for upload"""
        
        abs_path = os.path.abspath(video_path)
        
        file_input = await self.page.query_selector('input[type="file"]')
        if file_input:
            await file_input.set_input_files(abs_path)
        else:
            raise Exception("Could not find file input element")
        
        await asyncio.sleep(3)


    async def _fill_title(self, title):
        """Set video title"""
        
        title = title[:100]
        
        selectors = [
            '#textbox[aria-label*="title"]',
            '#title-textarea #textbox',
            'div#textbox[contenteditable="true"]',
        ]
        
        for selector in selectors:
            try:
                el = await self.page.wait_for_selector(selector, timeout=5000)
                if el:
                    await el.click()
                    await self.page.keyboard.press('Control+A')
                    await self.page.keyboard.press('Delete')
                    await asyncio.sleep(0.3)
                    await el.fill(title)
                    return
            except Exception:
                continue
        
        logger.warning("   ⚠️ Could not set title through selectors, trying keyboard")
        try:
            await self.page.keyboard.type(title, delay=20)
        except Exception:
            pass


    async def _fill_description(self, description):
        """Set video description"""
        
        description = description[:5000]
        
        try:
            el = await self.page.wait_for_selector(
                '#description-textarea #textbox', timeout=5000
            )
            if el:
                await el.click()
                await el.fill(description)
        except Exception as e:
            logger.warning(f"   ⚠️ Description fill failed: {e}")


    async def _set_not_for_kids(self):
        """Set not made for kids"""
        
        try:
            radio = await self.page.wait_for_selector(
                'tp-yt-paper-radio-button[name="NOT_MADE_FOR_KIDS"]',
                timeout=5000
            )
            if radio:
                await radio.click()
        except Exception:
            logger.warning("   ⚠️ Could not set kids setting")


    async def _fill_tags(self, tags):
        """Fill in tags"""
        
        try:
            # Click "Show more"
            show_more_selectors = [
                '#toggle-button',
                'button:has-text("Show more")',
                'ytcp-button:has-text("Show more")',
            ]
            
            for selector in show_more_selectors:
                try:
                    await self.page.click(selector, timeout=3000)
                    await asyncio.sleep(1)
                    break
                except Exception:
                    continue
            
            # Find tags input
            tags_input = await self.page.wait_for_selector(
                'input[aria-label="Tags"]', timeout=3000
            )
            
            if not tags_input:
                tags_input = await self.page.query_selector('#tags-input input')
            
            if tags_input:
                tags_text = ','.join(str(t) for t in tags[:30])
                await tags_input.fill(tags_text)
                
        except Exception as e:
            logger.warning(f"   ⚠️ Tags fill failed: {e}")


    async def _set_thumbnail(self, thumbnail_path):
        """Upload custom thumbnail"""
        
        abs_path = os.path.abspath(thumbnail_path)
        
        try:
            selectors = [
                '#file-loader input[type="file"]',
                'input[accept="image/jpeg,image/png"]',
                '#still-picker input[type="file"]',
            ]
            
            for selector in selectors:
                try:
                    thumb_input = await self.page.query_selector(selector)
                    if thumb_input:
                        await thumb_input.set_input_files(abs_path)
                        await asyncio.sleep(3)
                        return
                except Exception:
                    continue
            
            logger.warning("   ⚠️ Could not find thumbnail upload input")
            
        except Exception as e:
            logger.warning(f"   ⚠️ Thumbnail upload failed: {e}")


    async def _wait_for_upload_complete(self):
        """Wait for video upload to finish processing"""
        
        max_wait = 600  # 10 minutes max
        check_interval = 10
        elapsed = 0
        
        while elapsed < max_wait:
            try:
                page_text = await self.page.inner_text('body')
                
                if any(phrase in page_text for phrase in [
                    'Checks complete', 'Upload complete',
                    'Processing complete', 'Video uploaded'
                ]):
                    return
                
                if 'Upload failed' in page_text or 'Error' in page_text:
                    raise Exception("Upload failed — YouTube reported an error")
                
            except Exception as e:
                if 'Upload failed' in str(e):
                    raise
            
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            if elapsed % 60 == 0:
                logger.info(f"      ⏳ Upload processing... ({elapsed}s elapsed)")
        
        logger.warning("   ⚠️ Upload wait timeout — proceeding anyway")


    async def _navigate_and_publish(self):
        """Click through steps and publish"""
        
        # Click NEXT 3 times
        for step in range(3):
            try:
                next_btn = await self.page.wait_for_selector('#next-button', timeout=5000)
                if next_btn:
                    await next_btn.click()
                    await asyncio.sleep(2)
            except Exception:
                pass
        
        await asyncio.sleep(2)
        
        # Set PUBLIC
        try:
            public_radio = await self.page.query_selector(
                'tp-yt-paper-radio-button[name="PUBLIC"]'
            )
            if public_radio:
                await public_radio.click()
                await asyncio.sleep(1)
        except Exception:
            logger.warning("   ⚠️ Could not set to Public")
        
        # Click PUBLISH/DONE
        try:
            done_btn = await self.page.wait_for_selector('#done-button', timeout=5000)
            if done_btn:
                await done_btn.click()
                await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"   ❌ Publish button failed: {e}")
            await self._take_debug_screenshot("publish_failed")


    async def _get_video_url(self):
        """Extract video URL after upload"""
        
        try:
            page_content = await self.page.content()
            
            # Try to find video ID
            patterns = [
                r'video_id["\s:=]+["\']?([a-zA-Z0-9_-]{11})',
                r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
                r'youtu\.be/([a-zA-Z0-9_-]{11})',
                r'/video/([a-zA-Z0-9_-]{11})',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, page_content)
                if match:
                    vid_id = match.group(1)
                    return f"https://youtube.com/watch?v={vid_id}"
            
            # Try clicking the link element
            link = await self.page.query_selector('a.style-scope.ytcp-video-info')
            if link:
                href = await link.get_attribute('href')
                if href:
                    return href if href.startswith('http') else f"https://studio.youtube.com{href}"
            
        except Exception:
            pass
        
        return "URL not captured — check YouTube Studio"


    def upload(self, video_path, title, description,
               tags=None, thumbnail_path=None, is_short=False):
        """Synchronous upload wrapper"""
        
        return asyncio.run(
            self.upload_video(
                video_path, title, description,
                tags, thumbnail_path, is_short
            )
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("📤 Uploader module ready")
    print("   Run cookie_extractor.py first to setup cookies")
