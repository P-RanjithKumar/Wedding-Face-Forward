import sys
sys.path.insert(0, 'backend')

from app.upload_queue import get_upload_queue

# Get the upload queue instance
upload_queue = get_upload_queue()

print("=== Upload Queue Status ===")
print(f"Running: {upload_queue._running}")
print(f"Thread alive: {upload_queue._thread.is_alive() if upload_queue._thread else 'No thread'}")
print(f"Cloud enabled: {upload_queue.cloud.is_enabled}")
print(f"Queue enabled in config: {upload_queue.config.upload_queue_enabled}")

if not upload_queue._running:
    print("\n[WARNING] Upload queue is NOT running!")
    print("The worker needs to be started for uploads to process.")
else:
    print("\n[OK] Upload queue is running")
    
# Get stats
stats = upload_queue.get_stats()
print(f"\nQueue stats: {stats}")
