"""Reset all cb* photos back to pending so they can be reprocessed with the fix."""
import sqlite3

conn = sqlite3.connect('data/wedding.db')
cur = conn.cursor()

# Show current state
cur.execute("SELECT id, original_path, status, face_count FROM photos WHERE original_path LIKE '%cb%' ORDER BY id")
rows = cur.fetchall()
print(f"Found {len(rows)} cb photos:")
for r in rows:
    print(f"  ID {r[0]}: status={r[2]}, faces={r[3]}, file={r[1].split(chr(92))[-1]}")

# Reset all cb photos to pending
cur.execute("""
    UPDATE photos 
    SET status = 'pending', 
        processed_path = NULL, 
        thumbnail_path = NULL, 
        face_count = NULL, 
        processed_at = NULL 
    WHERE original_path LIKE '%cb%'
""")
print(f"\nReset {cur.rowcount} photos to 'pending'")

# Also delete any face records for these photos so they get re-detected
cur.execute("DELETE FROM faces WHERE photo_id IN (SELECT id FROM photos WHERE original_path LIKE '%cb%')")
print(f"Deleted {cur.rowcount} old face records")

conn.commit()
conn.close()
print("\nDone! Restart the app to reprocess these photos.")
