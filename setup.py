"""
FIRST-TIME SETUP SCRIPT

Run once before starting automation:
1. Checks system dependencies
2. Creates directory structure
3. Installs Playwright browsers
4. Downloads fonts for Telugu/Hindi
5. Guides YouTube cookie extraction
"""

import os
import sys
import subprocess
import logging
import requests

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()


def banner():
    print("\n" + "="*60)
    print("  🤖 YOUTUBE AUTOMATION BOT — FIRST TIME SETUP")
    print("="*60 + "\n")


def check_python():
    v = sys.version_info
    logger.info(f"✅ Python {v.major}.{v.minor}.{v.micro}")
    if v.major < 3 or (v.major == 3 and v.minor < 9):
        logger.error("❌ Python 3.9+ required!")
        sys.exit(1)


def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=10)
        if result.returncode == 0:
            logger.info("✅ FFmpeg installed")
            return
    except Exception:
        pass
    
    logger.error("❌ FFmpeg NOT FOUND")
    logger.info("   Install: sudo apt install ffmpeg")
    logger.info("   Or: brew install ffmpeg (Mac)")


def check_packages():
    packages = {
        'google.generativeai': 'google-generativeai',
        'edge_tts': 'edge-tts',
        'moviepy': 'moviepy',
        'PIL': 'Pillow',
        'cv2': 'opencv-python-headless',
        'playwright': 'playwright',
        'yaml': 'pyyaml',
        'requests': 'requests',
        'bs4': 'beautifulsoup4',
    }
    
    missing = []
    for module, pip_name in packages.items():
        try:
            __import__(module)
            logger.info(f"  ✅ {pip_name}")
        except ImportError:
            logger.error(f"  ❌ {pip_name} — MISSING")
            missing.append(pip_name)
    
    if missing:
        logger.info(f"\n  Install missing: pip install {' '.join(missing)}")


def create_directories():
    dirs = [
        "config/cookies",
        "assets/fonts", "assets/music", "assets/sounds", "assets/overlays",
        "output/logs", "output/logs/screenshots",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    logger.info("✅ Directories created")


def install_playwright():
    logger.info("Installing Playwright Chromium...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                   capture_output=True)
    logger.info("✅ Playwright browser installed")


def download_fonts():
    fonts = {
        "NotoSansTelugu-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/notosanstelugu/NotoSansTelugu%5Bwdth%2Cwght%5D.ttf",
        "NotoSansDevanagari-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf",
    }
    
    for name, url in fonts.items():
        path = f"assets/fonts/{name}"
        if os.path.exists(path):
            logger.info(f"  ✅ {name} already exists")
            continue
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                with open(path, 'wb') as f:
                    f.write(resp.content)
                logger.info(f"  ✅ Downloaded {name}")
            else:
                logger.warning(f"  ⚠️ Could not download {name}")
                logger.info(f"     Get from: https://fonts.google.com/noto")
        except Exception as e:
            logger.warning(f"  ⚠️ Font download failed: {e}")


def setup_cookies():
    print("\n" + "="*60)
    print("  YouTube Account Setup")
    print("="*60)
    print("""
  You need to login to YouTube for each channel.
  
  Run these commands separately:
  
    python -m src.cookie_extractor --channel telugu
    python -m src.cookie_extractor --channel hindi
  
  Each opens a browser for you to login.
  Use DIFFERENT Google accounts for each channel!
""")
    
    choice = input("  Run Telugu cookie setup now? (y/n): ").strip().lower()
    if choice == 'y':
        subprocess.run([sys.executable, "-m", "src.cookie_extractor", "--channel", "telugu"])
    
    choice = input("  Run Hindi cookie setup now? (y/n): ").strip().lower()
    if choice == 'y':
        subprocess.run([sys.executable, "-m", "src.cookie_extractor", "--channel", "hindi"])


def final_checklist():
    print("\n" + "="*60)
    print("  📋 FINAL CHECKLIST")
    print("="*60)
    print("""
  Before running the bot, make sure:

  1. ✏️ Add Gemini API key to config/config.yaml
     Get free: https://aistudio.google.com/apikey

  2. ✏️ Add Pexels API key to config/config.yaml
     Get free: https://www.pexels.com/api/

  3. 🎵 Download 2-3 background music tracks
     From: https://pixabay.com/music/search/background/
     Save to: assets/music/

  4. 🍪 Run cookie extraction for each channel

  5. 🧪 Test with: python main.py --language telugu --test

  6. 🚀 Start: python main.py --language all

  For GitHub Actions:
  - Add secrets: GEMINI_API_KEY, PEXELS_API_KEY
  - Add secrets: TELUGU_COOKIES, HINDI_COOKIES
  - Enable workflow in Actions tab
""")


def main():
    banner()
    
    print("Step 1: Checking system...\n")
    check_python()
    check_ffmpeg()
    
    print("\nStep 2: Checking Python packages...\n")
    check_packages()
    
    print("\nStep 3: Creating directories...\n")
    create_directories()
    
    print("\nStep 4: Installing Playwright...\n")
    install_playwright()
    
    print("\nStep 5: Downloading fonts...\n")
    download_fonts()
    
    print("\nStep 6: Music reminder...\n")
    print("  ⚠️ Download background music from https://pixabay.com/music/")
    print("  Save to: assets/music/\n")
    
    print("\nStep 7: YouTube login...\n")
    setup_cookies()
    
    final_checklist()
    
    print("\n✅ SETUP COMPLETE!\n")


if __name__ == "__main__":
    main()
