"""
Clustering module for Wedding Face Forward Phase 2 Backend.

Implements incremental centroid-based clustering for face embeddings.
Assigns new faces to existing person clusters or creates new clusters.
"""

import logging
from typing import Optional, Tuple
import numpy as np

from .config import get_config
from .db import get_db, Person

logger = logging.getLogger(__name__)


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


def find_nearest_person(
    embedding: np.ndarray,
    persons: list[Person]
) -> Tuple[Optional[Person], float]:
    """
    Find the nearest person cluster to a given embedding.
    Returns (person, distance) or (None, inf) if no persons exist.
    """
    if not persons:
        return None, float("inf")
    
    min_distance = float("inf")
    nearest_person = None
    
    for person in persons:
        distance = cosine_distance(embedding, person.centroid)
        if distance < min_distance:
            min_distance = distance
            nearest_person = person
    
    return nearest_person, min_distance


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
    threshold: Optional[float] = None
) -> int:
    """
    Assign an embedding to a person cluster.
    
    1. Load all existing person centroids from database
    2. Compute cosine distance to each centroid
    3. If min_distance < threshold: assign to that person, update centroid
    4. Else: create new person with this embedding as centroid
    5. Return person_id
    
    Args:
        embedding: 512-dimensional face embedding
        threshold: Maximum distance to consider a match (default from config)
    
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
    
    # Get all existing persons
    persons = db.get_all_persons()
    
    # Find nearest person
    nearest_person, distance = find_nearest_person(embedding, persons)
    
    if nearest_person is not None and distance < threshold:
        # Assign to existing person
        logger.debug(
            f"Matched to Person_{nearest_person.id:03d} (distance: {distance:.3f})"
        )
        
        # Update centroid
        new_centroid = update_centroid(
            nearest_person.centroid,
            embedding,
            nearest_person.face_count
        )
        new_count = nearest_person.face_count + 1
        db.update_person_centroid(nearest_person.id, new_centroid, new_count)
        
        return nearest_person.id
    else:
        # Create new person
        next_num = db.get_next_person_number()
        person_name = f"Person_{next_num:03d}"
        
        person_id = db.create_person(person_name, embedding)
        logger.info(f"Created new person: {person_name} (ID: {person_id})")
        
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
    db = get_db()
    assignments = {}
    
    for face_id, embedding in face_ids_and_embeddings:
        person_id = assign_person(embedding, threshold)
        assignments[face_id] = person_id
        
        # Update face record with person assignment
        db.update_face_person(face_id, person_id)
    
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
    All faces from person_id_remove are reassigned to person_id_keep.
    
    This is useful for manual correction of clustering errors.
    """
    db = get_db()
    
    person_keep = db.get_person_by_id(person_id_keep)
    person_remove = db.get_person_by_id(person_id_remove)
    
    if person_keep is None or person_remove is None:
        logger.error(f"Cannot merge: person {person_id_keep} or {person_id_remove} not found")
        return False
    
    # Combine centroids (weighted by face count)
    total_count = person_keep.face_count + person_remove.face_count
    new_centroid = (
        person_keep.centroid * person_keep.face_count +
        person_remove.centroid * person_remove.face_count
    ) / total_count
    
    # Normalize
    norm = np.linalg.norm(new_centroid)
    if norm > 0:
        new_centroid = new_centroid / norm
    
    # Update the kept person
    db.update_person_centroid(person_id_keep, new_centroid, total_count)
    
    # Reassign all faces from removed person
    conn = db.connect()
    conn.execute(
        "UPDATE faces SET person_id = ? WHERE person_id = ?",
        (person_id_keep, person_id_remove)
    )
    conn.execute("DELETE FROM persons WHERE id = ?", (person_id_remove,))
    conn.commit()
    
    logger.info(
        f"Merged Person_{person_id_remove:03d} into Person_{person_id_keep:03d} "
        f"(total faces: {total_count})"
    )
    return True
