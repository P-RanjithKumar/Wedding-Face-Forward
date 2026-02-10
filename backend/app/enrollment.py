"""
Enrollment module for Wedding Face Forward Phase 2 Backend.

Handles user enrollment via selfie:
1. Accept selfie + user info (name, phone, email)
2. Extract face embedding from selfie
3. Match to best existing person cluster
4. Link user to the cluster and rename folder
5. Save selfie as reference image in folder
"""

import logging
import shutil
import re
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

import numpy as np
from PIL import Image

from .config import get_config
from .db import get_db, Person
from .cluster import cosine_distance, find_nearest_person
from .processor import detect_faces, fix_orientation

logger = logging.getLogger(__name__)


@dataclass
class EnrollmentResult:
    """Result of an enrollment attempt."""
    success: bool
    person_id: Optional[int]
    person_name: Optional[str]
    match_confidence: float
    message: str
    solo_folder: Optional[Path] = None
    group_folder: Optional[Path] = None


def sanitize_folder_name(name: str) -> str:
    """
    Convert a user name to a safe folder name.
    Example: "John Doe" -> "John_Doe"
    """
    # Remove any characters that are not alphanumeric, space, or hyphen
    clean = re.sub(r'[^\w\s-]', '', name)
    # Replace spaces with underscores
    clean = re.sub(r'\s+', '_', clean.strip())
    # Limit length
    return clean[:50] if clean else "Unknown"


def generate_unique_folder_name(base_name: str, person_id: int, config=None) -> str:
    """
    Generate a unique folder name, appending ID if name already exists.
    Example: "John_Doe" or "John_Doe_142" if John_Doe exists
    """
    config = config or get_config()
    people_dir = config.people_dir
    
    # Try the base name first
    if not (people_dir / base_name).exists():
        return base_name
    
    # If exists, append person_id to make unique
    return f"{base_name}_{person_id}"


def rename_person_folder(
    person_id: int, 
    new_name: str,
    config=None
) -> Tuple[bool, Optional[Path], Optional[Path]]:
    """
    Rename a person's folder from Person_XXX to the new name.
    
    Also renames the folder in Google Cloud Drive and updates
    any pending upload queue entries to use the new path.
    
    Returns:
        (success, new_solo_path, new_group_path)
    """
    from .cloud import get_cloud
    
    config = config or get_config()
    db = get_db()
    
    # Get current folder name from database
    person = db.get_person_by_id(person_id)
    if person is None:
        logger.error(f"Person {person_id} not found in database")
        return False, None, None
    
    old_folder_name = person.name
    old_folder_path = config.people_dir / old_folder_name
    
    # Generate safe folder name
    safe_name = sanitize_folder_name(new_name)
    unique_name = generate_unique_folder_name(safe_name, person_id, config)
    new_folder_path = config.people_dir / unique_name
    
    try:
        if old_folder_path.exists():
            # Rename the existing folder
            shutil.move(str(old_folder_path), str(new_folder_path))
            logger.info(f"Renamed folder: {old_folder_name} -> {unique_name}")
        else:
            # Create new folder structure if it doesn't exist
            (new_folder_path / "Solo").mkdir(parents=True, exist_ok=True)
            (new_folder_path / "Group").mkdir(parents=True, exist_ok=True)
            logger.info(f"Created folder: {unique_name}")
        
        # Update person name in database
        db.update_person_name(person_id, unique_name)
        
        # ---- CLOUD SYNC: Rename folder in Google Drive ----
        cloud = get_cloud()
        if cloud.is_enabled and not config.dry_run:
            try:
                # Find the "People" parent folder in Drive
                people_folder_id = cloud.ensure_folder_path(["People"])
                
                # Rename the person folder inside People/
                renamed = cloud.rename_folder(old_folder_name, unique_name, parent_id=people_folder_id)
                
                if renamed:
                    logger.info(f"Cloud folder renamed: {old_folder_name} -> {unique_name}")
                else:
                    # Folder didn't exist in cloud yet — create it fresh
                    logger.info(f"Cloud folder '{old_folder_name}' not found, creating '{unique_name}' instead")
                    cloud.ensure_folder_path(["People", unique_name, "Solo"])
                    cloud.ensure_folder_path(["People", unique_name, "Group"])
            except Exception as cloud_err:
                # Don't fail the whole operation if cloud sync fails
                logger.warning(f"Cloud rename failed for {old_folder_name} -> {unique_name}: {cloud_err}")
        
        # ---- FIX PENDING UPLOADS: Update paths in upload queue ----
        try:
            updated_count = db.update_upload_paths(old_folder_name, unique_name)
            if updated_count > 0:
                logger.info(f"Updated {updated_count} pending upload paths: {old_folder_name} -> {unique_name}")
        except Exception as db_err:
            logger.warning(f"Failed to update upload paths: {db_err}")
        
        solo_path = new_folder_path / "Solo"
        group_path = new_folder_path / "Group"
        
        return True, solo_path, group_path
        
    except Exception as e:
        logger.error(f"Failed to rename folder {old_folder_name} -> {unique_name}: {e}")
        return False, None, None


def save_reference_selfie(
    selfie_path: Path,
    person_folder: Path,
    filename: str = "00_REFERENCE_SELFIE.jpg"
) -> Optional[Path]:
    """
    Save the enrollment selfie as the reference image in the person's folder.
    The '00_' prefix ensures it appears first in file explorers.
    
    Returns the path where the selfie was saved, or None on failure.
    """
    try:
        dest_path = person_folder / filename
        
        # Open, fix orientation, and save
        img = Image.open(selfie_path)
        img = fix_orientation(img)
        
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Resize to reasonable size if needed
        max_size = 800
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        img.save(dest_path, "JPEG", quality=95)
        logger.info(f"Saved reference selfie: {dest_path}")
        return dest_path
        
    except Exception as e:
        logger.error(f"Failed to save reference selfie: {e}")
        return None


