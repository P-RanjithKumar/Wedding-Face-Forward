# -*- coding: utf-8 -*-
"""
COMPREHENSIVE DATA ERASER - Wedding Face Forward
This script completely resets the database and deletes all photos and logs, 
allowing for a completely fresh start for a new event.

It preserves:
1. Database schema (the architecture)
2. WhatsApp login sessions (so you don't have to scan again)
3. Configuration and environment settings
"""

import sqlite3
import shutil
import os
import sys
import io
import time
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def clear_directory_contents(dir_path, delete_subdirs=True):
    """Remove all contents from a directory but keep the directory itself."""
    path = Path(dir_path)
    if not path.exists():
        return 0
    
    deleted_count = 0
    for item in path.iterdir():
        try:
            if item.is_file():
                item.unlink()
                deleted_count += 1
            elif item.is_dir() and delete_subdirs:
                shutil.rmtree(item)
                deleted_count += 1
            elif item.is_dir() and not delete_subdirs:
                # Recursively clear files but keep subdirs if requested
                deleted_count += clear_directory_contents(item, False)
        except Exception as e:
            print(f"  ❌ Error deleting {item}: {e}")
    
    return deleted_count

def clear_sqlite_db(db_path):
    """Clear all data from all tables in the SQLite database and reset counters."""
    path = Path(db_path)
    if not path.exists():
        return False
    
    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        
        # Get all table names except system ones
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Disable foreign keys temporarily to avoid deletion order issues
        cursor.execute("PRAGMA foreign_keys = OFF;")
        
        for table in tables:
            cursor.execute(f"DELETE FROM {table};")
            # Also reset auto-increment counters if they exist
            try:
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}';")
            except:
                pass
        
        conn.commit()
        
        # Optimize and clean up
        cursor.execute("VACUUM;")
        conn.close()
        
        # Also delete temporary SQLite files if they exist
        for ext in ['-wal', '-shm', '-journal']:
            tmp_file = Path(str(db_path) + ext)
            if tmp_file.exists():
                tmp_file.unlink()
                
        return True
    except Exception as e:
        print(f"  ❌ Database error ({db_path}): {e}")
        return False

def main(auto_confirm=False):
    print("\n" + "!" * 60)
    print("!!! WARNING: COMPREHENSIVE SYSTEM RESET !!!".center(60))
    print("!" * 60)
    print("\nThis will PERMANENTLY delete:")
    print("1. All photos (Incoming, Processed, People/Folders)")
    print("2. All guest records, face fingerprints, and match data")
    print("3. All cloud upload history")
    print("4. All log files\n")
    
    if not auto_confirm:
        confirm = input("Are you ABSOLUTELY sure you want to proceed? (type 'RESET' to confirm): ")
        if confirm != 'RESET':
            print("❌ Cleanup aborted.")
            return

    print("\n🚀 Starting deep cleanup...")
    time.sleep(1)

    # 1. Clear Photo Directories
    print("\n📂 Cleaning photo folders...")
    photo_dirs = [
        "EventRoot/Incoming",
        "EventRoot/Processed",
        "EventRoot/People",
        "EventRoot/Admin",
        "backend/EventRoot/Incoming",
        "backend/EventRoot/Processed",
        "backend/EventRoot/People",
        "backend/EventRoot/Admin"
    ]
    for d in photo_dirs:
        count = clear_directory_contents(d)
        if count > 0 or Path(d).exists():
            print(f"  ✅ Cleared {count} items from {d}")

    # 2. Clear Databases
    print("\n🗄️  Resetting databases...")
    dbs = ["data/wedding.db", "backend/data/wedding.db"]
    for db in dbs:
        if clear_sqlite_db(db):
            print(f"  ✅ Reset and vacuumed: {db}")

    # 3. Clear Logs
    print("\n📝 Clearing application logs...")
    log_count = clear_directory_contents("logs")
    print(f"  ✅ Deleted {log_count} log files")

    # 4. Reset WhatsApp state (but keep session)
    print("\n📱 Resetting WhatsApp queue...")
    wa_state = Path("whatsapp_tool/message_state_db.json")
    if wa_state.exists():
        with open(wa_state, 'w') as f:
            f.write("{}")
        print(f"  ✅ Cleared: {wa_state}")

    print("\n" + "=" * 60)
    print("✨ SYSTEM RESET COMPLETE! ✨".center(60))
    print("=" * 60)
    print("\nYour system is now ready for a brand new event.")
    print("You can start WeddingFFapp.py now.\n")

if __name__ == "__main__":
    # Check for auto-confirm flag
    force = "--force" in sys.argv
    main(auto_confirm=force)
