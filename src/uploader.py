"""
YOUTUBE UPLOADER — Handles hidden file inputs + JS fallbacks
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

    async def _click_js(self, js_code, description="element"):
        try:
            result = await self.page.evaluate(js_code)
            if result:
                logger.info(f"   ✅ {description}")
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
            await asyncio.sleep(4)

            if 'accounts.google.com' in self.page.url:
                raise Exception("Session expired")

            logger.info(f"   ✅ Studio loaded")

            # Step 2: Find file input — it is HIDDEN, use state='attached'
            logger.info(f"   2️⃣ Finding upload input...")

            file_input = None

            # Method 1: Find hidden file input directly
            try:
                file_input = await self.page.wait_for_selector(
                    'input[type="file"]', state='attached', timeout=8000
                )
                logger.info(f"   ✅ File input found (attached)")
            except Exception:
                logger.info(f"   🔄 File input not ready, trying button click...")

            # Method 2: Click SELECT FILES button to trigger dialog
            if not file_input:
                await self._click_js("""
                    () => {
                        // Try select files button
                        const sfb = document.querySelector('#select-files-button');
                        if (sfb) { sfb.click(); return true; }
                        // Try by text
                        const btns = document.querySelectorAll('ytcp-button, button');
                        for (const b of btns) {
                            const t = (b.textContent || '').toLowerCase();
                            if (t.includes('select file') || t.includes('upload')) {
                                b.click(); return true;
                            }
                        }
                        return false;
                    }
                """, "Select Files button")
                await asyncio.sleep(2)

                try:
                    file_input = await self.page.wait_for_selector(
                        'input[type="file"]', state='attached', timeout=8000
                    )
                    logger.info(f"   ✅ File input found after button click")
                except Exception:
                    pass

            # Method 3: Use page.set_input_files directly with locator
            if not file_input:
                logger.info(f"   🔄 Using direct locator method...")
                try:
                    locator = self.page.locator('input[type="file"]')
                    count = await locator.count()
                    logger.info(f"   Found {count} file inputs")
                    if count > 0:
                        await locator.first.set_input_files(os.path.abspath(video_path))
                        logger.info(f"   ✅ File set via locator")
                        await asyncio.sleep(5)
                        # Skip step 3 since file is already set
                        file_input = "ALREADY_SET"
                except Exception as e:
                    logger.warning(f"   ⚠️ Locator method failed: {e}")

            if not file_input:
                await self._screenshot("no_file_input")
                raise Exception("Could not find file input")

            # Step 3: Set file (if not already set)
            if file_input != "ALREADY_SET":
                logger.info(f"   3️⃣ Selecting file...")
                await file_input.set_input_files(os.path.abspath(video_path))
                logger.info(f"   ✅ File selected")
                await asyncio.sleep(5)

            # Step 4: Title
            logger.info(f"   4️⃣ Setting title...")
            await asyncio.sleep(2)

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
                        await self.page.keyboard.type(title[:100], delay=10)
                        title_set = True
                        logger.info(f"   ✅ Title set")
                        break
                except Exception:
                    continue

            if not title_set:
                await self._click_js(f"""
                    () => {{
                        const boxes = document.querySelectorAll('#textbox');
                        if (boxes.length > 0) {{
                            boxes[0].textContent = '{title[:100].replace("'", "").replace('"', '')}';
                            boxes[0].dispatchEvent(new Event('input', {{bubbles: true}}));
                            return true;
                        }}
                        return false;
                    }}
                """, "Title (JS)")

            # Step 5: Description
            logger.info(f"   5️⃣ Setting description...")
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

            # Step 6: Not for kids — multiple methods
            logger.info(f"   6️⃣ Setting 'Not made for kids'...")
            kids_set = False

            for sel in ['tp-yt-paper-radio-button[name="NOT_MADE_FOR_KIDS"]',
                        'tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]']:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=3000)
                    if el:
                        await el.click()
                        kids_set = True
                        logger.info(f"   ✅ Not for kids (selector)")
                        break
                except Exception:
                    continue

            if not kids_set:
                kids_set = await self._click_js("""
                    () => {
                        const radios = document.querySelectorAll('tp-yt-paper-radio-button');
                        for (const r of radios) {
                            const name = r.getAttribute('name') || '';
                            const text = (r.textContent || '').toLowerCase();
                            if (name.includes('NOT_MADE') || name.includes('NOT_MFK') ||
                                text.includes('not made for kids') || text.includes("no, it")) {
                                r.click(); return true;
                            }
                        }
                        const all = document.querySelectorAll('#audience tp-yt-paper-radio-button');
                        if (all.length >= 2) { all[1].click(); return true; }
                        return false;
                    }
                """, "Not for kids (JS)")

            if not kids_set:
                logger.warning(f"   ⚠️ Kids setting failed — may go to drafts")
                await self._screenshot("kids_failed")

            # Step 7: Thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"   7️⃣ Setting thumbnail...")
                try:
                    thumb = self.page.locator('#file-loader input[type="file"], input[accept="image/jpeg,image/png"]')
                    if await thumb.count() > 0:
                        await thumb.first.set_input_files(os.path.abspath(thumbnail_path))
                        await asyncio.sleep(2)
                        logger.info(f"   ✅ Thumbnail set")
                except Exception:
                    logger.warning(f"   ⚠️ Thumbnail skipped")

            # Step 8: Wait for processing
            logger.info(f"   8️⃣ Waiting for processing...")
            for i in range(36):
                try:
                    body = await self.page.inner_text('body')
                    if any(p in body for p in ['Checks complete', 'Upload complete',
                                                'Processing complete', 'SD', 'HD']):
                        logger.info(f"   ✅ Processed ({i*5}s)")
                        break
                except Exception:
                    pass
                await asyncio.sleep(5)
                if i > 0 and i % 6 == 0:
                    logger.info(f"      ⏳ Processing... ({i*5}s)")

            # Step 9: NEXT × 3
            logger.info(f"   9️⃣ Navigating to visibility...")
            for step in range(3):
                try:
                    btn = await self.page.wait_for_selector('#next-button', timeout=3000)
                    if btn:
                        await btn.click()
                except Exception:
                    await self._click_js("""
                        () => {
                            const b = document.querySelector('#next-button');
                            if (b) { b.click(); return true; }
                            return false;
                        }
                    """, f"Next {step+1}")
                await asyncio.sleep(2)

            # Step 10: PUBLIC
            logger.info(f"   🔟 Setting PUBLIC...")
            try:
                el = await self.page.wait_for_selector(
                    'tp-yt-paper-radio-button[name="PUBLIC"]', timeout=3000
                )
                if el:
                    await el.click()
                    logger.info(f"   ✅ Public set")
            except Exception:
                await self._click_js("""
                    () => {
                        const radios = document.querySelectorAll('tp-yt-paper-radio-button');
                        for (const r of radios) {
                            if ((r.getAttribute('name')||'') === 'PUBLIC' ||
                                (r.textContent||'').includes('Public')) {
                                r.click(); return true;
                            }
                        }
                        return false;
                    }
                """, "Public (JS)")

            # Step 11: PUBLISH
            logger.info(f"   1️⃣1️⃣ Publishing...")
            try:
                btn = await self.page.wait_for_selector('#done-button', timeout=3000)
                if btn:
                    await btn.click()
                    logger.info(f"   ✅ Publish clicked")
            except Exception:
                await self._click_js("""
                    () => {
                        const b = document.querySelector('#done-button');
                        if (b) { b.click(); return true; }
                        const btns = document.querySelectorAll('ytcp-button');
                        for (const x of btns) {
                            if ((x.textContent||'').match(/publish|done|save/i)) {
                                x.click(); return true;
                            }
                        }
                        return false;
                    }
                """, "Publish (JS)")

            # Wait for confirmation (max 60s)
            logger.info(f"   ⏳ Confirming publish (max 60s)...")
            for i in range(12):
                await asyncio.sleep(5)
                try:
                    body = await self.page.inner_text('body')
                    if any(p in body for p in ['Video published', 'has been published',
                                                'is being published', 'is live']):
                        logger.info(f"   ✅ PUBLISHED!")
                        break
                    close = await self.page.query_selector('ytcp-button[id="close-button"]')
                    if close:
                        logger.info(f"   ✅ PUBLISHED (close dialog found)")
                        break
                except Exception:
                    pass

            video_url = await self._get_url()
            logger.info(f"\n   ✅✅✅ UPLOAD COMPLETE ✅✅✅")
            logger.info(f"   🔗 {video_url}")
            return video_url

        except Exception as e:
            logger.error(f"   ❌ Upload FAILED: {e}")
            await self._screenshot("upload_error")
            raise
        finally:
            await self._stop_browser()

    async def _get_url(self):
        try:
            content = await self.page.content()
            for p in [r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
                       r'youtu\.be/([a-zA-Z0-9_-]{11})',
                       r'/video/([a-zA-Z0-9_-]{11})',
                       r'video_id["\s:=]+["\']?([a-zA-Z0-9_-]{11})']:
                m = re.search(p, content)
                if m:
                    return f"https://youtube.com/watch?v={m.group(1)}"
        except Exception:
            pass
        return "URL not captured — check YouTube Studio"

    def upload(self, video_path, title, description,
               tags=None, thumbnail_path=None, is_short=False):
        return asyncio.run(
            self.upload_video(video_path, title, description,
                             tags, thumbnail_path, is_short)
        )