def enroll_user(
    selfie_path: Path,
    user_name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    consent_given: bool = True,
    match_threshold: Optional[float] = None,
    config=None
) -> EnrollmentResult:
    """
    Complete enrollment flow:
    1. Detect face in selfie and extract embedding
    2. Find best matching person cluster
    3. Create enrollment record
    4. Rename person folder to user's name
    5. Save selfie as reference image
    
    Args:
        selfie_path: Path to the user's selfie image
        user_name: User's display name
        phone: Optional phone number
        email: Optional email address
        consent_given: Whether user consented to data usage
        match_threshold: Maximum distance for a valid match (default from config)
        config: Configuration (uses global if None)
    
    Returns:
        EnrollmentResult with success status and details
    """
    config = config or get_config()
    db = get_db()
    
    if match_threshold is None:
        match_threshold = config.cluster_threshold
    
    selfie_path = Path(selfie_path)
    
    # Validate input
    if not selfie_path.exists():
        return EnrollmentResult(
            success=False,
            person_id=None,
            person_name=None,
            match_confidence=0.0,
            message=f"Selfie file not found: {selfie_path}"
        )
    
    if not user_name or not user_name.strip():
        return EnrollmentResult(
            success=False,
            person_id=None,
            person_name=None,
            match_confidence=0.0,
            message="User name is required"
        )
    
    # Step 1: Detect face in selfie
    logger.info(f"Processing enrollment selfie for: {user_name}")
    faces = detect_faces(selfie_path)
    
    if not faces:
        return EnrollmentResult(
            success=False,
            person_id=None,
            person_name=None,
            match_confidence=0.0,
            message="No face detected in selfie. Please upload a clear photo of your face."
        )
    
    if len(faces) > 1:
        logger.warning(f"Multiple faces detected in selfie, using the most confident one")
    
    # Use the face with highest confidence
    best_face = max(faces, key=lambda f: f.confidence)
    selfie_embedding = best_face.embedding
    
    # Normalize embedding
    norm = np.linalg.norm(selfie_embedding)
    if norm > 0:
        selfie_embedding = selfie_embedding / norm
    
    # Step 2: Find best matching person cluster
    persons = db.get_all_persons()
    
    if not persons:
        return EnrollmentResult(
            success=False,
            person_id=None,
            person_name=None,
            match_confidence=0.0,
            message="No photos have been processed yet. Please wait for event photos to be uploaded."
        )
    
    nearest_person, distance = find_nearest_person(selfie_embedding, persons)
    
    if nearest_person is None or distance >= match_threshold:
        # No good match found
        confidence = 1.0 - distance if nearest_person else 0.0
        return EnrollmentResult(
            success=False,
            person_id=None,
            person_name=None,
            match_confidence=confidence,
            message=f"Could not find a confident match for your face. Best match confidence: {confidence:.1%}"
        )
    
    # Check if this person is already enrolled
    if db.is_person_enrolled(nearest_person.id):
        existing = db.get_enrollment_by_person(nearest_person.id)
        return EnrollmentResult(
            success=False,
            person_id=nearest_person.id,
            person_name=nearest_person.name,
            match_confidence=1.0 - distance,
            message=f"This face cluster is already enrolled under: {existing.user_name}"
        )
    
    match_confidence = 1.0 - distance  # Convert distance to confidence (0-1)
    logger.info(f"Matched to {nearest_person.name} with confidence {match_confidence:.1%}")
    
    # Step 3: Rename folder to user's name
    success, solo_path, group_path = rename_person_folder(
        nearest_person.id, 
        user_name,
        config
    )
    
    if not success:
        return EnrollmentResult(
            success=False,
            person_id=nearest_person.id,
            person_name=nearest_person.name,
            match_confidence=match_confidence,
            message="Failed to rename person folder"
        )
    
    # Get updated person name (folder name)
    updated_person = db.get_person_by_id(nearest_person.id)
    folder_name = updated_person.name if updated_person else user_name
    
    # Step 4: Save reference selfie in the person's folder
    person_folder = config.people_dir / folder_name
    saved_selfie_path = save_reference_selfie(selfie_path, person_folder)
    
    # Step 5: Create enrollment record
    enrollment_id = db.create_enrollment(
        person_id=nearest_person.id,
        user_name=user_name,
        selfie_path=str(saved_selfie_path or selfie_path),
        match_confidence=match_confidence,
        phone=phone,
        email=email,
        consent_given=consent_given
    )
    
    logger.info(f"Enrollment complete! ID: {enrollment_id}, Person: {folder_name}")
    
    return EnrollmentResult(
        success=True,
        person_id=nearest_person.id,
        person_name=folder_name,
        match_confidence=match_confidence,
        message=f"Successfully enrolled! Your photos are in: {folder_name}",
        solo_folder=solo_path,
        group_folder=group_path
    )


def get_enrollment_status() -> dict:
    """Get summary of enrollment status."""
    db = get_db()
    config = get_config()
    
    persons = db.get_all_persons()
    enrollments = db.get_all_enrollments()
    
    enrolled_ids = {e.person_id for e in enrollments}
    
    return {
        "total_persons": len(persons),
        "total_enrolled": len(enrollments),
        "pending_enrollment": len([p for p in persons if p.id not in enrolled_ids]),
        "enrollments": [
            {
                "id": e.id,
                "person_id": e.person_id,
                "user_name": e.user_name,
                "phone": e.phone,
                "email": e.email,
                "confidence": f"{e.match_confidence:.1%}",
                "enrolled_at": str(e.created_at)
            }
            for e in enrollments
        ]
    }
