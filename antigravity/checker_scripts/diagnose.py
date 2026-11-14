import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path("backend").resolve()
sys.path.insert(0, str(backend_path))

try:
    from app.config import get_config
    from app.db import get_db
    from app.cloud import get_cloud

    config = get_config()
    db = get_db()
    cloud = get_cloud()

    print(f"--- System Diagnostics ---")
    print(f"CWD: {os.getcwd()}")
    print(f"EVENT_ROOT: {config.event_root}")
    print(f"DB_PATH: {config.db_path}")
    print(f"INCOMING_DIR: {config.incoming_dir} (Exists: {config.incoming_dir.exists()})")
    print(f"GOOGLE_CREDS: {config.google_credentials_file} (Exists: {config.google_credentials_file.exists()})")
    print(f"CLOUD_ENABLED: {cloud.is_enabled}")
    
    stats = db.get_stats()
    print(f"DB Stats: {stats}")
    
    # Check for pending photos
    pending = db.get_pending_photos()
    print(f"Pending photos in DB: {len(pending)}")
    
    if config.incoming_dir.exists():
        files = list(config.incoming_dir.iterdir())
        print(f"Files in Incoming: {len(files)}")
        for f in files[:5]:
            print(f"  - {f.name}")

except Exception as e:
    print(f"DIAGNOSTIC ERROR: {e}")
    import traceback
    traceback.print_exc()
