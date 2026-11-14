"""
Clustering module for AURA Phase 2 Backend (by DARK intelligence).

Implements incremental centroid-based clustering for face embeddings.
Assigns new faces to existing person clusters or creates new clusters.
"""

import logging
import pickle
import threading
from datetime import datetime
from typing import Optional, Tuple
import numpy as np

from .config import get_config
from .db import get_db, Person

logger = logging.getLogger(__name__)

# Serializes clustering between the worker's threads (they share one process).
# The database write transaction in assign_person / merge_persons also
# protects against other processes (e.g. the desktop app merging people).
_cluster_lock = threading.Lock()


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine distance between two vectors.
    Returns value in [0, 2], where 0 = identical, 2 = opposite.
    """
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    
    if a_norm == 0 or b_norm == 0:
        return 2.0  # Maximum distance for zero vectors
    
    similarity = np.dot(a, b) / (a_norm * b_norm)
    # Clamp to [-1, 1] to handle floating point errors
    similarity = np.clip(similarity, -1.0, 1.0)
    return 1.0 - similarity


def euclidean_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Euclidean distance between two vectors."""
    return float(np.linalg.norm(a - b))


def cosine_distances(embedding: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    """
    Cosine distance from one embedding to every row of `centroids` (N x D),
    in one matrix operation. Same values as cosine_distance(); zero vectors
    get the maximum distance 2.0.
    """
    centroids = np.asarray(centroids, dtype=np.float64)
    embedding = np.asarray(embedding, dtype=np.float64)
    e_norm = np.linalg.norm(embedding)
    c_norms = np.linalg.norm(centroids, axis=1)
    distances = np.full(len(centroids), 2.0)
    if e_norm == 0:
        return distances
    valid = c_norms > 0
    similarity = (centroids[valid] @ embedding) / (c_norms[valid] * e_norm)
    distances[valid] = 1.0 - np.clip(similarity, -1.0, 1.0)
    return distances


def find_nearest_person(
    embedding: np.ndarray,
    persons: list[Person]
) -> Tuple[Optional[Person], float]:
    """
    Find the nearest person cluster to a given embedding.
    Returns (person, distance) or (None, inf) if no persons exist.
    On ties the first person in the list wins (same as before).
    """
    if not persons:
        return None, float("inf")

    distances = cosine_distances(embedding, np.stack([p.centroid for p in persons]))
    idx = int(np.argmin(distances))
    return persons[idx], float(distances[idx])


def update_centroid(
    old_centroid: np.ndarray,
    new_embedding: np.ndarray,
    old_count: int
) -> np.ndarray:
    """
    Update a centroid with a new embedding using running average.
    """
    # New centroid = (old_centroid * old_count + new_embedding) / (old_count + 1)
    new_centroid = (old_centroid * old_count + new_embedding) / (old_count + 1)
    # Normalize to unit length for cosine similarity
    norm = np.linalg.norm(new_centroid)
    if norm > 0:
        new_centroid = new_centroid / norm
    return new_centroid


def assign_person(
    embedding: np.ndarray,
    threshold: Optional[float] = None,
    face_id: Optional[int] = None,
) -> int:
    """
    Assign an embedding to a person cluster.

    1. Load all existing person centroids from database
    2. Compute cosine distance to each centroid
    3. If min_distance < threshold: assign to that person, update centroid
    4. Else: create new person with this embedding as centroid
    5. If face_id is given, link that face to the person
    6. Return person_id

    Steps 1-5 run as ONE atomic step (thread lock + database write
    transaction). Before 2026-11-14 they did not: worker threads processing
    two photos of the same new guest at the same time could both see "no
    match" and create two people, create two people with the same
    Person_NNN name, or overwrite each other's centroid/face_count updates.

    Args:
        embedding: 512-dimensional face embedding
        threshold: Maximum distance to consider a match (default from config)
        face_id: Optional face row to link to the chosen person in the same
                 transaction

    Returns:
        person_id of assigned (existing or new) person
    """
    config = get_config()
    db = get_db()

    if threshold is None:
        threshold = config.cluster_threshold

    # Normalize embedding
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    with _cluster_lock, db.write_transaction() as conn:
        rows = conn.execute(
            "SELECT id, centroid, face_count FROM persons ORDER BY id"
        ).fetchall()

        best_idx, distance = None, float("inf")
        if rows:
            centroids = [pickle.loads(r["centroid"]) for r in rows]
            distances = cosine_distances(embedding, np.stack(centroids))
            best_idx = int(np.argmin(distances))
            distance = float(distances[best_idx])

        if best_idx is not None and distance < threshold:
            # Assign to existing person and update its centroid
            row = rows[best_idx]
            person_id = row["id"]
            new_centroid = update_centroid(centroids[best_idx], embedding, row["face_count"])
            conn.execute(
                "UPDATE persons SET centroid = ?, face_count = ? WHERE id = ?",
                (pickle.dumps(new_centroid), row["face_count"] + 1, person_id),
            )
            logger.debug(f"Matched to Person_{person_id:03d} (distance: {distance:.3f})")
        else:
            # Create new person (name number = MAX(id) + 1, as before)
            max_id = conn.execute("SELECT MAX(id) FROM persons").fetchone()[0]
            person_name = f"Person_{(max_id or 0) + 1:03d}"
            cursor = conn.execute(
                "INSERT INTO persons (name, centroid, face_count, created_at) VALUES (?, ?, 1, ?)",
                (person_name, pickle.dumps(embedding), datetime.now()),
            )
            person_id = cursor.lastrowid
            logger.info(f"Created new person: {person_name} (ID: {person_id})")

        if face_id is not None:
            conn.execute("UPDATE faces SET person_id = ? WHERE id = ?", (person_id, face_id))

    return person_id


def cluster_faces(
    face_ids_and_embeddings: list[Tuple[int, np.ndarray]],
    threshold: Optional[float] = None
) -> dict[int, int]:
    """
    Cluster multiple faces from a single photo.
    
    Args:
        face_ids_and_embeddings: List of (face_id, embedding) tuples
        threshold: Maximum distance for matching
    
    Returns:
        Dictionary mapping face_id -> person_id
    """
    assignments = {}
    
    for face_id, embedding in face_ids_and_embeddings:
        # Links the face to the person in the same atomic step
        assignments[face_id] = assign_person(embedding, threshold, face_id=face_id)
    
    return assignments


def get_cluster_stats() -> dict:
    """Get statistics about the current clusters."""
    db = get_db()
    persons = db.get_all_persons()
    
    if not persons:
        return {
            "total_persons": 0,
            "total_faces": 0,
            "avg_faces_per_person": 0,
            "min_faces": 0,
            "max_faces": 0,
        }
    
    face_counts = [p.face_count for p in persons]
    
    return {
        "total_persons": len(persons),
        "total_faces": sum(face_counts),
        "avg_faces_per_person": sum(face_counts) / len(persons),
        "min_faces": min(face_counts),
        "max_faces": max(face_counts),
    }


def merge_persons(person_id_keep: int, person_id_remove: int) -> bool:
    """
    Merge two person clusters into one.
    All faces AND guest enrollments of person_id_remove move to
    person_id_keep, then person_id_remove is deleted. One atomic step: it
    fully happens or not at all.

    Before 2026-11-14 this ran as separate auto-committed statements and did
    not move enrollments, so merging a person that a guest had enrolled as
    failed on the foreign key AFTER the faces had already moved (half-merged).

    Only the database changes here. Moving the photo folders on disk is done
    by the caller (aura_app/widgets/merge_dialog.py).
    """
    if person_id_keep == person_id_remove:
        logger.error("Cannot merge a person into itself")
        return False

    db = get_db()

    with _cluster_lock, db.write_transaction() as conn:
        rows = {
            r["id"]: r for r in conn.execute(
                "SELECT id, centroid, face_count FROM persons WHERE id IN (?, ?)",
                (person_id_keep, person_id_remove),
            ).fetchall()
        }
        if person_id_keep not in rows or person_id_remove not in rows:
            logger.error(f"Cannot merge: person {person_id_keep} or {person_id_remove} not found")
            return False

        keep, remove = rows[person_id_keep], rows[person_id_remove]
        keep_centroid = pickle.loads(keep["centroid"])
        remove_centroid = pickle.loads(remove["centroid"])

        # Combine centroids (weighted by face count)
        total_count = keep["face_count"] + remove["face_count"]
        new_centroid = (
            keep_centroid * keep["face_count"] + remove_centroid * remove["face_count"]
        ) / max(total_count, 1)
        norm = np.linalg.norm(new_centroid)
        if norm > 0:
            new_centroid = new_centroid / norm

        conn.execute(
            "UPDATE persons SET centroid = ?, face_count = ? WHERE id = ?",
            (pickle.dumps(new_centroid), total_count, person_id_keep),
        )
        conn.execute("UPDATE faces SET person_id = ? WHERE person_id = ?",
                     (person_id_keep, person_id_remove))
        conn.execute("UPDATE enrollments SET person_id = ? WHERE person_id = ?",
                     (person_id_keep, person_id_remove))
        conn.execute("DELETE FROM persons WHERE id = ?", (person_id_remove,))

    logger.info(
        f"Merged Person_{person_id_remove:03d} into Person_{person_id_keep:03d} "
        f"(total faces: {total_count})"
    )
    return True
