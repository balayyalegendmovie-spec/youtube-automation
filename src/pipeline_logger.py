"""
═══════════════════════════════════════════════════════════════
  PIPELINE LOGGER
  Beautiful, detailed logging for GitHub Actions output
  
  Shows:
  ✅ What step is currently running
  ✅ Progress within each step
  ✅ Time taken per step
  ✅ Success/failure status
  ✅ Summary at the end
═══════════════════════════════════════════════════════════════
"""

import time
import sys
import logging
from datetime import datetime
from contextlib import contextmanager


class PipelineLogger:
    """Rich logging for GitHub Actions with step tracking"""
    
    EMOJIS = {
        'start':     '🚀',
        'step':      '📌',
        'progress':  '⏳',
        'success':   '✅',
        'error':     '❌',
        'warning':   '⚠️',
        'info':      'ℹ️',
        'time':      '⏱️',
        'topic':     '💡',
        'script':    '📝',
        'review':    '🔍',
        'voice':     '🎙️',
        'anime':     '🎨',
        'video':     '🎥',
        'shorts':    '✂️',
        'thumbnail': '🖼️',
        'upload':    '📤',
        'done':      '🎉',
        'stats':     '📊',
        'cleanup':   '🧹',
    }
    
    def __init__(self, pipeline_name="YouTube Automation"):
        self.pipeline_name = pipeline_name
        self.start_time = time.time()
        self.step_times = {}
        self.step_statuses = {}
        self.current_step = None
        self.step_count = 0
        self.total_steps = 12
        
        # Configure standard logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(message)s',
            stream=sys.stdout
        )
        self.logger = logging.getLogger('pipeline')
        
        # Flush stdout for GitHub Actions real-time output
        sys.stdout.reconfigure(line_buffering=True)
    

    def _flush(self):
        sys.stdout.flush()
    

    def _timestamp(self):
        return datetime.now().strftime('%H:%M:%S')
    

    def pipeline_start(self, language, run_id):
        """Log pipeline start"""
        
        self.language = language
        self.run_id = run_id
        self.start_time = time.time()
        
        print()
        print("═" * 70)
        print(f"  {self.EMOJIS['start']}  {self.pipeline_name}")
        print(f"  Language: {language.upper()} | Run: {run_id}")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("═" * 70)
        print()
        self._flush()
    

    @contextmanager
    def step(self, step_number, step_name, emoji_key='step'):
        """Context manager for tracking a pipeline step"""
        
        self.step_count = step_number
        self.current_step = step_name
        step_start = time.time()
        
        emoji = self.EMOJIS.get(emoji_key, self.EMOJIS['step'])
        
        # GitHub Actions group (collapsible)
        print(f"::group::{emoji} Step {step_number}/{self.total_steps}: {step_name}")
        print()
        print(f"  {'─' * 55}")
        print(f"  {emoji}  STEP {step_number}: {step_name}")
        print(f"  {'─' * 55}")
        print(f"  ⏱️  Started at {self._timestamp()}")
        print()
        self._flush()
        
        try:
            yield self
            
            # Step succeeded
            elapsed = time.time() - step_start
            self.step_times[step_name] = elapsed
            self.step_statuses[step_name] = 'success'
            
            print()
            print(f"  ✅  STEP {step_number} COMPLETE: {step_name}")
            print(f"  ⏱️  Duration: {elapsed:.1f}s")
            print(f"  {'─' * 55}")
            print()
            print("::endgroup::")
            self._flush()
            
        except Exception as e:
            # Step failed
            elapsed = time.time() - step_start
            self.step_times[step_name] = elapsed
            self.step_statuses[step_name] = 'failed'
            
            print()
            print(f"  ❌  STEP {step_number} FAILED: {step_name}")
            print(f"  ❌  Error: {str(e)}")
            print(f"  ⏱️  Failed after: {elapsed:.1f}s")
            print(f"  {'─' * 55}")
            print()
            print("::endgroup::")
            self._flush()
            raise
    

    def log(self, message, level='info'):
        """Log a message within a step"""
        
        emoji = self.EMOJIS.get(level, 'ℹ️')
        timestamp = self._timestamp()
        print(f"  {emoji}  [{timestamp}] {message}")
        self._flush()
    

    def progress(self, current, total, item_name=""):
        """Log progress within a step"""
        
        percentage = int((current / total) * 100)
        bar_length = 30
        filled = int(bar_length * current / total)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        extra = f" — {item_name}" if item_name else ""
        print(f"  ⏳  [{bar}] {percentage}% ({current}/{total}){extra}")
        self._flush()
    

    def detail(self, key, value):
        """Log a key-value detail"""
        
        print(f"      📎 {key}: {value}")
        self._flush()
    

    def sub_step(self, message):
        """Log a sub-step"""
        
        print(f"    → {message}")
        self._flush()
    

    def pipeline_end(self, results=None):
        """Log pipeline completion with summary"""
        
        total_time = time.time() - self.start_time
        
        print()
        print("═" * 70)
        print(f"  {self.EMOJIS['done']}  PIPELINE COMPLETE")
        print("═" * 70)
        print()
        
        # Step summary table
        print("  📊  STEP SUMMARY")
        print(f"  {'─' * 55}")
        print(f"  {'Step':<35} {'Status':<10} {'Time':>8}")
        print(f"  {'─' * 55}")
        
        for step_name, status in self.step_statuses.items():
            time_taken = self.step_times.get(step_name, 0)
            status_emoji = '✅' if status == 'success' else '❌'
            print(f"  {step_name:<35} {status_emoji:<10} {time_taken:>7.1f}s")
        
        print(f"  {'─' * 55}")
        print(f"  {'TOTAL':<35} {'':10} {total_time:>7.1f}s")
        print()
        
        # Results summary
        if results:
            print("  📤  UPLOAD SUMMARY")
            print(f"  {'─' * 55}")
            
            long_count = len([v for v in results.get('uploaded', []) 
                            if v.get('type') == 'long_form'])
            short_count = len([v for v in results.get('uploaded', []) 
                             if v.get('type') == 'short'])
            
            print(f"  Long-form videos uploaded:  {long_count}")
            print(f"  Shorts uploaded:            {short_count}")
            print(f"  Total videos:               {long_count + short_count}")
            
            if results.get('uploaded'):
                print()
                print("  📎  Video URLs:")
                for v in results['uploaded']:
                    type_emoji = '🎥' if v['type'] == 'long_form' else '📱'
                    print(f"    {type_emoji}  {v.get('url', 'N/A')}")
        
        print()
        print("═" * 70)
        print(f"  Total pipeline time: {total_time:.1f}s ({total_time/60:.1f} min)")
        print("═" * 70)
        print()
        self._flush()
    

    def pipeline_error(self, error):
        """Log pipeline-level error"""
        
        total_time = time.time() - self.start_time
        
        print()
        print("═" * 70)
        print(f"  ❌  PIPELINE FAILED")
        print("═" * 70)
        print(f"  Error: {str(error)}")
        print(f"  Failed at step: {self.current_step or 'Unknown'}")
        print(f"  Time elapsed: {total_time:.1f}s")
        print("═" * 70)
        print()
        self._flush()
