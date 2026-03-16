"""
YOUTUBE UPLOADER — Fixed publish flow with proper waits
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
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
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

    async def _click_js(self, js_selector_code, description="element"):
        """Click element using JavaScript — most reliable method"""
        try:
            result = await self.page.evaluate(js_selector_code)
            if result:
                logger.info(f"   ✅ {description} (via JS)")
                await asyncio.sleep(1)
                return True
        except Exception:
            pass
        return False

    async def upload_video(self, video_path, title, description,
                            tags=None, thumbnail_path=None, is_short=False):
        vtype = "Short" if is_short else "Long-form"
        logger.info(f"\n   {'─'*50}")
        logger.info(f"   📤 UPLOADING {vtype}: {title[:50]}...")
        logger.info(f"   📊 Size: {os.path.getsize(video_path)/(1024*1024):.1f} MB")

        try:
            await self._start_browser()

            # Step 1: Go to upload page
            logger.info(f"   1️⃣ Opening upload page...")
            await self.page.goto(
                'https://studio.youtube.com/channel/UC/videos/upload?d=ud',
                wait_until='domcontentloaded', timeout=30000
            )
            await asyncio.sleep(3)

            if 'accounts.google.com' in self.page.url:
                raise Exception("Session expired")

            logger.info(f"   ✅ Studio loaded")

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

            # Step 4: Title — use JavaScript for reliability
            logger.info(f"   4️⃣ Setting title...")
            title_clean = title[:100].replace("'", "\\'").replace('"', '\\"')

            # Wait for title field to appear
            await asyncio.sleep(2)

            # Try Playwright selector first
            title_set = False
            for sel in ['#textbox[aria-label*="title"]', '#textbox[aria-label*="Title"]',
                        '#title-textarea #textbox']:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=5000)
                    if el:
                        await el.click()
                        await self.page.keyboard.press('Control+A')
                        await self.page.keyboard.press('Delete')
                        await asyncio.sleep(0.3)
                        await self.page.keyboard.type(title_clean, delay=10)
                        title_set = True
                        logger.info(f"   ✅ Title set")
                        break
                except Exception:
                    continue

            if not title_set:
                # JS fallback
                await self._click_js(f"""
                    () => {{
                        const boxes = document.querySelectorAll('#textbox');
                        if (boxes.length > 0) {{
                            boxes[0].textContent = '{title_clean}';
                            boxes[0].dispatchEvent(new Event('input', {{bubbles: true}}));
                            return true;
                        }}
                        return false;
                    }}
                """, "Title (JS)")

            # Step 5: Description
            logger.info(f"   5️⃣ Setting description...")
            desc_clean = description[:2000].replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n')
            try:
                desc_el = await self.page.wait_for_selector(
                    '#description-textarea #textbox', timeout=5000
                )
                if desc_el:
                    await desc_el.click()
                    await desc_el.fill(description[:2000])
                    logger.info(f"   ✅ Description set")
            except Exception:
                logger.warning(f"   ⚠️ Description skipped")

            # Step 6: NOT MADE FOR KIDS — Critical fix!
            logger.info(f"   6️⃣ Setting 'Not made for kids'...")

            # Method 1: Direct Playwright click
            kids_set = False
            for sel in ['tp-yt-paper-radio-button[name="NOT_MADE_FOR_KIDS"]',
                        'tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]']:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=5000)
                    if el:
                        await el.click()
                        kids_set = True
                        logger.info(f"   ✅ Not for kids set (selector)")
                        break
                except Exception:
                    continue

            # Method 2: JavaScript click (more reliable)
            if not kids_set:
                kids_set = await self._click_js("""
                    () => {
                        // Find all radio buttons
                        const radios = document.querySelectorAll('tp-yt-paper-radio-button');
                        for (const radio of radios) {
                            const name = radio.getAttribute('name') || '';
                            const text = radio.textContent || '';
                            if (name.includes('NOT_MADE_FOR_KIDS') || 
                                name.includes('NOT_MFK') ||
                                text.includes('not made for kids') ||
                                text.includes('No, it') ) {
                                radio.click();
                                return true;
                            }
                        }
                        // Try second radio button in the audience section
                        const audienceRadios = document.querySelectorAll('#audience tp-yt-paper-radio-button, #made-for-kids-group tp-yt-paper-radio-button');
                        if (audienceRadios.length >= 2) {
                            audienceRadios[1].click();
                            return true;
                        }
                        return false;
                    }
                """, "Not for kids (JS)")

            # Method 3: Scroll down and try again
            if not kids_set:
                logger.info(f"   🔄 Scrolling to find kids setting...")
                await self.page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(1)
                kids_set = await self._click_js("""
                    () => {
                        const all = document.querySelectorAll('tp-yt-paper-radio-button');
                        for (let i = 0; i < all.length; i++) {
                            const t = all[i].textContent || '';
                            if (t.toLowerCase().includes('not made') || t.toLowerCase().includes("no, it's not")) {
                                all[i].click();
                                return true;
                            }
                        }
                        // Last resort: click second radio in any group
                        if (all.length >= 2) {
                            all[1].click();
                            return true;
                        }
                        return false;
                    }
                """, "Not for kids (scroll+JS)")

            if not kids_set:
                logger.warning(f"   ⚠️ Could not set 'Not for kids' — video may go to drafts")
                await self._screenshot("kids_setting_failed")

            await asyncio.sleep(1)

            # Step 7: Thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"   7️⃣ Setting thumbnail...")
                try:
                    for sel in ['#file-loader input[type="file"]',
                                'input[accept="image/jpeg,image/png"]']:
                        thumb = await self.page.query_selector(sel)
                        if thumb:
                            await thumb.set_input_files(os.path.abspath(thumbnail_path))
                            await asyncio.sleep(2)
                            logger.info(f"   ✅ Thumbnail set")
                            break
                except Exception:
                    logger.warning(f"   ⚠️ Thumbnail skipped")

            # Step 8: Wait for upload to process
            logger.info(f"   8️⃣ Waiting for upload processing...")
            for i in range(36):
                try:
                    body = await self.page.inner_text('body')
                    if any(p in body for p in ['Checks complete', 'Upload complete',
                                                'Processing complete', 'SD', 'HD',
                                                'Checking', 'checks']):
                        logger.info(f"   ✅ Upload processed ({i*5}s)")
                        break
                except Exception:
                    pass
                await asyncio.sleep(5)
                if i > 0 and i % 6 == 0:
                    logger.info(f"      ⏳ Processing... ({i*5}s)")

            # Step 9: Click NEXT 3 times to reach visibility page
            logger.info(f"   9️⃣ Navigating to visibility...")

            for step in range(3):
                # Try Playwright
                clicked = False
                try:
                    btn = await self.page.wait_for_selector('#next-button', timeout=3000)
                    if btn:
                        await btn.click()
                        clicked = True
                except Exception:
                    pass

                # JS fallback
                if not clicked:
                    await self._click_js("""
                        () => {
                            const btn = document.querySelector('#next-button');
                            if (btn) { btn.click(); return true; }
                            // Try aria-label
                            const buttons = document.querySelectorAll('ytcp-button');
                            for (const b of buttons) {
                                if (b.textContent.includes('Next') || b.textContent.includes('next')) {
                                    b.click(); return true;
                                }
                            }
                            return false;
                        }
                    """, f"Next {step+1}")

                await asyncio.sleep(2)

            # Step 10: Set PUBLIC visibility
            logger.info(f"   🔟 Setting PUBLIC visibility...")

            # Try Playwright
            public_set = False
            try:
                el = await self.page.wait_for_selector(
                    'tp-yt-paper-radio-button[name="PUBLIC"]', timeout=3000
                )
                if el:
                    await el.click()
                    public_set = True
                    logger.info(f"   ✅ Set to Public")
            except Exception:
                pass

            # JS fallback
            if not public_set:
                public_set = await self._click_js("""
                    () => {
                        const radios = document.querySelectorAll('tp-yt-paper-radio-button');
                        for (const r of radios) {
                            const name = r.getAttribute('name') || '';
                            const text = r.textContent || '';
                            if (name === 'PUBLIC' || text.includes('Public')) {
                                r.click();
                                return true;
                            }
                        }
                        // Try the third radio (Public is usually third: Private, Unlisted, Public)
                        const visRadios = document.querySelectorAll('#privacy-radios tp-yt-paper-radio-button');
                        if (visRadios.length >= 3) {
                            visRadios[2].click();
                            return true;
                        }
                        return false;
                    }
                """, "Public (JS)")

            if not public_set:
                logger.warning(f"   ⚠️ Could not set Public — may publish as Private")

            await asyncio.sleep(1)

            # Step 11: Click PUBLISH / DONE button
            logger.info(f"   1️⃣1️⃣ Clicking Publish...")

            publish_clicked = False

            # Try Playwright
            try:
                btn = await self.page.wait_for_selector('#done-button', timeout=3000)
                if btn:
                    await btn.click()
                    publish_clicked = True
                    logger.info(f"   ✅ Publish clicked")
            except Exception:
                pass

            # JS fallback
            if not publish_clicked:
                publish_clicked = await self._click_js("""
                    () => {
                        // Try done-button
                        const done = document.querySelector('#done-button');
                        if (done) { done.click(); return true; }
                        // Try by text
                        const buttons = document.querySelectorAll('ytcp-button');
                        for (const b of buttons) {
                            const text = b.textContent || '';
                            if (text.includes('Publish') || text.includes('Done') || 
                                text.includes('Save') || text.includes('publish')) {
                                b.click(); return true;
                            }
                        }
                        return false;
                    }
                """, "Publish (JS)")

            if not publish_clicked:
                logger.error(f"   ❌ Could not click Publish!")
                await self._screenshot("publish_button_not_found")

            # Step 12: Wait for confirmation (max 60 seconds)
            logger.info(f"   ⏳ Waiting for publish confirmation (max 60s)...")
            published = False

            for i in range(12):  # 12 × 5s = 60s max
                await asyncio.sleep(5)
                try:
                    body = await self.page.inner_text('body')

                    # Check for success indicators
                    if any(phrase in body for phrase in [
                        'Video published', 'has been published',
                        'video is being published',
                        'Your video is live',
                    ]):
                        published = True
                        logger.info(f"   ✅ PUBLISHED! (confirmed)")
                        break

                    # Check for close/share dialog (means published)
                    close_btn = await self.page.query_selector(
                        'ytcp-button[id="close-button"]'
                    )
                    if close_btn:
                        published = True
                        logger.info(f"   ✅ PUBLISHED! (close dialog found)")
                        break

                    # Check if dialog closed (means published)
                    dialog = await self.page.query_selector(
                        'ytcp-uploads-dialog'
                    )
                    if not dialog:
                        published = True
                        logger.info(f"   ✅ PUBLISHED! (dialog closed)")
                        break

                except Exception:
                    pass

                if i > 0 and i % 4 == 0:
                    logger.info(f"      ⏳ Waiting... ({i*5}s)")

            if not published:
                # Try clicking close/done one more time
                await self._click_js("""
                    () => {
                        const btns = document.querySelectorAll('ytcp-button');
                        for (const b of btns) {
                            const t = b.textContent || '';
                            if (t.includes('Close') || t.includes('close')) {
                                b.click(); return true;
                            }
                        }
                        return false;
                    }
                """, "Close dialog")

                logger.warning(f"   ⚠️ Could not confirm publish — check Studio")
                await self._screenshot("publish_unconfirmed")

            # Get video URL
            video_url = await self._get_video_url()

            logger.info(f"\n   ✅✅✅ UPLOAD COMPLETE ✅✅✅")
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
            for p in [r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
                       r'youtu\.be/([a-zA-Z0-9_-]{11})',
                       r'/video/([a-zA-Z0-9_-]{11})',
                       r'video_id["\s:=]+["\']?([a-zA-Z0-9_-]{11})']:
                m = re.search(p, content)
                if m:
                    return f"https://youtube.com/watch?v={m.group(1)}"

            # Try link elements
            for sel in ['a.style-scope.ytcp-video-info',
                        'a[href*="youtu"]', 'a[href*="watch"]']:
                try:
                    links = await self.page.query_selector_all(sel)
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and ('watch' in href or 'youtu.be' in href):
                            return href if href.startswith('http') else f"https://studio.youtube.com{href}"
                except Exception:
                    continue
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
