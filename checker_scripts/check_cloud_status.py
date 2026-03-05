import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, 'backend')
from app.config import get_config
from app.db import get_db

db = get_db()
config = get_config()

# Check upload queue status
conn = sqlite3.connect('data/wedding.db')
cursor = conn.cursor()

print("\n=== Upload Queue Status ===")
cursor.execute("""
    SELECT status, COUNT(*) as count
    FROM upload_queue
    GROUP BY status
""")
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]}")

print("\n=== Recent Upload Queue Items (last 10) ===")
cursor.execute("""
    SELECT id, photo_id, local_path, status, retry_count, last_error
    FROM upload_queue
    ORDER BY id DESC
    LIMIT 10
""")
for row in cursor.fetchall():
    path = Path(row[2]).name if row[2] else "N/A"
    print(f"Queue {row[0]}: Photo {row[1]} - {path} - Status: {row[3]} - Retries: {row[4]}")
    if row[5]:
        print(f"  Error: {row[5][:100]}")

print("\n=== Failed Uploads ===")
cursor.execute("""
    SELECT id, photo_id, local_path, retry_count, last_error
    FROM upload_queue
    WHERE status = 'failed'
    ORDER BY id DESC
""")
failed = cursor.fetchall()
if failed:
    for row in failed:
        path = Path(row[2]).name if row[2] else "N/A"
        print(f"Queue {row[0]}: Photo {row[1]} - {path} - Retries: {row[3]}")
        if row[4]:
            print(f"  Error: {row[4][:200]}")
else:
    print("No failed uploads")

conn.close()

# Check cloud configuration
print("\n=== Cloud Configuration ===")
from app.cloud import get_cloud
cloud = get_cloud()
print(f"Cloud enabled: {cloud.is_enabled}")
if cloud.is_enabled:
    print(f"Cloud type: {cloud.__class__.__name__}")
else:
    print("Cloud is disabled - check .env file and credentials")
