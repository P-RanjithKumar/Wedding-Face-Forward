import psutil
import os

def check_worker():
    print(f"Checking for worker process...")
    found = False
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = p.info.get('cmdline') or []
            cmd_str = ' '.join(cmd).lower()
            name = (p.info.get('name') or '').lower()
            
            if 'aura' in name or 'backend' in name or '--run' in cmd_str:
                print(f"Candidate: PID={p.info['pid']}, Name={name}, Cmd={cmd}")
                
            if '--run-worker' in cmd_str:
                print(f"!!! MATCH FOUND (Worker): PID={p.info['pid']}, Cmd={cmd_str}")
                found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if not found:
        print("No worker process detected via '--run-worker' flag.")

if __name__ == "__main__":
    check_worker()
