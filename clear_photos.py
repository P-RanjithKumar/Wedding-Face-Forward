# -*- coding: utf-8 -*-
"""
Clear all photos and reset the database while preserving the structure.
This script will:
1. Delete all photos from EventRoot/Incoming, EventRoot/Processed, EventRoot/People, EventRoot/Admin
2. Clear all data from database tables (photos, faces, persons, enrollments)
3. Keep the database structure intact
"""

import sqlite3
import shutil
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path

def clear_directory(dir_path):
    """Remove all contents from a directory but keep the directory itself."""
    path = Path(dir_path)
    if not path.exists():
        print(f"⚠️  Directory does not exist: {dir_path}")
        return
    
    deleted_count = 0
    for item in path.iterdir():
        try:
            if item.is_file():
                item.unlink()
                deleted_count += 1
            elif item.is_dir():
                shutil.rmtree(item)
                deleted_count += 1
        except Exception as e:
            print(f"❌ Error deleting {item}: {e}")
    
    print(f"✅ Cleared {deleted_count} items from {dir_path}")

def clear_database(db_path):
    """Clear all data from database tables while preserving structure."""
    path = Path(db_path)
    if not path.exists():
        print(f"⚠️  Database does not exist: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence';")
        tables = cursor.fetchall()
        
        # Clear each table
        for table in tables:
            table_name = table[0]
            cursor.execute(f"DELETE FROM {table_name}")
            print(f"  - Cleared table: {table_name}")
        
        # Reset sqlite_sequence (auto-increment counters)
        cursor.execute("DELETE FROM sqlite_sequence")
        print(f"  - Reset auto-increment counters")
        
        conn.commit()
        conn.close()
        print(f"✅ Database cleared: {db_path}")
        
    except Exception as e:
        print(f"❌ Error clearing database {db_path}: {e}")

def clear_whatsapp_state(file_path):
    """Reset the WhatsApp message state database to empty."""
    path = Path(file_path)
    if not path.exists():
        return
    
    try:
        import json
        with open(path, 'w') as f:
            json.dump({}, f)
        print(f"✅ Reset WhatsApp state: {file_path}")
    except Exception as e:
        print(f"❌ Error resetting WhatsApp state: {e}")

def main():
    print("=" * 60)
    print("🧹 COMPREHENSIVE SYSTEM CLEANUP (RESET EVERYTHING)")
    print("=" * 60)
    
    # Clear photo directories
    print("\n📁 Clearing photo directories...")
    clear_directory("EventRoot/Incoming")
    clear_directory("EventRoot/Processed")
    clear_directory("EventRoot/People")
    clear_directory("EventRoot/Admin")
    
    # Also check backend EventRoot if it exists
    if Path("backend/EventRoot").exists():
        print("\n📁 Clearing backend photo directories...")
        clear_directory("backend/EventRoot/Incoming")
        clear_directory("backend/EventRoot/Processed")
        clear_directory("backend/EventRoot/People")
        clear_directory("backend/EventRoot/Admin")
    
    # Clear databases
    print("\n🗄️  Clearing databases (Contacts, Photos, Faces)...")
    clear_database("data/wedding.db")
    clear_database("backend/data/wedding.db")
    
    # Clear WhatsApp state
    print("\n📱 Clearing WhatsApp status (Sent/Invalid logs)...")
    clear_whatsapp_state("whatsapp_tool/message_state_db.json")
    
    print("\n" + "=" * 60)
    print("✨ CLEANUP COMPLETE!")
    print("=" * 60)
    print("\n📋 Summary:")
    print("  ✓ All photos deleted (Incoming, Processed, People, Admin)")
    print("  ✓ All contacts/enrollments cleared from database")
    print("  ✓ WhatsApp message history (sent/invalid) reset")
    print("  ✓ Database structure preserved for fresh start")
    print("\n⚠️  Note: WhatsApp login (session data) was preserved.")
    print()

if __name__ == "__main__":
    main()
