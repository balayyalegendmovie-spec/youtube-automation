"""
YOUTUBE UPLOADER — Fixed: ensures upload modal actually opens
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
            await self.page.screenshot(path=path, full_page=True)
            logger.info(f"   📸 Screenshot: {path}")
        except Exception:
            pass

    async def upload_video(self, video_path, title, description,
                            tags=None, thumbnail_path=None, is_short=False):
        vtype = "Short" if is_short else "Long-form"
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        logger.info(f"\n   {'─'*50}")
        logger.info(f"   📤 UPLOADING {vtype}: {title[:50]}...")
        logger.info(f"   📊 Size: {file_size_mb:.1f} MB")

        try:
            await self._start_browser()

            # ════════════════════════════════════════
            # STEP 1: Open YouTube Studio
            # ════════════════════════════════════════
            logger.info(f"   1️⃣ Opening YouTube Studio...")
            await self.page.goto(
                'https://studio.youtube.com',
                wait_until='networkidle', timeout=30000
            )
            await asyncio.sleep(3)

            if 'accounts.google.com' in self.page.url:
                raise Exception("Session expired — cookies invalid")

            current_url = self.page.url
            logger.info(f"   ✅ Studio loaded: {current_url[:60]}")
            await self._screenshot("step1_studio_loaded")

            # ════════════════════════════════════════
            # STEP 2: Click CREATE button to open menu
            # ════════════════════════════════════════
            logger.info(f"   2️⃣ Clicking CREATE button...")

            create_clicked = False

            # Method A: Click the create/upload icon
            for sel in ['#create-icon', 'ytcp-button#create-icon',
                        '#upload-icon', '.ytcp-button-shape-impl--icon-button']:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=3000)
                    if el:
                        await el.click()
                        create_clicked = True
                        logger.info(f"   ✅ Create button clicked: {sel}")
                        break
                except Exception:
                    continue

            # Method B: JavaScript
            if not create_clicked:
                create_clicked = await self.page.evaluate("""
                    () => {
                        // Look for create/upload button
                        const icons = document.querySelectorAll(
                            '#create-icon, [id*="create"], [id*="upload"]'
                        );
                        for (const icon of icons) {
                            const btn = icon.closest('ytcp-button') || 
                                       icon.closest('button') || icon;
                            if (btn) { btn.click(); return true; }
                        }
                        // Try by aria-label
                        const btns = document.querySelectorAll('button, ytcp-button');
                        for (const b of btns) {
                            const label = b.getAttribute('aria-label') || '';
                            if (label.includes('Create') || label.includes('Upload')) {
                                b.click(); return true;
                            }
                        }
                        return false;
                    }
                """)
                if create_clicked:
                    logger.info(f"   ✅ Create button clicked (JS)")

            if not create_clicked:
                await self._screenshot("step2_no_create_button")
                raise Exception("Could not find Create button")

            await asyncio.sleep(2)

            # ════════════════════════════════════════
            # STEP 3: Click "Upload videos" from dropdown
            # ════════════════════════════════════════
            logger.info(f"   3️⃣ Clicking 'Upload videos'...")

            upload_clicked = False

            for sel in ['#text-item-0', 'tp-yt-paper-item:first-child',
                        'tp-yt-paper-item:has-text("Upload")']:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=3000)
                    if el:
                        await el.click()
                        upload_clicked = True
                        logger.info(f"   ✅ Upload menu clicked: {sel}")
                        break
                except Exception:
                    continue

            if not upload_clicked:
                upload_clicked = await self.page.evaluate("""
                    () => {
                        const items = document.querySelectorAll(
                            'tp-yt-paper-item, ytcp-ve, [role="menuitem"]'
                        );
                        for (const item of items) {
                            const text = (item.textContent || '').toLowerCase();
                            if (text.includes('upload video') || text.includes('upload')) {
                                item.click(); return true;
                            }
                        }
                        return false;
                    }
                """)
                if upload_clicked:
                    logger.info(f"   ✅ Upload menu clicked (JS)")

            if not upload_clicked:
                await self._screenshot("step3_no_upload_menu")
                raise Exception("Could not find Upload option in menu")

            await asyncio.sleep(3)
            await self._screenshot("step3_upload_dialog")

            # ════════════════════════════════════════
            # STEP 4: Upload file via hidden input
            # ════════════════════════════════════════
            logger.info(f"   4️⃣ Uploading file...")

            # Find the file input (hidden)
            file_input = await self.page.wait_for_selector(
                'input[type="file"]', state='attached', timeout=10000
            )

            if not file_input:
                raise Exception("File input not found in upload dialog")

            await file_input.set_input_files(os.path.abspath(video_path))
            logger.info(f"   ✅ File selected: {os.path.basename(video_path)}")

            # ════════════════════════════════════════
            # STEP 5: VERIFY upload actually started
            # ════════════════════════════════════════
            logger.info(f"   5️⃣ Verifying upload started...")

            upload_started = False
            for i in range(20):  # Check for 100 seconds
                await asyncio.sleep(5)
                try:
                    body = await self.page.inner_text('body')

                    # These indicate upload dialog is active
                    if any(indicator in body for indicator in [
                        'Upload', 'Uploading', 'Processing',
                        'Add a title', 'Details', 'Video elements',
                        'Checks', 'Visibility'
                    ]):
                        # Check it's NOT just the regular video list
                        if any(dialog_indicator in body for dialog_indicator in [
                            'Add a title', 'Details',
                            'description', 'Description',
                            'Made for kids', 'Audience',
                            'Uploading', 'Processing',
                        ]):
                            upload_started = True
                            logger.info(f"   ✅ Upload dialog active! ({i*5}s)")
                            break

                    # Check for percentage
                    pct_match = re.search(r'(\d+)%', body)
                    if pct_match:
                        pct = int(pct_match.group(1))
                        if pct > 0:
                            upload_started = True
                            logger.info(f"   ✅ Upload progress: {pct}% ({i*5}s)")
                            break

                except Exception:
                    pass

                if i > 0 and i % 4 == 0:
                    logger.info(f"      ⏳ Waiting for upload to start... ({i*5}s)")

            if not upload_started:
                await self._screenshot("step5_upload_not_started")
                logger.error(f"   ❌ Upload does not appear to have started!")
                logger.info(f"   Current URL: {self.page.url}")
                # Try to get page title for debugging
                try:
                    title_text = await self.page.title()
                    logger.info(f"   Page title: {title_text}")
                except Exception:
                    pass
                raise Exception(
                    "Upload did not start — dialog may not have opened. "
                    "Check screenshot."
                )

            # ════════════════════════════════════════
            # STEP 6: Set title
            # ════════════════════════════════════════
            logger.info(f"   6️⃣ Setting title...")
            title_clean = title[:100]

            for sel in ['#textbox[aria-label*="title"]',
                        '#textbox[aria-label*="Title"]',
                        '#title-textarea #textbox',
                        'div#textbox[contenteditable="true"]']:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=5000)
                    if el:
                        await el.click()
                        await self.page.keyboard.press('Control+A')
                        await self.page.keyboard.press('Delete')
                        await asyncio.sleep(0.3)
                        await self.page.keyboard.type(title_clean, delay=15)
                        logger.info(f"   ✅ Title set")
                        break
                except Exception:
                    continue

            # ════════════════════════════════════════
            # STEP 7: Set description
            # ════════════════════════════════════════
            logger.info(f"   7️⃣ Setting description...")
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

            # ════════════════════════════════════════
            # STEP 8: Not made for kids
            # ════════════════════════════════════════
            logger.info(f"   8️⃣ Setting 'Not made for kids'...")

            # Scroll down to find the audience section
            await self.page.evaluate("window.scrollBy(0, 300)")
            await asyncio.sleep(1)

            kids_set = False
            for sel in ['tp-yt-paper-radio-button[name="NOT_MADE_FOR_KIDS"]',
                        'tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]']:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=5000)
                    if el:
                        await el.click()
                        kids_set = True
                        logger.info(f"   ✅ Not for kids set")
                        break
                except Exception:
                    continue

            if not kids_set:
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
                        return false;
                    }
                """)
                if kids_set:
                    logger.info(f"   ✅ Not for kids (JS)")

            if not kids_set:
                logger.warning(f"   ⚠️ Could not set kids — video may go to drafts")
                await self._screenshot("step8_kids_failed")

            # ════════════════════════════════════════
            # STEP 9: Set thumbnail
            # ════════════════════════════════════════
            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"   9️⃣ Setting thumbnail...")
                try:
                    thumb_locator = self.page.locator(
                        '#file-loader input[type="file"], input[accept*="image"]'
                    )
                    if await thumb_locator.count() > 0:
                        await thumb_locator.first.set_input_files(
                            os.path.abspath(thumbnail_path)
                        )
                        await asyncio.sleep(2)
                        logger.info(f"   ✅ Thumbnail set")
                except Exception:
                    logger.warning(f"   ⚠️ Thumbnail skipped")

            # ════════════════════════════════════════
            # STEP 10: Wait for upload to finish processing
            # ════════════════════════════════════════
            logger.info(f"   🔟 Waiting for upload to finish...")

            for i in range(60):  # Max 5 minutes
                try:
                    body = await self.page.inner_text('body')

                    if 'Checks complete' in body or 'Processing complete' in body:
                        logger.info(f"   ✅ Upload processing complete ({i*5}s)")
                        break

                    # Check for percentage
                    pct_match = re.search(r'(\d+)\s*%\s*(?:uploaded|processed)', body, re.I)
                    if pct_match:
                        logger.info(f"      Upload: {pct_match.group(0)}")

                    if 'Upload failed' in body:
                        raise Exception("YouTube reported upload failed")

                except Exception as e:
                    if 'failed' in str(e).lower():
                        raise
                await asyncio.sleep(5)
                if i > 0 and i % 6 == 0:
                    logger.info(f"      ⏳ Still processing... ({i*5}s)")

            # ════════════════════════════════════════
            # STEP 11: Click NEXT buttons (3 times)
            # ════════════════════════════════════════
            logger.info(f"   1️⃣1️⃣ Navigating to visibility...")

            for step in range(3):
                for sel in ['#next-button', 'ytcp-button#next-button']:
                    try:
                        btn = await self.page.wait_for_selector(sel, timeout=5000)
                        if btn:
                            await btn.click()
                            logger.info(f"      Next {step+1}/3 ✅")
                            break
                    except Exception:
                        continue
                await asyncio.sleep(2)

            # ════════════════════════════════════════
            # STEP 12: Set PUBLIC and Publish
            # ════════════════════════════════════════
            logger.info(f"   1️⃣2️⃣ Setting Public and Publishing...")

            # Click Public
            for sel in ['tp-yt-paper-radio-button[name="PUBLIC"]']:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=5000)
                    if el:
                        await el.click()
                        logger.info(f"      Public ✅")
                        break
                except Exception:
                    pass

            await asyncio.sleep(1)

            # Click Publish/Done
            for sel in ['#done-button', 'ytcp-button#done-button']:
                try:
                    btn = await self.page.wait_for_selector(sel, timeout=5000)
                    if btn:
                        await btn.click()
                        logger.info(f"      Publish clicked ✅")
                        break
                except Exception:
                    pass

            # Wait for confirmation
            logger.info(f"   ⏳ Confirming (max 30s)...")
            for i in range(6):
                await asyncio.sleep(5)
                try:
                    body = await self.page.inner_text('body')
                    if any(p in body for p in [
                        'Video published', 'has been published',
                        'Your video is live'
                    ]):
                        logger.info(f"   ✅ PUBLISHED CONFIRMED!")
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
