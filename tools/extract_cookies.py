"""
═══════════════════════════════════════════════════════════════
  YOUTUBE COOKIE EXTRACTOR
  Run this LOCALLY on your computer (not on GitHub Actions)
  
  What it does:
  1. Opens a browser window
  2. You login to YouTube manually
  3. Saves cookies as base64 string
  4. You paste that string into GitHub Secrets
  
  Run separately for each channel (Telugu and Hindi)
═══════════════════════════════════════════════════════════════
"""

import asyncio
import json
import base64
import sys
import os


async def extract_cookies(channel_name: str):
    """Extract YouTube cookies interactively"""
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("\n❌ Playwright not installed!")
        print("Run: pip install playwright")
        print("Then: python -m playwright install chromium\n")
        sys.exit(1)
    
    print("\n" + "=" * 65)
    print(f"  🔐 YOUTUBE COOKIE EXTRACTION — {channel_name.upper()} CHANNEL")
    print("=" * 65)
    print()
    print("  A Chrome window will open now.")
    print("  Please do the following:")
    print()
    print("  1. Login to the Google account for your")
    print(f"     {channel_name.upper()} YouTube channel")
    print("  2. Make sure you can see YouTube Studio")
    print("  3. Come back here and press ENTER")
    print()
    print("=" * 65)
    
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
            viewport={'width': 1366, 'height': 768},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/125.0.0.0 Safari/537.36'
            ),
            locale='en-US'
        )
        
        page = await context.new_page()
        
        # Navigate to YouTube Studio
        print("\n⏳ Opening YouTube Studio...")
        await page.goto('https://studio.youtube.com', wait_until='networkidle')
        
        print("\n✅ Browser is open!")
        print()
        input(">>> After logging in successfully, press ENTER here... ")
        
        # Verify we're logged in
        current_url = page.url
        print(f"\n📍 Current URL: {current_url}")
        
        if 'accounts.google.com' in current_url:
            print("\n⚠️  It looks like you're still on the login page!")
            print("    Please complete the login first.")
            input("\n>>> Press ENTER when login is complete... ")
        
        # Navigate to YouTube Studio to ensure all cookies are set
        await page.goto('https://studio.youtube.com', wait_until='networkidle')
        await asyncio.sleep(3)
        
        # Also visit regular YouTube to get all necessary cookies
        await page.goto('https://www.youtube.com', wait_until='networkidle')
        await asyncio.sleep(2)
        
        # Extract cookies
        cookies = await context.cookies()
        
        # Filter relevant cookies (YouTube + Google auth)
        relevant_domains = [
            '.youtube.com',
            'youtube.com',
            'studio.youtube.com',
            '.google.com',
            'accounts.google.com',
            '.googleapis.com'
        ]
        
        filtered_cookies = []
        for cookie in cookies:
            domain = cookie.get('domain', '')
            if any(d in domain for d in relevant_domains):
                # Remove expiry for session cookies that need it
                filtered_cookies.append({
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': cookie['domain'],
                    'path': cookie.get('path', '/'),
                    'secure': cookie.get('secure', False),
                    'httpOnly': cookie.get('httpOnly', False),
                    'sameSite': cookie.get('sameSite', 'Lax')
                })
        
        await browser.close()
        
        if not filtered_cookies:
            print("\n❌ No cookies captured! Login may have failed.")
            print("   Please try again.\n")
            return
        
        print(f"\n✅ Captured {len(filtered_cookies)} cookies!")
        
        # Convert to JSON then base64
        cookies_json = json.dumps(filtered_cookies, indent=2)
        cookies_b64 = base64.b64encode(cookies_json.encode()).decode()
        
        # Save locally for reference
        local_file = f"cookies_{channel_name}.json"
        with open(local_file, 'w') as f:
            f.write(cookies_json)
        print(f"📄 Cookies saved locally: {local_file}")
        
        # Print base64 for GitHub Secrets
        print()
        print("=" * 65)
        print(f"  📋 COPY THE TEXT BELOW INTO GITHUB SECRETS")
        print(f"  Secret name: {channel_name.upper()}_COOKIES")
        print("=" * 65)
        print()
        print(cookies_b64)
        print()
        print("=" * 65)
        print()
        print("  Steps:")
        print("  1. Copy ALL the text above (it's one long line)")
        print("  2. Go to your GitHub repo → Settings → Secrets → Actions")
        print(f"  3. Create new secret: {channel_name.upper()}_COOKIES")
        print("  4. Paste the copied text as the value")
        print("  5. Save")
        print()
        
        # Also save to clipboard if possible
        try:
            import subprocess
            process = subprocess.Popen(
                ['clip'] if sys.platform == 'win32' else 
                ['xclip', '-selection', 'clipboard'],
                stdin=subprocess.PIPE
            )
            process.communicate(cookies_b64.encode())
            print("  ✅ Also copied to clipboard!\n")
        except Exception:
            print("  (Could not copy to clipboard — copy manually)\n")
        
        return cookies_b64


def main():
    print("\n" + "🔐" * 32)
    print("\n  YOUTUBE AUTOMATION — COOKIE EXTRACTOR\n")
    print("🔐" * 32 + "\n")
    
    print("  This tool extracts YouTube login cookies")
    print("  for automated uploads via GitHub Actions.\n")
    print("  You need to run this for EACH YouTube channel.\n")
    
    print("  Which channel do you want to setup?\n")
    print("  1. Telugu channel")
    print("  2. Hindi channel")
    print("  3. Both channels")
    print()
    
    choice = input("  Enter choice (1/2/3): ").strip()
    
    channels = []
    if choice == '1':
        channels = ['telugu']
    elif choice == '2':
        channels = ['hindi']
    elif choice == '3':
        channels = ['telugu', 'hindi']
    else:
        print("\n  Invalid choice. Running for both.\n")
        channels = ['telugu', 'hindi']
    
    for channel in channels:
        asyncio.run(extract_cookies(channel))
        
        if len(channels) > 1 and channel != channels[-1]:
            print("\n" + "-" * 65)
            print("  Now setting up the next channel...")
            print("  You may need to LOGOUT and login with a DIFFERENT account!")
            input("\n  Press ENTER when ready... ")
    
    print("\n✅ All done!")
    print("\nNext step: Add the secrets to GitHub and run the workflow.\n")


if __name__ == "__main__":
    # Install playwright browsers if needed
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Installing playwright...")
        os.system(f"{sys.executable} -m pip install playwright")
        os.system(f"{sys.executable} -m playwright install chromium")
    
    main()
