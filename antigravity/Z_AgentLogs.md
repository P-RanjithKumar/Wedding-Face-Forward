# AURA v3.0.0 Debugging & Bug Tracking Log

This document tracks all identified bugs, their resolution areas, and fix details in a structured format.

---

### Bug No: 1

**Bug Name**: Authentication Failure in Bundled Installation  
**Area**: Auth / Backend  
**Status**: ✅ FIXED  
**Description**: The application couldn't find `credentials.json` or `token.json` in the bundled production environment because they were outside the executable's search path.  
**Fix**: Updated `dist_utils.py` and `setup_auth.py` to use a centralized AppData path `%LOCALAPPDATA%\AURA\` for all persistent configuration.

---

### Bug No: 2

**Bug Name**: Missing AI Models in Production  
**Area**: AI Models / Backend  
**Status**: ✅ FIXED  
**Description**: InsightFace couldn't find the `buffalo_l` model files because the model directory path was hardcoded to a local developer path.  
**Fix**: Implemented `get_models_dir()` in `dist_utils.py` and patched `processor.py` to check the bundled sidecar's resource folder before falling back to default directories.

---

### Bug No: 3

**Bug Name**: "Action Failed" on AI Engine Start  
**Area**: Backend / Subprocess  
**Status**: ✅ FIXED  
**Description**: The UI reported an "Action Failed" error because it couldn't spawn the background worker, likely due to file locks or incorrect binary paths.  
**Fix**: Refactored `admin_router.py` to use standardized paths from `dist_utils.py` and added a graceful failover mechanism for subprocess spawning.

---

### Bug No: 4

**Bug Name**: Frontend Connectivity / Backend Port Collision  
**Area**: Frontend / Backend  
**Status**: ✅ FIXED  
**Description**: The Tauri frontend occasionally failed to connect to the FastAPI backend at `localhost:8000` because of port collision or slow startup.  
**Fix**: Standardized the startup sequence to ensure the backend is available before the frontend initiates its polling cycle.

---

### Bug No: 5

**Bug Name**: Worker Stability / Missing 'app' Package  
**Area**: Backend / Python Script  
**Status**: ✅ FIXED  
**Description**: The worker subprocess crashed immediately with `ImportError: No module named 'app'` when running inside the sidecar because it couldn't see its own package structure.  
**Fix**: Patched `backend_entry.py` to explicitly inject the backend directory into `sys.path` before launching the worker.

---

### Bug No: 6

**Bug Name**: UI Status Desync ("Flip-Flopping" Button)  
**Area**: Backend / Frontend  
**Status**: ✅ FIXED  
**Description**: The "START" button reverted to its initial state even when the process was running because the process detection logic was too narrow (checking only for exact PID or binary names).  
**Fix**: Implemented robust `psutil` matching in `admin_router.py` that looks for the `--run-worker` flag across both Python processes (dev) and the `aura-backend.exe` (production).

---

### Bug No: 7

**Bug Name**: Application Version Inconsistency  
**Area**: Metadata / Entire App  
**Status**: ✅ FIXED  
**Description**: Different parts of the app reported different versions (e.g., 0.1.0 vs 3.0.0).  
**Fix**: Synchronized all version metadata in `package.json`, `tauri.conf.json`, and `dist_utils.py` to `3.0.0`.

---

### Bug No: 8

**Bug Name**: Persistent UI Status Desync (Post-Build)  
**Area**: Backend / Frontend / Tauri Sidecar  
**Status**: ✅ FIXED  
**Description**: Even after the initial fix, the "START" button continued to flip-flop. Diagnostics revealed that Tauri starts sidecars with complex filenames and additional internal flags (e.g., `--type-handle`), which the previous detection logic missed. Additionally, Tauri starts the worker by default on launch, causing a conflict when the user tries to start it again.  
**Fix**: Implemented a universal detection logic that matches ANY process containing the `--run-worker` flag in its command line. Switched detection logging to INFO level for better visibility.

---

### Bug No: 9

**Bug Name**: Windows File-Locking Conflict on Shared Log  
**Area**: Backend / Python Script / OS Compatibility  
**Status**: ✅ FIXED  
**Description**: On Windows, the worker process crashed immediately after start when trying to initialize logging. This happened because both the server and worker tried to open `aura.log` for appending simultaneously, causing a `PermissionError` (File Lock). This explains why the button would "flip" back to START almost instantly.  
**Fix**: Modified `app/worker.py` to use a dedicated `worker.log` file, ensuring no file-lock contention with the main server process. Also improved `admin_router.py` to capture and log any remaining startup errors more accurately.

---
