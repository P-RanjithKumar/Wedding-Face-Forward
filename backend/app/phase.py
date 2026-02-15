"""
Phase Coordinator for Wedding Face Forward.

Controls the alternating phases between PROCESSING and UPLOADING:
  - PROCESSING phase: Workers process photos, cloud upload is paused.
  - UPLOADING phase: Cloud uploads run, processing workers are paused.
  - Enrollment (user registration) is ALWAYS allowed in both phases.

Flow:
  1. System starts in PROCESSING phase.
  2. After PROCESS_BATCH_SIZE photos are processed, switch to UPLOADING phase.
  3. Processing workers pause (they check can_process() before taking jobs).
  4. Upload queue drains all pending uploads.
  5. After all uploads complete, refresh cloud connection, then switch back to PROCESSING.
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
        Check if processing is allowed. Blocks up to `timeout` seconds
        if we're in the UPLOADING phase.
        
        Processing workers should call this before taking a job from the queue.
        
        Args:
            timeout: How long to wait for processing to be allowed (seconds).
                     Returns False if still in UPLOADING phase after timeout.
        
        Returns:
            True if processing is allowed, False if still uploading.
        """
        return self._processing_allowed.wait(timeout=timeout)
    
    def on_photo_processed(self) -> None:
        """
        Called after a photo is successfully processed (or errored out).
        Increments the batch counter and triggers phase switch if batch is full.
        """
        with self._lock:
            self._photos_processed_in_batch += 1
            count = self._photos_processed_in_batch
            batch = self._batch_size
        
        if count >= batch:
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
            f"({count} photos processed, batch limit reached) ==="
        )
        
        # Pause processing workers
        self._processing_allowed.clear()
        
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
    
    def flush_if_needed(self) -> bool:
        """
        Force a switch to UPLOADING phase if there are processed photos
        waiting to be uploaded, even if the batch isn't full yet.
        
        This handles the case where fewer than batch_size photos exist.
        Should be called from the main loop when the processing queue is 
        empty and workers are idle.
        
        Returns:
            True if flush was triggered, False if nothing to flush.
        """
        with self._lock:
            if self._phase != Phase.PROCESSING:
                return False  # Already uploading
            if self._photos_processed_in_batch == 0:
                return False  # Nothing processed, nothing to flush
            
            count = self._photos_processed_in_batch
        
        logger.info(
            f"=== FLUSH: Only {count} photos in batch (< {self._batch_size}), "
            f"but queue is idle. Triggering upload phase. ==="
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
            f"(batch #{batch_num} complete, uploads drained) ==="
        )
        
        # Pause upload worker
        self._uploading_allowed.clear()
        
        # Resume processing workers
        self._processing_allowed.set()
    
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
