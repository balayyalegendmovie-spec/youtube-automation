"""
GOOGLE DRIVE UPLOADER — OAuth2 based (works with personal Gmail)
"""

import os
import json
import logging
from datetime import datetime
import requests as http_requests

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
FILES_URL = "https://www.googleapis.com/drive/v3/files"


class DriveUploader:

    def __init__(self):
        self.folder_id = os.environ.get('GDRIVE_FOLDER_ID', '')
        self.refresh_token = os.environ.get('GDRIVE_REFRESH_TOKEN', '')
        self.client_id = os.environ.get('GDRIVE_CLIENT_ID', '')
        self.client_secret = os.environ.get('GDRIVE_CLIENT_SECRET', '')
        self.access_token = None

        if not all([self.refresh_token, self.client_id, self.client_secret, self.folder_id]):
            # Fallback to GitHub Releases
            self.github_token = os.environ.get('GITHUB_TOKEN', '')
            self.repo = os.environ.get('GITHUB_REPOSITORY', '')
            self.is_github = os.environ.get('GITHUB_ACTIONS') == 'true'

            if self.is_github and self.repo and self.github_token:
                self.enabled = True
                self.use_drive = False
                logger.info("☁️ Backup: GitHub Releases (Drive not configured)")
            else:
                self.enabled = False
                self.use_drive = False
                logger.info("☁️ Backup disabled")
            return

        self.enabled = True
        self.use_drive = True
        logger.info("☁️ Google Drive uploader ready (OAuth2)")

    def _get_token(self):
        if self.access_token:
            return self.access_token
        try:
            resp = http_requests.post(TOKEN_URL, data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': self.refresh_token,
                'grant_type': 'refresh_token'
            }, timeout=15)
            if resp.status_code == 200:
                self.access_token = resp.json().get('access_token')
                logger.info("   ✅ Drive token obtained")
                return self.access_token
            logger.error(f"   ❌ Token failed: {resp.status_code} {resp.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"   ❌ Token error: {e}")
            return None

    def _headers(self):
        token = self._get_token()
        return {'Authorization': f'Bearer {token}'} if token else None

    def _create_folder(self, name, parent_id=None):
        headers = self._headers()
        if not headers:
            return None
        try:
            resp = http_requests.post(FILES_URL,
                headers={**headers, 'Content-Type': 'application/json'},
                json={'name': name, 'mimeType': 'application/vnd.google-apps.folder',
                      'parents': [parent_id or self.folder_id]},
                timeout=15)
            if resp.status_code == 200:
                fid = resp.json().get('id')
                logger.info(f"   📁 Folder: {name}")
                return fid
            logger.error(f"   ❌ Folder failed: {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"   ❌ Folder error: {e}")
            return None

    def _upload_file(self, file_path, parent_id, custom_name=None):
        headers = self._headers()
        if not headers or not os.path.exists(file_path):
            return None

        name = custom_name or os.path.basename(file_path)
        size = os.path.getsize(file_path)
        size_mb = size / (1024 * 1024)

        ext = os.path.splitext(file_path)[1].lower()
        mimes = {'.mp4': 'video/mp4', '.mp3': 'audio/mpeg',
                 '.jpg': 'image/jpeg', '.png': 'image/png',
                 '.txt': 'text/plain', '.json': 'application/json',
                 '.srt': 'text/plain'}
        mime = mimes.get(ext, 'application/octet-stream')

        try:
            init = http_requests.post(f"{UPLOAD_URL}?uploadType=resumable",
                headers={**headers,
                         'Content-Type': 'application/json; charset=UTF-8',
                         'X-Upload-Content-Type': mime,
                         'X-Upload-Content-Length': str(size)},
                json={'name': name, 'parents': [parent_id]},
                timeout=15)

            if init.status_code != 200:
                logger.error(f"   ❌ Init failed: {init.status_code} {init.text[:200]}")
                return None

            upload_url = init.headers.get('Location')
            if not upload_url:
                return None

            with open(file_path, 'rb') as f:
                up = http_requests.put(upload_url,
                    headers={'Content-Type': mime},
                    data=f.read(), timeout=600)

            if up.status_code in [200, 201]:
                file_id = up.json().get('id', '')
                link = f"https://drive.google.com/file/d/{file_id}/view"
                logger.info(f"   ☁️ Uploaded: {name} ({size_mb:.1f} MB)")
                return {'id': file_id, 'name': name, 'size_mb': round(size_mb, 1), 'link': link}
            else:
                logger.error(f"   ❌ Upload failed: {up.status_code} {up.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"   ❌ Upload error {name}: {e}")
            return None

    def _github_release_upload(self, topic, language, all_files):
        """Fallback: GitHub Releases"""
        try:
            safe = "".join(c for c in topic[:20] if c.isalnum() or c in '-_').strip()
            tag = f"v{datetime.now().strftime('%Y%m%d-%H%M')}-{safe}"
            title = f"📹 {language.upper()}: {topic[:50]}"

            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }

            # Create release
            resp = http_requests.post(
                f"https://api.github.com/repos/{self.repo}/releases",
                headers=headers,
                json={'tag_name': tag, 'name': title, 'body': f'Generated: {datetime.now().isoformat()}',
                      'draft': False, 'prerelease': False},
                timeout=15)

            if resp.status_code not in [201]:
                return None

            upload_url = resp.json().get('upload_url', '').split('{')[0]
            uploaded = []

            for fp in all_files:
                if not os.path.exists(fp):
                    continue
                name = os.path.basename(fp)
                size = os.path.getsize(fp)
                ext = os.path.splitext(fp)[1].lower()
                ct = {'mp4': 'video/mp4', 'mp3': 'audio/mpeg', 'jpg': 'image/jpeg',
                      'txt': 'text/plain'}.get(ext.strip('.'), 'application/octet-stream')

                with open(fp, 'rb') as f:
                    ur = http_requests.post(f"{upload_url}?name={name}",
                        headers={**headers, 'Content-Type': ct},
                        data=f.read(), timeout=300)
                if ur.status_code == 201:
                    uploaded.append({'name': name, 'size_mb': round(size/(1024*1024), 1)})
                    logger.info(f"   ☁️ Release: {name}")

            link = f"https://github.com/{self.repo}/releases/tag/{tag}"
            return {'folder_link': link, 'files': uploaded,
                    'total_size_mb': sum(f['size_mb'] for f in uploaded)}
        except Exception as e:
            logger.error(f"   ❌ GitHub Release failed: {e}")
            return None

    def upload_pipeline_output(self, run_id, language, topic,
                                long_video_path=None, shorts=None,
                                thumbnail_long_path=None,
                                short_thumbnails=None,
                                script_text=None, output_dir=None):
        if not self.enabled:
            logger.info("☁️ Backup skipped")
            return None

        logger.info(f"\n☁️ STEP: Backing up to {'Google Drive' if self.use_drive else 'GitHub Releases'}...")

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

        if not all_files:
            logger.info("   No files to upload")
            return None

        # Try Google Drive first
        if self.use_drive:
            safe = "".join(c for c in topic[:30] if c.isalnum() or c in ' _-').strip()
            folder_name = f"{datetime.now().strftime('%Y-%m-%d')}_{language}_{safe}"

            root = self._create_folder(folder_name)
            if root:
                uploaded = []

                if long_video_path and os.path.exists(long_video_path):
                    logger.info(f"   📤 Long video...")
                    r = self._upload_file(long_video_path, root)
                    if r: uploaded.append(r)

                if thumbnail_long_path and os.path.exists(thumbnail_long_path):
                    r = self._upload_file(thumbnail_long_path, root)
                    if r: uploaded.append(r)

                if shorts:
                    sf = self._create_folder("shorts", root)
                    if sf:
                        for i, s in enumerate(shorts):
                            p = s.get('path', '')
                            if p and os.path.exists(p):
                                logger.info(f"   📤 Short {i+1}/{len(shorts)}...")
                                r = self._upload_file(p, sf)
                                if r: uploaded.append(r)

                if short_thumbnails:
                    tf = self._create_folder("thumbnails", root)
                    if tf:
                        for i, tp in enumerate(short_thumbnails):
                            if tp and os.path.exists(tp):
                                r = self._upload_file(tp, tf, f"thumb_{i}.jpg")
                                if r: uploaded.append(r)

                # Script
                for fp in all_files:
                    if fp.endswith('.txt') and fp not in [long_video_path]:
                        r = self._upload_file(fp, root)
                        if r: uploaded.append(r)

                if uploaded:
                    total = sum(f.get('size_mb', 0) for f in uploaded)
                    link = f"https://drive.google.com/drive/folders/{root}"
                    logger.info(f"\n   ☁️ Drive: {len(uploaded)} files, {total:.1f} MB")
                    logger.info(f"   🔗 {link}")
                    return {'folder_id': root, 'folder_link': link,
                            'files': uploaded, 'total_size_mb': round(total, 1)}

        # Fallback to GitHub Releases
        if hasattr(self, 'github_token') and self.github_token:
            return self._github_release_upload(topic, language, all_files)

        return None
