"""
FILE BACKUP — Uploads generated videos to GitHub Releases
No extra setup needed! Uses the existing GITHUB_TOKEN.

Each pipeline run creates a GitHub Release with:
  - Long-form video
  - All shorts
  - All thumbnails
  - Script text

Files are downloadable from the Releases page.
Free, unlimited, no quota issues.
"""

import os
import json
import logging
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)


class DriveUploader:
    """
    Despite the name, this uploads to GitHub Releases.
    Kept same class name so main.py doesn't need changes.
    """

    def __init__(self):
        self.github_token = os.environ.get('GITHUB_TOKEN', '')
        self.repo = os.environ.get('GITHUB_REPOSITORY', '')
        self.is_github = os.environ.get('GITHUB_ACTIONS') == 'true'

        if self.is_github and self.repo:
            self.enabled = True
            logger.info("☁️ GitHub Release uploader initialized")
        else:
            # Try Google Drive as fallback
            self.refresh_token = os.environ.get('GDRIVE_REFRESH_TOKEN', '')
            self.client_id = os.environ.get('GDRIVE_CLIENT_ID', '')
            self.client_secret = os.environ.get('GDRIVE_CLIENT_SECRET', '')
            self.folder_id = os.environ.get('GDRIVE_FOLDER_ID', '')

            if self.refresh_token and self.client_id and self.folder_id:
                self.enabled = True
                self.use_drive = True
                logger.info("☁️ Google Drive uploader initialized")
            else:
                self.enabled = False
                self.use_drive = False
                logger.info("☁️ Backup disabled (not in GitHub Actions)")
                return

        self.use_drive = False

    def _create_github_release(self, tag, title):
        """Create a GitHub Release"""
        try:
            import requests

            url = f"https://api.github.com/repos/{self.repo}/releases"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }

            data = {
                'tag_name': tag,
                'name': title,
                'body': f'Auto-generated content from YouTube Automation Bot\n\nCreated: {datetime.now().isoformat()}',
                'draft': False,
                'prerelease': False
            }

            # Create tag first
            try:
                tag_url = f"https://api.github.com/repos/{self.repo}/git/refs"
                sha_resp = requests.get(
                    f"https://api.github.com/repos/{self.repo}/git/ref/heads/main",
                    headers=headers, timeout=10
                )
                if sha_resp.status_code == 200:
                    sha = sha_resp.json().get('object', {}).get('sha', '')
                    if sha:
                        requests.post(tag_url, headers=headers, json={
                            'ref': f'refs/tags/{tag}',
                            'sha': sha
                        }, timeout=10)
            except Exception:
                pass

            resp = requests.post(url, headers=headers, json=data, timeout=15)

            if resp.status_code == 201:
                release = resp.json()
                logger.info(f"   ✅ Release created: {title}")
                return release.get('id'), release.get('upload_url', '').split('{')[0]
            elif resp.status_code == 422:
                # Tag already exists, try with timestamp
                data['tag_name'] = f"{tag}-{datetime.now().strftime('%H%M%S')}"
                resp = requests.post(url, headers=headers, json=data, timeout=15)
                if resp.status_code == 201:
                    release = resp.json()
                    return release.get('id'), release.get('upload_url', '').split('{')[0]

            logger.error(f"   ❌ Release creation failed: {resp.status_code} {resp.text[:200]}")
            return None, None

        except Exception as e:
            logger.error(f"   ❌ Release error: {e}")
            return None, None

    def _upload_to_release(self, upload_url, file_path, file_name=None):
        """Upload file to GitHub Release"""
        try:
            import requests

            name = file_name or os.path.basename(file_path)
            size = os.path.getsize(file_path)
            size_mb = size / (1024 * 1024)

            ext = os.path.splitext(file_path)[1].lower()
            content_types = {
                '.mp4': 'video/mp4',
                '.mp3': 'audio/mpeg',
                '.jpg': 'image/jpeg',
                '.png': 'image/png',
                '.txt': 'text/plain',
                '.json': 'application/json',
            }
            content_type = content_types.get(ext, 'application/octet-stream')

            url = f"{upload_url}?name={name}"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Content-Type': content_type,
            }

            with open(file_path, 'rb') as f:
                data = f.read()

            resp = requests.post(url, headers=headers, data=data, timeout=300)

            if resp.status_code == 201:
                download_url = resp.json().get('browser_download_url', '')
                logger.info(f"   ☁️ Uploaded: {name} ({size_mb:.1f} MB)")
                return {
                    'name': name,
                    'size_mb': round(size_mb, 1),
                    'url': download_url
                }
            else:
                logger.error(f"   ❌ Upload failed {name}: {resp.status_code}")
                return None

        except Exception as e:
            logger.error(f"   ❌ Upload error {file_path}: {e}")
            return None

    def _drive_upload(self, **kwargs):
        """Fallback: Google Drive OAuth upload"""
        import requests as http_requests

        TOKEN_URL = "https://oauth2.googleapis.com/token"
        UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
        FILES_URL = "https://www.googleapis.com/drive/v3/files"

        # Get access token
        resp = http_requests.post(TOKEN_URL, data={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token'
        }, timeout=15)

        if resp.status_code != 200:
            logger.error(f"   ❌ Drive token failed")
            return None

        token = resp.json().get('access_token')
        headers = {'Authorization': f'Bearer {token}'}

        # Create folder
        topic = kwargs.get('topic', 'video')
        language = kwargs.get('language', 'unknown')
        safe = "".join(c for c in topic[:30] if c.isalnum() or c in ' _-').strip()
        folder_name = f"{datetime.now().strftime('%Y-%m-%d')}_{language}_{safe}"

        folder_resp = http_requests.post(FILES_URL,
            headers={**headers, 'Content-Type': 'application/json'},
            json={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder',
                  'parents': [self.folder_id]}, timeout=15)

        if folder_resp.status_code != 200:
            return None

        folder_id = folder_resp.json().get('id')
        uploaded = []

        for file_path in kwargs.get('files', []):
            if not os.path.exists(file_path):
                continue
            name = os.path.basename(file_path)
            size = os.path.getsize(file_path)

            ext = os.path.splitext(file_path)[1].lower()
            mime = {'mp4': 'video/mp4', 'mp3': 'audio/mpeg', 'jpg': 'image/jpeg',
                    'txt': 'text/plain'}.get(ext.strip('.'), 'application/octet-stream')

            init = http_requests.post(f"{UPLOAD_URL}?uploadType=resumable",
                headers={**headers, 'Content-Type': 'application/json; charset=UTF-8',
                         'X-Upload-Content-Type': mime,
                         'X-Upload-Content-Length': str(size)},
                json={'name': name, 'parents': [folder_id]}, timeout=15)

            if init.status_code != 200:
                continue

            upload_url = init.headers.get('Location')
            with open(file_path, 'rb') as f:
                up = http_requests.put(upload_url,
                    headers={'Content-Type': mime}, data=f.read(), timeout=300)
                if up.status_code in [200, 201]:
                    uploaded.append({'name': name, 'size_mb': round(size/(1024*1024), 1)})
                    logger.info(f"   ☁️ Drive: {name}")

        link = f"https://drive.google.com/drive/folders/{folder_id}"
        return {'folder_link': link, 'files': uploaded,
                'total_size_mb': sum(f['size_mb'] for f in uploaded)}

    def upload_pipeline_output(self, run_id, language, topic,
                                long_video_path=None, shorts=None,
                                thumbnail_long_path=None,
                                short_thumbnails=None,
                                script_text=None, output_dir=None):
        if not self.enabled:
            logger.info("☁️ Backup skipped (not configured)")
            return None

        logger.info(f"\n☁️ STEP: Backing up generated content...")

        # Collect all files
        all_files = []
        if long_video_path and os.path.exists(long_video_path):
            all_files.append(long_video_path)
        if thumbnail_long_path and os.path.exists(thumbnail_long_path):
            all_files.append(thumbnail_long_path)
        if shorts:
            for s in shorts:
                p = s.get('path', '')
                if p and os.path.exists(p):
                    all_files.append(p)
        if short_thumbnails:
            for tp in short_thumbnails:
                if tp and os.path.exists(tp):
                    all_files.append(tp)

        # Save script
        if script_text and output_dir:
            sp = os.path.join(output_dir, 'script.txt')
            try:
                with open(sp, 'w', encoding='utf-8') as f:
                    f.write(f"Topic: {topic}\nLanguage: {language}\n")
                    f.write(f"Date: {datetime.now().isoformat()}\n{'='*50}\n\n")
                    f.write(script_text)
                all_files.append(sp)
            except Exception:
                pass

        # Try Google Drive first if configured
        if self.use_drive:
            try:
                result = self._drive_upload(
                    topic=topic, language=language, files=all_files
                )
                if result and result.get('files'):
                    total = result.get('total_size_mb', 0)
                    logger.info(f"\n   ☁️ Drive backup: {len(result['files'])} files, {total:.1f} MB")
                    logger.info(f"   🔗 {result.get('folder_link', '')}")
                    return result
            except Exception as e:
                logger.warning(f"   ⚠️ Drive failed: {e}, trying GitHub Releases...")

        # GitHub Releases
        if not self.is_github:
            logger.info("   ☁️ Not in GitHub Actions, skipping release")
            return None

        safe_topic = "".join(c for c in topic[:20] if c.isalnum() or c in '-_').strip()
        tag = f"v{datetime.now().strftime('%Y%m%d-%H%M')}-{safe_topic}"
        title = f"📹 {language.upper()}: {topic[:50]}"

        release_id, upload_url = self._create_github_release(tag, title)
        if not release_id or not upload_url:
            logger.error("   ❌ Could not create release")
            return None

        uploaded = []
        for file_path in all_files:
            result = self._upload_to_release(upload_url, file_path)
            if result:
                uploaded.append(result)

        total = sum(f.get('size_mb', 0) for f in uploaded)
        release_url = f"https://github.com/{self.repo}/releases/tag/{tag}"

        logger.info(f"\n   ☁️ Backup complete: {len(uploaded)} files, {total:.1f} MB")
        logger.info(f"   🔗 {release_url}")

        return {
            'folder_link': release_url,
            'files': uploaded,
            'total_size_mb': round(total, 1)
        }
