"""
Router module for Wedding Face Forward Phase 2 Backend.

Routes processed photos to the appropriate folders:
- Solo: Photos with exactly 1 person
- Group: Photos with 2+ persons (copied to each person's folder)
- NoFaces: Photos with no detected faces
- Errors: Failed/corrupt files
"""

import logging
import os
import shutil
from pathlib import Path
from typing import List, Set, Tuple

from .config import get_config
from .db import get_db

logger = logging.getLogger(__name__)


def ensure_person_folders(person_id: int, config=None) -> tuple[Path, Path]:
    """
    Ensure Solo and Group folders exist for a person.
    Uses the person's name from the database (could be human name if enrolled).
    Returns (solo_path, group_path).
    
    Also creates the folder structure in Google Cloud Drive immediately for real-time sync.
    """
    from .db import get_db
    from .cloud import get_cloud
    
    config = config or get_config()
    db = get_db()
    
    # Get person's actual name from database
    person = db.get_person_by_id(person_id)
    if person:
        person_folder_name = person.name
    else:
        # Fallback if person not found (shouldn't happen)
        person_folder_name = f"Person_{person_id:03d}"
    
    person_dir = config.people_dir / person_folder_name
    solo_dir = person_dir / "Solo"
    group_dir = person_dir / "Group"
    
    # Create local folders
    solo_dir.mkdir(parents=True, exist_ok=True)
    group_dir.mkdir(parents=True, exist_ok=True)
    
    # CLOUD SYNC: Create cloud folder structure in background thread
    # This MUST be non-blocking to prevent SSL/network errors from stalling
    # the photo processing workers. Cloud folder creation involves network
    # calls with retries that can take 30-60+ seconds on SSL failures.
    import threading
    
    cloud = get_cloud()
    if cloud.is_enabled and not config.dry_run:
        def _create_cloud_folders():
            try:
                cloud.ensure_folder_path(["People", person_folder_name, "Solo"])
                cloud.ensure_folder_path(["People", person_folder_name, "Group"])
                logger.debug(f"Cloud folders created for: {person_folder_name}")
            except Exception as e:
                logger.warning(f"Failed to create cloud folders for {person_folder_name}: {e}")
        
        threading.Thread(
            target=_create_cloud_folders,
            daemon=True,
            name=f"CloudFolders-{person_folder_name}"
        ).start()
    
    return solo_dir, group_dir


def copy_or_link(src: Path, dst: Path, use_hardlinks: bool = True, dry_run: bool = False) -> bool:
    """
    Copy or hardlink a file to destination.
    
    Args:
        src: Source file path
        dst: Destination file path
        use_hardlinks: Try to use hardlinks (saves disk space)
        dry_run: If True, only log what would happen
    
    Returns:
        True on success
    """
    try:
        if dry_run:
            logger.info(f"[DRY RUN] Would copy: {src} -> {dst}")
            return True
        
        # Ensure destination directory exists
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # Skip if destination already exists
        if dst.exists():
            logger.debug(f"Destination already exists: {dst}")
            return True
        
        if use_hardlinks:
            try:
                # Try hardlink first (Windows NTFS supports this)
                os.link(src, dst)
                logger.debug(f"Hardlinked: {src} -> {dst}")
                return True
            except OSError:
                # Fall back to copy if hardlink fails
                pass
        
        # Regular copy
        shutil.copy2(src, dst)
        logger.debug(f"Copied: {src} -> {dst}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to copy/link {src} -> {dst}: {e}")
        return False


def move_to_folder(src: Path, dst_folder: Path, dry_run: bool = False) -> bool:
    """Move a file to a destination folder."""
    try:
        dst = dst_folder / src.name
        
        if dry_run:
            logger.info(f"[DRY RUN] Would move: {src} -> {dst}")
            return True
        
        dst_folder.mkdir(parents=True, exist_ok=True)
        
        # Handle duplicate names
        if dst.exists():
            base = src.stem
            ext = src.suffix
            counter = 1
            while dst.exists():
                dst = dst_folder / f"{base}_{counter}{ext}"
                counter += 1
        
        shutil.move(str(src), str(dst))
        logger.debug(f"Moved: {src} -> {dst}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to move {src} -> {dst_folder}: {e}")
        return False


