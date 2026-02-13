"""
File watcher module for Wedding Face Forward Phase 2 Backend.

Monitors the Incoming directory for new photos using watchdog,
with a periodic fallback scan for reliability.
"""

import hashlib
import logging
import time
from pathlib import Path
from queue import Queue
from threading import Thread, Event
from typing import Optional, Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent

from .config import get_config
from .db import get_db

logger = logging.getLogger(__name__)


def compute_file_hash(file_path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of a file for deduplication."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (IOError, OSError) as e:
        logger.error(f"Error computing hash for {file_path}: {e}")
        raise


def is_file_ready(file_path: Path, wait_time: float = 0.5) -> bool:
    """
    Check if a file is completely written and ready for processing.
    Waits briefly and checks if file size is stable.
    On Windows, also attempts to open the file to check for write locks.
    """
    try:
        if not file_path.exists():
            return False
            
        initial_size = file_path.stat().st_size
        if initial_size == 0:
            return False
            
        # Try to check for file locks (common on Windows during copy)
        try:
            # Opening in append mode will fail if another process has a write lock
            with open(file_path, "ab"):
                pass
        except (IOError, OSError):
            return False
            
        time.sleep(wait_time)
        final_size = file_path.stat().st_size
        
        return initial_size == final_size and final_size > 0
    except (IOError, OSError):
        return False


class PhotoEventHandler(FileSystemEventHandler):
    """Watchdog event handler for new photos."""
    
    def __init__(self, job_queue: Queue, config=None):
        super().__init__()
        self.job_queue = job_queue
        self.config = config or get_config()
        self._pending_files: Set[Path] = set()
    
    def _is_supported_file(self, path: Path) -> bool:
        """Check if the file has a supported extension."""
        return path.suffix.lower() in self.config.supported_extensions
    
    def _enqueue_file(self, file_path: Path) -> None:
        """Add file to processing queue if it's new and ready."""
        if not self._is_supported_file(file_path):
            return
        
        if file_path in self._pending_files:
            return
        
        self._pending_files.add(file_path)
        
        # Wait for file to be fully written
        if not is_file_ready(file_path):
            logger.debug(f"File not ready, skipping: {file_path}")
            self._pending_files.discard(file_path)
            return
        
        try:
            file_hash = compute_file_hash(file_path)
            db = get_db()
            
            # Check if already processed
            if db.photo_exists(file_hash):
                logger.debug(f"Already processed, skipping: {file_path}")
                self._pending_files.discard(file_path)
                return
            
            # Create photo record and enqueue
            photo_id = db.create_photo(file_hash, str(file_path))
            self.job_queue.put((photo_id, file_path, file_hash))
            
            # Track progress for user feedback
            from .worker import progress
            progress.on_enqueue()
            
            logger.info(f"Enqueued: {file_path.name} (ID: {photo_id})")
            
        except Exception as e:
            logger.error(f"Error enqueuing {file_path}: {e}")
        finally:
            self._pending_files.discard(file_path)
    
    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return
        self._enqueue_file(Path(event.src_path))
    
    def on_moved(self, event: FileMovedEvent) -> None:
        """Handle file move events (e.g., temp file renamed)."""
        if event.is_directory:
            return
        self._enqueue_file(Path(event.dest_path))
    
    def on_modified(self, event) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return
        self._enqueue_file(Path(event.src_path))


class DirectoryScanner(Thread):
    """Periodic scanner for files that might be missed by watchdog."""
    
    def __init__(self, job_queue: Queue, stop_event: Event, config=None):
        super().__init__(daemon=True, name="DirectoryScanner")
        self.job_queue = job_queue
        self.stop_event = stop_event
        self.config = config or get_config()
    
    def run(self) -> None:
        """Periodically scan the incoming directory."""
        logger.info(f"Scanner started, interval: {self.config.scan_interval}s")
        
        while not self.stop_event.is_set():
            try:
                self._scan_directory()
            except Exception as e:
                logger.error(f"Scan error: {e}")
            
            # Wait for next scan or stop
            self.stop_event.wait(self.config.scan_interval)
        
        logger.info("Scanner stopped")
    
    def _scan_directory(self) -> None:
        """Scan incoming directory for unprocessed files."""
        incoming_dir = self.config.incoming_dir
        
        if not incoming_dir.exists():
            return
        
        db = get_db()
        enqueued = 0
        
        for file_path in incoming_dir.iterdir():
            if not file_path.is_file():
                continue
            
            if file_path.suffix.lower() not in self.config.supported_extensions:
                continue
            
            if not is_file_ready(file_path, wait_time=0.1):
                continue
            
            try:
                file_hash = compute_file_hash(file_path)
                
                # Skip if already in database
                if db.photo_exists(file_hash):
                    continue
                
                # Create photo record and enqueue
                photo_id = db.create_photo(file_hash, str(file_path))
                self.job_queue.put((photo_id, file_path, file_hash))
                enqueued += 1
                logger.info(f"Scanner found: {file_path.name} (ID: {photo_id})")
                
            except Exception as e:
                # UNIQUE constraint = duplicate file, expected on re-scans
                if "UNIQUE constraint" in str(e):
                    logger.debug(f"Already in DB (duplicate hash): {file_path.name}")
                else:
                    logger.error(f"Scanner error for {file_path}: {e}")
        
        if enqueued > 0:
            logger.info(f"Scanner enqueued {enqueued} files")


class Watcher:
    """Main watcher class combining watchdog and periodic scanning."""
    
    def __init__(self, job_queue: Queue, config=None):
        self.job_queue = job_queue
        self.config = config or get_config()
        self.stop_event = Event()
        self._observer: Optional[Observer] = None
        self._scanner: Optional[DirectoryScanner] = None
    
    def start(self) -> None:
        """Start watching the incoming directory."""
        incoming_dir = self.config.incoming_dir
        incoming_dir.mkdir(parents=True, exist_ok=True)
        
        # Start watchdog observer
        handler = PhotoEventHandler(self.job_queue, self.config)
        self._observer = Observer()
        self._observer.schedule(handler, str(incoming_dir), recursive=False)
        self._observer.start()
        logger.info(f"Watching: {incoming_dir}")
        
        # Start periodic scanner
        self._scanner = DirectoryScanner(self.job_queue, self.stop_event, self.config)
        self._scanner.start()
        
        # Do an immediate scan
        self._scanner._scan_directory()
    
    def stop(self) -> None:
        """Stop all watchers."""
        self.stop_event.set()
        
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
        
        if self._scanner:
            self._scanner.join(timeout=5)
        
        logger.info("Watcher stopped")
    
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._observer is not None and self._observer.is_alive()
