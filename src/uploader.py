"""
YOUTUBE UPLOADER — Browser-based upload with updated selectors
Supports latest YouTube Studio UI (2025-2026)
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
        self.playwright_instance = None
        self.browser = None
        self.context = None
        self.page = None
        logger.info(f"📤 Uploader initialized for: {channel_name}")
        logger.info(f"   Cookie file: {cookie_file}")

    async def _start_browser(self):
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
            ]
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/125.0.0.0 Safari/537.36'
            ),
            locale='en-US',
            timezone_id='Asia/Kolkata'
        )

        if os.path.exists(self.cookie_file):
            with open(self.cookie_file, 'r') as f:
                cookie_data = json.load(f)
            cookies = cookie_data
            if isinstance(cookie_data, dict):
                cookies = cookie_data.get('cookies', [])
            if cookies:
                await self.context.add_cookies(cookies)
                logger.info(f"   🍪 Loaded {len(cookies)} cookies")
            else:
                raise Exception("No cookies found!")
        else:
            raise FileNotFoundError(f"Cookie file not found: {self.cookie_file}")

        self.page = await self.context.new_page()

        # Remove automation detection
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

    async def _stop_browser(self):
        if self.context:
            try:
                cookies = await self.context.cookies()
                cookie_data = {
                    'cookies': cookies,
                    'updated_at': datetime.now().isoformat(),
                    'channel': self.channel_name
                }
                with open(self.cookie_file, 'w') as f:
                    json.dump(cookie_data, f, indent=2)
                logger.info(f"   🍪 Cookies updated and saved")
            except Exception:
                pass
        if self.browser:
            await self.browser.close()
        if self.playwright_instance:
            await self.playwright_instance.stop()

    async def _screenshot(self, name="debug"):
        try:
            ss_dir = "output/logs/screenshots"
            os.makedirs(ss_dir, exist_ok=True)
            path = f"{ss_dir}/{name}_{datetime.now().strftime('%H%M%S')}.png"
            await self.page.screenshot(path=path, full_page=True)
            logger.info(f"   📸 Debug screenshot: {path}")
        except Exception:
            pass

    async def upload_video(self, video_path, title, description,
                            tags=None, thumbnail_path=None, is_short=False):
        video_type = "Short" if is_short else "Long-form"

        logger.info(f"\n   {'─'*50}")
        logger.info(f"   📤 UPLOADING {video_type}: {title[:50]}...")
        logger.info(f"   📁 File: {video_path}")
        logger.info(f"   📊 Size: {os.path.getsize(video_path)/(1024*1024):.1f} MB")
        logger.info(f"   {'─'*50}")

        try:
            await self._start_browser()

            # Step 1: Go to YouTube Studio upload page DIRECTLY
            logger.info(f"   1️⃣ Navigating to YouTube Studio upload...")

            # Go directly to upload URL — skips needing to find Create button
            await self.page.goto(
                'https://studio.youtube.com/channel/UC/videos/upload?d=ud',
                wait_until='domcontentloaded',
                timeout=30000
            )
            await asyncio.sleep(3)

            # Check login
            if 'accounts.google.com' in self.page.url:
                logger.error(f"   ❌ NOT LOGGED IN — cookies expired!")
                await self._screenshot("login_required")
                raise Exception("Session expired — re-login required")

            logger.info(f"   ✅ YouTube Studio loaded")
            logger.info(f"   Current URL: {self.page.url[:80]}")

            # Step 2: Try to find upload dialog or navigate to it
            logger.info(f"   2️⃣ Finding upload dialog...")

            # Method 1: Direct upload URL
            upload_found = False

            # Check if upload dialog is already open
            file_input = await self.page.query_selector('input[type="file"]')
            if file_input:
                upload_found = True
                logger.info(f"   ✅ Upload dialog found (direct)")

            if not upload_found:
                # Method 2: Try clicking Create button with various selectors
                create_selectors = [
                    '#create-icon',
                    'ytcp-button#create-icon',
                    '[id="create-icon"]',
                    '#upload-icon',
                    'ytcp-icon-button#create-icon',
                    'button[aria-label="Create"]',
                    'button[aria-label="Upload videos"]',
                    '#create-button',
                    'ytcp-button:has-text("Create")',
                    'tp-yt-paper-icon-button#create-icon',
                    '#upload-button',
                ]

                for sel in create_selectors:
                    try:
                        elem = await self.page.wait_for_selector(sel, timeout=3000)
                        if elem:
                            await elem.click()
                            await asyncio.sleep(2)
                            logger.info(f"   ✅ Clicked Create via: {sel}")

                            # Now click "Upload videos" from dropdown
                            upload_menu_selectors = [
                                '#text-item-0',
                                'tp-yt-paper-item:first-child',
                                'tp-yt-paper-item:has-text("Upload")',
                                'tp-yt-paper-item:has-text("upload")',
                                '[test-id="upload-beta"]',
                                'tp-yt-paper-item:nth-child(1)',
                            ]

                            for us in upload_menu_selectors:
                                try:
                                    await self.page.click(us, timeout=3000)
                                    await asyncio.sleep(2)
                                    upload_found = True
                                    logger.info(f"   ✅ Upload menu clicked via: {us}")
                                    break
                                except Exception:
                                    continue

                            if upload_found:
                                break
                    except Exception:
                        continue

            if not upload_found:
                # Method 3: Navigate directly to upload page
                logger.info(f"   🔄 Trying direct upload navigation...")
                
                # Try multiple direct URLs
                upload_urls = [
                    'https://studio.youtube.com/channel/UC/videos/upload?d=ud',
                    'https://www.youtube.com/upload',
                    'https://studio.youtube.com',
                ]
                
                for url in upload_urls:
                    try:
                        await self.page.goto(url, wait_until='domcontentloaded', timeout=15000)
                        await asyncio.sleep(3)
                        
                        file_input = await self.page.query_selector('input[type="file"]')
                        if file_input:
                            upload_found = True
                            logger.info(f"   ✅ Upload page found via: {url}")
                            break
                    except Exception:
                        continue

            if not upload_found:
                # Method 4: Use JavaScript to trigger upload
                logger.info(f"   🔄 Trying JavaScript method...")
                try:
                    await self.page.goto('https://studio.youtube.com', 
                                        wait_until='networkidle', timeout=20000)
                    await asyncio.sleep(3)
                    
                    # Try to click using JavaScript
                    await self.page.evaluate("""
                        () => {
                            // Find and click create button
                            const buttons = document.querySelectorAll('ytcp-button, button, tp-yt-paper-icon-button');
                            for (const btn of buttons) {
                                const id = btn.id || '';
                                const label = btn.getAttribute('aria-label') || '';
                                const text = btn.textContent || '';
                                if (id.includes('create') || id.includes('upload') ||
                                    label.includes('Create') || label.includes('Upload') ||
                                    text.includes('Create') || text.includes('Upload')) {
                                    btn.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)
                    
                    await asyncio.sleep(3)
                    
                    # Click upload in dropdown
                    await self.page.evaluate("""
                        () => {
                            const items = document.querySelectorAll('tp-yt-paper-item, ytcp-ve');
                            for (const item of items) {
                                const text = item.textContent || '';
                                if (text.includes('Upload') || text.includes('upload')) {
                                    item.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)
                    
                    await asyncio.sleep(3)
                    file_input = await self.page.query_selector('input[type="file"]')
                    if file_input:
                        upload_found = True
                        logger.info(f"   ✅ Upload found via JavaScript")
                        
                except Exception as e:
                    logger.warning(f"   ⚠️ JavaScript method failed: {e}")

            if not upload_found:
                await self._screenshot("no_upload_dialog")
                
                # Log page content for debugging
                try:
                    page_title = await self.page.title()
                    logger.info(f"   Page title: {page_title}")
                    logger.info(f"   Page URL: {self.page.url}")
                    
                    # Count interactive elements
                    button_count = await self.page.evaluate(
                        "document.querySelectorAll('button, ytcp-button, tp-yt-paper-icon-button').length"
                    )
                    logger.info(f"   Buttons on page: {button_count}")
                except Exception:
                    pass
                
                raise Exception(
                    "Could not find upload dialog. "
                    "YouTube Studio UI may have changed. "
                    "Check debug screenshot."
                )

            # Step 3: Upload file
            logger.info(f"   3️⃣ Uploading file...")
            
            file_input = await self.page.query_selector('input[type="file"]')
            if not file_input:
                # Wait a bit more for it to appear
                file_input = await self.page.wait_for_selector(
                    'input[type="file"]', timeout=10000
                )
            
            if file_input:
                abs_path = os.path.abspath(video_path)
                await file_input.set_input_files(abs_path)
                logger.info(f"   ✅ File selected")
            else:
                raise Exception("File input not found")

            await asyncio.sleep(5)

            # Step 4: Fill title
            logger.info(f"   4️⃣ Setting title...")
            title_clean = title[:100]
            
            title_selectors = [
                '#textbox[aria-label*="title"]',
                '#textbox[aria-label*="Title"]',
                '#title-textarea #textbox',
                'div#textbox[contenteditable="true"]',
                'ytcp-social-suggestion-input #textbox',
            ]
            
            for sel in title_selectors:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=5000)
                    if el:
                        await el.click()
                        await self.page.keyboard.press('Control+A')
                        await self.page.keyboard.press('Delete')
                        await asyncio.sleep(0.3)
                        await el.fill(title_clean)
                        logger.info(f"   ✅ Title set")
                        break
                except Exception:
                    continue

            # Step 5: Fill description
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
                logger.warning(f"   ⚠️ Description failed")

            # Step 6: Not made for kids
            logger.info(f"   6️⃣ Setting audience...")
            try:
                kids_selectors = [
                    'tp-yt-paper-radio-button[name="NOT_MADE_FOR_KIDS"]',
                    '#audience tp-yt-paper-radio-button:nth-child(2)',
                    'tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]',
                ]
                for sel in kids_selectors:
                    try:
                        el = await self.page.wait_for_selector(sel, timeout=3000)
                        if el:
                            await el.click()
                            logger.info(f"   ✅ Not for kids set")
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            # Step 7: Set thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"   7️⃣ Setting thumbnail...")
                try:
                    thumb_selectors = [
                        '#file-loader input[type="file"]',
                        'input[accept="image/jpeg,image/png"]',
                        '#still-picker input[type="file"]',
                    ]
                    for sel in thumb_selectors:
                        try:
                            thumb_input = await self.page.query_selector(sel)
                            if thumb_input:
                                await thumb_input.set_input_files(
                                    os.path.abspath(thumbnail_path)
                                )
                                await asyncio.sleep(3)
                                logger.info(f"   ✅ Thumbnail set")
                                break
                        except Exception:
                            continue
                except Exception:
                    logger.warning(f"   ⚠️ Thumbnail failed")

            # Step 8: Wait for upload processing
            logger.info(f"   8️⃣ Waiting for upload processing...")
            await self._wait_for_processing()

            # Step 9: Navigate through steps and publish
            logger.info(f"   9️⃣ Publishing...")
            await self._publish()

            # Step 10: Get URL
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

    async def _wait_for_processing(self):
        for i in range(60):  # Max 5 minutes
            try:
                page_text = await self.page.inner_text('body')
                if any(phrase in page_text for phrase in [
                    'Checks complete', 'Upload complete',
                    'Processing complete', 'SD', 'HD'
                ]):
                    logger.info(f"   ✅ Processing complete")
                    return
                if 'Upload failed' in page_text:
                    raise Exception("YouTube reported upload failed")
            except Exception as e:
                if 'failed' in str(e).lower():
                    raise
            await asyncio.sleep(5)
            if i % 12 == 0 and i > 0:
                logger.info(f"      ⏳ Processing... ({i*5}s)")

    async def _publish(self):
        # Click NEXT 3 times
        for step in range(3):
            try:
                next_selectors = [
                    '#next-button',
                    'ytcp-button#next-button',
                    '#step-badge-3',
                ]
                for sel in next_selectors:
                    try:
                        btn = await self.page.wait_for_selector(sel, timeout=5000)
                        if btn:
                            await btn.click()
                            await asyncio.sleep(2)
                            logger.info(f"      Next clicked (step {step+1})")
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        await asyncio.sleep(2)

        # Set PUBLIC
        try:
            public_selectors = [
                'tp-yt-paper-radio-button[name="PUBLIC"]',
                '#privacy-radios tp-yt-paper-radio-button:nth-child(3)',
            ]
            for sel in public_selectors:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=3000)
                    if el:
                        await el.click()
                        await asyncio.sleep(1)
                        logger.info(f"      Set to Public")
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Click PUBLISH/DONE
        try:
            done_selectors = [
                '#done-button',
                'ytcp-button#done-button',
            ]
            for sel in done_selectors:
                try:
                    btn = await self.page.wait_for_selector(sel, timeout=5000)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(5)
                        logger.info(f"      Published!")
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"      Publish failed: {e}")
            await self._screenshot("publish_failed")

    async def _get_video_url(self):
        try:
            page_content = await self.page.content()
            patterns = [
                r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
                r'youtu\.be/([a-zA-Z0-9_-]{11})',
                r'/video/([a-zA-Z0-9_-]{11})',
                r'video_id["\s:=]+["\']?([a-zA-Z0-9_-]{11})',
            ]
            for pattern in patterns:
                match = re.search(pattern, page_content)
                if match:
                    return f"https://youtube.com/watch?v={match.group(1)}"

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
        return asyncio.run(
            self.upload_video(video_path, title, description,
                             tags, thumbnail_path, is_short)
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Uploader ready")
