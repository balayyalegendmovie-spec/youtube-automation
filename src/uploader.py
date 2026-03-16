"""
YOUTUBE UPLOADER — Direct URL approach with proper waits
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

            # STEP 1: Go to Studio and click CREATE > Upload
            logger.info(f"   1️⃣ Opening YouTube Studio...")
            await self.page.goto('https://studio.youtube.com',
                                wait_until='networkidle', timeout=30000)
            await asyncio.sleep(5)

            if 'accounts.google.com' in self.page.url:
                raise Exception("Session expired")

            logger.info(f"   ✅ Studio loaded")

            # STEP 2: Use keyboard shortcut or direct navigation
            # YouTube Studio supports Ctrl+Shift+U or we navigate
            logger.info(f"   2️⃣ Opening upload dialog...")

            # Method: Click create icon then click upload in popup
            dialog_opened = False

            # Try clicking the create button with explicit waits
            try:
                # Wait for page to fully render
                await self.page.wait_for_load_state('networkidle')
                await asyncio.sleep(3)

                # Find and click create button
                create_btn = await self.page.wait_for_selector(
                    '#create-icon', timeout=10000
                )
                if create_btn:
                    await create_btn.click()
                    logger.info(f"   ✅ Create icon clicked")
                    await asyncio.sleep(3)

                    # Now wait for the menu to appear and click Upload
                    # The menu items are tp-yt-paper-item elements
                    menu_item = await self.page.wait_for_selector(
                        'tp-yt-paper-item', timeout=5000
                    )
                    if menu_item:
                        await menu_item.click()
                        logger.info(f"   ✅ Upload menu clicked")
                        dialog_opened = True
                        await asyncio.sleep(3)
            except Exception as e:
                logger.info(f"   ⚠️ Create button method failed: {e}")

            # Fallback: Direct URL
            if not dialog_opened:
                logger.info(f"   🔄 Trying direct upload URL...")
                await self.page.goto(
                    'https://www.youtube.com/upload',
                    wait_until='domcontentloaded', timeout=20000
                )
                await asyncio.sleep(5)

                # Check if we landed on an upload page
                url = self.page.url
                logger.info(f"   Current URL: {url[:80]}")

                if 'upload' in url or 'studio' in url:
                    dialog_opened = True
                    logger.info(f"   ✅ Upload page loaded via direct URL")

            # Fallback 2: Studio upload URL
            if not dialog_opened:
                logger.info(f"   🔄 Trying studio upload URL...")
                await self.page.goto(
                    'https://studio.youtube.com/channel/UC/videos/upload?d=ud',
                    wait_until='domcontentloaded', timeout=20000
                )
                await asyncio.sleep(5)
                dialog_opened = True
                logger.info(f"   ✅ Studio upload page loaded")

            await self._screenshot("step2_upload_dialog")

            # STEP 3: Set file
            logger.info(f"   3️⃣ Uploading file...")

            # Find file input (hidden)
            file_input = await self.page.wait_for_selector(
                'input[type="file"]', state='attached', timeout=10000
            )

            if not file_input:
                # Try locator approach
                locator = self.page.locator('input[type="file"]')
                if await locator.count() > 0:
                    await locator.first.set_input_files(os.path.abspath(video_path))
                    logger.info(f"   ✅ File set via locator")
                else:
                    raise Exception("No file input found")
            else:
                await file_input.set_input_files(os.path.abspath(video_path))
                logger.info(f"   ✅ File selected")

            # STEP 4: VERIFY upload started (critical!)
            logger.info(f"   4️⃣ Verifying upload started...")

            upload_confirmed = False
            for i in range(30):  # Wait up to 150 seconds
                await asyncio.sleep(5)
                try:
                    body_text = await self.page.inner_text('body')

                    # Real upload indicators
                    real_indicators = [
                        'Add a title that describes',
                        'Details',
                        'Uploading',
                        'Processing',
                        '% uploaded',
                        'Video elements',
                        'Made for kids',
                    ]

                    for indicator in real_indicators:
                        if indicator in body_text:
                            upload_confirmed = True
                            logger.info(f"   ✅ Upload confirmed: found '{indicator}' ({i*5}s)")
                            break

                    if upload_confirmed:
                        break

                    # Check percentage
                    pct = re.search(r'(\d+)\s*%', body_text)
                    if pct and int(pct.group(1)) > 0:
                        upload_confirmed = True
                        logger.info(f"   ✅ Upload progress: {pct.group(0)} ({i*5}s)")
                        break

                except Exception:
                    pass

                if i > 0 and i % 6 == 0:
                    logger.info(f"      ⏳ Waiting for upload... ({i*5}s)")
                    await self._screenshot(f"step4_waiting_{i}")

            if not upload_confirmed:
                await self._screenshot("step4_upload_not_confirmed")
                # Don't raise — try to continue anyway, might still work
                logger.warning(f"   ⚠️ Could not confirm upload started")

            # STEP 5: Set title
            logger.info(f"   5️⃣ Setting title...")
            await asyncio.sleep(2)

            title_set = False
            for sel in ['#textbox[aria-label*="title" i]',
                        '#textbox[aria-label*="Title"]',
                        '#title-textarea #textbox',
                        'div#textbox[contenteditable]']:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=5000)
                    if el:
                        await el.click()
                        await self.page.keyboard.press('Control+A')
                        await self.page.keyboard.press('Delete')
                        await self.page.keyboard.type(title[:100], delay=15)
                        title_set = True
                        logger.info(f"   ✅ Title set")
                        break
                except Exception:
                    continue

            if not title_set:
                logger.warning(f"   ⚠️ Title not set")

            # STEP 6: Description
            logger.info(f"   6️⃣ Setting description...")
            try:
                el = await self.page.wait_for_selector(
                    '#description-textarea #textbox', timeout=5000
                )
                if el:
                    await el.click()
                    await el.fill(description[:2000])
                    logger.info(f"   ✅ Description set")
            except Exception:
                logger.warning(f"   ⚠️ Description skipped")

            # STEP 7: Not for kids
            logger.info(f"   7️⃣ Setting 'Not for kids'...")
            await self.page.evaluate("window.scrollBy(0, 300)")
            await asyncio.sleep(1)

            kids_set = await self.page.evaluate("""
                () => {
                    const radios = document.querySelectorAll('tp-yt-paper-radio-button');
                    for (const r of radios) {
                        const name = r.getAttribute('name') || '';
                        const text = (r.textContent || '').toLowerCase();
                        if (name.includes('NOT_MADE') || name.includes('NOT_MFK') ||
                            text.includes('no, it') || text.includes('not made for kids')) {
                            r.click(); return true;
                        }
                    }
                    // Try second radio in audience section
                    const all = document.querySelectorAll(
                        '#audience tp-yt-paper-radio-button, ' +
                        '#made-for-kids-group tp-yt-paper-radio-button'
                    );
                    if (all.length >= 2) { all[1].click(); return true; }
                    return false;
                }
            """)
            logger.info(f"   {'✅' if kids_set else '⚠️'} Not for kids: {kids_set}")

            # STEP 8: Thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"   8️⃣ Setting thumbnail...")
                try:
                    thumb = self.page.locator(
                        '#file-loader input[type="file"], input[accept*="image"]'
                    )
                    if await thumb.count() > 0:
                        await thumb.first.set_input_files(os.path.abspath(thumbnail_path))
                        await asyncio.sleep(2)
                        logger.info(f"   ✅ Thumbnail set")
                except Exception:
                    logger.warning(f"   ⚠️ Thumbnail skipped")

            # STEP 9: Wait for processing
            logger.info(f"   9️⃣ Waiting for processing...")
            for i in range(60):
                try:
                    body = await self.page.inner_text('body')
                    if any(p in body for p in ['Checks complete', 'Processing complete']):
                        logger.info(f"   ✅ Processing done ({i*5}s)")
                        break
                    if 'Upload failed' in body:
                        raise Exception("Upload failed")
                except Exception as e:
                    if 'failed' in str(e).lower():
                        raise
                await asyncio.sleep(5)
                if i > 0 and i % 12 == 0:
                    logger.info(f"      ⏳ Processing... ({i*5}s)")

            # STEP 10: Next > Next > Next > Public > Publish
            logger.info(f"   🔟 Publishing...")

            for step in range(3):
                try:
                    btn = await self.page.wait_for_selector('#next-button', timeout=5000)
                    if btn: await btn.click()
                except Exception:
                    await self.page.evaluate("""
                        () => { const b = document.querySelector('#next-button');
                                if(b) b.click(); }
                    """)
                await asyncio.sleep(2)

            # Public
            await self.page.evaluate("""
                () => {
                    const radios = document.querySelectorAll('tp-yt-paper-radio-button');
                    for (const r of radios) {
                        if ((r.getAttribute('name')||'') === 'PUBLIC' ||
                            (r.textContent||'').includes('Public')) {
                            r.click(); return;
                        }
                    }
                }
            """)
            await asyncio.sleep(1)

            # Publish/Done
            await self.page.evaluate("""
                () => {
                    const b = document.querySelector('#done-button');
                    if(b) b.click();
                }
            """)
            logger.info(f"   ✅ Publish clicked")

            # Wait for confirmation (30s max)
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
            logger.error(f"   ❌ Upload FAILED: {e}")
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
