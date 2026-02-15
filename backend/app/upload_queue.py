"""
Upload queue manager for Wedding Face Forward.

Handles asynchronous uploads to Google Drive with retry logic.

Integrates with the Phase Coordinator:
  - Waits for UPLOADING phase before processing uploads.
  - Drains ALL pending uploads during the UPLOADING phase.
  - Refreshes the cloud connection after each batch completes.
  - Signals the coordinator to switch back to PROCESSING phase when done.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional

from .config import get_config
from .db import get_db
from .cloud import get_cloud
from .phase import get_coordinator

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
        logger.info("Upload queue worker started (phase-coordinated mode)")
    
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
        """
        Main worker loop that processes the upload queue.
        
        Phase-coordinated flow:
          1. Wait for UPLOADING phase signal from coordinator.
          2. Drain ALL pending + failed uploads.
          3. Refresh cloud connection.
          4. Signal coordinator to switch back to PROCESSING.
          5. Repeat.
        """
        logger.info("Upload queue worker loop started (phase-coordinated)")
        
        # Recover any uploads stuck in 'uploading' from previous crash/hang
        self._recover_stuck_uploads()
        
        coordinator = get_coordinator()
        
        while not self._stop_event.is_set():
            try:
                # ──────────────────────────────────────────────
                # WAIT for the UPLOADING phase
                # ──────────────────────────────────────────────
                # This blocks until the coordinator signals that
                # processing workers have finished their batch.
                # Checks every 2 seconds so we can respond to shutdown.
                if not coordinator.should_upload(timeout=2.0):
                    # Not our turn yet — also do periodic time-based refresh
                    self.cloud.check_and_refresh()
                    continue
                
                # ──────────────────────────────────────────────
                # UPLOADING PHASE — drain everything
                # ──────────────────────────────────────────────
                logger.info("=== Upload phase started - draining all pending uploads ===")
                
                # Recover any stuck uploads first
                self._recover_stuck_uploads()
                
                # Drain loop: keep uploading until nothing is left
                total_uploaded = 0
                total_failed = 0
                drain_rounds = 0
                
                while not self._stop_event.is_set():
                    # Get all pending uploads
                    pending = self.db.get_pending_uploads(limit=50)  # Larger batch during drain
                    
                    # Get retryable failed uploads
                    failed = self.db.get_failed_uploads(max_retries=self.config.upload_max_retries)
                    
                    if not pending and not failed:
                        # Everything is drained!
                        break
                    
                    drain_rounds += 1
                    round_count = len(pending) + len(failed)
                    logger.info(
                        f"Upload drain round #{drain_rounds}: "
                        f"{len(pending)} pending + {len(failed)} retrying = {round_count} total"
                    )
                    
                    # Upload pending files
                    for upload in pending:
                        if self._stop_event.is_set():
                            break
                        success = self._upload_file(upload)
                        if success:
                            total_uploaded += 1
                        else:
                            total_failed += 1
                    
                    # Retry failed uploads
                    for upload in failed:
                        if self._stop_event.is_set():
                            break
                        
                        # Brief delay before retry
                        retry_delay = min(
                            self.config.upload_retry_delay * (2 ** upload['retry_count']),
                            10  # Cap at 10s during drain (faster than normal)
                        )
                        self._stop_event.wait(timeout=retry_delay)
                        if self._stop_event.is_set():
                            break
                        
                        success = self._upload_file(upload)
                        if success:
                            total_uploaded += 1
                        else:
                            total_failed += 1
                    
                    # Check for stuck uploads between rounds
                    self._recover_stuck_uploads()
                
                # ──────────────────────────────────────────────
                # UPLOAD PHASE COMPLETE
                # ──────────────────────────────────────────────
                logger.info(
                    f"=== Upload phase complete: {total_uploaded} uploaded, "
                    f"{total_failed} failed in {drain_rounds} rounds ==="
                )
                
                # Refresh cloud connection after completing all uploads
                # This gives us a fresh connection for the next batch
                logger.info("Refreshing cloud connection after upload batch...")
                self.cloud._rebuild_service(reason="post-batch refresh")
                
                # Signal coordinator to switch back to PROCESSING
                coordinator.on_uploads_complete()
                
            except Exception as e:
                logger.exception(f"Error in upload queue worker: {e}")
                self._stop_event.wait(timeout=10)
        
        logger.info("Upload queue worker loop exited")
    
    def _upload_file(self, upload: dict) -> bool:
        """Upload a single file from the queue. Returns True on success."""
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
            return False
        
        try:
            # Mark as uploading
            self.db.update_upload_status(upload_id, 'uploading')
            
            # Perform upload
            success = self.cloud.upload_file(local_path, relative_to)
            
            if success:
                self.db.update_upload_status(upload_id, 'completed')
                logger.info(f"Upload {upload_id} completed: {local_path.name}")
                return True
            else:
                error_msg = "Upload returned False"
                self.db.update_upload_status(
                    upload_id, 'failed', 
                    error=error_msg, 
                    increment_retry=True
                )
                logger.warning(f"Upload {upload_id} failed: {error_msg}")
                return False
        
        except Exception as e:
            error_msg = str(e)
            self.db.update_upload_status(
                upload_id, 'failed',
                error=error_msg,
                increment_retry=True
            )
            logger.error(f"Upload {upload_id} failed with exception: {error_msg}")
            return False
    
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
