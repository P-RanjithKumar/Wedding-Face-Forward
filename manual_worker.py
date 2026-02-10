import os
import sys
import logging
from pathlib import Path
from PIL import Image
import numpy as np
import hashlib

# Add backend to path
backend_path = Path("backend").resolve()
sys.path.insert(0, str(backend_path))

from app.config import get_config
from app.db import get_db
from app.processor import process_photo

# Setup logging to stdout
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

config = get_config()
db = get_db()
incoming_dir = config.incoming_dir

# Create a unique image
test_image_path = incoming_dir / f"test_debug_2.jpg"
img = Image.fromarray(np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8))
img.save(test_image_path)

sha256 = hashlib.sha256()
with open(test_image_path, "rb") as f:
    sha256.update(f.read())
file_hash = sha256.hexdigest()

photo_id = db.create_photo(file_hash, str(test_image_path))
print(f"Created Photo ID: {photo_id}")

result = process_photo(test_image_path, photo_id, config)
print(f"Success: {result.success}")
print(f"Faces found: {len(result.faces)}")
print(f"Error: {result.error}")

if result.success:
    from app.worker import process_single_photo
    success = process_single_photo(photo_id, test_image_path, file_hash, config)
    print(f"Full pipeline result: {success}")
