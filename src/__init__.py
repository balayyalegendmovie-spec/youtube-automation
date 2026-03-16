"""
YouTube Automation Bot — Telugu & Hindi Faceless Channels

Fully automated pipeline:
  Trending Topics → Script → Voice → Anime Video → Upload

Modules:
  - gemini_brain:     AI engine for content generation
  - trend_finder:     Finds trending topics in India
  - breathing:        Makes voice natural with emotions
  - voice_maker:      Text-to-speech generation
  - video_animator:   Anime-style video creation
  - shorts_cutter:    Cuts long video into shorts
  - thumbnail_maker:  Creates anime thumbnails
  - uploader:         YouTube browser-based upload
  - cookie_extractor: Gets YouTube session tokens
"""

__version__ = "2.0.0"
__author__ = "YouTube Automation Bot"

import logging
import sys
import os

# =============================================
# CONFIGURE LOGGING FOR GITHUB ACTIONS
# =============================================

def setup_pipeline_logging(log_level=logging.INFO):
    """
    Setup logging that works beautifully in GitHub Actions.
    
    Features:
    - Emoji prefixes for easy scanning
    - Timestamps
    - Module names
    - Both console and file output
    - GitHub Actions group markers
    """
    
    class GitHubActionsFormatter(logging.Formatter):
        """Custom formatter with emojis and GitHub Actions support"""
        
        LEVEL_EMOJIS = {
            logging.DEBUG:    '🔍',
            logging.INFO:     '✅',
            logging.WARNING:  '⚠️',
            logging.ERROR:    '❌',
            logging.CRITICAL: '🔥',
        }
        
        STEP_EMOJIS = {
            'trend_finder':    '📊',
            'gemini_brain':    '🧠',
            'breathing':       '🫁',
            'voice_maker':     '🎙️',
            'video_animator':  '🎬',
            'shorts_cutter':   '✂️',
            'thumbnail_maker': '🖼️',
            'uploader':        '📤',
            'cookie_extractor':'🍪',
            'main':            '🚀',
        }
        
        def format(self, record):
            # Get emoji for level
            emoji = self.LEVEL_EMOJIS.get(record.levelno, '📌')
            
            # Get emoji for module
            module_name = record.name.split('.')[-1] if '.' in record.name else record.name
            module_emoji = self.STEP_EMOJIS.get(module_name, '📌')
            
            # Check if running in GitHub Actions
            is_github = os.environ.get('GITHUB_ACTIONS') == 'true'
            
            # Format message
            timestamp = self.formatTime(record, '%H:%M:%S')
            
            if is_github:
                # GitHub Actions format with collapsible groups
                if 'STEP' in record.getMessage() and record.levelno == logging.INFO:
                    return f"\n{'='*60}\n{emoji} {module_emoji} [{timestamp}] {record.getMessage()}\n{'='*60}"
                elif record.levelno >= logging.ERROR:
                    return f"::error::{emoji} [{timestamp}] [{module_name}] {record.getMessage()}"
                elif record.levelno >= logging.WARNING:
                    return f"::warning::{emoji} [{timestamp}] [{module_name}] {record.getMessage()}"
                else:
                    return f"{emoji} [{timestamp}] [{module_name}] {record.getMessage()}"
            else:
                return f"{emoji} {module_emoji} [{timestamp}] [{module_name}] {record.getMessage()}"
    
    
    # Create log directory
    os.makedirs("output/logs", exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # Console handler (GitHub Actions sees this)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(GitHubActionsFormatter())
    root_logger.addHandler(console_handler)
    
    # File handler
    from datetime import datetime
    log_file = f"output/logs/pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    ))
    root_logger.addHandler(file_handler)
    
    return root_logger


# GitHub Actions helper functions
def github_group_start(title):
    """Start a collapsible group in GitHub Actions log"""
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        print(f"::group::{title}")
    else:
        print(f"\n{'━'*60}")
        print(f"  {title}")
        print(f"{'━'*60}")


def github_group_end():
    """End a collapsible group in GitHub Actions log"""
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        print("::endgroup::")
    else:
        print(f"{'━'*60}\n")


def github_set_output(name, value):
    """Set a GitHub Actions output variable"""
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
            f.write(f"{name}={value}\n")


def github_summary(markdown_text):
    """Add to GitHub Actions job summary"""
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        summary_file = os.environ.get('GITHUB_STEP_SUMMARY', '/dev/null')
        with open(summary_file, 'a') as f:
            f.write(markdown_text + '\n')
