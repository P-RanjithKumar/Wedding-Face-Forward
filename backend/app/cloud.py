"""
Cloud manager for Wedding Face Forward.
Handles uploading processed photos to Google Drive.
"""

import logging
import os
import ssl
import threading
import time
from pathlib import Path
from typing import Optional, Dict
from functools import wraps

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import httplib2
import google_auth_httplib2

from .config import get_config

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive']


def retry_with_backoff(max_retries: int = 3, initial_delay: int = 2):
    """Decorator to retry function with exponential backoff on failure."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (HttpError, TimeoutError, OSError, ssl.SSLError, ConnectionError) as e:
                    last_exception = e
                    error_msg = str(e)
                    
                    # Don't retry on certain errors
                    if isinstance(e, HttpError):
                        if e.resp.status in [400, 401, 403, 404]:
                            logger.error(f"Non-retryable error: {error_msg}")
                            raise
                    
                    # On SSL errors, try to rebuild the Drive service
                    # The httplib2 connection pool may be corrupted
                    if isinstance(e, (ssl.SSLError, OSError)) and 'ssl' in error_msg.lower():
                        self_obj = args[0] if args and isinstance(args[0], CloudManager) else None
                        if self_obj:
                            self_obj._ssl_error_count += 1
                            if self_obj._ssl_error_count >= 3:
                                self_obj._rebuild_service()
                    
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {error_msg}. Retrying in {delay}s...")
                        time.sleep(delay)
                        delay = min(delay * 2, 16)  # Exponential backoff, capped at 16s
                    else:
                        logger.error(f"All {max_retries} attempts failed: {error_msg}")
            
            raise last_exception
        return wrapper
    return decorator


class CloudManager:
    """Manages Google Drive interactions."""

    def __init__(self, config=None):
        self.config = config or get_config()
        self.creds = None
        self.service = None
        self.root_folder_id = self.config.drive_root_folder_id
        self._folder_cache: Dict[str, str] = {}  # Cache path -> folder_id
        self._folder_lock = threading.Lock()  # Thread-safe folder creation
        self._ssl_error_count = 0  # Track SSL errors for service rebuild
        self._rebuild_lock = threading.Lock()  # Prevent concurrent rebuilds
        
        self.initialize()

    def initialize(self) -> None:
        """Authenticate and build the Drive service."""
        creds_path = self.config.google_credentials_file
        
        if not creds_path or not creds_path.exists():
            logger.warning(f"Google credentials not found at {creds_path}. Cloud upload disabled.")
            return

        # Search for token.json in multiple locations
        possible_token_paths = [
            self.config.event_root.parent / "backend" / "token.json",
            self.config.event_root.parent / "token.json",
            Path("token.json").resolve(),
            Path("backend/token.json").resolve()
        ]
        
        token_path = None
        for path in possible_token_paths:
            if path.exists():
                token_path = path
                break
        
        try:
            # First try Token (User Credentials) - required for personal Google Drive uploads
            if token_path and token_path.exists():
                logger.info(f"Loading user credentials from {token_path}")
                self.creds = UserCredentials.from_authorized_user_file(str(token_path), SCOPES)
            
            # Fallback to Service Account
            elif creds_path and creds_path.exists():
                logger.info(f"Loading service account from {creds_path}")
                self.creds = service_account.Credentials.from_service_account_file(
                    str(creds_path), scopes=SCOPES
                )
            else:
                logger.warning(f"No Google credentials found (checked {token_path} and {creds_path}). Cloud upload disabled.")
                return
            
            # Configure HTTP client with timeouts
            # Configure HTTP client with timeouts
            # httplib2 uses a single timeout for both connect and read
            timeout = max(self.config.upload_timeout_connect, self.config.upload_timeout_read)
            http = httplib2.Http(
                timeout=timeout,
                disable_ssl_certificate_validation=False
            )
            
            # Authorize the http object explicitly
            authed_http = google_auth_httplib2.AuthorizedHttp(self.creds, http=http)
            
            self.service = build('drive', 'v3', http=authed_http)
            logger.info(f"Successfully connected to Google Drive API (timeout={timeout}s)")
            
            # Verify root folder exists
            if not self.root_folder_id:
                logger.warning("DRIVE_ROOT_FOLDER_ID not set. Files will be uploaded to service account's root.")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive: {e}")
            self.service = None

    @property
    def is_enabled(self) -> bool:
        """Check if cloud upload is configured and working."""
        return self.service is not None

    def _rebuild_service(self):
        """Rebuild the Google Drive service when SSL errors indicate a corrupted connection pool."""
        if not self._rebuild_lock.acquire(blocking=False):
            return  # Another thread is already rebuilding
        try:
            logger.warning(f"Rebuilding Google Drive service after {self._ssl_error_count} SSL errors...")
            self._ssl_error_count = 0
            
            # Rebuild HTTP client and service
            timeout = max(self.config.upload_timeout_connect, self.config.upload_timeout_read)
            http = httplib2.Http(
                timeout=timeout,
                disable_ssl_certificate_validation=False
            )
            authed_http = google_auth_httplib2.AuthorizedHttp(self.creds, http=http)
            self.service = build('drive', 'v3', http=authed_http)
            logger.info("Google Drive service rebuilt successfully")
        except Exception as e:
            logger.error(f"Failed to rebuild Google Drive service: {e}")
        finally:
            self._rebuild_lock.release()

    @retry_with_backoff(max_retries=3, initial_delay=2)
    def _find_folder(self, name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """Find a folder by name within a parent folder."""
        if not self.is_enabled:
            return None
            
        query = f"mimeType='application/vnd.google-apps.folder' and name='{name}' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
            
        results = self.service.files().list(
            q=query, fields="files(id, name)", pageSize=1
        ).execute()
        
        # Validate response is a dict (can be malformed during network issues)
        if not isinstance(results, dict):
            logger.warning(f"Unexpected API response type for _find_folder: {type(results)}")
            return None
        
        items = results.get('files', [])
        return items[0]['id'] if items else None

    @retry_with_backoff(max_retries=3, initial_delay=2)
    def rename_folder(self, old_name: str, new_name: str, parent_id: Optional[str] = None) -> bool:
        """
        Rename an existing folder in Google Drive.
        
        Args:
            old_name: Current folder name to find.
            new_name: New name to assign.
            parent_id: Parent folder ID to search within (defaults to root).
            
        Returns:
            True if renamed successfully, False otherwise.
        """
        if not self.is_enabled:
            return False
        
        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would rename cloud folder: {old_name} -> {new_name}")
            return True
        
        # Find the folder by its old name
        search_parent = parent_id or self.root_folder_id
        folder_id = self._find_folder(old_name, search_parent)
        
        if not folder_id:
            logger.warning(f"Cloud folder not found for rename: {old_name}")
            return False
        
        try:
            # Rename in-place via Drive API
            self.service.files().update(
                fileId=folder_id,
                body={'name': new_name}
            ).execute()
            
            logger.info(f"Renamed cloud folder: {old_name} -> {new_name} ({folder_id})")
            
            # Invalidate stale cache entries that contain the old name
            stale_keys = [k for k in self._folder_cache if old_name in k]
            for key in stale_keys:
                del self._folder_cache[key]
            
            # Re-cache with new name so future lookups are fast
            if parent_id:
                # Build partial cache key
                for key, val in list(self._folder_cache.items()):
                    if val == search_parent:
                        self._folder_cache[f"{key}/{new_name}"] = folder_id
                        break
                else:
                    self._folder_cache[new_name] = folder_id
            else:
                self._folder_cache[new_name] = folder_id
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to rename cloud folder {old_name} -> {new_name}: {e}")
            return False

    @retry_with_backoff(max_retries=3, initial_delay=2)
    def _create_folder(self, name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """Create a new folder."""
        if not self.is_enabled:
            return None
            
        metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
        }
        if parent_id:
            metadata['parents'] = [parent_id]
            
        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would create cloud folder: {name}")
            return "dry_run_folder_id"

        result = self.service.files().create(
            body=metadata, fields='id'
        ).execute()
        
        # Validate response is a dict (can be malformed during network issues)
        if not isinstance(result, dict):
            logger.error(f"Unexpected API response type for _create_folder('{name}'): {type(result)}")
            return None
        
        folder_id = result.get('id')
        if not folder_id:
            logger.error(f"API response missing 'id' for _create_folder('{name}'): {result}")
            return None
        
        logger.info(f"Created cloud folder: {name} ({folder_id})")
        return folder_id

    def _get_path_lock(self, path: str) -> threading.Lock:
        """Get or create a lock specific to a folder path.
        
        This allows threads working on DIFFERENT folder paths to proceed
        in parallel, while threads working on the SAME path serialize
        their find-or-create operations to prevent duplicate folders.
        """
        with self._folder_lock:
            if not hasattr(self, "_path_locks"):
                self._path_locks: Dict[str, threading.Lock] = {}
            if path not in self._path_locks:
                self._path_locks[path] = threading.Lock()
            return self._path_locks[path]

    def ensure_folder_path(self, path_parts: list[str]) -> Optional[str]:
        """
        Ensure a folder hierarchy exists in Drive.
        
        Thread-safe: uses per-path locks so that only threads working on the
        EXACT SAME folder path block each other. The entire find-or-create
        sequence (network calls included) is held under the path lock to
        guarantee no two threads can simultaneously discover "missing" and
        both create the same folder.
        
        Args:
            path_parts: List of folder names, e.g. ["People", "Person_123", "Solo"]
            
        Returns:
            The ID of the final folder, or None on error.
        """
        if not self.is_enabled:
            return None

        # Check cache without lock first (fast path, read-only)
        cache_key = "/".join(path_parts)
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        current_parent_id = self.root_folder_id
        current_path_str = ""

        for part in path_parts:
            # Build up key for partial cache check
            current_path_str = f"{current_path_str}/{part}" if current_path_str else part
            
            # Quick cache check (no lock needed for reads)
            if current_path_str in self._folder_cache:
                current_parent_id = self._folder_cache[current_path_str]
                continue
            
            # Acquire a lock specific to THIS folder path.
            # This keeps the find+create atomic for the same path,
            # while threads working on different paths are NOT blocked.
            path_lock = self._get_path_lock(current_path_str)
            acquired = path_lock.acquire(timeout=60)
            if not acquired:
                logger.error(f"Timeout waiting for folder lock (path: {current_path_str})")
                return None
            
            try:
                # Double-check cache after acquiring lock
                if current_path_str in self._folder_cache:
                    current_parent_id = self._folder_cache[current_path_str]
                    continue
                
                # Both find AND create happen INSIDE the path lock.
                # This is safe because only threads targeting the same folder
                # path will contend; other paths proceed in parallel.
                folder_id = self._find_folder(part, current_parent_id)
                if not folder_id:
                    folder_id = self._create_folder(part, current_parent_id)
                    
                    if not folder_id:
                        logger.error(f"Failed to create cloud folder: {part} (parent: {current_parent_id})")
                        return None
                
                # Update cache
                with self._folder_lock:
                    self._folder_cache[current_path_str] = folder_id
                
                current_parent_id = folder_id
                
            except Exception as e:
                logger.error(f"Error ensuring cloud folder '{part}': {e}")
                return None
            finally:
                path_lock.release()

        return current_parent_id

    def upload_file(self, local_path: Path, relative_to: Path) -> bool:
        """
        Uploads a file to Google Drive, mirroring the folder structure.
        
        Args:
            local_path: Absolute path to the file.
            relative_to: Base path to calculate relative folder structure.
                         e.g., processed_path.parent relative to EventRoot.
        """
        if not self.is_enabled:
            return False

        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would upload to cloud: {local_path.name}")
            return True

        try:
            # Calculate folder structure
            # e.g. local: .../EventRoot/People/Person_123/Solo/img.jpg
            # relative_to: .../EventRoot
            # relative_path: People/Person_123/Solo/img.jpg
            # parts: ["People", "Person_123", "Solo"]
            relative_path = local_path.relative_to(relative_to)
            folder_parts = list(relative_path.parent.parts)
            
            # Ensure folder exists
            parent_folder_id = self.ensure_folder_path(folder_parts)
            if not parent_folder_id:
                logger.error(f"Could not create folder structure for {local_path.name}")
                return False

            # Check if file already exists to avoid duplicates
            existing_id = self._find_folder(local_path.name, parent_folder_id)
            if existing_id:
                logger.info(f"File already exists in cloud: {local_path.name}, skipping.")
                return True

            # Upload with retry logic for transient network/SSL errors
            return self._upload_file_with_retry(local_path, parent_folder_id)

        except Exception as e:
            logger.error(f"Failed to upload {local_path.name}: {e}")
            return False

    @retry_with_backoff(max_retries=3, initial_delay=2)
    def _upload_file_with_retry(self, local_path: Path, parent_folder_id: str) -> bool:
        """Perform the actual file upload with retry on transient errors."""
        file_metadata = {
            'name': local_path.name,
            'parents': [parent_folder_id]
        }
        media = MediaFileUpload(
            str(local_path),
            mimetype='image/jpeg',
            resumable=True
        )
        
        result = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        # Validate response
        if not isinstance(result, dict):
            raise OSError(f"Unexpected API response type during upload: {type(result)}")
        
        file_id = result.get('id')
        if not file_id:
            raise OSError(f"API response missing 'id' during upload: {result}")
        
        logger.info(f"Uploaded to cloud: {local_path.name} ({file_id})")
        return True

    def get_folder_link(self, folder_id: str) -> Optional[str]:
        """Get web link for a folder."""
        if not self.is_enabled:
            return None
        try:
            file = self.service.files().get(
                fileId=folder_id, fields='webViewLink'
            ).execute()
            return file.get('webViewLink')
        except Exception:
            return None

    @retry_with_backoff(max_retries=3, initial_delay=2)
    def share_folder_publicly(self, folder_id: str) -> bool:
        """
        Sets permission for a folder to 'anyone with the link can view'.
        """
        if not self.is_enabled:
            return False

        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would set public permission on folder {folder_id}")
            return True

        try:
            # Check if already shared (optional optimization, but API is idempotent enough usually)
            # For simplicity, we just apply it. valid roles: reader, commenter, writer
            # valid types: user, group, domain, anyone
            self.service.permissions().create(
                fileId=folder_id,
                body={'role': 'reader', 'type': 'anyone'},
                fields='id'
            ).execute()
            logger.info(f"Set public permission on folder {folder_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to set permission on {folder_id}: {e}")
            return False

# Global instance
_cloud: Optional[CloudManager] = None

def get_cloud() -> CloudManager:
    global _cloud
    if _cloud is None:
        _cloud = CloudManager()
    return _cloud
