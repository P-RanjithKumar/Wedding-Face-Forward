import sqlite3
from pathlib import Path

db_path = Path("data/wedding.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Persons in data/wedding.db:")
cursor.execute("SELECT id, name, face_count FROM persons")
rows = cursor.fetchall()
for row in rows:
    print(f"ID: {row['id']}, Name: {row['name']}, Faces: {row['face_count']}")

conn.close()
