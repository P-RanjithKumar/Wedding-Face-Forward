import sqlite3
import sys
from pathlib import Path

def check_db(path):
    print(f"\n--- Checking DB: {path} ---")
    if not Path(path).exists():
        print("Does not exist.")
        return
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables: {tables}")
        for table in tables:
            name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {name}")
            count = cursor.fetchone()[0]
            print(f"  - {name}: {count} rows")
        conn.close()
    except Exception as e:
        print(f"Error checking {path}: {e}")

check_db("data/wedding.db")
check_db("backend/data/wedding.db")
