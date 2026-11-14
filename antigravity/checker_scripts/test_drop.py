import os
import sys
import time
from pathlib import Path
from PIL import Image
import numpy as np

# Add backend to path
backend_path = Path("backend").resolve()
sys.path.insert(0, str(backend_path))

from app.config import get_config
from app.db import get_db

config = get_config()
db = get_db()
incoming_dir = config.incoming_dir

# Create a unique image
test_image_path = incoming_dir / f"test_{int(time.time())}.jpg"
print(f"Creating test image: {test_image_path}")

# Random noise image to ensure unique hash
noise = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
img = Image.fromarray(noise)
img.save(test_image_path)

print("Waiting for 10 seconds for watcher and worker to react...")
time.sleep(10)

# Check DB
import hashlib
def compute_file_hash(file_path: Path):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

file_hash = compute_file_hash(test_image_path)
photo = db.get_photo_by_hash(file_hash)

if photo:
    print(f"SUCCESS: Photo found in DB with status: {photo.status}")
else:
    print("FAILURE: Photo NOT found in DB. Watcher or Worker is not processing new files.")

# Cleanup
# os.remove(test_image_path)
