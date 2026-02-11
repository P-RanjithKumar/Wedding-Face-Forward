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
from threading import Event
from typing import Optional

from .config import get_config
from .db import get_db
from .watcher import Watcher
from .processor import process_photo, DetectedFace
from .cluster import assign_person
from .router import route_photo, route_to_errors, route_to_no_faces, get_routing_summary
from .cloud import get_cloud
from .upload_queue import get_upload_queue

logger = logging.getLogger(__name__)

# Global shutdown flag
shutdown_event = Event()


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
        logger.info(f"Processing: {file_path.name} (ID: {photo_id})")
        
        # Update status to processing
        db.update_photo_status(photo_id, "processing")
        
        # Step 1-3: Process the image
        result = process_photo(file_path, photo_id, config)
        
        if not result.success:
            logger.error(f"Processing failed: {result.error}")
            db.update_photo_status(photo_id, "error")
            route_to_errors(file_path, config)
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
        logger.info(
            f"Completed: {file_path.name} | "
            f"{len(result.faces)} faces, {unique_persons} persons | "
            f"Cloud: {'Enabled' if cloud.is_enabled else 'Disabled'} | "
            f"{elapsed:.2f}s"
        )
        return True
        
    except Exception as e:
        logger.exception(f"Error processing {file_path.name}: {e}")
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
    """
    config = config or get_config()
    
    while not shutdown_event.is_set():
        try:
            # Wait for a job with timeout
            job = job_queue.get(timeout=1.0)
            
            if job is None:
                # Poison pill - shutdown
                break
            
            photo_id, file_path, file_hash = job
            process_single_photo(photo_id, file_path, file_hash, config)
            job_queue.task_done()
            
        except Empty:
            continue
        except Exception as e:
            logger.error(f"Worker error: {e}")
            # Still mark job as done on error to prevent queue blocking
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
                
                # Print stats periodically
                if not shutdown_event.is_set():
                    queue_size = job_queue.qsize()
                    if queue_size > 0:
                        logger.info(f"Queue size: {queue_size}")
                
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
