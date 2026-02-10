import sqlite3
from pathlib import Path

db_path = "data/wedding.db"

def check_all_photos():
    if not Path(db_path).exists():
        print("DB does not exist.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, original_path, status, face_count FROM photos ORDER BY id DESC")
    rows = cursor.fetchall()
    print(f"Total photos in DB: {len(rows)}")
    for row in rows[:10]:
        print(f"  ID: {row[0]}, Status: {row[2]}, Paths: {row[1]}")
    conn.close()

check_all_photos()
