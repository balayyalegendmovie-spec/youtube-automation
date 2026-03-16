"""
YOUTUBE UPLOADER — With proper timeouts to prevent hanging
"""

import asyncio
import json
import os
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class YouTubeUploader:

    def __init__(self, cookie_file, channel_name=""):
        self.cookie_file = cookie_file
        self.channel_name = channel_name
        self.playwright_instance = None
        self.browser = None
        self.context = None
        self.page = None
        logger.info(f"📤 Uploader initialized for: {channel_name}")

    async def _start_browser(self):
        from playwright.async_api import async_playwright
        self.playwright_instance = await async_playwright().start()
        self.browser = await self.playwright_instance.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox',
                  '--disable-dev-shm-usage',
                  '--disable-blink-features=AutomationControlled']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            locale='en-US', timezone_id='Asia/Kolkata'
        )
        if os.path.exists(self.cookie_file):
            with open(self.cookie_file, 'r') as f:
                data = json.load(f)
            cookies = data.get('cookies', data) if isinstance(data, dict) else data
            if cookies:
                await self.context.add_cookies(cookies)
                logger.info(f"   🍪 Loaded {len(cookies)} cookies")
        else:
            raise FileNotFoundError(f"Cookie file not found: {self.cookie_file}")
        self.page = await self.context.new_page()
        await self.page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )

    async def _stop_browser(self):
        if self.context:
            try:
                cookies = await self.context.cookies()
                with open(self.cookie_file, 'w') as f:
                    json.dump({'cookies': cookies,
                               'updated_at': datetime.now().isoformat(),
                               'channel': self.channel_name}, f, indent=2)
                logger.info(f"   🍪 Cookies saved")
            except Exception:
                pass
        if self.browser:
            await self.browser.close()
        if self.playwright_instance:
            await self.playwright_instance.stop()

    async def _screenshot(self, name="debug"):
        try:
            os.makedirs("output/logs/screenshots", exist_ok=True)
            path = f"output/logs/screenshots/{name}_{datetime.now().strftime('%H%M%S')}.png"
            await self.page.screenshot(path=path)
            logger.info(f"   📸 Screenshot: {path}")
        except Exception:
            pass

    async def _safe_click(self, selectors, timeout=5000, description="element"):
        """Try multiple selectors, return True if any clicked"""
        for sel in selectors:
            try:
                el = await self.page.wait_for_selector(sel, timeout=timeout)
                if el:
                    await el.click()
                    await asyncio.sleep(1)
                    logger.info(f"   ✅ Clicked {description}")
                    return True
            except Exception:
                continue
        logger.warning(f"   ⚠️ Could not click {description}")
        return False

    async def upload_video(self, video_path, title, description,
                            tags=None, thumbnail_path=None, is_short=False):
        vtype = "Short" if is_short else "Long-form"
        logger.info(f"\n   {'─'*50}")
        logger.info(f"   📤 UPLOADING {vtype}: {title[:50]}...")
        logger.info(f"   📊 Size: {os.path.getsize(video_path)/(1024*1024):.1f} MB")
        logger.info(f"   {'─'*50}")

        try:
            await self._start_browser()

            # Step 1: Go to upload page directly
            logger.info(f"   1️⃣ Opening upload page...")
            await self.page.goto(
                'https://studio.youtube.com/channel/UC/videos/upload?d=ud',
                wait_until='domcontentloaded', timeout=30000
            )
            await asyncio.sleep(3)

            if 'accounts.google.com' in self.page.url:
                raise Exception("Session expired — re-login required")

            logger.info(f"   ✅ Studio loaded: {self.page.url[:70]}")

            # Step 2: Find file input
            logger.info(f"   2️⃣ Finding upload input...")
            file_input = await self.page.wait_for_selector(
                'input[type="file"]', timeout=10000
            )
            if not file_input:
                raise Exception("File input not found")

            # Step 3: Upload file
            logger.info(f"   3️⃣ Selecting file...")
            await file_input.set_input_files(os.path.abspath(video_path))
            logger.info(f"   ✅ File selected")
            await asyncio.sleep(5)

            # Step 4: Title
            logger.info(f"   4️⃣ Setting title...")
            await self._safe_click([
                '#textbox[aria-label*="title"]',
                '#textbox[aria-label*="Title"]',
                '#title-textarea #textbox',
            ], timeout=8000, description="title field")

            await self.page.keyboard.press('Control+A')
            await self.page.keyboard.press('Delete')
            await asyncio.sleep(0.3)
            await self.page.keyboard.type(title[:100], delay=10)
            logger.info(f"   ✅ Title set")

            # Step 5: Description
            logger.info(f"   5️⃣ Setting description...")
            try:
                desc_el = await self.page.wait_for_selector(
                    '#description-textarea #textbox', timeout=5000
                )
                if desc_el:
                    await desc_el.click()
                    await desc_el.fill(description[:5000])
                    logger.info(f"   ✅ Description set")
            except Exception:
                logger.warning(f"   ⚠️ Description skipped")

            # Step 6: Not made for kids (with SHORT timeout)
            logger.info(f"   6️⃣ Setting audience...")
            await self._safe_click([
                'tp-yt-paper-radio-button[name="NOT_MADE_FOR_KIDS"]',
                'tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]',
            ], timeout=3000, description="not for kids")

            # Step 7: Thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"   7️⃣ Setting thumbnail...")
                try:
                    thumb = await self.page.query_selector(
                        '#file-loader input[type="file"]'
                    )
                    if not thumb:
                        thumb = await self.page.query_selector(
                            'input[accept="image/jpeg,image/png"]'
                        )
                    if thumb:
                        await thumb.set_input_files(os.path.abspath(thumbnail_path))
                        await asyncio.sleep(2)
                        logger.info(f"   ✅ Thumbnail set")
                except Exception:
                    logger.warning(f"   ⚠️ Thumbnail skipped")

            # Step 8: Wait for upload (max 3 minutes)
            logger.info(f"   8️⃣ Waiting for upload...")
            for i in range(36):  # 36 * 5s = 3 minutes max
                try:
                    body = await self.page.inner_text('body')
                    if any(p in body for p in ['Checks complete', 'Upload complete',
                                                'Processing complete', 'SD', 'HD']):
                        logger.info(f"   ✅ Upload processed")
                        break
                    if 'Upload failed' in body:
                        raise Exception("YouTube said upload failed")
                except Exception as e:
                    if 'failed' in str(e).lower():
                        raise
                await asyncio.sleep(5)
                if i > 0 and i % 6 == 0:
                    logger.info(f"      ⏳ Still processing... ({i*5}s)")

            # Step 9: Click NEXT 3 times (short timeouts)
            logger.info(f"   9️⃣ Navigating to publish...")
            for step in range(3):
                clicked = await self._safe_click(
                    ['#next-button', 'ytcp-button#next-button'],
                    timeout=3000, description=f"Next ({step+1}/3)"
                )
                if not clicked:
                    # Try clicking via JS
                    try:
                        await self.page.evaluate("""
                            () => {
                                const btn = document.querySelector('#next-button');
                                if (btn) btn.click();
                            }
                        """)
                        await asyncio.sleep(1)
                    except Exception:
                        pass
                await asyncio.sleep(2)

            # Step 10: Set PUBLIC
            logger.info(f"   🔟 Setting visibility...")
            await self._safe_click([
                'tp-yt-paper-radio-button[name="PUBLIC"]',
            ], timeout=3000, description="Public")

            # Step 11: Click DONE/PUBLISH (with timeout)
            logger.info(f"   1️⃣1️⃣ Publishing...")

            publish_clicked = await self._safe_click(
                ['#done-button', 'ytcp-button#done-button'],
                timeout=5000, description="Publish/Done"
            )

            if not publish_clicked:
                # JS fallback
                try:
                    await self.page.evaluate("""
                        () => {
                            const btn = document.querySelector('#done-button');
                            if (btn) btn.click();
                        }
                    """)
                except Exception:
                    pass

            # Wait for publish to complete (max 30 seconds, not forever)
            logger.info(f"   ⏳ Waiting for publish confirmation...")
            for i in range(6):  # 6 * 5s = 30s max
                await asyncio.sleep(5)
                try:
                    body = await self.page.inner_text('body')
                    if any(p in body for p in ['Video published', 'has been published',
                                                'Close', 'Share']):
                        logger.info(f"   ✅ Published!")
                        break
                except Exception:
                    pass

            # Get URL
            video_url = await self._get_video_url()

            logger.info(f"\n   ✅✅✅ UPLOAD SUCCESSFUL ✅✅✅")
            logger.info(f"   🔗 URL: {video_url}")
            return video_url

        except Exception as e:
            logger.error(f"   ❌ Upload FAILED: {e}")
            await self._screenshot("upload_error")
            raise
        finally:
            await self._stop_browser()

    async def _get_video_url(self):
        try:
            content = await self.page.content()
            patterns = [
                r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
                r'youtu\.be/([a-zA-Z0-9_-]{11})',
                r'/video/([a-zA-Z0-9_-]{11})',
                r'video_id["\s:=]+["\']?([a-zA-Z0-9_-]{11})',
            ]
            for p in patterns:
                m = re.search(p, content)
                if m:
                    return f"https://youtube.com/watch?v={m.group(1)}"

            # Try finding link element
            link = await self.page.query_selector('a.style-scope.ytcp-video-info')
            if link:
                href = await link.get_attribute('href')
                if href:
                    return href if href.startswith('http') else f"https://studio.youtube.com{href}"

            # Try dialog link
            links = await self.page.query_selector_all('a[href*="youtu"]')
            for l in links:
                href = await l.get_attribute('href')
                if href and ('watch' in href or 'youtu.be' in href):
                    return href

        except Exception:
            pass
        return "URL not captured — check YouTube Studio"

    def upload(self, video_path, title, description,
               tags=None, thumbnail_path=None, is_short=False):
        return asyncio.run(
            self.upload_video(video_path, title, description,
                             tags, thumbnail_path, is_short)
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Uploader ready")
