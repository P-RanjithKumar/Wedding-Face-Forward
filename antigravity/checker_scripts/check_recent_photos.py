import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, 'backend')
from app.config import get_config
from app.db import get_db

db = get_db()
config = get_config()

# Get recent photos
conn = sqlite3.connect('data/wedding.db')
cursor = conn.cursor()

print("\n=== Recent Photos (last 10) ===")
cursor.execute("""
    SELECT id, original_path, status 
    FROM photos 
    ORDER BY id DESC 
    LIMIT 10
""")
for row in cursor.fetchall():
    print(f"Photo {row[0]}: {row[1]} - Status: {row[2]}")

print("\n=== Recent Faces (last 10) ===")
cursor.execute("""
    SELECT f.id, f.photo_id, f.person_id, p.name
    FROM faces f
    LEFT JOIN persons p ON f.person_id = p.id
    ORDER BY f.id DESC
    LIMIT 10
""")
for row in cursor.fetchall():
    print(f"Face {row[0]}: Photo {row[1]} -> Person {row[2]} ({row[3]})")

print("\n=== All Persons ===")
cursor.execute("""
    SELECT id, name, face_count, created_at
    FROM persons
    ORDER BY id DESC
""")
for row in cursor.fetchall():
    print(f"Person {row[0]}: {row[1]} - {row[2]} faces - Created: {row[3]}")

conn.close()
