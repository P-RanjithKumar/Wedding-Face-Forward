
import logging
import sys
import time
from pathlib import Path

# Add backend to path
backend_path = Path("backend").resolve()
sys.path.insert(0, str(backend_path))

from app.config import get_config
from app.cloud import get_cloud, CloudManager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

def wipe_folder_contents(cloud: CloudManager, folder_id: str):
    """
    Recursively deletes everything inside a folder. 
    If a folder cannot be deleted (e.g. permissions), it empties it and moves on.
    """
    logger.info(f"Scanning folder {folder_id}...")
    
    page_token = None
    while True:
        try:
            results = cloud.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page_token,
                pageSize=100
            ).execute()
        except Exception as e:
            logger.error(f"Error listing folder {folder_id}: {e}")
            break

        items = results.get('files', [])
        
        for item in items:
            delete_item(cloud, item)

        page_token = results.get('nextPageToken')
        if not page_token:
            break

def delete_item(cloud: CloudManager, item):
    """Try to trash an item. If it's a locked folder, empty it instead."""
    item_id = item['id']
    name = item['name']
    mime_type = item['mimeType']
    is_folder = (mime_type == 'application/vnd.google-apps.folder')

    try:
        logger.info(f"Trashing {name}...")
        cloud.service.files().update(
            fileId=item_id, 
            body={'trashed': True}
        ).execute()
        
    except Exception as e:
        # Check for permission errors
        if "insufficientFilePermissions" in str(e) or "403" in str(e):
            if is_folder:
                logger.warning(f"Permission denied deleting folder '{name}'. Clearing contents instead...")
                wipe_folder_contents(cloud, item_id)
                logger.info(f"Folder '{name}' cleared (but kept due to permissions).")
            else:
                logger.error(f"Cannot delete file '{name}' due to permissions: {e}")
        else:
            logger.error(f"Failed to delete '{name}': {e}")

def reupload_all_photos(config, cloud: CloudManager):
    """Walk through EventRoot/People and upload all photos."""
    people_dir = config.people_dir
    
    if not people_dir.exists():
        logger.warning(f"People directory not found: {people_dir}")
        return

    logger.info(f"Scanning {people_dir} for photos to upload...")
    
    count = 0
    errors = 0
    
    # Walk through the directory
    for file_path in people_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in config.supported_extensions:
            try:
                # Calculate relative path for correct folder structure
                success = cloud.upload_file(file_path, config.event_root)
                if success:
                    count += 1
                else:
                    errors += 1
            except Exception as e:
                logger.error(f"Failed to upload {file_path.name}: {e}")
                errors += 1

    logger.info(f"Upload complete! {count} files uploaded, {errors} errors.")

def main():
    print("=" * 60)
    print("CLOUD RESET AND RE-UPLOAD TOOL (V2)")
    print("=" * 60)
    
    config = get_config()
    cloud = get_cloud()
    
    if not cloud.is_enabled:
        print("X Cloud upload is not enabled.")
        return
        
    root_folder_id = config.drive_root_folder_id
    if not root_folder_id:
        print("X DRIVE_ROOT_FOLDER_ID is not set.")
        return

    print(f"Target Cloud Folder ID: {root_folder_id}")
    
    if config.dry_run:
         print("DRY RUN MODE ENABLED.")
    
    print("\nStarting in 3 seconds...")
    time.sleep(3)
    
    # 1. Clear Cloud
    print("\nStep 1: Clearing Cloud Folder...")
    if not config.dry_run:
        wipe_folder_contents(cloud, root_folder_id)
    else:
        print("[DRY RUN] Would wipe folder contents.")
        
    # 2. Reset internal cache
    cloud._folder_cache = {} 
    
    # 3. Re-upload
    print("\nStep 2: Re-uploading Organized Photos...")
    reupload_all_photos(config, cloud)
    
    print("\n" + "=" * 60)
    print("PROCESS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
