import sqlite3
from pathlib import Path

db_path = Path("data/wedding.db")
if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT count(*) FROM enrollments")
total = cursor.fetchone()[0]

cursor.execute("SELECT count(*) FROM enrollments WHERE phone IS NOT NULL AND phone != ''")
with_phone = cursor.fetchone()[0]

print(f"Total enrollments: {total}")
print(f"Enrollments with phone: {with_phone}")

cursor.execute("SELECT user_name, phone FROM enrollments WHERE phone IS NOT NULL AND phone != ''")
rows = cursor.fetchall()
for row in rows:
    print(f"User: {row[0]}, Phone: {row[1]}")

conn.close()
