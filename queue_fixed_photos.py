import sys
from pathlib import Path

sys.path.insert(0, 'backend')

from app.config import get_config
from app.db import get_db
from app.upload_queue import get_upload_queue

config = get_config()
db = get_db()

# Get photos that were manually fixed (44, 46, 47)
photo_ids = [44, 46, 47]

print("=== Adding manually fixed photos to upload queue ===\n")

for photo_id in photo_ids:
    # Get person folders for this photo
    person_ids = db.get_unique_persons_in_photo(photo_id)
    
    if not person_ids:
        print(f"Photo {photo_id}: No persons found, skipping")
        continue
    
    # Find the routed files
    routed_files = []
    for person_id in person_ids:
        person = db.get_person_by_id(person_id)
        if not person:
            continue
        
        person_folder = config.people_dir / person.name
        solo_file = person_folder / "Solo" / f"{photo_id:06d}.jpg"
        group_file = person_folder / "Group" / f"{photo_id:06d}.jpg"
        
        if solo_file.exists():
            routed_files.append(solo_file)
        if group_file.exists():
            routed_files.append(group_file)
    
    if routed_files:
        print(f"Photo {photo_id}: Found {len(routed_files)} routed files")
        upload_queue = get_upload_queue()
        for file_path in routed_files:
            upload_queue.enqueue(photo_id, file_path, config.event_root)
            print(f"  Queued: {file_path.relative_to(config.event_root)}")
    else:
        print(f"Photo {photo_id}: No routed files found")

print("\nDone! Files added to upload queue.")
