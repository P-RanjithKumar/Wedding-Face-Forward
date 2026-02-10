"""
Upload queue manager for Wedding Face Forward.

Handles asynchronous uploads to Google Drive with retry logic.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional

from .config import get_config
from .db import get_db
from .cloud import get_cloud

logger = logging.getLogger(__name__)


class UploadQueueManager:
    """Manages background uploads to Google Drive."""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.db = get_db()
        self.cloud = get_cloud()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
    
    def start(self) -> None:
        """Start the upload queue worker thread."""
        if not self.config.upload_queue_enabled:
            logger.info("Upload queue disabled in configuration")
            return
        
        if not self.cloud.is_enabled:
            logger.info("Cloud upload disabled, upload queue will not start")
            return
        
        if self._running:
            logger.warning("Upload queue already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="UploadQueue")
        self._thread.start()
        logger.info("Upload queue worker started")
    
    def stop(self) -> None:
        """Stop the upload queue worker thread."""
        if not self._running:
            return
        
        logger.info("Stopping upload queue worker...")
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=10)
        
        self._running = False
        logger.info("Upload queue worker stopped")
    
    def enqueue(self, photo_id: int, local_path: Path, relative_to: Path) -> None:
        """Add a file to the upload queue."""
        try:
            upload_id = self.db.enqueue_upload(
                photo_id=photo_id,
                local_path=str(local_path),
                relative_to=str(relative_to)
            )
            logger.debug(f"Queued upload {upload_id}: {local_path.name}")
        except Exception as e:
            logger.error(f"Failed to enqueue upload for {local_path.name}: {e}")
    
    def _worker_loop(self) -> None:
        """Main worker loop that processes the upload queue."""
        logger.info("Upload queue worker loop started")
        
        while not self._stop_event.is_set():
            try:
                # Process pending uploads
                self._process_pending_uploads()
                
                # Retry failed uploads
                self._retry_failed_uploads()
                
                # Sleep before next iteration (2 seconds for near real-time sync)
                self._stop_event.wait(timeout=2)
                
            except Exception as e:
                logger.exception(f"Error in upload queue worker: {e}")
                self._stop_event.wait(timeout=10)
        
        logger.info("Upload queue worker loop exited")
    
    def _process_pending_uploads(self) -> None:
        """Process pending uploads from the queue."""
        pending = self.db.get_pending_uploads(limit=self.config.upload_batch_size)
        
        if not pending:
            return
        
        logger.info(f"Processing {len(pending)} pending uploads")
        
        for upload in pending:
            if self._stop_event.is_set():
                break
            
            self._upload_file(upload)
    
    def _retry_failed_uploads(self) -> None:
        """Retry failed uploads that haven't exceeded max retries."""
        failed = self.db.get_failed_uploads(max_retries=self.config.upload_max_retries)
        
        if not failed:
            return
        
        logger.info(f"Retrying {len(failed)} failed uploads")
        
        for upload in failed:
            if self._stop_event.is_set():
                break
            
            # Wait before retry based on retry count
            retry_delay = self.config.upload_retry_delay * (2 ** upload['retry_count'])
            time.sleep(min(retry_delay, 60))  # Cap at 60 seconds
            
            self._upload_file(upload)
    
    def _upload_file(self, upload: dict) -> None:
        """Upload a single file from the queue."""
        upload_id = upload['id']
        local_path = Path(upload['local_path'])
        relative_to = Path(upload['relative_to'])
        
        # Check if file still exists
        if not local_path.exists():
            logger.warning(f"Upload {upload_id}: File no longer exists: {local_path}")
            self.db.update_upload_status(upload_id, 'failed', error='File not found')
            return
        
        try:
            # Mark as uploading
            self.db.update_upload_status(upload_id, 'uploading')
            
            # Perform upload
            success = self.cloud.upload_file(local_path, relative_to)
            
            if success:
                self.db.update_upload_status(upload_id, 'completed')
                logger.info(f"Upload {upload_id} completed: {local_path.name}")
            else:
                error_msg = "Upload returned False"
                self.db.update_upload_status(
                    upload_id, 'failed', 
                    error=error_msg, 
                    increment_retry=True
                )
                logger.warning(f"Upload {upload_id} failed: {error_msg}")
        
        except Exception as e:
            error_msg = str(e)
            self.db.update_upload_status(
                upload_id, 'failed',
                error=error_msg,
                increment_retry=True
            )
            logger.error(f"Upload {upload_id} failed with exception: {error_msg}")
    
    def get_stats(self) -> dict:
        """Get upload queue statistics."""
        return self.db.get_upload_stats()


# Global instance
_upload_queue: Optional[UploadQueueManager] = None


def get_upload_queue() -> UploadQueueManager:
    """Get the global upload queue instance."""
    global _upload_queue
    if _upload_queue is None:
        _upload_queue = UploadQueueManager()
    return _upload_queue
