"""
Worker module for Wedding Face Forward Phase 2 Backend.

Main orchestration: runs the file watcher and processes photos
through the full pipeline using a worker pool.
"""

import logging
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from queue import Queue, Empty
import threading
from threading import Event, Lock
from typing import Optional

from .config import get_config
from .db import get_db
from .watcher import Watcher
from .processor import process_photo, DetectedFace
from .cluster import assign_person
from .router import route_photo, route_to_errors, route_to_no_faces, get_routing_summary
from .cloud import get_cloud
from .upload_queue import get_upload_queue
from .phase import get_coordinator, Phase

logger = logging.getLogger(__name__)

# Global shutdown flag
shutdown_event = Event()


class ProgressTracker:
    """Thread-safe progress tracker for photo processing batches."""
    
    def __init__(self):
        self._lock = Lock()
        self._total_enqueued = 0
        self._completed = 0
        self._active = 0  # currently being processed
        self._last_idle_reported = False
    
    def on_enqueue(self, count: int = 1):
        """Called when new photos are added to the queue."""
        with self._lock:
            self._total_enqueued += count
            self._last_idle_reported = False
    
    def on_start(self) -> str:
        """Called when a worker starts processing a photo. Returns progress string."""
        with self._lock:
            self._active += 1
            current = self._completed + 1
            return f"[{current}/{self._total_enqueued}]"
    
    def on_complete(self) -> str:
        """Called when a photo finishes processing. Returns progress string."""
        with self._lock:
            self._completed += 1
            self._active -= 1
            return f"[{self._completed}/{self._total_enqueued}]"
    
    def get_status(self) -> dict:
        """Get current processing status."""
        with self._lock:
            return {
                "total": self._total_enqueued,
                "completed": self._completed,
                "active": self._active,
                "remaining": self._total_enqueued - self._completed,
                "all_done": self._completed >= self._total_enqueued and self._total_enqueued > 0,
            }
    
    def check_and_report_idle(self) -> bool:
        """Returns True if just went idle (transitions from busy to all done). Only reports once."""
        with self._lock:
            if self._completed >= self._total_enqueued and self._total_enqueued > 0 and not self._last_idle_reported:
                self._last_idle_reported = True
                return True
            return False


# Global progress tracker
progress = ProgressTracker()


