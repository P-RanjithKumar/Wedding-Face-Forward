"""
Database module for Wedding Face Forward Phase 2 Backend.

SQLite schema and queries for tracking photos, faces, and person clusters.
"""

import sqlite3
import pickle
import threading
import logging
import time
import functools
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple
from dataclasses import dataclass
import numpy as np

from .config import get_config

logger = logging.getLogger(__name__)


def retry_on_lock(max_retries=5, initial_delay=1.0, backoff_factor=2.0):
    """
    Decorator to retry database operations on 'database is locked' errors.
    
    Args:
        max_retries (int): Maximum number of retries.
        initial_delay (float): Initial delay in seconds before first retry.
        backoff_factor (float): Multiplier for delay after each retry.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e):
                        last_exception = e
                        if attempt < max_retries:
                            logger.warning(
                                f"Database locked in {func.__name__}, retrying "
                                f"({attempt + 1}/{max_retries}) in {delay:.2f}s..."
                            )
                            time.sleep(delay)
                            delay *= backoff_factor
                        else:
                            logger.error(f"Database locked in {func.__name__}, max retries reached.")
                    else:
                        raise e
            
            if last_exception:
                raise last_exception
        return wrapper
    return decorator


@dataclass
class Photo:
    """Represents a photo record in the database."""
    id: int
    file_hash: str
    original_path: str
    processed_path: Optional[str]
    thumbnail_path: Optional[str]
    status: str
    face_count: Optional[int]
    created_at: datetime
    processed_at: Optional[datetime]


@dataclass
class Face:
    """Represents a detected face in the database."""
    id: int
    photo_id: int
    person_id: Optional[int]
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int
    embedding: np.ndarray
    confidence: float


@dataclass
class Person:
    """Represents a person cluster in the database."""
    id: int
    name: str
    centroid: np.ndarray
    face_count: int
    created_at: datetime


@dataclass
class Enrollment:
    """Represents an enrolled user in the database."""
    id: int
    person_id: int
    user_name: str
    phone: Optional[str]
    email: Optional[str]
    selfie_path: str
    match_confidence: float
    consent_given: bool
    created_at: datetime


SCHEMA_SQL = """
-- Photos table: tracks all ingested photos
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT UNIQUE NOT NULL,
    original_path TEXT NOT NULL,
    processed_path TEXT,
    thumbnail_path TEXT,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'completed', 'error', 'no_faces')),
    face_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

-- Faces table: detected faces with embeddings
CREATE TABLE IF NOT EXISTS faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    person_id INTEGER REFERENCES persons(id),
    bbox_x INTEGER NOT NULL,
    bbox_y INTEGER NOT NULL,
    bbox_w INTEGER NOT NULL,
    bbox_h INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    confidence REAL NOT NULL
);

-- Persons table: cluster centroids
CREATE TABLE IF NOT EXISTS persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    centroid BLOB NOT NULL,
    face_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Enrollments table: user registrations linked to person clusters
CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER REFERENCES persons(id),
    user_name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    selfie_path TEXT NOT NULL,
    match_confidence REAL NOT NULL,
    consent_given BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Upload queue table: tracks cloud upload status
