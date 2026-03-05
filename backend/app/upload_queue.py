"""
Upload queue manager for Wedding Face Forward.

Handles asynchronous uploads to Google Drive with retry logic.

Integrates with the Phase Coordinator:
  - Waits for UPLOADING phase before processing uploads.
  - Drains ALL pending uploads during the UPLOADING phase using a
    thread pool for parallel uploads (UPLOAD_WORKERS threads).
  - Processing workers are NOT blocked during the upload phase —
    processing and uploading run as a true concurrent pipeline.
  - Refreshes the cloud connection after each batch completes.
  - Signals the coordinator to switch back to PROCESSING phase when done.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from .config import get_config
from .db import get_db
from .cloud import get_cloud
from .phase import get_coordinator

logger = logging.getLogger(__name__)


class UploadQueueManager:
    """Manages background uploads to Google Drive with parallel upload workers."""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.db = get_db()
        self.cloud = get_cloud()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        
        # Stats for monitoring
        self._stats_lock = threading.Lock()
        self._total_uploaded = 0
        self._total_failed = 0
    
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
        logger.info(
            f"Upload queue worker started (parallel mode: {self.config.upload_workers} upload threads)"
        )
    
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

        Pipeline flow (processing and uploading are concurrent):
          1. Wait for UPLOADING phase signal from coordinator.
          2. Drain ALL pending + failed uploads using a thread pool.
          3. Refresh cloud connection.
          4. Signal coordinator to switch back to PROCESSING.
          5. Repeat.

        NOTE: Processing workers are NOT paused during this phase.
        Both pipelines run concurrently for maximum throughput.
        """
        logger.info("Upload queue worker loop started (concurrent pipeline mode)")
        
        # Recover any uploads stuck in 'uploading' from previous crash/hang
        self._recover_stuck_uploads()
        
        coordinator = get_coordinator()
        
        while not self._stop_event.is_set():
            try:
                # ──────────────────────────────────────────────
                # WAIT for the UPLOADING phase
                # ──────────────────────────────────────────────
                if not coordinator.should_upload(timeout=2.0):
                    # Not our turn yet — do periodic time-based refresh
                    self.cloud.check_and_refresh()
                    continue
                
                # ──────────────────────────────────────────────
                # UPLOADING PHASE — drain everything in parallel
                # ──────────────────────────────────────────────
                logger.info(
                    f"=== Upload phase started - draining all pending uploads "
                    f"({self.config.upload_workers} parallel threads) ==="
                )
                
                # Recover any stuck uploads first
                self._recover_stuck_uploads()
                
                total_uploaded = 0
                total_failed = 0
                drain_rounds = 0
                
                # Use a thread pool for parallel uploads
                with ThreadPoolExecutor(
                    max_workers=self.config.upload_workers,
                    thread_name_prefix="Uploader"
                ) as pool:
                    while not self._stop_event.is_set():
                        # Fetch pending + retryable failed uploads
                        # Fetch a generous batch — the pool will work through them
                        pending = self.db.get_pending_uploads(
                            limit=self.config.upload_workers * 4
                        )
                        failed = self.db.get_failed_uploads(
                            max_retries=self.config.upload_max_retries
                        )
                        
                        all_uploads = pending + failed
                        
                        if not all_uploads:
                            # Everything is drained!
                            break
                        
                        drain_rounds += 1
                        logger.info(
                            f"Upload drain round #{drain_rounds}: "
                            f"{len(pending)} pending + {len(failed)} retrying "
                            f"= {len(all_uploads)} total "
                            f"(submitting to {self.config.upload_workers} threads)"
                        )
                        
                        # Apply retry delay for failed items before submitting them
                        # We do this by wrapping them in a delayed callable
                        futures = {}
                        for upload in all_uploads:
                            if self._stop_event.is_set():
                                break
                            
                            # For failed (retry) uploads, calculate back-off delay
                            retry_delay = 0
                            if upload.get('retry_count', 0) > 0:
                                retry_delay = min(
                                    self.config.upload_retry_delay * (2 ** upload['retry_count']),
                                    10  # Cap at 10s during drain
                                )
                            
                            future = pool.submit(self._upload_file_with_delay, upload, retry_delay)
                            futures[future] = upload['id']
                        
                        # Collect results as they complete
                        for future in as_completed(futures):
                            if self._stop_event.is_set():
                                break
                            try:
                                success = future.result()
                                if success:
                                    total_uploaded += 1
                                else:
                                    total_failed += 1
                            except Exception as exc:
                                upload_id = futures[future]
                                logger.error(f"Upload {upload_id} raised an exception: {exc}")
                                total_failed += 1
                        
                        # Check for newly-stuck uploads between rounds
                        self._recover_stuck_uploads()
                
                # ──────────────────────────────────────────────
                # UPLOAD PHASE COMPLETE
                # ──────────────────────────────────────────────
                logger.info(
                    f"=== Upload phase complete: {total_uploaded} uploaded, "
                    f"{total_failed} failed in {drain_rounds} rounds ==="
                )
                
                with self._stats_lock:
                    self._total_uploaded += total_uploaded
                    self._total_failed += total_failed
                
                # Refresh cloud connection after completing all uploads
                logger.info("Refreshing cloud connection after upload batch...")
                self.cloud._rebuild_service(reason="post-batch refresh")
                
                # Signal coordinator to switch back to PROCESSING
                coordinator.on_uploads_complete()
                
            except Exception as e:
                logger.exception(f"Error in upload queue worker: {e}")
                self._stop_event.wait(timeout=10)
        
        logger.info("Upload queue worker loop exited")
    
    def _upload_file_with_delay(self, upload: dict, delay_seconds: float) -> bool:
        """
        Optional pre-delay (for back-off on retries), then upload the file.
        This is the function submitted to the thread pool.
        """
        if delay_seconds > 0:
            # Respect stop event during the delay
            self._stop_event.wait(timeout=delay_seconds)
        if self._stop_event.is_set():
            return False
        return self._upload_file(upload)
    
    def _upload_file(self, upload: dict) -> bool:
        """Upload a single file from the queue. Returns True on success."""
        upload_id = upload['id']
        local_path = Path(upload['local_path'])
        relative_to = Path(upload['relative_to'])
        
        # Check if file still exists
        if not local_path.exists():
            logger.warning(f"Upload {upload_id}: File no longer exists: {local_path}")
            # Set retry_count to max so this won't be retried
            self.db.update_upload_status(
                upload_id, 'failed', 
                error='File not found',
                increment_retry=False
            )
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
        
        Handles crashes, network timeouts, or other failures.
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
        stats = self.db.get_upload_stats()
        with self._stats_lock:
            stats['session_uploaded'] = self._total_uploaded
            stats['session_failed'] = self._total_failed
        return stats


# Global instance
_upload_queue: Optional[UploadQueueManager] = None


def get_upload_queue() -> UploadQueueManager:
    """Get the global upload queue instance."""
    global _upload_queue
    if _upload_queue is None:
        _upload_queue = UploadQueueManager()
    return _upload_queue
