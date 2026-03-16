"""
YOUTUBE UPLOADER — Direct URL + JavaScript title/description
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
            await self.page.screenshot(path=path, full_page=True)
            logger.info(f"   📸 Screenshot: {path}")
        except Exception:
            pass

    async def upload_video(self, video_path, title, description,
                            tags=None, thumbnail_path=None, is_short=False):
        vtype = "Short" if is_short else "Long-form"
        logger.info(f"\n   {'─'*50}")
        logger.info(f"   📤 UPLOADING {vtype}: {title[:50]}...")
        logger.info(f"   📊 Size: {os.path.getsize(video_path)/(1024*1024):.1f} MB")

        try:
            await self._start_browser()

            # Step 1: Go to upload URL directly
            logger.info(f"   1️⃣ Opening upload page...")
            await self.page.goto(
                'https://www.youtube.com/upload',
                wait_until='domcontentloaded', timeout=30000
            )
            await asyncio.sleep(5)

            if 'accounts.google.com' in self.page.url:
                raise Exception("Session expired")

            # If redirected to studio, try direct URL
            if 'upload' not in self.page.url:
                await self.page.goto(
                    'https://studio.youtube.com/channel/UC/videos/upload?d=ud',
                    wait_until='domcontentloaded', timeout=20000
                )
                await asyncio.sleep(5)

            logger.info(f"   ✅ Page loaded: {self.page.url[:60]}")

            # Step 2: Set file on hidden input
            logger.info(f"   2️⃣ Selecting file...")
            file_input = await self.page.wait_for_selector(
                'input[type="file"]', state='attached', timeout=10000
            )
            if file_input:
                await file_input.set_input_files(os.path.abspath(video_path))
                logger.info(f"   ✅ File selected")
            else:
                locator = self.page.locator('input[type="file"]')
                await locator.first.set_input_files(os.path.abspath(video_path))
                logger.info(f"   ✅ File selected (locator)")

            # Step 3: Verify upload started
            logger.info(f"   3️⃣ Verifying upload...")
            upload_ok = False
            for i in range(30):
                await asyncio.sleep(5)
                try:
                    body = await self.page.inner_text('body')
                    if any(w in body for w in ['Add a title', 'Details', 'Uploading',
                                                'Processing', 'Video elements']):
                        upload_ok = True
                        logger.info(f"   ✅ Upload dialog active ({i*5}s)")
                        break
                except Exception:
                    pass
                if i > 0 and i % 6 == 0:
                    logger.info(f"      ⏳ Waiting... ({i*5}s)")

            if not upload_ok:
                await self._screenshot("upload_not_started")
                logger.warning(f"   ⚠️ Upload dialog not confirmed")

            # Step 4: Set title via JavaScript
            logger.info(f"   4️⃣ Setting title...")
            await asyncio.sleep(3)

            # Escape special characters for JS string
            safe_title = (title[:100]
                         .replace('\\', '\\\\')
                         .replace("'", "\\'")
                         .replace('"', '\\"')
                         .replace('\n', ' ')
                         .replace('\r', ''))

            title_set = await self.page.evaluate(f"""
                () => {{
                    const boxes = document.querySelectorAll(
                        '#textbox[contenteditable="true"]'
                    );
                    if (boxes.length > 0) {{
                        const titleBox = boxes[0];
                        titleBox.focus();
                        titleBox.textContent = '';
                        document.execCommand('selectAll', false, null);
                        document.execCommand('insertText', false, '{safe_title}');
                        titleBox.dispatchEvent(new Event('input', {{bubbles: true}}));
                        return true;
                    }}
                    return false;
                }}
            """)
            logger.info(f"   {'✅' if title_set else '⚠️'} Title: {title_set}")

            # Step 5: Set description
            logger.info(f"   5️⃣ Setting description...")
            safe_desc = (description[:500]
                        .replace('\\', '\\\\')
                        .replace("'", "\\'")
                        .replace('"', '\\"')
                        .replace('\n', '\\n')
                        .replace('\r', ''))

            desc_set = await self.page.evaluate(f"""
                () => {{
                    const boxes = document.querySelectorAll(
                        '#textbox[contenteditable="true"]'
                    );
                    if (boxes.length > 1) {{
                        const descBox = boxes[1];
                        descBox.focus();
                        descBox.textContent = '';
                        document.execCommand('selectAll', false, null);
                        document.execCommand('insertText', false, '{safe_desc}');
                        descBox.dispatchEvent(new Event('input', {{bubbles: true}}));
                        return true;
                    }}
                    return false;
                }}
            """)
            logger.info(f"   {'✅' if desc_set else '⚠️'} Description: {desc_set}")

            # Step 6: Not for kids
            logger.info(f"   6️⃣ Setting audience...")
            await self.page.evaluate("window.scrollBy(0, 300)")
            await asyncio.sleep(1)

            kids = await self.page.evaluate("""
                () => {
                    const radios = document.querySelectorAll('tp-yt-paper-radio-button');
                    for (const r of radios) {
                        const n = r.getAttribute('name') || '';
                        const t = (r.textContent || '').toLowerCase();
                        if (n.includes('NOT_MADE') || n.includes('NOT_MFK') ||
                            t.includes('no, it') || t.includes('not made for kids')) {
                            r.click(); return true;
                        }
                    }
                    const all = document.querySelectorAll('#audience tp-yt-paper-radio-button');
                    if (all.length >= 2) { all[1].click(); return true; }
                    return false;
                }
            """)
            logger.info(f"   {'✅' if kids else '⚠️'} Not for kids: {kids}")

            # Step 7: Thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"   7️⃣ Thumbnail...")
                try:
                    thumb = self.page.locator(
                        '#file-loader input[type="file"], input[accept*="image"]'
                    )
                    if await thumb.count() > 0:
                        await thumb.first.set_input_files(os.path.abspath(thumbnail_path))
                        await asyncio.sleep(2)
                        logger.info(f"   ✅ Thumbnail set")
                except Exception:
                    pass

            # Step 8: Wait for processing
            logger.info(f"   8️⃣ Processing...")
            for i in range(60):
                try:
                    body = await self.page.inner_text('body')
                    if any(p in body for p in ['Checks complete', 'Processing complete']):
                        logger.info(f"   ✅ Done ({i*5}s)")
                        break
                    if 'Upload failed' in body:
                        raise Exception("Upload failed")
                except Exception as e:
                    if 'failed' in str(e).lower():
                        raise
                await asyncio.sleep(5)
                if i > 0 and i % 12 == 0:
                    logger.info(f"      ⏳ {i*5}s...")

            # Step 9: Next × 3 → Public → Publish
            logger.info(f"   9️⃣ Publishing...")
            for step in range(3):
                await self.page.evaluate(
                    "() => { const b = document.querySelector('#next-button'); if(b) b.click(); }"
                )
                await asyncio.sleep(2)

            await self.page.evaluate("""
                () => {
                    const r = document.querySelectorAll('tp-yt-paper-radio-button');
                    for (const x of r) {
                        if ((x.getAttribute('name')||'') === 'PUBLIC' ||
                            (x.textContent||'').includes('Public')) {
                            x.click(); return;
                        }
                    }
                }
            """)
            await asyncio.sleep(1)

            await self.page.evaluate(
                "() => { const b = document.querySelector('#done-button'); if(b) b.click(); }"
            )
            logger.info(f"   ✅ Publish clicked")

            for i in range(6):
                await asyncio.sleep(5)
                try:
                    body = await self.page.inner_text('body')
                    if any(p in body for p in ['Video published', 'has been published', 'is live']):
                        logger.info(f"   ✅ PUBLISHED!")
                        break
                except Exception:
                    pass

            url = await self._get_url()
            logger.info(f"\n   ✅ UPLOAD COMPLETE: {url}")
            return url

        except Exception as e:
            logger.error(f"   ❌ FAILED: {e}")
            await self._screenshot("upload_error")
            raise
        finally:
            await self._stop_browser()

    async def _get_url(self):
        try:
            content = await self.page.content()
            for p in [r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
                       r'/video/([a-zA-Z0-9_-]{11})',
                       r'video_id["\s:=]+["\']?([a-zA-Z0-9_-]{11})']:
                m = re.search(p, content)
                if m:
                    return f"https://youtube.com/watch?v={m.group(1)}"
        except Exception:
            pass
        return "check YouTube Studio"

    def upload(self, video_path, title, description,
               tags=None, thumbnail_path=None, is_short=False):
        return asyncio.run(
            self.upload_video(video_path, title, description,
                             tags, thumbnail_path, is_short)
        )
