import sys
from pathlib import Path

sys.path.insert(0, 'backend')

from app.config import get_config
from app.db import get_db
from app.router import route_photo

config = get_config()
db = get_db()

# Get all photos stuck in "processing" status
conn = db.connect()
cursor = conn.execute("SELECT id, original_path FROM photos WHERE status = 'processing' ORDER BY id")
stuck_photos = cursor.fetchall()

print(f"Found {len(stuck_photos)} photos stuck in 'processing' status\n")

for row in stuck_photos:
    photo_id = row[0]
    original_path = row[1]
    
    # Find the processed file
    processed_path = config.processed_dir / f"{photo_id:06d}.jpg"
    
    if not processed_path.exists():
        print(f"Photo {photo_id}: Processed file not found at {processed_path}")
        continue
    
    # Get person IDs
    person_ids = db.get_unique_persons_in_photo(photo_id)
    
    print(f"Photo {photo_id} ({Path(original_path).name}): {len(person_ids)} persons")
    
    try:
        routed_paths = route_photo(photo_id, processed_path, person_ids, config)
        if routed_paths:
            db.update_photo_status(photo_id, "completed")
            print(f"  [OK] Routed to {len(routed_paths)} locations and marked completed")
        else:
            print(f"  [FAIL] Routing returned no paths")
    except Exception as e:
        print(f"  [ERROR] {e}")

print("\nDone!")
