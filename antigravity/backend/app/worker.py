"""
Worker module for AURA Phase 2 Backend (by DARK intelligence).

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


class WorkerStateManager:
    """Thread-safe manager to track the real-time state of each worker thread via a shared file."""
    
    def __init__(self):
        self._states = {}  # {thread_name: state_id}
        self._lock = Lock()
        try:
            import dist_utils
            self._state_file = dist_utils.get_logs_dir() / "worker_states.json"
        except:
            self._state_file = Path("logs/worker_states.json")
        
        # Ensure directory exists
        self._state_file.parent.mkdir(parents=True, exist_ok=True)

    def clear(self):
        with self._lock:
            self._states = {}
            self._save_to_file(self._states)

    def set_state(self, thread_name: str, state: str):
        with self._lock:
            self._states[thread_name] = state
            self._save_to_file(self._states)
            
    def _save_to_file(self, data: dict):
        """Save states to a shared JSON file for the API server to read."""
        try:
            import json
            temp_file = self._state_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(data, f)
            temp_file.replace(self._state_file) # Atomic swap
        except Exception as e:
            pass # Silent failure to avoid worker crashes

    def get_all_states(self) -> dict:
        """Read states from the shared file (called by the API process)."""
        try:
            import json
            if self._state_file.exists():
                with open(self._state_file, "r") as f:
                    return json.load(f)
        except:
            pass
        return {}

# Global state trackers
progress = ProgressTracker()
worker_states = WorkerStateManager()


def setup_logging(level: str = "INFO") -> None:
    """Configure logging with console output."""
    import dist_utils

    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            dist_utils.rotating_log_handler("worker.log"),  # 5 MB x 3, was unbounded
        ],
        force=True
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
    """
    config = config or get_config()
    db = get_db()
    start_time = time.time()
    thread_name = threading.current_thread().name
    
    try:
        prog = progress.on_start()
        logger.info(f"Processing {prog}: {file_path.name} (ID: {photo_id})")
        
        # Step 1: Normalizing (starts automatically in process_photo)
        worker_states.set_state(thread_name, "normalizing")
        
        # Check if already processing/completed
        current_photo = db.get_photo_by_id(photo_id)
        if current_photo and current_photo.status in ("processing", "completed", "no_faces"):
            progress.on_complete()
            return True

        # Update status to processing
        db.update_photo_status(photo_id, "processing")
        
        # Step 1-3: Process the image (Normalizing -> Thumbnailing -> Detecting)
        # Note: We can manually trigger state changes here to make it visible
        worker_states.set_state(thread_name, "normalizing")
        # (A 0.1 s "visual stability" pause used to sit here. Removed
        # 2026-11-14: with the GPU a photo takes ~0.2 s, so it cost up to a
        # third of the processing time.)

        # Internal process_photo handles the heavy lifting
        # We'll set 'detecting' before calling it as that's the longest phase
        worker_states.set_state(thread_name, "detecting")
        result = process_photo(file_path, photo_id, config)
        
        if not result.success:
            logger.error(f"Processing failed: {result.error}")
            db.update_photo_status(photo_id, "error")
            route_to_errors(file_path, config)
            progress.on_complete()
            return False
        
        # Step 4: Clustering & Embedding
        worker_states.set_state(thread_name, "embedding")
        person_ids = []
        for face in result.faces:
            face_id = db.create_face(
                photo_id=photo_id,
                bbox=face.bbox,
                embedding=face.embedding,
                confidence=face.confidence
            )
            
            # Assignment is the 'clustering' part
            worker_states.set_state(thread_name, "clustering")
            # Atomic: picks/creates the person AND links this face in one step
            person_id = assign_person(face.embedding, config.cluster_threshold, face_id=face_id)
            person_ids.append(person_id)
        
        # Step 5: Routing
        worker_states.set_state(thread_name, "routing")
        cloud = get_cloud()
        
        if len(result.faces) == 0:
            db.update_photo_processing(photo_id, str(result.processed_path), "", 0, "no_faces")
            route_to_no_faces(result.processed_path, config)
        else:
            try:
                routed_paths = route_photo(photo_id, result.processed_path, person_ids, config)
                
                # Step 6: Uploading (enqueuing)
                worker_states.set_state(thread_name, "uploading")
                upload_queue = get_upload_queue()
                if upload_queue.config.upload_queue_enabled and upload_queue.cloud.is_enabled:
                    for path in routed_paths:
                        upload_queue.enqueue(photo_id, path, config.event_root)
                
                db.update_photo_processing(
                    photo_id,
                    str(result.processed_path),
                    str(result.thumbnail_path) if result.thumbnail_path else "",
                    len(result.faces),
                    "completed"
                )
            except Exception as routing_error:
                logger.error(f"Routing failed: {routing_error}")
                db.update_photo_processing(photo_id, str(result.processed_path), "", len(result.faces), "completed")
        
        progress.on_complete()
        return True
        
    except Exception as e:
        logger.exception(f"Error processing {file_path.name}: {e}")
        progress.on_complete()
        return False


def worker_loop(
    job_queue: Queue,
    config=None
) -> None:
    """
    Main processing loop for a single worker.
    """
    config = config or get_config()
    coordinator = get_coordinator()
    thread_name = threading.current_thread().name
    
    logger.info(f"[{thread_name}] Worker started")
    worker_states.set_state(thread_name, "idle")
    
    while not shutdown_event.is_set():
        try:
            # We are waiting for files, keep state idle
            worker_states.set_state(thread_name, "idle")

            if not coordinator.can_process(timeout=1.0):
                continue

            try:
                job = job_queue.get(timeout=1.0)
            except Empty:
                continue            
            if job is None:
                break
            
            photo_id, file_path, file_hash = job
            process_single_photo(photo_id, file_path, file_hash, config)
            
            coordinator.on_photo_processed()
            job_queue.task_done()
            
            # Back to idle after job
            worker_states.set_state(thread_name, "idle")
            
        except Exception as e:
            logger.error(f"[{thread_name}] Worker error: {e}")
            worker_states.set_state(thread_name, "idle")


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
    logger.info("  AURA - Phase 2 Backend (by DARK intelligence)")
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
    
    # Decide graphics card vs processor before the first photo (runs the
    # one-time speed test if needed, ~40 s) so it is logged clearly up front
    try:
        from .processor import get_compute_plan
        get_compute_plan()
    except Exception as e:
        logger.error(f"Could not choose GPU/CPU, the processor will be used: {e}")

    # Start worker pool
    logger.info(f"Starting {config.worker_count} workers...")
    worker_states.clear()
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
                    # Also handles restart resume: if the DB has pending uploads
                    # from a previous session (and no new photos arrived),
                    # we still need to kick off the upload phase.
                    if status["active"] == 0 and queue_size == 0:
                        coordinator = get_coordinator()
                        upload_stats = db.get_upload_stats()
                        pending_count = upload_stats.get("pending", 0) if upload_stats else 0
                        coordinator.flush_if_needed(pending_upload_count=pending_count)
                
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
