"""
COOKIE EXTRACTOR — Get YouTube Session Tokens

This script:
1. Opens a real browser window
2. You login to YouTube manually
3. Captures ALL cookies and session tokens
4. Saves them for automated uploads later

Run separately for EACH channel (Telugu & Hindi)
since they use different Google accounts.

Usage:
    python -m src.cookie_extractor --channel telugu
    python -m src.cookie_extractor --channel hindi
"""

import asyncio
import json
import os
import sys
import argparse
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CookieExtractor:
    
    def __init__(self):
        self.cookies_dir = "config/cookies"
        os.makedirs(self.cookies_dir, exist_ok=True)
    

    async def extract_cookies(self, channel_name, cookie_file):
        """
        Interactive cookie extraction.
        Opens browser → user logs in → cookies saved.
        """
        
        from playwright.async_api import async_playwright
        
        print("\n" + "🍪" * 30)
        print(f"\n  YOUTUBE LOGIN — {channel_name.upper()} CHANNEL")
        print(f"\n" + "🍪" * 30)
        print(f"""
┌──────────────────────────────────────────────────────┐
│                                                      │
│  A browser window will open now.                     │
│                                                      │
│  Please do the following:                            │
│                                                      │
│  1. Login to the Google account for                  │
│     your {channel_name.upper()} YouTube channel              │
│                                                      │
│  2. Make sure you can see YouTube Studio              │
│     (studio.youtube.com)                             │
│                                                      │
│  3. Come back here and press ENTER                   │
│                                                      │
│  ⚠️  Use a DIFFERENT Google account for each         │
│     channel (Telugu ≠ Hindi)                         │
│                                                      │
└──────────────────────────────────────────────────────┘
        """)
        
        input("Press ENTER to open the browser...")
        
        async with async_playwright() as p:
            # Launch visible browser
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    '--start-maximized',
                    '--disable-blink-features=AutomationControlled'
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/125.0.0.0 Safari/537.36'
                ),
                locale='en-US',
                timezone_id='Asia/Kolkata'
            )
            
            page = await context.new_page()
            
            # Navigate to YouTube Studio login
            print("\n📺 Opening YouTube Studio...")
            await page.goto('https://accounts.google.com/signin/v2/identifier?service=youtube')
            
            print("\n⏳ Waiting for you to login...")
            print("   Login to your Google account in the browser window.")
            print("   After login, you should see YouTube Studio.\n")
            
            # Wait for user to login
            input("\n✅ After you've logged in successfully, press ENTER here...")
            
            # Navigate to Studio to ensure we have all cookies
            print("\n🔄 Navigating to YouTube Studio to capture all cookies...")
            await page.goto('https://studio.youtube.com', wait_until='networkidle')
            await asyncio.sleep(5)
            
            # Check if actually logged in
            current_url = page.url
            if 'accounts.google.com' in current_url:
                print("\n❌ ERROR: Still on login page. Please login first!")
                print("   Try again: python -m src.cookie_extractor --channel " + channel_name)
                await browser.close()
                return False
            
            # Capture cookies
            cookies = await context.cookies()
            
            # Capture localStorage and sessionStorage
            local_storage = await page.evaluate("() => JSON.stringify(localStorage)")
            session_storage = await page.evaluate("() => JSON.stringify(sessionStorage)")
            
            # Get channel info
            channel_info = {}
            try:
                # Try to get channel name from page
                channel_name_element = await page.query_selector('.channel-name')
                if channel_name_element:
                    channel_info['name'] = await channel_name_element.inner_text()
                
                channel_info['url'] = current_url
                channel_info['extracted_at'] = datetime.now().isoformat()
            except Exception:
                pass
            
            # Save everything
            cookie_data = {
                'cookies': cookies,
                'local_storage': json.loads(local_storage) if local_storage else {},
                'session_storage': json.loads(session_storage) if session_storage else {},
                'channel_info': channel_info,
                'extracted_at': datetime.now().isoformat(),
                'channel_type': channel_name,
                'user_agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/125.0.0.0 Safari/537.36'
                )
            }
            
            # Save to file
            with open(cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookie_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n✅ SUCCESS! Cookies saved to: {cookie_file}")
            print(f"   Total cookies captured: {len(cookies)}")
            print(f"   Channel URL: {current_url}")
            
            # Show important cookies
            important_cookies = [
                'SID', 'HSID', 'SSID', 'APISID', 'SAPISID',
                '__Secure-1PSID', '__Secure-3PSID',
                'LOGIN_INFO', 'PREF'
            ]
            
            found_cookies = [c['name'] for c in cookies if c['name'] in important_cookies]
            print(f"   Key cookies found: {', '.join(found_cookies)}")
            
            if len(found_cookies) < 3:
                print("\n⚠️  WARNING: Some important cookies are missing.")
                print("   The upload might not work. Try logging in again.")
            
            # Generate the string for GitHub Secrets
            print(f"\n{'='*60}")
            print(f"📋 FOR GITHUB SECRETS:")
            print(f"{'='*60}")
            print(f"\n1. Go to your repo → Settings → Secrets → Actions")
            secret_name = f"{'TELUGU' if channel_name == 'telugu' else 'HINDI'}_COOKIES"
            print(f"2. Create a new secret named: {secret_name}")
            print(f"3. Paste the ENTIRE contents of: {cookie_file}")
            print(f"\n   Or run this command to copy to clipboard:")
            print(f"   cat {cookie_file} | pbcopy  (Mac)")
            print(f"   cat {cookie_file} | xclip   (Linux)")
            print(f"{'='*60}\n")
            
            await browser.close()
            return True


    def verify_cookies(self, cookie_file):
        """Verify that saved cookies are still valid"""
        
        if not os.path.exists(cookie_file):
            print(f"❌ Cookie file not found: {cookie_file}")
            return False
        
        with open(cookie_file, 'r') as f:
            data = json.load(f)
        
        cookies = data.get('cookies', [])
        
        # Check for essential cookies
        essential = ['SID', 'HSID', '__Secure-1PSID']
        found = [c['name'] for c in cookies if c['name'] in essential]
        
        if len(found) >= 2:
            print(f"✅ Cookies look valid. Found: {', '.join(found)}")
            print(f"   Extracted at: {data.get('extracted_at', 'unknown')}")
            return True
        else:
            print(f"❌ Cookies may be expired. Only found: {', '.join(found)}")
            print(f"   Re-run cookie extraction!")
            return False


def main():
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(
        description='Extract YouTube session cookies for automation'
    )
    parser.add_argument(
        '--channel', '-c',
        choices=['telugu', 'hindi'],
        required=True,
        help='Which channel to login to'
    )
    parser.add_argument(
        '--verify', '-v',
        action='store_true',
        help='Verify existing cookies without re-login'
    )
    
    args = parser.parse_args()
    
    extractor = CookieExtractor()
    cookie_file = f"config/cookies/{args.channel}_channel.json"
    
    if args.verify:
        extractor.verify_cookies(cookie_file)
    else:
        asyncio.run(extractor.extract_cookies(args.channel, cookie_file))


if __name__ == "__main__":
    main()
