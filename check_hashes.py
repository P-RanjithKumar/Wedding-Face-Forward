import os
import sys
import hashlib
from pathlib import Path

# Add backend to path
backend_path = Path("backend").resolve()
sys.path.insert(0, str(backend_path))

from app.config import get_config
from app.db import get_db

def compute_file_hash(file_path: Path, chunk_size: int = 8192) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

config = get_config()
db = get_db()
incoming_dir = config.incoming_dir

print(f"Checking files in {incoming_dir}...")
for file_path in incoming_dir.iterdir():
    if file_path.is_file():
        file_hash = compute_file_hash(file_path)
        exists = db.photo_exists(file_hash)
        photo = db.get_photo_by_hash(file_hash)
        print(f"File: {file_path.name}")
        print(f"  Hash: {file_hash}")
        print(f"  Exists in DB: {exists}")
        if photo:
            print(f"  DB Status: {photo.status}")
            print(f"  DB Path: {photo.original_path}")
