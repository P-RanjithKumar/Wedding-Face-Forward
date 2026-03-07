import sqlite3
from pathlib import Path

db_path = Path("data/wedding.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Actual photo counts vs face counts:")
cursor.execute("""
    SELECT 
        p.id, 
        p.name, 
        p.face_count as recorded_face_count,
        (SELECT COUNT(*) FROM faces WHERE person_id = p.id) as actual_face_count,
        (SELECT COUNT(DISTINCT photo_id) FROM faces WHERE person_id = p.id) as unique_photo_count
    FROM persons p
""")
rows = cursor.fetchall()

for row in rows:
    print(f"ID: {row['id']}, Name: {row['name']} | Recorded Face Count: {row['recorded_face_count']} | Actual Face Count: {row['actual_face_count']} | Unique Photo Count: {row['unique_photo_count']}")

conn.close()
