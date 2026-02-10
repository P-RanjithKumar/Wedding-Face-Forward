import sys
from pathlib import Path

sys.path.insert(0, 'backend')

from app.config import get_config
from app.db import get_db
from app.router import route_photo

config = get_config()
db = get_db()

# Try to route photo 44 manually
photo_id = 44
processed_path = Path("EventRoot/Processed/000044.jpg")

# Get the person IDs for this photo
person_ids = db.get_unique_persons_in_photo(photo_id)
print(f"Photo {photo_id}: {len(person_ids)} unique persons: {person_ids}")

# Try routing
print(f"\nAttempting to route photo {photo_id}...")
try:
    routed_paths = route_photo(photo_id, processed_path, person_ids, config)
    print(f"Success! Routed to {len(routed_paths)} paths:")
    for path in routed_paths:
        print(f"  - {path}")
    
    # Update database status
    if routed_paths:
        db.update_photo_status(photo_id, "completed")
        print(f"\nUpdated photo {photo_id} status to 'completed'")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
