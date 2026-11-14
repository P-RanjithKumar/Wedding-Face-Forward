import os
import sys
import time
import subprocess
import webbrowser
import threading

def kill_port(port):
    print(f" - Cleaning up Port {port}...")
    ps_script = f"""
    try {{
        $connection = Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue
        if ($connection) {{
            foreach ($conn in $connection) {{
                $procId = $conn.OwningProcess
                if ($procId) {{
                    Write-Host "   -> Found process on Port {port} (PID: $procId). Terminating..."
                    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                }}
            }}
        }}
    }} catch {{
        $netstat = netstat -ano | Select-String ":{port} "
        if ($netstat) {{
            foreach ($line in $netstat) {{
                $parts = $line.ToString().Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
                $procId = $parts[$parts.Length - 1]
                if ($procId -match '^\d+$') {{
                    Write-Host "   -> Found process on Port {port} (PID: $procId). Terminating..."
                    taskkill /F /PID $procId /T 2>$null
                }}
            }}
        }}
    }}
    """
    subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True)

def aggressive_cleanup():
    print(" - Performing aggressive cleanup of stray Node/Python processes...")
    try:
        # Kill node
        subprocess.run(["powershell", "-Command", "Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force"], capture_output=True)
        
        # Kill specific python processes
        ps_kill_py = """Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*backend_entry*' -or $_.CommandLine -like '*uvicorn*' -or $_.CommandLine -like '*aura_web*' } | Stop-Process -Force"""
        subprocess.run(["powershell", "-Command", ps_kill_py], capture_output=True)
        
    except Exception:
        pass
        
    lock_file = os.path.join("aura_web", ".next", "dev", "lock")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except:
            pass

# Keep track of running processes
processes = []

def run_process_and_pipe(name, cmd_args, cwd=None, shell=False):
    print(f" -> Starting {name}...")
    
    # Run the process without creating a new console
    # stderr is redirected to stdout to capture everything
    p = subprocess.Popen(
        cmd_args, 
        cwd=cwd,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append((name, p))
    
    # Thread to read output and prefix it with the process name
    def reader_thread():
        # Readline blocks until a newline is encountered or process ends
        for line in iter(p.stdout.readline, ''):
            if line:
                print(f"[{name}] {line.rstrip()}")
        p.stdout.close()
        
    # Start thread in background
    threading.Thread(target=reader_thread, daemon=True).start()
    return p

def main():
    print("==========================================")
    print("          AURA - DARK intelligence        ")
    print("        Single Terminal Launch Tool       ")
    print("==========================================")
    print("\n[1/3] CLEANING UP PORTS 8000 AND 3000...")
    
    kill_port(8000)
    kill_port(3000)
    aggressive_cleanup()

    print("\n[OK] PORTS CLEANED SUCCESSFULLY!")
    print("==========================================")

    choice = input("\nDo you want to launch the AURA app? (y/n): ")
    print("")
    
    if choice.lower() != 'y':
        print("==========================================")
        print("   STOPPED. Only port cleanup was done.  ")
        print("==========================================")
        input("Press Enter to exit...")
        sys.exit(0)

    print("[2/3] STARTING BACKEND COMPONENTS...")
    
    # Since we are running in the current console context, we use the python executable that started this script
    python_exe = sys.executable

    run_process_and_pipe("SERVER", [python_exe, "backend_entry.py", "--run-server"])
    
    if os.path.exists("backend_entry.py"):
        # The worker and whatsapp processes are now generally started from the UI
        # run_process_and_pipe("WORKER", [python_exe, "backend_entry.py", "--run-worker"])
        # run_process_and_pipe("WHATSAPP", [python_exe, "backend_entry.py", "--run-whatsapp"])
        pass
        
    print("\n[3/3] STARTING FRONTEND DASHBOARD...")
    if os.path.isdir("aura_web"):
        # For npm we use shell=True so it resolves via the system path easily
        run_process_and_pipe("FRONTEND", "npm run dev", cwd="aura_web", shell=True)
    else:
        print(" [WARNING] aura_web directory not found!")
        
    print("\n==========================================")
    print("       AURA IS STARTING UP!               ")
    print("==========================================")
    print(" Waiting 8 seconds for servers to initialize...")
    time.sleep(8)
    
    print("\n Launching Interfaces:")
    print("  - Admin Dashboard: http://localhost:3000")
    print("  - Guest Registration: http://localhost:8000")
    
    webbrowser.open("http://localhost:3000")
    
    print("\nDone! All processes are running in THIS terminal.")
    print("Their logs will appear below, prefixed with [SERVER], [WORKER], etc.")
    print("==========================================================================")
    print("Press Ctrl+C to stop all processes and exit.")
    print("==========================================================================\n")
    
    try:
        # Keep the main thread alive indefinitely to allow background threads to print
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[SYSTEM] Ctrl+C detected. Shutting down all services...")
        for name, p in processes:
            print(f" -> Terminating {name}...")
            # Terminate sends a signal to politely ask the process to stop
            p.terminate()
        print("[SYSTEM] All services stopped. Goodbye!")
        sys.exit(0)

if __name__ == "__main__":
    # Change to directory of this script
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
