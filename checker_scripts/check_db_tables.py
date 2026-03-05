import sqlite3
from pathlib import Path

db_paths = [
    Path("data/wedding.db"),
    Path("backend/data/wedding.db")
]

for db_path in db_paths:
    if not db_path.exists():
        continue
    
    print(f"\nSchema for {db_path}:")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table in tables:
        print(f"  Table: {table[0]}")
        cursor.execute(f"SELECT count(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"    Rows: {count}")
    conn.close()
