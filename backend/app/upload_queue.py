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
        
        # Recover any uploads stuck in 'uploading' from previous crash/hang
        self._recover_stuck_uploads()
        
        iteration_count = 0
        last_idle_reported = False
        while not self._stop_event.is_set():
            try:
                # Process pending uploads
                pending_count = len(self.db.get_pending_uploads(limit=self.config.upload_batch_size))
                self._process_pending_uploads()
                
                # Retry failed uploads
                failed_count = len(self.db.get_failed_uploads(max_retries=self.config.upload_max_retries))
                self._retry_failed_uploads()
                
                # Heartbeat: Report idle status when queue is empty
                if pending_count == 0 and failed_count == 0 and not last_idle_reported:
                    stats = self.db.get_upload_stats()
                    if stats.get('completed', 0) > 0:
                        logger.info(f"[OK] All uploads complete ({stats['completed']} total). Queue is idle, monitoring for new files...")
                    last_idle_reported = True
                elif (pending_count > 0 or failed_count > 0) and last_idle_reported:
                    # Reset flag when work resumes
                    last_idle_reported = False
                
                # Periodically check for stuck uploads (every ~60 seconds)
                iteration_count += 1
                if iteration_count % 30 == 0:
                    self._recover_stuck_uploads()
                
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
            
            # Wait before retry based on retry count (uses stop_event so shutdown isn't blocked)
            retry_delay = self.config.upload_retry_delay * (2 ** upload['retry_count'])
            self._stop_event.wait(timeout=min(retry_delay, 60))  # Cap at 60 seconds
            if self._stop_event.is_set():
                break
            
            self._upload_file(upload)
    
    def _upload_file(self, upload: dict) -> None:
        """Upload a single file from the queue."""
        upload_id = upload['id']
        local_path = Path(upload['local_path'])
        relative_to = Path(upload['relative_to'])
        
        # Check if file still exists
        if not local_path.exists():
            logger.warning(f"Upload {upload_id}: File no longer exists: {local_path}")
            # Set retry_count to max so this won't be retried (file is permanently gone)
            self.db.update_upload_status(
                upload_id, 'failed', 
                error='File not found',
                increment_retry=False
            )
            # Manually set retry_count to max to prevent retries
            try:
                conn = self.db.connect()
                with conn:
                    conn.execute(
                        "UPDATE upload_queue SET retry_count = ? WHERE id = ?",
                        (self.config.upload_max_retries, upload_id)
                    )
            except Exception as e:
                logger.error(f"Failed to update retry_count for missing file: {e}")
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
    
    def _recover_stuck_uploads(self) -> None:
        """Reset uploads stuck in 'uploading' status back to 'pending'.
        
        This handles cases where uploads get stuck due to crashes, network
        timeouts, or other failures that prevent the status from being updated.
        Uploads in 'uploading' status for more than 5 minutes are considered stuck.
        """
        try:
            count = self.db.reset_stuck_uploads(timeout_minutes=5)
            if count > 0:
                logger.warning(f"Reset {count} upload(s) stuck in 'uploading' status back to 'pending'")
        except Exception as e:
            logger.error(f"Failed to recover stuck uploads: {e}")
    
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
