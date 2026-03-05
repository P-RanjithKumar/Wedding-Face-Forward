import sqlite3
from pathlib import Path

db_paths = [
    Path("data/wedding.db"),
    Path("backend/data/wedding.db")
]

for db_path in db_paths:
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        continue
    
    print(f"\nChecking {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT count(*) FROM enrollments")
        total = cursor.fetchone()[0]
        print(f"Total enrollments: {total}")

        cursor.execute("SELECT user_name, phone FROM enrollments")
        rows = cursor.fetchall()
        for row in rows:
            print(f"User: {row[0]}, Phone: {row[1]}")
    except Exception as e:
        print(f"Error reading {db_path}: {e}")
    finally:
        conn.close()
