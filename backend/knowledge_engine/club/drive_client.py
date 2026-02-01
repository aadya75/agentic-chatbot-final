"""
Google Drive Client for Club Knowledge
Downloads documents from fixed folder structure
"""
import json
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import io

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

from knowledge_engine.club.config import club_config
from utils.logger import logger


class ClubDriveClient:
    """
    Google Drive client for downloading club documents
    
    Folder Structure Expected:
    RoboticsClub/
    ├── Events/
    │   ├── RoboSprint/
    │   │   ├── overview.md
    │   │   ├── problem_statement.pdf
    │   │   ├── rules.md
    │   │   └── metadata.json
    │   └── ...
    ├── Announcements/
    │   ├── announcements.md
    │   └── pinned.md
    ├── Coordinators/
    │   └── coordinators.csv
    └── Archives/ (ignored)
    """
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    # Supported file types and their MIME types
    SUPPORTED_MIME_TYPES = {
        'application/pdf': '.pdf',
        'application/vnd.google-apps.document': '.docx',  # Google Docs
        'text/plain': '.txt',
        'text/markdown': '.md',
        'text/csv': '.csv',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    }
    
    # Export MIME types for Google Workspace files
    EXPORT_MIME_TYPES = {
        'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.google-apps.spreadsheet': 'text/csv',
    }
    
    def __init__(self):
        """Initialize Google Drive client with service account"""
        self.service_account_file = club_config.CLUB_DRIVE_SERVICE_ACCOUNT_FILE
        self.root_folder_id = club_config.CLUB_DRIVE_FOLDER_ID
        self.service = None
        
        logger.info("Initializing ClubDriveClient")
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate using service account"""
        try:
            if not self.service_account_file.exists():
                raise FileNotFoundError(
                    f"Service account file not found: {self.service_account_file}. "
                    "Please add the JSON file to backend/credentials/"
                )
            
            credentials = service_account.Credentials.from_service_account_file(
                str(self.service_account_file),
                scopes=self.SCOPES
            )
            
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("✓ Authenticated with Google Drive")
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise
    
    def download_all_documents(self) -> Dict[str, Any]:
        """
        Download all documents from RoboticsClub folder structure
        
        Returns:
            {
                "total_files": int,
                "downloaded": int,
                "skipped": int,
                "errors": int,
                "files": [{"path": str, "category": str, "metadata": dict}, ...],
                "timestamp": str
            }
        """
        logger.info(f"Starting download from folder ID: {self.root_folder_id}")
        
        result = {
            "total_files": 0,
            "downloaded": 0,
            "skipped": 0,
            "errors": 0,
            "files": [],
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Download from each main folder
            for folder_name in [
                club_config.CLUB_EVENTS_FOLDER,
                club_config.CLUB_ANNOUNCEMENTS_FOLDER,
                club_config.CLUB_COORDINATORS_FOLDER
            ]:
                category = folder_name.lower()
                
                # Find folder ID
                folder_id = self._find_folder(folder_name, self.root_folder_id)
                if not folder_id:
                    logger.warning(f"Folder '{folder_name}' not found, skipping")
                    continue
                
                # Download contents recursively
                folder_result = self._download_folder_recursive(
                    folder_id=folder_id,
                    folder_name=folder_name,
                    category=category,
                    parent_path=""
                )
                
                result["total_files"] += folder_result["total_files"]
                result["downloaded"] += folder_result["downloaded"]
                result["skipped"] += folder_result["skipped"]
                result["errors"] += folder_result["errors"]
                result["files"].extend(folder_result["files"])
            
            logger.info(
                f"Download complete: {result['downloaded']} downloaded, "
                f"{result['skipped']} skipped, {result['errors']} errors"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error during download: {e}")
            result["errors"] += 1
            return result
    
    def _find_folder(self, folder_name: str, parent_id: str) -> Optional[str]:
        """Find folder ID by name within parent"""
        try:
            query = (
                f"name='{folder_name}' and "
                f"'{parent_id}' in parents and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"trashed=false"
            )
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name)"
            ).execute()
            
            files = results.get('files', [])
            if files:
                return files[0]['id']
            return None
            
        except HttpError as e:
            logger.error(f"Error finding folder '{folder_name}': {e}")
            return None
    
    def _download_folder_recursive(
        self,
        folder_id: str,
        folder_name: str,
        category: str,
        parent_path: str
    ) -> Dict[str, Any]:
        """Recursively download folder contents"""
        result = {
            "total_files": 0,
            "downloaded": 0,
            "skipped": 0,
            "errors": 0,
            "files": []
        }
        
        try:
            # List all items in folder
            query = f"'{folder_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType, modifiedTime, parents)",
                pageSize=1000
            ).execute()
            
            items = results.get('files', [])
            
            for item in items:
                item_name = item['name']
                item_mime = item['mimeType']
                
                # Build path
                current_path = f"{parent_path}/{folder_name}" if parent_path else folder_name
                
                # Skip ignored files
                if item_name in club_config.CLUB_IGNORED_FILES:
                    logger.debug(f"Skipping ignored file: {item_name}")
                    result["skipped"] += 1
                    continue
                
                # Handle folders
                if item_mime == 'application/vnd.google-apps.folder':
                    # Skip ignored folders
                    if item_name in club_config.CLUB_IGNORED_FOLDERS:
                        logger.debug(f"Skipping ignored folder: {item_name}")
                        continue
                    
                    # Recurse into subfolder
                    subfolder_result = self._download_folder_recursive(
                        folder_id=item['id'],
                        folder_name=item_name,
                        category=category,
                        parent_path=current_path
                    )
                    
                    result["total_files"] += subfolder_result["total_files"]
                    result["downloaded"] += subfolder_result["downloaded"]
                    result["skipped"] += subfolder_result["skipped"]
                    result["errors"] += subfolder_result["errors"]
                    result["files"].extend(subfolder_result["files"])
                    continue
                
                # Handle files
                result["total_files"] += 1
                
                # Check if supported
                if not self._is_supported_file(item_mime, item_name):
                    logger.debug(f"Skipping unsupported file: {item_name} ({item_mime})")
                    result["skipped"] += 1
                    continue
                
                # Download file
                file_path = f"{current_path}/{item_name}"
                downloaded = self._download_file(item, file_path, category)
                
                if downloaded:
                    result["downloaded"] += 1
                    result["files"].append(downloaded)
                else:
                    result["errors"] += 1
            
            return result
            
        except HttpError as e:
            logger.error(f"Error listing folder '{folder_name}': {e}")
            result["errors"] += 1
            return result
    
    def _is_supported_file(self, mime_type: str, filename: str) -> bool:
        """Check if file type is supported"""
        # Check by MIME type
        if mime_type in self.SUPPORTED_MIME_TYPES:
            return True
        
        # Check by extension
        ext = Path(filename).suffix.lower()
        return ext in ['.md', '.txt', '.pdf', '.csv', '.docx']
    
    def _download_file(
        self,
        file_item: Dict[str, Any],
        relative_path: str,
        category: str
    ) -> Optional[Dict[str, Any]]:
        """
        Download a single file
        
        Returns:
            {
                "path": str,           # Relative path from RoboticsClub/
                "local_path": str,     # Local file path
                "category": str,       # events | announcements | coordinators
                "metadata": dict       # File metadata
            }
        """
        try:
            file_id = file_item['id']
            file_name = file_item['name']
            mime_type = file_item['mimeType']
            
            logger.info(f"Downloading: {relative_path}")
            
            # Determine export settings for Google Workspace files
            if mime_type in self.EXPORT_MIME_TYPES:
                export_mime = self.EXPORT_MIME_TYPES[mime_type]
                request = self.service.files().export_media(fileId=file_id, mimeType=export_mime)
                # Update filename extension
                file_name = Path(file_name).stem + self.SUPPORTED_MIME_TYPES.get(export_mime, '.txt')
            else:
                request = self.service.files().get_media(fileId=file_id)
            
            # Download to memory
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            # Save to disk
            local_path = club_config.CLUB_UPLOADS_DIR / relative_path.lstrip('/')
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(local_path, 'wb') as f:
                f.write(fh.getvalue())
            
            logger.info(f"✓ Downloaded: {relative_path} → {local_path}")
            
            # Extract event name from path if in Events folder
            event_name = None
            if category == "events":
                path_parts = Path(relative_path).parts
                if len(path_parts) >= 2:
                    event_name = path_parts[1]  # Events/RoboSprint/... → RoboSprint
            
            return {
                "path": relative_path,
                "local_path": str(local_path),
                "category": category,
                "metadata": {
                    "source": relative_path,
                    "category": category,
                    "event_name": event_name,
                    "file_id": file_id,
                    "modified_time": file_item.get('modifiedTime'),
                    "mime_type": mime_type,
                    "filename": file_name
                }
            }
            
        except Exception as e:
            logger.error(f"Error downloading {relative_path}: {e}")
            return None


# Singleton instance
drive_client = ClubDriveClient()