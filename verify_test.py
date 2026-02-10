import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path("backend").resolve()
sys.path.insert(0, str(backend_path))

from app.config import get_config
from app.db import get_db

config = get_config()
db = get_db()

# Check NoFaces
no_faces_dir = config.no_faces_dir
print(f"Checking NoFaces dir: {no_faces_dir}")
if no_faces_dir.exists():
    files = list(no_faces_dir.iterdir())
    for f in files:
        if "test_" in f.name:
            print(f"  FOUND TEST FILE: {f.name}")

# Check DB for any 'no_faces' status
conn = db.connect()
cursor = conn.execute("SELECT id, original_path, status FROM photos WHERE status = 'no_faces' ORDER BY id DESC LIMIT 5")
rows = cursor.fetchall()
print("\nRecent no_faces in DB:")
for row in rows:
    print(f"  ID: {row[0]}, Path: {row[1]}, Status: {row[2]}")