CREATE TABLE IF NOT EXISTS upload_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_id INTEGER REFERENCES photos(id) ON DELETE CASCADE,
    local_path TEXT NOT NULL,
    relative_to TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'uploading', 'completed', 'failed')),
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_photos_status ON photos(status);
CREATE INDEX IF NOT EXISTS idx_photos_hash ON photos(file_hash);
CREATE INDEX IF NOT EXISTS idx_faces_photo ON faces(photo_id);
CREATE INDEX IF NOT EXISTS idx_faces_person ON faces(person_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_person ON enrollments(person_id);
CREATE INDEX IF NOT EXISTS idx_upload_queue_status ON upload_queue(status);
CREATE INDEX IF NOT EXISTS idx_upload_queue_photo ON upload_queue(photo_id);
"""


class Database:
    """SQLite database manager for the photo pipeline.
    
    Uses thread-local storage to ensure each thread has its own connection,
    preventing "database locked" errors when multiple threads access the DB.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_config().db_path
        self._local = threading.local()
    
    def connect(self) -> sqlite3.Connection:
        """Get or create thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=60.0,
                isolation_level=None  # Autocommit mode to prevent dangling read transactions
            )
            self._local.connection.row_factory = sqlite3.Row
            
            # Configure SQLite for better concurrency
            self._local.connection.execute("PRAGMA busy_timeout = 60000")
            self._local.connection.execute("PRAGMA journal_mode = WAL")
            self._local.connection.execute("PRAGMA foreign_keys = ON")
            self._local.connection.execute("PRAGMA synchronous = NORMAL")
            
        return self._local.connection
    
    def close(self) -> None:
        """Close the thread-local database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
    
    def initialize(self) -> None:
        """Create tables if they don't exist."""
        conn = self.connect()
        conn.executescript(SCHEMA_SQL)
        # Commit not strictly needed for DDL in autocommit but good practice
        try:
            conn.commit() 
        except Exception:
            pass
            
        # Reset any photos stuck in processing from a previous crash
        try:
            self._reset_stuck_processing()
        except Exception as e:
            logger.warning(f"Could not reset stuck processing photos: {e}")
    
    @retry_on_lock()
    def _reset_stuck_processing(self) -> int:
        """Reset photos stuck in 'processing' status back to 'pending'."""
        conn = self.connect()
        # Use explicit transaction block
        with conn:
            cursor = conn.execute(
                "UPDATE photos SET status = 'pending' WHERE status = 'processing'"
            )
            count = cursor.rowcount
        
        if count > 0:
            logger.warning(f"Reset {count} photo(s) stuck in 'processing' status back to 'pending'")
        return count
    
    # =========================================================================
    # Photo Operations
    # =========================================================================
    
    @retry_on_lock()
    def photo_exists(self, file_hash: str) -> bool:
        """Check if a photo with this hash already exists."""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT 1 FROM photos WHERE file_hash = ?",
            (file_hash,)
        )
        result = cursor.fetchone() is not None
        conn.commit() # Close implicit read transaction
        return result
    
    @retry_on_lock()
    def create_photo(self, file_hash: str, original_path: str) -> int:
        """Create a new photo record, returns photo ID."""
        conn = self.connect()
        with conn:
            cursor = conn.execute(
                """INSERT INTO photos (file_hash, original_path, status, created_at)
                   VALUES (?, ?, 'pending', ?)""",
                (file_hash, original_path, datetime.now())
            )
            return cursor.lastrowid
    
    @retry_on_lock()
    def update_photo_processing(
        self,
        photo_id: int,
        processed_path: str,
        thumbnail_path: str,
        face_count: int,
        status: str = "completed"
    ) -> None:
        """Update photo after processing."""
        conn = self.connect()
        with conn:
            conn.execute(
                """UPDATE photos 
                   SET processed_path = ?, thumbnail_path = ?, face_count = ?,
                       status = ?, processed_at = ?
                   WHERE id = ?""",
                (processed_path, thumbnail_path, face_count, status, datetime.now(), photo_id)
            )
    
    @retry_on_lock()
    def update_photo_status(self, photo_id: int, status: str) -> None:
        """Update photo status."""
        conn = self.connect()
        with conn:
            conn.execute(
                "UPDATE photos SET status = ? WHERE id = ?",
                (status, photo_id)
            )
    
    @retry_on_lock()
    def get_pending_photos(self) -> List[Photo]:
        """Get all photos with pending status."""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT * FROM photos WHERE status = 'pending' ORDER BY created_at"
        )
        rows = cursor.fetchall()
        conn.commit()
        return [self._row_to_photo(row) for row in rows]
    
    @retry_on_lock()
    def get_photo_by_id(self, photo_id: int) -> Optional[Photo]:
        """Get a photo by ID."""
        conn = self.connect()
        cursor = conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,))
        row = cursor.fetchone()
        conn.commit()
        return self._row_to_photo(row) if row else None
    
    @retry_on_lock()
    def get_photo_by_hash(self, file_hash: str) -> Optional[Photo]:
        """Get a photo by file hash."""
        conn = self.connect()
        cursor = conn.execute("SELECT * FROM photos WHERE file_hash = ?", (file_hash,))
        row = cursor.fetchone()
        conn.commit()
        return self._row_to_photo(row) if row else None
    
    def _row_to_photo(self, row: sqlite3.Row) -> Photo:
        """Convert database row to Photo object."""
        return Photo(
            id=row["id"],
            file_hash=row["file_hash"],
            original_path=row["original_path"],
            processed_path=row["processed_path"],
            thumbnail_path=row["thumbnail_path"],
            status=row["status"],
            face_count=row["face_count"],
            created_at=row["created_at"],
            processed_at=row["processed_at"],
        )
    
    # =========================================================================
    # Face Operations
    # =========================================================================
    
    @retry_on_lock()
    def create_face(
        self,
        photo_id: int,
        bbox: Tuple[int, int, int, int],
        embedding: np.ndarray,
        confidence: float,
        person_id: Optional[int] = None
    ) -> int:
        """Create a new face record."""
        conn = self.connect()
        embedding_blob = pickle.dumps(embedding)
        with conn:
            cursor = conn.execute(
                """INSERT INTO faces (photo_id, person_id, bbox_x, bbox_y, bbox_w, bbox_h, embedding, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (photo_id, person_id, bbox[0], bbox[1], bbox[2], bbox[3], embedding_blob, confidence)
            )
            return cursor.lastrowid
    
    @retry_on_lock()
    def update_face_person(self, face_id: int, person_id: int) -> None:
        """Assign a face to a person."""
        conn = self.connect()
        with conn:
            conn.execute(
                "UPDATE faces SET person_id = ? WHERE id = ?",
                (person_id, face_id)
            )
    
    @retry_on_lock()
    def get_faces_by_photo(self, photo_id: int) -> List[Face]:
        """Get all faces for a photo."""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT * FROM faces WHERE photo_id = ?",
            (photo_id,)
        )
        rows = cursor.fetchall()
        conn.commit()
        return [self._row_to_face(row) for row in rows]
    
    @retry_on_lock()
    def get_unique_persons_in_photo(self, photo_id: int) -> List[int]:
        """Get list of unique person IDs in a photo."""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT DISTINCT person_id FROM faces WHERE photo_id = ? AND person_id IS NOT NULL",
            (photo_id,)
        )
        rows = cursor.fetchall()
        conn.commit()
        return [row[0] for row in rows]
    
    def _row_to_face(self, row: sqlite3.Row) -> Face:
        """Convert database row to Face object."""
        return Face(
            id=row["id"],
            photo_id=row["photo_id"],
            person_id=row["person_id"],
            bbox_x=row["bbox_x"],
            bbox_y=row["bbox_y"],
            bbox_w=row["bbox_w"],
            bbox_h=row["bbox_h"],
            embedding=pickle.loads(row["embedding"]),
            confidence=row["confidence"],
        )
    
    # =========================================================================
    # Person Operations
    # =========================================================================
    
    @retry_on_lock()
    def create_person(self, name: str, centroid: np.ndarray) -> int:
        """Create a new person cluster."""
        conn = self.connect()
        centroid_blob = pickle.dumps(centroid)
        with conn:
            cursor = conn.execute(
                """INSERT INTO persons (name, centroid, face_count, created_at)
                   VALUES (?, ?, 1, ?)""",
                (name, centroid_blob, datetime.now())
            )
            return cursor.lastrowid
    
    @retry_on_lock()
    def update_person_centroid(self, person_id: int, centroid: np.ndarray, face_count: int) -> None:
        """Update person centroid and face count."""
        conn = self.connect()
        centroid_blob = pickle.dumps(centroid)
        with conn:
            conn.execute(
                "UPDATE persons SET centroid = ?, face_count = ? WHERE id = ?",
                (centroid_blob, face_count, person_id)
            )
    
    @retry_on_lock()
    def get_all_persons(self) -> List[Person]:
        """Get all person clusters."""
        conn = self.connect()
        cursor = conn.execute("SELECT * FROM persons ORDER BY id")
        rows = cursor.fetchall()
        conn.commit()
        return [self._row_to_person(row) for row in rows]
    
    @retry_on_lock()
    def get_person_by_id(self, person_id: int) -> Optional[Person]:
        """Get a person by ID."""
        conn = self.connect()
        cursor = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,))
        row = cursor.fetchone()
        conn.commit()
        return self._row_to_person(row) if row else None
    
    @retry_on_lock()
    def get_next_person_number(self) -> int:
        """Get the next available person number."""
        conn = self.connect()
        cursor = conn.execute("SELECT MAX(id) FROM persons")
        result = cursor.fetchone()[0]
        conn.commit()
        return (result or 0) + 1
    
    def _row_to_person(self, row: sqlite3.Row) -> Person:
        """Convert database row to Person object."""
        return Person(
            id=row["id"],
            name=row["name"],
            centroid=pickle.loads(row["centroid"]),
            face_count=row["face_count"],
            created_at=row["created_at"],
        )
    
    # =========================================================================
    # Enrollment Operations
    # =========================================================================
    
    @retry_on_lock()
    def create_enrollment(
        self,
        person_id: int,
        user_name: str,
        selfie_path: str,
        match_confidence: float,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        consent_given: bool = True
    ) -> int:
        """Create a new enrollment record linking a user to a person cluster."""
        conn = self.connect()
        with conn:
            cursor = conn.execute(
                """INSERT INTO enrollments 
                   (person_id, user_name, phone, email, selfie_path, match_confidence, consent_given, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (person_id, user_name, phone, email, selfie_path, match_confidence, consent_given, datetime.now())
            )
            return cursor.lastrowid
    
    @retry_on_lock()
    def get_enrollment_by_person(self, person_id: int) -> Optional[Enrollment]:
        """Get enrollment for a person if exists."""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT * FROM enrollments WHERE person_id = ?",
            (person_id,)
        )
        row = cursor.fetchone()
        conn.commit()
        return self._row_to_enrollment(row) if row else None
    
    @retry_on_lock()
    def get_all_enrollments(self) -> List[Enrollment]:
        """Get all enrollments."""
        conn = self.connect()
        cursor = conn.execute("SELECT * FROM enrollments ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.commit()
        return [self._row_to_enrollment(row) for row in rows]
    
    @retry_on_lock()
    def is_person_enrolled(self, person_id: int) -> bool:
        """Check if a person has been enrolled."""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT 1 FROM enrollments WHERE person_id = ?",
            (person_id,)
        )
        result = cursor.fetchone() is not None
        conn.commit()
        return result
    
    @retry_on_lock()
    def update_person_name(self, person_id: int, new_name: str) -> None:
        """Update the name of a person cluster."""
        conn = self.connect()
        with conn:
            conn.execute(
                "UPDATE persons SET name = ? WHERE id = ?",
                (new_name, person_id)
            )
    
    def _row_to_enrollment(self, row: sqlite3.Row) -> Enrollment:
        """Convert database row to Enrollment object."""
        return Enrollment(
            id=row["id"],
            person_id=row["person_id"],
            user_name=row["user_name"],
            phone=row["phone"],
            email=row["email"],
            selfie_path=row["selfie_path"],
            match_confidence=row["match_confidence"],
            consent_given=bool(row["consent_given"]),
            created_at=row["created_at"],
        )
    
    # =========================================================================
    # Upload Queue Operations
    # =========================================================================
    
    @retry_on_lock()
    def enqueue_upload(self, photo_id: int, local_path: str, relative_to: str) -> int:
        """Add a file to the upload queue."""
        conn = self.connect()
        with conn:
            cursor = conn.execute(
                """INSERT INTO upload_queue (photo_id, local_path, relative_to, status, created_at, updated_at)
                   VALUES (?, ?, ?, 'pending', ?, ?)""",
                (photo_id, local_path, relative_to, datetime.now(), datetime.now())
            )
            return cursor.lastrowid
    
    @retry_on_lock()
    def get_pending_uploads(self, limit: int = 10) -> List[dict]:
        """Get pending uploads from the queue."""
        conn = self.connect()
        cursor = conn.execute(
            """SELECT * FROM upload_queue 
               WHERE status = 'pending' 
               ORDER BY created_at 
               LIMIT ?""",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.commit()
        return [dict(row) for row in rows]
    
    @retry_on_lock()
    def update_upload_status(
        self, 
        upload_id: int, 
        status: str, 
        error: Optional[str] = None,
        increment_retry: bool = False
    ) -> None:
        """Update upload status."""
        conn = self.connect()
        with conn:
            if increment_retry:
                conn.execute(
                    """UPDATE upload_queue 
                       SET status = ?, last_error = ?, retry_count = retry_count + 1, updated_at = ?
                       WHERE id = ?""",
                    (status, error, datetime.now(), upload_id)
                )
            else:
                conn.execute(
                    """UPDATE upload_queue 
                       SET status = ?, last_error = ?, updated_at = ?
                       WHERE id = ?""",
                    (status, error, datetime.now(), upload_id)
                )
    
    @retry_on_lock()
    def get_failed_uploads(self, max_retries: int = 5) -> List[dict]:
        """Get failed uploads that haven't exceeded max retries."""
        conn = self.connect()
        cursor = conn.execute(
            """SELECT * FROM upload_queue 
               WHERE status = 'failed' AND retry_count < ?
               ORDER BY updated_at""",
            (max_retries,)
        )
        rows = cursor.fetchall()
        conn.commit()
        return [dict(row) for row in rows]
    
    @retry_on_lock()
    def get_upload_stats(self) -> dict:
        """Get upload queue statistics."""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT status, COUNT(*) FROM upload_queue GROUP BY status"
        )
        rows = cursor.fetchall()
        conn.commit()
        return dict(rows)
    
    @retry_on_lock()
    def get_upload_stats_unique(self) -> dict:
        """Get upload queue statistics counting unique photos vs total files."""
        conn = self.connect()
        stats = {}
        
        # Total file copies by status
        cursor = conn.execute(
            "SELECT status, COUNT(*) FROM upload_queue GROUP BY status"
        )
        stats['by_status'] = dict(cursor.fetchall())
        
        # Unique photos by status
        cursor = conn.execute(
            """SELECT status, COUNT(DISTINCT photo_id)
               FROM upload_queue GROUP BY status"""
        )
        stats['unique_by_status'] = dict(cursor.fetchall())
        
        conn.commit()
        return stats
    
    @retry_on_lock()
    def update_upload_paths(self, old_folder_name: str, new_folder_name: str) -> int:
        """
        Update local_path in pending/failed uploads when a person folder is renamed.
        
        Replaces occurrences of the old folder name with the new one in any
        uploads that haven't completed yet, so the uploader can find the files
        at their new location.
        
        Returns the number of rows updated.
        """
        conn = self.connect()
        with conn:
            cursor = conn.execute(
                """UPDATE upload_queue 
                   SET local_path = REPLACE(local_path, ?, ?), updated_at = ?
                   WHERE status IN ('pending', 'failed')
                     AND local_path LIKE ?""",
                (old_folder_name, new_folder_name, datetime.now(), f"%{old_folder_name}%")
            )
            return cursor.rowcount
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    @retry_on_lock()
    def get_stats(self) -> dict:
        """Get processing statistics."""
        conn = self.connect()
        stats = {}
        
        # Photo counts by status
        cursor = conn.execute(
            "SELECT status, COUNT(*) FROM photos GROUP BY status"
        )
        stats["photos_by_status"] = dict(cursor.fetchall())
        
        # Total faces and persons
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM faces")
            stats["total_faces"] = cursor.fetchone()[0]
        except (TypeError, IndexError):
            stats["total_faces"] = 0
        
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM persons")
            stats["total_persons"] = cursor.fetchone()[0]
        except (TypeError, IndexError):
            stats["total_persons"] = 0
        
        # Total enrollments
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM enrollments")
            stats["total_enrollments"] = cursor.fetchone()[0]
        except (TypeError, IndexError):
            stats["total_enrollments"] = 0
        
        conn.commit()
        return stats


# Global database instance
_db: Database | None = None


def get_db() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
        _db.initialize()
    return _db


def reset_db() -> None:
    """Reset the global database (useful for testing)."""
    global _db
    if _db:
        _db.close()
    _db = None
