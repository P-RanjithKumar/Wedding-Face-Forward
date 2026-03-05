"""
Phase Coordinator for Wedding Face Forward.

Controls the alternating phases between PROCESSING and UPLOADING.
Key design: processing and uploading now run CONCURRENTLY — there is
no hard pause on processing workers while uploads happen.

  - PROCESSING phase: Workers process photos AND enqueue uploads.
  - UPLOADING phase: Cloud uploads run in parallel WITH continued processing.
    Processing workers are NOT paused — we overlap both workloads.
  - Enrollment (user registration) is ALWAYS allowed in both phases.

Flow:
  1. System starts in PROCESSING phase.
  2. After PROCESS_BATCH_SIZE photos are processed, trigger UPLOADING phase.
  3. Processing workers continue working (no pause).
  4. Upload queue drains all pending uploads concurrently.
  5. After all uploads complete, refresh cloud connection, switch back to PROCESSING.
  6. Repeat.
"""

import logging
import os
import threading
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Phase(Enum):
    PROCESSING = "processing"
    UPLOADING = "uploading"


class PhaseCoordinator:
    """
    Thread-safe coordinator that alternates between PROCESSING and UPLOADING phases.
    
    Usage:
        coordinator = get_coordinator()
        
        # In processing workers:
        if coordinator.can_process():
            process_photo(...)
            coordinator.on_photo_processed()
        
        # In upload queue worker loop:
        if coordinator.should_upload():
            upload_all_pending()
            coordinator.on_uploads_complete()
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._phase = Phase.PROCESSING
        self._photos_processed_in_batch = 0
        self._batch_size = int(os.getenv('PROCESS_BATCH_SIZE', '20'))
        self._total_batches_completed = 0
        
        # Event that processing workers wait on when paused
        self._processing_allowed = threading.Event()
        self._processing_allowed.set()  # Start in PROCESSING phase
        
        # Event that upload worker waits on when not its turn
        self._uploading_allowed = threading.Event()
        self._uploading_allowed.clear()  # Upload not allowed initially
        
        logger.info(
            f"Phase Coordinator initialized: batch_size={self._batch_size}, "
            f"starting phase=PROCESSING"
        )
    
    @property
    def current_phase(self) -> Phase:
        """Get the current phase."""
        return self._phase
    
    @property
    def batch_size(self) -> int:
        """Get the configured batch size."""
        return self._batch_size
    
    @property
    def photos_in_current_batch(self) -> int:
        """How many photos have been processed in the current batch."""
        return self._photos_processed_in_batch
    
    def can_process(self, timeout: float = 1.0) -> bool:
        """
        Check if processing is allowed.

        In concurrent pipeline mode, processing workers are NEVER blocked —
        this always returns True immediately. Processing and uploading run
        side-by-side for maximum throughput.

        The timeout parameter is kept for API compatibility but is not used.

        Returns:
            Always True.
        """
        return True
    
    def on_photo_processed(self) -> None:
        """
        Called after a photo is successfully processed (or errored out).
        Increments the batch counter and triggers phase switch if batch is full.
        """
        with self._lock:
            self._photos_processed_in_batch += 1
            count = self._photos_processed_in_batch
            batch = self._batch_size
        
        # batch_size=0 means "no batching, keep uploading continuously".
        # We do NOT switch to uploading on every photo — the flush loop handles
        # it when the job queue goes idle.
        if batch > 0 and count >= batch:
            self._switch_to_uploading()
    
    def _switch_to_uploading(self) -> None:
        """Switch from PROCESSING to UPLOADING phase."""
        with self._lock:
            if self._phase == Phase.UPLOADING:
                return  # Already in uploading phase
            
            count = self._photos_processed_in_batch
            self._phase = Phase.UPLOADING
        
        logger.info(
            f"=== PHASE SWITCH: PROCESSING -> UPLOADING "
            f"({count} photos processed, batch limit reached) "
            f"[processing continues concurrently] ==="
        )
        
        # NOTE: We do NOT pause processing workers (no _processing_allowed.clear()).
        # Processing and uploading run concurrently for maximum throughput.
        
        # Signal upload worker to start
        self._uploading_allowed.set()
    
    def should_upload(self, timeout: float = 2.0) -> bool:
        """
        Check if uploading is allowed. Blocks up to `timeout` seconds
        if we're in the PROCESSING phase.
        
        The upload queue worker should call this to know when to start
        uploading.
        
        Returns:
            True if uploading phase is active, False otherwise.
        """
        return self._uploading_allowed.wait(timeout=timeout)
    
    def flush_if_needed(self, pending_upload_count: int = 0) -> bool:
        """
        Force a switch to UPLOADING phase if there are uploads waiting,
        even if no photos were processed this session.

        This covers two important cases:
          1. Partial batch: fewer photos processed than batch_size — still
             need to upload what's pending.
          2. Restart resume: app restarted with no new photos to process,
             but the DB has pending uploads left over from the last session.
             Pass pending_upload_count > 0 to trigger uploads in this case.

        Args:
            pending_upload_count: Number of pending uploads currently in the DB.
                                  If > 0, upload phase is triggered even when
                                  no photos were processed this session.

        Returns:
            True if flush was triggered, False if nothing to flush.
        """
        with self._lock:
            if self._phase == Phase.UPLOADING:
                return False  # Already uploading

            has_processed = self._photos_processed_in_batch > 0
            has_pending_uploads = pending_upload_count > 0

            if not has_processed and not has_pending_uploads:
                return False  # Truly nothing to do

            count = self._photos_processed_in_batch

        if has_pending_uploads and not has_processed:
            logger.info(
                f"=== FLUSH: {pending_upload_count} pending upload(s) in DB from "
                f"previous session. Triggering upload phase on startup. ==="
            )
        else:
            logger.info(
                f"=== FLUSH: {count} photo(s) processed (< batch_size={self._batch_size}), "
                f"queue is idle. Triggering upload phase. ==="
            )
        self._switch_to_uploading()
        return True
    
    def on_uploads_complete(self) -> None:
        """
        Called when all pending uploads have been drained.
        Resets the batch counter and switches back to PROCESSING phase.
        """
        with self._lock:
            self._total_batches_completed += 1
            batch_num = self._total_batches_completed
            self._photos_processed_in_batch = 0
            self._phase = Phase.PROCESSING
        
        logger.info(
            f"=== PHASE SWITCH: UPLOADING -> PROCESSING "
            f"(batch #{batch_num} complete, uploads drained) "
            f"[processing was never paused] ==="
        )
        
        # Pause upload worker
        self._uploading_allowed.clear()
        
        # Processing workers were never paused, so no need to resume them
    
    def get_status(self) -> dict:
        """Get current phase coordinator status for monitoring/UI."""
        with self._lock:
            return {
                "phase": self._phase.value,
                "photos_in_batch": self._photos_processed_in_batch,
                "batch_size": self._batch_size,
                "batches_completed": self._total_batches_completed,
                "processing_allowed": self._processing_allowed.is_set(),
                "uploading_allowed": self._uploading_allowed.is_set(),
            }


# Global singleton
_coordinator: Optional[PhaseCoordinator] = None
_coordinator_lock = threading.Lock()


def get_coordinator() -> PhaseCoordinator:
    """Get the global PhaseCoordinator instance (thread-safe singleton)."""
    global _coordinator
    if _coordinator is None:
        with _coordinator_lock:
            if _coordinator is None:
                _coordinator = PhaseCoordinator()
    return _coordinator
