"""
Run this to check if your repo is correctly set up.
python check_repo.py
"""

import os
import sys

print("\n" + "="*60)
print("  REPO HEALTH CHECK")
print("="*60 + "\n")

required_files = {
    "requirements.txt": True,
    "main.py": True,
    "setup.py": True,
    "config/config.yaml": True,
    ".github/workflows/youtube_automation.yml": True,
    "src/__init__.py": True,
    "src/gemini_brain.py": True,
    "src/trend_finder.py": True,
    "src/breathing.py": True,
    "src/voice_maker.py": True,
    "src/video_animator.py": True,
    "src/shorts_cutter.py": True,
    "src/thumbnail_maker.py": True,
    "src/uploader.py": True,
    "src/cookie_extractor.py": True,
}

all_ok = True
missing = []

for filepath, required in required_files.items():
    exists = os.path.exists(filepath)
    status = "OK" if exists else "MISSING"
    icon = "✅" if exists else "❌"
    print(f"  {icon} {filepath:<50} {status}")
    
    if not exists and required:
        all_ok = False
        missing.append(filepath)

# Check requirements.txt content
print(f"\n{'─'*60}")
print("  Checking requirements.txt content...")

if os.path.exists("requirements.txt"):
    with open("requirements.txt", "r") as f:
        content = f.read()
    
    bad_lines = []
    for i, line in enumerate(content.split("\n"), 1):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("---") or line.startswith("==="):
            bad_lines.append((i, line))
            print(f"  ❌ Line {i}: '{line}' — THIS WILL CAUSE pip ERROR")
    
    if not bad_lines:
        print(f"  ✅ requirements.txt looks clean")
    else:
        print(f"\n  ❌ FIX: Remove lines with --- or === from requirements.txt")
        all_ok = False

# Check config.yaml
print(f"\n{'─'*60}")
print("  Checking config.yaml...")

if os.path.exists("config/config.yaml"):
    try:
        import yaml
        with open("config/config.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        checks = {
            "gemini.api_key": config.get("gemini", {}).get("api_key", ""),
            "gemini.model": config.get("gemini", {}).get("model", ""),
            "channels.telugu": "telugu" in config.get("channels", {}),
            "channels.hindi": "hindi" in config.get("channels", {}),
            "footage.pexels_api_key": config.get("footage", {}).get("pexels_api_key", ""),
        }
        
        for key, value in checks.items():
            if value and value != "" and value != "${GEMINI_API_KEY}" and value != "${PEXELS_API_KEY}":
                print(f"  ✅ {key}: configured")
            else:
                print(f"  ⚠️  {key}: needs to be set (OK if using GitHub Secrets)")
        
        print(f"  ✅ config.yaml is valid YAML")
        
    except yaml.YAMLError as e:
        print(f"  ❌ config.yaml has YAML errors: {e}")
        all_ok = False
    except ImportError:
        print(f"  ⚠️  PyYAML not installed locally — can't validate")
else:
    print(f"  ❌ config.yaml not found!")

# Check for common issues in Python files
print(f"\n{'─'*60}")
print("  Checking Python files for syntax errors...")

python_files = [f for f in required_files if f.endswith(".py")]
for filepath in python_files:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                source = f.read()
            compile(source, filepath, "exec")
            print(f"  ✅ {filepath}: syntax OK")
        except SyntaxError as e:
            print(f"  ❌ {filepath}: SYNTAX ERROR at line {e.lineno}: {e.msg}")
            all_ok = False

# Summary
print(f"\n{'='*60}")
if all_ok:
    print("  ✅ ALL CHECKS PASSED!")
    print("  Your repo is ready to run.")
else:
    print("  ❌ SOME CHECKS FAILED!")
    print(f"\n  Missing files:")
    for f in missing:
        print(f"    - {f}")
    print(f"\n  Fix these issues before running the pipeline.")
print("="*60 + "\n")

sys.exit(0 if all_ok else 1)
