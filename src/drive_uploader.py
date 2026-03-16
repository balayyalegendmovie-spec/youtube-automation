"""
GOOGLE DRIVE UPLOADER — Backs up all generated videos to Google Drive

Uses Service Account authentication (no OAuth flow needed).
Uploads:
  - Long-form video
  - All shorts
  - All thumbnails
  - Script text file

Organizes in folders:
  YouTube Bot Videos/
  └── 2026-03-16_telugu_Taj_Mahal/
      ├── long_form_video.mp4
      ├── thumbnail_long.jpg
      ├── shorts/
      │   ├── short_01.mp4
      │   ├── short_02.mp4
      │   └── ...
      ├── thumbnails/
      │   ├── thumb_short_0.jpg
      │   └── ...
      └── script.txt
"""

import os
import json
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class DriveUploader:
    """Upload files to Google Drive using Service Account"""

    def __init__(self):
        self.service = None
        self.root_folder_id = os.environ.get('GDRIVE_FOLDER_ID', '')
        self.credentials_json = os.environ.get('GDRIVE_SERVICE_ACCOUNT', '')

        if not self.root_folder_id:
            logger.warning("☁️ GDRIVE_FOLDER_ID not set — Drive backup disabled")
            self.enabled = False
            return

        if not self.credentials_json:
            logger.warning("☁️ GDRIVE_SERVICE_ACCOUNT not set — Drive backup disabled")
            self.enabled = False
            return

        self.enabled = True
        logger.info("☁️ Google Drive uploader initialized")

    def _get_service(self):
        """Lazy-initialize the Drive service"""
        if self.service:
            return self.service

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            # Parse credentials from environment variable
            creds_dict = json.loads(self.credentials_json)

            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )

            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("   ✅ Drive API connected")
            return self.service

        except ImportError:
            logger.error("   ❌ google-auth or google-api-python-client not installed")
            logger.error("   Run: pip install google-auth google-api-python-client")
            self.enabled = False
            return None

        except Exception as e:
            logger.error(f"   ❌ Drive auth failed: {e}")
            self.enabled = False
            return None

    def _create_folder(self, name, parent_id=None):
        """Create a folder in Google Drive"""
        service = self._get_service()
        if not service:
            return None

        metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        if parent_id:
            metadata['parents'] = [parent_id]

        try:
            folder = service.files().create(
                body=metadata,
                fields='id, name, webViewLink'
            ).execute()

            logger.info(f"   📁 Folder created: {name}")
            return folder.get('id')

        except Exception as e:
            logger.error(f"   ❌ Folder creation failed: {e}")
            return None

    def _upload_file(self, file_path, parent_folder_id, custom_name=None):
        """Upload a single file to Google Drive"""
        service = self._get_service()
        if not service:
            return None

        if not os.path.exists(file_path):
            logger.warning(f"   ⚠️ File not found: {file_path}")
            return None

        from googleapiclient.http import MediaFileUpload

        file_name = custom_name or os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / (1024 * 1024)

        # Determine MIME type
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            '.mp4': 'video/mp4',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.srt': 'text/plain',
        }
        mime_type = mime_types.get(ext, 'application/octet-stream')

        metadata = {
            'name': file_name,
            'parents': [parent_folder_id]
        }

        try:
            media = MediaFileUpload(
                file_path,
                mimetype=mime_type,
                resumable=True,
                chunksize=5 * 1024 * 1024  # 5MB chunks
            )

            request = service.files().create(
                body=metadata,
                media_body=media,
                fields='id, name, webViewLink, size'
            )

            # Upload with progress
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    if progress % 25 == 0:
                        logger.info(f"      ↑ {file_name}: {progress}%")

            file_id = response.get('id')
            web_link = response.get('webViewLink', '')

            logger.info(f"   ☁️ Uploaded: {file_name} ({file_size:.1f} MB)")

            return {
                'id': file_id,
                'name': file_name,
                'link': web_link,
                'size_mb': round(file_size, 1)
            }

        except Exception as e:
            logger.error(f"   ❌ Upload failed for {file_name}: {e}")
            return None

    def upload_pipeline_output(self, run_id, language, topic,
                                long_video_path=None,
                                shorts=None,
                                thumbnail_long_path=None,
                                short_thumbnails=None,
                                script_text=None,
                                output_dir=None):
        """
        Upload all pipeline output to Google Drive.

        Creates a structured folder and uploads everything.
        """

        if not self.enabled:
            logger.info("☁️ Drive backup skipped (not configured)")
            return None

        logger.info(f"\n☁️ STEP: Backing up to Google Drive...")

        # Create run folder
        safe_topic = "".join(c for c in topic[:30] if c.isalnum() or c in ' _-').strip()
        folder_name = f"{datetime.now().strftime('%Y-%m-%d')}_{language}_{safe_topic}"

        run_folder_id = self._create_folder(folder_name, self.root_folder_id)
        if not run_folder_id:
            logger.error("   ❌ Could not create run folder")
            return None

        uploaded_files = []

        # Upload long-form video
        if long_video_path and os.path.exists(long_video_path):
            logger.info(f"   📤 Uploading long-form video...")
            result = self._upload_file(long_video_path, run_folder_id)
            if result:
                uploaded_files.append(result)

        # Upload long thumbnail
        if thumbnail_long_path and os.path.exists(thumbnail_long_path):
            result = self._upload_file(thumbnail_long_path, run_folder_id,
                                        "thumbnail_long.jpg")
            if result:
                uploaded_files.append(result)

        # Upload shorts
        if shorts:
            shorts_folder_id = self._create_folder("shorts", run_folder_id)
            if shorts_folder_id:
                for i, short_info in enumerate(shorts):
                    short_path = short_info.get('path', '')
                    if short_path and os.path.exists(short_path):
                        logger.info(f"   📤 Uploading short {i+1}/{len(shorts)}...")
                        result = self._upload_file(short_path, shorts_folder_id)
                        if result:
                            uploaded_files.append(result)

        # Upload short thumbnails
        if short_thumbnails:
            thumbs_folder_id = self._create_folder("thumbnails", run_folder_id)
            if thumbs_folder_id:
                for i, thumb_path in enumerate(short_thumbnails):
                    if thumb_path and os.path.exists(thumb_path):
                        result = self._upload_file(
                            thumb_path, thumbs_folder_id,
                            f"thumb_short_{i}.jpg"
                        )
                        if result:
                            uploaded_files.append(result)

        # Upload script as text file
        if script_text:
            script_path = os.path.join(output_dir or '/tmp', 'script_backup.txt')
            try:
                with open(script_path, 'w', encoding='utf-8') as f:
                    f.write(f"Topic: {topic}\n")
                    f.write(f"Language: {language}\n")
                    f.write(f"Date: {datetime.now().isoformat()}\n")
                    f.write(f"{'='*50}\n\n")
                    f.write(script_text)

                result = self._upload_file(script_path, run_folder_id, "script.txt")
                if result:
                    uploaded_files.append(result)
            except Exception:
                pass

        # Upload any remaining files in output directory
        if output_dir and os.path.exists(output_dir):
            for fname in ['review.json', 'full_subtitles.srt']:
                fpath = os.path.join(output_dir, fname)
                if os.path.exists(fpath):
                    result = self._upload_file(fpath, run_folder_id)
                    if result:
                        uploaded_files.append(result)

        # Summary
        total_size = sum(f.get('size_mb', 0) for f in uploaded_files)
        logger.info(f"\n   ☁️ Drive backup complete:")
        logger.info(f"      Files: {len(uploaded_files)}")
        logger.info(f"      Total size: {total_size:.1f} MB")
        logger.info(f"      Folder: {folder_name}")

        drive_link = f"https://drive.google.com/drive/folders/{run_folder_id}"
        logger.info(f"      🔗 Link: {drive_link}")

        return {
            'folder_id': run_folder_id,
            'folder_name': folder_name,
            'folder_link': drive_link,
            'files': uploaded_files,
            'total_size_mb': round(total_size, 1)
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uploader = DriveUploader()
    if uploader.enabled:
        print("Drive uploader ready")
    else:
        print("Drive uploader disabled (no credentials)")
