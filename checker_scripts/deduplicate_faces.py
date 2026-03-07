import sqlite3
import pickle
import numpy as np
from pathlib import Path

db_path = Path("data/wedding.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Analyzing database for duplicate faces...")

# Group faces by photo and coordinates
cursor.execute("""
    SELECT photo_id, bbox_x, bbox_y, bbox_w, bbox_h, COUNT(*) as count
    FROM faces
    GROUP BY photo_id, bbox_x, bbox_y, bbox_w, bbox_h
    HAVING count > 1
""")
duplicates = cursor.fetchall()

if not duplicates:
    print("No duplicates found.")
else:
    print(f"Found {len(duplicates)} sets of duplicate faces.")
    
    total_removed = 0
    affected_persons = set()
    
    for dup in duplicates:
        # Get all face IDs for this coordinate set
        cursor.execute("""
            SELECT id, person_id FROM faces
            WHERE photo_id = ? AND bbox_x = ? AND bbox_y = ? AND bbox_w = ? AND bbox_h = ?
            ORDER BY id
        """, (dup['photo_id'], dup['bbox_x'], dup['bbox_y'], dup['bbox_w'], dup['bbox_h']))
        
        face_rows = cursor.fetchall()
        # Keep the first one, delete the rest
        ids_to_remove = [row['id'] for row in face_rows[1:]]
        person_ids = set(row['person_id'] for row in face_rows if row['person_id'] is not None)
        affected_persons.update(person_ids)
        
        for face_id in ids_to_remove:
            cursor.execute("DELETE FROM faces WHERE id = ?", (face_id,))
            total_removed += 1
            
    print(f"Removed {total_removed} duplicate face records.")
    
    # Recalculate face counts for affected persons
    for person_id in affected_persons:
        cursor.execute("SELECT COUNT(*) FROM faces WHERE person_id = ?", (person_id,))
        actual_count = cursor.fetchone()[0]
        
        if actual_count == 0:
            cursor.execute("DELETE FROM persons WHERE id = ?", (person_id,))
            print(f"Removed empty person ID: {person_id}")
        else:
            # Also recalculate centroid while we are at it
            cursor.execute("SELECT embedding FROM faces WHERE person_id = ?", (person_id,))
            embeddings_blobs = cursor.fetchall()
            embeddings = [pickle.loads(row[0]) for row in embeddings_blobs]
            
            new_centroid = np.mean(embeddings, axis=0)
            norm = np.linalg.norm(new_centroid)
            if norm > 0:
                new_centroid = new_centroid / norm
            
            centroid_blob = pickle.dumps(new_centroid)
            cursor.execute("UPDATE persons SET face_count = ?, centroid = ? WHERE id = ?", 
                           (actual_count, centroid_blob, person_id))
            print(f"Updated Person {person_id}: New Face Count = {actual_count}")

    conn.commit()
    print("Deduplication complete.")

# Final check of the stats
cursor.execute("SELECT COUNT(*) FROM faces")
total_faces = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM photos")
total_photos = cursor.fetchone()[0]
print(f"Current Stats: Photos: {total_photos}, Faces: {total_faces}")

conn.close()