def route_photo(
    photo_id: int,
    processed_path: Path,
    person_ids: List[int],
    config=None
) -> bool:
    """
    Route a processed photo to the appropriate person folders.
    
    Args:
        photo_id: Database photo ID
        processed_path: Path to the processed JPEG
        person_ids: List of unique person IDs detected in the photo
        config: Configuration (uses global if None)
    
    Returns:
        List of paths to the routed files (empty if failed or no faces).
    """
    config = config or get_config()
    unique_persons: Set[int] = set(person_ids)
    routed_paths: List[Path] = []
    
    if len(unique_persons) == 0:
        # No faces - move to NoFaces folder
        if move_to_folder(processed_path, config.no_faces_dir, config.dry_run):
            # We don't necessarily need to upload "NoFaces" to the cloud structure defined for people, 
            # but if we wanted to, we'd add it here. For now, let's skip "NoFaces" upload or handle it if needed.
            # The prompt says "upload all the photos to cloud(same like now, with folders and sub folders)".
            # "NoFaces" is in Admin/NoFaces.
            pass
        return []
    
    if len(unique_persons) == 1:
        # Solo photo - one person
        person_id = list(unique_persons)[0]
        solo_dir, _ = ensure_person_folders(person_id, config)
        dst = solo_dir / f"{photo_id:06d}.jpg"
        if copy_or_link(
            processed_path, dst,
            use_hardlinks=config.use_hardlinks,
            dry_run=config.dry_run
        ):
            routed_paths.append(dst)
    else:
        # Group photo - multiple persons
        for person_id in unique_persons:
            _, group_dir = ensure_person_folders(person_id, config)
            dst = group_dir / f"{photo_id:06d}.jpg"
            if copy_or_link(
                processed_path, dst,
                use_hardlinks=config.use_hardlinks,
                dry_run=config.dry_run
            ):
                routed_paths.append(dst)
        
        if len(routed_paths) == len(unique_persons):
             logger.debug(
                f"Photo {photo_id} routed to {len(unique_persons)} persons' Group folders"
            )

    return routed_paths


def route_to_errors(
    original_path: Path,
    config=None
) -> bool:
    """Move a file to the Errors folder."""
    config = config or get_config()
    return move_to_folder(original_path, config.errors_dir, config.dry_run)


def route_to_no_faces(
    processed_path: Path,
    config=None
) -> bool:
    """Copy a file to the NoFaces folder."""
    config = config or get_config()
    return copy_or_link(
        processed_path,
        config.no_faces_dir / processed_path.name,
        use_hardlinks=config.use_hardlinks,
        dry_run=config.dry_run
    )


def get_routing_summary(config=None) -> dict:
    """Get summary of files in each routing destination."""
    config = config or get_config()
    summary = {
        "processed_count": 0,
        "no_faces_count": 0,
        "errors_count": 0,
        "persons": {},
    }
    
    # Count processed files
    if config.processed_dir.exists():
        summary["processed_count"] = len([
            f for f in config.processed_dir.iterdir()
            if f.is_file() and not f.stem.endswith("_thumb")
        ])
    
    # Count no faces
    if config.no_faces_dir.exists():
        summary["no_faces_count"] = len(list(config.no_faces_dir.iterdir()))
    
    # Count errors
    if config.errors_dir.exists():
        summary["errors_count"] = len(list(config.errors_dir.iterdir()))
    
    # Count per person (includes both Person_XXX and enrolled human names)
    if config.people_dir.exists():
        for person_dir in config.people_dir.iterdir():
            if person_dir.is_dir():
                solo_count = 0
                group_count = 0
                
                solo_dir = person_dir / "Solo"
                group_dir = person_dir / "Group"
                
                if solo_dir.exists():
                    solo_count = len(list(solo_dir.iterdir()))
                if group_dir.exists():
                    group_count = len(list(group_dir.iterdir()))
                
                # Check if this person is enrolled
                is_enrolled = not person_dir.name.startswith("Person_")
                
                summary["persons"][person_dir.name] = {
                    "solo": solo_count,
                    "group": group_count,
                    "enrolled": is_enrolled,
                }
    
    return summary