def setup_logging(level: str = "INFO") -> None:
    """Configure logging with console output."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("insightface").setLevel(logging.WARNING)
    logging.getLogger("onnxruntime").setLevel(logging.WARNING)


def process_single_photo(
    photo_id: int,
    file_path: Path,
    file_hash: str,
    config=None
) -> bool:
    """
    Process a single photo through the full pipeline.
    
    1. Normalize image (RAW→JPEG if needed)
    2. Create thumbnail
    3. Detect faces and extract embeddings
    4. Assign faces to person clusters
    5. Route photo to appropriate folders
    """
    config = config or get_config()
    db = get_db()
    start_time = time.time()
    
    try:
        prog = progress.on_start()
        logger.info(f"Processing {prog}: {file_path.name} (ID: {photo_id})")
        
        # Safety check: clean up any orphaned face records from a previous crash
        existing_faces = db.get_faces_count_for_photo(photo_id)
        if existing_faces > 0:
            logger.warning(
                f"Photo {photo_id} has {existing_faces} orphaned face records from a previous crash, cleaning up..."
            )
            db._cleanup_orphaned_faces([photo_id])
        
        # Update status to processing
        db.update_photo_status(photo_id, "processing")
        
        # Step 1-3: Process the image
        result = process_photo(file_path, photo_id, config)
        
        if not result.success:
            logger.error(f"Processing failed: {result.error}")
            db.update_photo_status(photo_id, "error")
            route_to_errors(file_path, config)
            progress.on_complete()  # Count errors toward progress
            return False
        
        # Step 4: Cluster faces and assign to persons
        person_ids = []
        for face in result.faces:
            # Store face in database
            face_id = db.create_face(
                photo_id=photo_id,
                bbox=face.bbox,
                embedding=face.embedding,
                confidence=face.confidence
            )
            
            # Assign to person cluster
            person_id = assign_person(face.embedding, config.cluster_threshold)
            db.update_face_person(face_id, person_id)
            person_ids.append(person_id)
        
        # Route photo to appropriate folders
        cloud = get_cloud()
        
        if len(result.faces) == 0:
            # No faces detected
            db.update_photo_processing(
                photo_id,
                str(result.processed_path),
                str(result.thumbnail_path) if result.thumbnail_path else "",
                0,
                "no_faces"
            )
            route_to_no_faces(result.processed_path, config)
            logger.info(f"No faces detected: {file_path.name}")
        else:
            # Route to person folders
            try:
                routed_paths = route_photo(photo_id, result.processed_path, person_ids, config)
                
                # Queue uploads for background processing
                upload_queue = get_upload_queue()
                if upload_queue.config.upload_queue_enabled and upload_queue.cloud.is_enabled:
                    for path in routed_paths:
                        upload_queue.enqueue(photo_id, path, config.event_root)
                    logger.debug(f"Queued {len(routed_paths)} files for upload")
                
                db.update_photo_processing(
                    photo_id,
                    str(result.processed_path),
                    str(result.thumbnail_path) if result.thumbnail_path else "",
                    len(result.faces),
                    "completed"
                )
            except Exception as routing_error:
                logger.error(f"Routing failed for {file_path.name}: {routing_error}")
                # Still mark as completed in DB since faces were detected and stored
                db.update_photo_processing(
                    photo_id,
                    str(result.processed_path),
                    str(result.thumbnail_path) if result.thumbnail_path else "",
                    len(result.faces),
                    "completed"
                )
                # Log the routing failure but don't fail the entire photo processing
                logger.warning(f"Photo {photo_id} marked completed despite routing error")
        
        elapsed = time.time() - start_time
        unique_persons = len(set(person_ids))
        cloud = get_cloud()
        prog = progress.on_complete()
        logger.info(
            f"Completed {prog}: {file_path.name} | "
            f"{len(result.faces)} faces, {unique_persons} persons | "
            f"Cloud: {'Enabled' if cloud.is_enabled else 'Disabled'} | "
            f"{elapsed:.2f}s"
        )
        return True
        
    except Exception as e:
        logger.exception(f"Error processing {file_path.name}: {e}")
        progress.on_complete()  # Count errors toward progress
        # Ensure photo status is updated to error, even if DB operation fails
        try:
            db.update_photo_status(photo_id, "error")
        except Exception as db_error:
            logger.error(f"Failed to update photo status to error: {db_error}")
        # Try to move file to errors folder
        try:
            route_to_errors(file_path, config)
            logger.info(f"Moved error file to Errors folder: {file_path.name}")
        except Exception as move_error:
            logger.error(f"Failed to move error file {file_path.name} to Errors folder: {move_error}")
            logger.error(f"File remains at original location: {file_path}")
        return False


def worker_loop(
    job_queue: Queue,
    config=None
) -> None:
    """
    Main processing loop for a single worker.
    Pulls jobs from the queue and processes them.
    
    Respects the Phase Coordinator: pauses during UPLOADING phase,
    only processes during PROCESSING phase.
    """
    config = config or get_config()
    coordinator = get_coordinator()
    thread_name = threading.current_thread().name
    
    logger.info(f"[{thread_name}] Worker started (phase-coordinated, batch_size={coordinator.batch_size})")
    
    while not shutdown_event.is_set():
        try:
            # Wait for PROCESSING phase — blocks if we're in UPLOADING phase.
            # Returns False on timeout (1s), at which point we loop back
            # to check shutdown_event.
            if not coordinator.can_process(timeout=1.0):
                continue  # Still in UPLOADING phase, check shutdown and retry
            
            # Try to get a job from the queue
            job = job_queue.get(timeout=1.0)
            
            if job is None:
                # Poison pill - shutdown
                break
            
            photo_id, file_path, file_hash = job
            
            try:
                process_single_photo(photo_id, file_path, file_hash, config)
            except Exception as e:
                logger.error(f"[{thread_name}] Error processing photo {photo_id}: {e}")
            
            # Notify phase coordinator that a photo was processed (success OR failure).
            # This MUST happen regardless of success/failure so the batch counter
            # advances and the upload phase eventually triggers.
            coordinator.on_photo_processed()
            batch_status = coordinator.get_status()
            logger.debug(
                f"[{thread_name}] Batch progress: {batch_status['photos_in_batch']}/{batch_status['batch_size']}"
            )
            
            job_queue.task_done()
            
        except Empty:
            continue
        except Exception as e:
            logger.error(f"[{thread_name}] Worker error: {e}")
            try:
                job_queue.task_done()
            except:
                pass


def print_stats(config=None) -> None:
    """Print current processing statistics."""
    config = config or get_config()
    db = get_db()
    
    db_stats = db.get_stats()
    routing_stats = get_routing_summary(config)
    upload_stats = db.get_upload_stats()
    
    logger.info("=" * 50)
    logger.info("                PROCESSING STATS")
    logger.info("=" * 50)
    logger.info(f"Photos by status: {db_stats['photos_by_status']}")
    logger.info(f"Total faces detected: {db_stats['total_faces']}")
    logger.info(f"Total persons identified: {db_stats['total_persons']}")
    logger.info(f"Processed files: {routing_stats['processed_count']}")
    logger.info(f"No-face photos: {routing_stats['no_faces_count']}")
    logger.info(f"Error photos: {routing_stats['errors_count']}")
    
    if upload_stats:
        logger.info(f"Upload queue: {upload_stats}")
    
    if routing_stats['persons']:
        logger.info("Person distribution:")
        for person_name, counts in routing_stats['persons'].items():
            logger.info(f"  {person_name}: {counts['solo']} solo, {counts['group']} group")
    logger.info("=" * 50)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Shutdown signal received...")
    shutdown_event.set()


def main():
    """Main entry point for the worker."""
    # Load configuration
    config = get_config()
    
    # Setup logging
    setup_logging(config.log_level)
    
    logger.info("=" * 50)
    logger.info("  Wedding Face Forward - Phase 2 Backend")
    logger.info("=" * 50)
    logger.info(f"Event Root: {config.event_root}")
    logger.info(f"Database: {config.db_path}")
    logger.info(f"Workers: {config.worker_count}")
    logger.info(f"Cluster Threshold: {config.cluster_threshold}")
    logger.info(f"Dry Run: {config.dry_run}")
    logger.info("=" * 50)
    
    # Ensure directories exist
    config.ensure_directories()
    
    # Initialize database
    db = get_db()
    db.initialize()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create job queue
    job_queue: Queue = Queue()
    
    # Start watcher
    watcher = Watcher(job_queue, config)
    watcher.start()
    
    # Resume pending photos from previous session
    # After a restart the in-memory queue is empty, but the DB may still
    # contain photos in 'pending' status that were never processed.
    pending_photos = db.get_pending_photos()
    if pending_photos:
        logger.info(f"Resuming {len(pending_photos)} pending photo(s) from previous session")
        for photo in pending_photos:
            file_path = Path(photo.original_path)
            if file_path.exists():
                job_queue.put((photo.id, file_path, photo.file_hash))
                progress.on_enqueue()
            else:
                logger.warning(
                    f"Skipping resume for photo {photo.id}: "
                    f"original file no longer exists at {photo.original_path}"
                )
        logger.info(f"Re-queued {job_queue.qsize()} photo(s) for processing")
    
    # Start upload queue
    upload_queue = get_upload_queue()
    upload_queue.start()
    
    # Start worker pool
    logger.info(f"Starting {config.worker_count} workers...")
    with ThreadPoolExecutor(max_workers=config.worker_count) as executor:
        futures = [
            executor.submit(worker_loop, job_queue, config)
            for _ in range(config.worker_count)
        ]
        
        try:
            # Main loop - wait for shutdown
            main_loop_count = 0
            while not shutdown_event.is_set():
                time.sleep(5)
                main_loop_count += 1
                
                # Report meaningful progress status
                if not shutdown_event.is_set():
                    status = progress.get_status()
                    queue_size = job_queue.qsize()
                    
                    if status["active"] > 0 or queue_size > 0:
                        # Actively processing
                        coord_status = get_coordinator().get_status()
                        phase_str = coord_status['phase'].upper()
                        batch_str = f"{coord_status['photos_in_batch']}/{coord_status['batch_size']}"
                        logger.info(
                            f"Progress: {status['completed']}/{status['total']} done | "
                            f"{status['active']} processing | {queue_size} queued | "
                            f"Phase: {phase_str} ({batch_str} in batch)"
                        )
                    elif progress.check_and_report_idle():
                        # Just finished a batch — show clear "done" message
                        logger.info(
                            f">> All {status['total']} photos processed! "
                            f"Waiting for new photos..."
                        )
                    
                    # If the queue is idle and workers aren't busy,
                    # flush any partial batch to trigger uploads.
                    # This handles the case where fewer than batch_size
                    # photos exist (e.g., only 5 photos with batch_size=20).
                    if status["active"] == 0 and queue_size == 0:
                        coordinator = get_coordinator()
                        if coordinator.photos_in_current_batch > 0:
                            coordinator.flush_if_needed()
                
                # Periodically check for stuck processing photos (~every 2 minutes)
                if main_loop_count % 24 == 0:
                    try:
                        stuck_count = db.reset_stuck_processing_live(timeout_minutes=10)
                        if stuck_count > 0:
                            logger.warning(f"Recovered {stuck_count} stuck processing photo(s)")
                    except Exception as e:
                        logger.error(f"Failed to check for stuck processing: {e}")
                        
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            shutdown_event.set()
        
        finally:
            # Shutdown gracefully
            logger.info("Shutting down...")
            
            # Stop watcher
            watcher.stop()
            
            # Stop upload queue
            upload_queue.stop()
            
            # Send poison pills to workers
            for _ in range(config.worker_count):
                job_queue.put(None)
            
            # Wait for workers to finish
            for future in as_completed(futures, timeout=10):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Worker shutdown error: {e}")
    
    # Print final stats
    print_stats(config)
    
    logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
