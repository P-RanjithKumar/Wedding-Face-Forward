"""
AURA — Admin API Router (by DARK intelligence)

REST + WebSocket endpoints for the Next.js admin dashboard.
Mounted under /api/admin/* on the FastAPI server.
"""

import os
import json
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

# Backend imports
import sys
try:
    import dist_utils
    backend_path = dist_utils.get_backend_dir()
except ImportError:
    backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.config import get_config
from app.db import get_db
from app.cloud import get_auth_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============================================================
# Pydantic Models
# ============================================================

class SettingsUpdate(BaseModel):
    """Partial settings update — only provided fields are written."""
    EVENT_ROOT: Optional[str] = None
    DB_PATH: Optional[str] = None
    WORKER_COUNT: Optional[int] = None
    CLUSTER_THRESHOLD: Optional[float] = None
    SCAN_INTERVAL: Optional[int] = None
    LOG_LEVEL: Optional[str] = None
    UPLOAD_QUEUE_ENABLED: Optional[bool] = None
    UPLOAD_WORKERS: Optional[int] = None
    UPLOAD_BATCH_SIZE: Optional[int] = None
    FOLDER_SYNC_INTERVAL: Optional[int] = None
    GPU_ACCELERATION: Optional[bool] = None
    GPU_DEVICE_ID: Optional[int] = None
    GOOGLE_CREDENTIALS_FILE: Optional[str] = None
    DRIVE_ROOT_FOLDER_ID: Optional[str] = None


class MergeRequest(BaseModel):
    person_id_keep: int
    person_id_remove: int


class StuckPhotoAction(BaseModel):
    action: str  # "reset" | "skip"
    photo_ids: list[int] = []


# ============================================================
# Global Process References
# ============================================================
_worker_proc = None
_whatsapp_proc = None


# ============================================================
# Settings  GET / PUT
# ============================================================

def _read_env_file() -> dict[str, str]:
    """Read the .env file into a key=value dict."""
    try:
        env_path = dist_utils.get_env_file_path()
    except (NameError, AttributeError):
        env_path = Path(__file__).parent.parent / ".env"

    settings: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                settings[key.strip()] = value.strip()
    return settings


def _write_env_file(settings: dict[str, str]) -> None:
    """Write key=value pairs back to the .env file, preserving comments."""
    try:
        env_path = dist_utils.get_env_file_path()
    except (NameError, AttributeError):
        env_path = Path(__file__).parent.parent / ".env"

    lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()
    else:
        existing_lines = []

    written_keys: set[str] = set()

    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in settings:
                lines.append(f"{key}={settings[key]}")
                written_keys.add(key)
            else:
                lines.append(line)
        else:
            lines.append(line)

    # Append any new keys that weren't in the original file
    for key, value in settings.items():
        if key not in written_keys:
            lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@router.get("/settings")
async def get_settings():
    """Return all current .env settings."""
    return _read_env_file()


@router.put("/settings")
async def update_settings(update: SettingsUpdate):
    """Update .env settings. Only provided (non-None) fields are written."""
    current = _read_env_file()

    for key, value in update.model_dump(exclude_none=True).items():
        current[key] = str(value).lower() if isinstance(value, bool) else str(value)

    _write_env_file(current)

    # Reset config cache so next request picks up new values
    from app.config import reset_config
    reset_config()

    return {"status": "ok", "updated": list(update.model_dump(exclude_none=True).keys())}


# ============================================================
# Person Actions (Local Folder / Cloud URL)
# ============================================================

@router.get("/person/open-local")
async def open_local_person_folder(name: str):
    """Opens the local folder for a given person."""
    config = get_config()
    # Sanitize name to prevent path traversal
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    person_dir = config.people_dir / safe_name
    
    if not person_dir.exists():
        # Fallback to create it just in case
        person_dir.mkdir(parents=True, exist_ok=True)
        
    try:
        if sys.platform == "win32":
            os.startfile(str(person_dir))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(person_dir)])
        else:
            subprocess.Popen(["xdg-open", str(person_dir)])
        return {"status": "ok", "path": str(person_dir)}
    except Exception as e:
        logger.error(f"Failed to open folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/person/cloud-url")
async def get_person_cloud_url(name: str):
    """Gets the Google Drive web link for a given person's folder."""
    config = get_config()
    from app.cloud import CloudManager
    manager = CloudManager(config)
    if not manager.is_enabled:
        raise HTTPException(status_code=400, detail="Cloud upload is not enabled")
    
    # Check if folder exists
    folder_id = manager._find_folder(name, manager.root_folder_id)
    # If not in root, maybe under People?
    if not folder_id:
        people_id = manager._find_folder("People", manager.root_folder_id)
        if people_id:
            folder_id = manager._find_folder(name, people_id)
            
    if folder_id:
        url = manager.get_folder_link(folder_id)
        return {"url": url}
    else:
        # Generate it via ensure (which will create if missing)
        folder_id = manager.ensure_folder_path(["People", name])
        if folder_id:
            url = manager.get_folder_link(folder_id)
            return {"url": url}
        
    raise HTTPException(status_code=404, detail="Could not find or create cloud folder")


# ============================================================
# Merge Persons  POST
# ============================================================

@router.post("/merge")
async def merge_persons_endpoint(req: MergeRequest):
    """Merge two person clusters."""
    from app.cluster import merge_persons

    if req.person_id_keep == req.person_id_remove:
        raise HTTPException(status_code=400, detail="Cannot merge a person with itself")

    success = merge_persons(req.person_id_keep, req.person_id_remove)
    if not success:
        raise HTTPException(status_code=404, detail="One or both person IDs not found")

    return {
        "status": "ok",
        "merged_into": req.person_id_keep,
        "removed": req.person_id_remove,
    }


# ============================================================
# Self-Heal  POST
# ============================================================

@router.post("/self-heal")
async def self_heal():
    """Run database self-healing routines."""
    db = get_db()
    results = {}

    # 1. Reset stuck photos (processing -> pending)
    try:
        db._reset_stuck_processing()
        results["stuck_photos_reset"] = True
    except Exception as e:
        results["stuck_photos_reset"] = False
        results["stuck_photos_error"] = str(e)

    # 2. Reset stuck uploads
    try:
        reset_count = db.reset_stuck_uploads(timeout_minutes=5)
        results["stuck_uploads_reset"] = reset_count
    except Exception as e:
        results["stuck_uploads_reset"] = 0
        results["stuck_uploads_error"] = str(e)

    # 3. Refresh stats
    stats = db.get_stats()
    results["stats_after"] = stats

    return {"status": "ok", "results": results}


# ============================================================
# GPU  GET / PUT
# ============================================================

@router.get("/gpu")
async def get_gpu_status():
    """Get full GPU status & wizard state."""
    from app.gpu_manager import get_full_gpu_status
    import dataclasses

    info = get_full_gpu_status()
    return dataclasses.asdict(info)


@router.put("/gpu")
async def update_gpu_settings(gpu_on: bool, device_id: int = 0):
    """Toggle GPU acceleration on/off."""
    current = _read_env_file()
    current["GPU_ACCELERATION"] = str(gpu_on).lower()
    current["GPU_DEVICE_ID"] = str(device_id)
    _write_env_file(current)

    from app.config import reset_config
    reset_config()

    return {"status": "ok", "gpu_acceleration": gpu_on, "device_id": device_id}


# ============================================================
# Stuck Photos  GET / POST
# ============================================================

@router.get("/stuck-photos")
async def get_stuck_photos():
    """Get photos stuck in 'processing' status."""
    db = get_db()
    conn = db.connect()
    cursor = conn.execute(
        "SELECT id, original_path, status, created_at FROM photos WHERE status = 'processing'"
    )
    rows = cursor.fetchall()
    return [
        {
            "id": row["id"],
            "path": row["original_path"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


@router.post("/stuck-photos")
async def fix_stuck_photos(action: StuckPhotoAction):
    """Reset or skip stuck photos."""
    db = get_db()

    if action.action == "reset":
        db._reset_stuck_processing()
        return {"status": "ok", "action": "reset_all"}
    elif action.action == "skip":
        for pid in action.photo_ids:
            db.update_photo_status(pid, "error")
        return {"status": "ok", "action": "skipped", "count": len(action.photo_ids)}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action.action}")


# ============================================================
# WhatsApp Status  GET
# ============================================================

@router.get("/whatsapp/status")
async def get_whatsapp_status():
    """Get WhatsApp sending status from the database and process state."""
    db = get_db()
    config = get_config()

    # Count enrolled users
    enrollments = db.get_all_enrollments()
    total_enrolled = len(enrollments)

    # Count those with phone numbers (sendable)
    sendable = sum(1 for e in enrollments if e.phone)

    # Check if WhatsApp data dir exists
    try:
        wa_dir = dist_utils.get_whatsapp_dir()
    except (NameError, AttributeError):
        wa_dir = Path(__file__).parent.parent / "whatsapp_data"

    session_exists = (wa_dir / "whatsapp_data").exists() if wa_dir.exists() else False

    # Check if process is running
    global _whatsapp_proc
    is_running = False
    
    if _whatsapp_proc is not None:
        if _whatsapp_proc.poll() is None:
            is_running = True
        else:
            _whatsapp_proc = None
            
        try:
            import psutil
            for p in psutil.process_iter(['name', 'cmdline']):
                name = p.info.get('name', '') or ''
                cmd = p.info.get('cmdline') or []
                cmd_str = ' '.join(cmd).lower()
                
                name_lower = name.lower()
                is_worker_binary = 'aura-backend' in name_lower or 'aura_backend' in name_lower
                is_python = 'python' in name_lower

                if (is_python or is_worker_binary) and ('--run-whatsapp' in cmd_str or 'db_whatsapp_sender' in cmd_str):
                    is_running = True
                    break
        except Exception as e:
            logger.error(f"Error checking WA process: {e}")

    return {
        "total_enrolled": total_enrolled,
        "sendable": sendable,
        "session_exists": session_exists,
        "is_running": is_running,
    }

@router.post("/whatsapp/start")
async def start_whatsapp():
    """Start the WhatsApp sender subprocess."""
    global _whatsapp_proc
    try:
        import subprocess
        # Check if already running
        status = await get_whatsapp_status()
        if status["is_running"]:
            return {"status": "ok", "message": "Already running"}
            
        python_exe = sys.executable
        if dist_utils.is_frozen():
            args = [python_exe, "--run-whatsapp"]
        else:
            args = [python_exe, "backend_entry.py", "--run-whatsapp"]
            
        _whatsapp_proc = subprocess.Popen(
            args,
            cwd=str(backend_path.parent),
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        logger.info("[User Action] WhatsApp process manually started by user")
        return {"status": "ok", "message": "WhatsApp process started"}
    except Exception as e:
        logger.error(f"Failed to start WA process: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/whatsapp/stop")
async def stop_whatsapp():
    """Stop the WhatsApp sender subprocess."""
    global _whatsapp_proc
    try:
        stopped = False
        
        # 1. Try stopping tracked process
        if _whatsapp_proc is not None:
            if _whatsapp_proc.poll() is None:
                try:
                    _whatsapp_proc.terminate()
                    try:
                        import subprocess
                        _whatsapp_proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        _whatsapp_proc.kill()
                        _whatsapp_proc.wait(timeout=1)
                    stopped = True
                except Exception as e:
                    logger.warning(f"Failed to terminate tracked WA: {e}")
            _whatsapp_proc = None
            
        # 2. Try cleanup with psutil
        import psutil
        for p in psutil.process_iter(['name', 'cmdline']):
            name = p.info.get('name', '') or ''
            cmd = p.info.get('cmdline') or []
            cmd_str = ' '.join(cmd).lower()
            if 'python' in name.lower() and ('--run-whatsapp' in cmd_str or 'db_whatsapp_sender' in cmd_str):
                try:
                    p.terminate()
                    p.wait(timeout=3)
                    stopped = True
                except psutil.TimeoutExpired:
                    logger.warning("WhatsApp terminate timed out, killing process")
                    p.kill()
                    p.wait(timeout=1)
                    stopped = True
                except Exception as e:
                    logger.warning(f"Failed to terminate cleanly, killing whatsapp: {e}")
                    p.kill()
                    p.wait(timeout=1)
                    stopped = True
                        
        if stopped:
            logger.info("[User Action] WhatsApp process manually stopped by user")
            return {"status": "ok", "message": "WhatsApp process stopped"}
        else:
            return {"status": "ok", "message": "WhatsApp process was not running"}
    except Exception as e:
        logger.error(f"Failed to stop WA process: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Worker Status  GET / POST
# ============================================================

@router.get("/worker/status")
async def get_worker_status():
    """Check if the processing worker is running."""
    global _worker_proc
    is_running = False
    
    # 1. Check direct handle (if started in this session)
    if _worker_proc is not None:
        if _worker_proc.poll() is None:
            is_running = True
        else:
            logger.info("Worker process handle detected exit.")
            _worker_proc = None
            
    # 2. Robust check for orphaned or side-car processes (crucial for production)
    if not is_running:
        try:
            import psutil
            # Iterate through all processes and check command lines
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmd = p.info.get('cmdline') or []
                    cmd_str = ' '.join(cmd).lower()
                    
                    # More aggressive detection:
                    # If ANY process has '--run-worker' in its command line, it's our worker.
                    # We don't strictly care about the process name 'aura' or 'backend' 
                    # because sidecars can have platform-specific suffixes.
                    if '--run-worker' in cmd_str:
                        is_running = True
                        logger.info(f"Verified worker running: PID={p.info['pid']}, Cmd={cmd_str}")
                        break
                        
                    # Fallback for dev mode
                    name = (p.info.get('name') or '').lower()
                    if ('python' in name or 'backend_entry' in name) and 'worker' in cmd_str:
                        is_running = True
                        logger.info(f"Verified worker (dev/alt): PID={p.info['pid']}, Name={name}")
                        break
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.error(f"Detection error: {e}")
            
    return {"is_running": is_running}


@router.post("/worker/start")
async def start_worker():
    """Start the worker subprocess."""
    global _worker_proc
    try:
        import subprocess
        # Check if already running
        status = await get_worker_status()
        if status["is_running"]:
            return {"status": "ok", "message": "Already running"}
            
        python_exe = sys.executable
        if dist_utils.is_frozen():
            args = [python_exe, "--run-worker"]
        else:
            args = [python_exe, "backend_entry.py", "--run-worker"]
            
        log_path = dist_utils.get_logs_dir() / "worker_process.log"
        logger.info(f"Starting worker process. Logs directed to: {log_path}")
        
        try:
            log_file = open(log_path, "a", buffering=1) # Line buffered
        except Exception as log_err:
            logger.error(f"Could not open worker log file: {log_err}")
            # Fallback to dev null or similar if needed, but here we'll just fail
            raise

        _worker_proc = subprocess.Popen(
            args,
            cwd=str(backend_path.parent),
            stdout=log_file,
            stderr=log_file,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        logger.info(f"[User Action] AI Worker process manually started by user (PID: {_worker_proc.pid})")
        return {"status": "ok", "message": "Worker process started"}
    except Exception as e:
        logger.error(f"Failed to start worker process: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/worker/stop")
async def stop_worker():
    """Stop the worker subprocess."""
    global _worker_proc
    try:
        stopped = False
        
        # 1. Try stopping tracked process
        if _worker_proc is not None:
            if _worker_proc.poll() is None:
                try:
                    _worker_proc.terminate()
                    try:
                        import subprocess
                        _worker_proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        _worker_proc.kill()
                        _worker_proc.wait(timeout=1)
                    stopped = True
                except Exception as e:
                    logger.warning(f"Failed to terminate tracked worker: {e}")
            _worker_proc = None
            
        # 2. Try cleanup with psutil
        import psutil
        for p in psutil.process_iter(['name', 'cmdline']):
            name = p.info.get('name', '') or ''
            cmd = p.info.get('cmdline') or []
            cmd_str = ' '.join(cmd).lower()
            if 'python' in name.lower() and ('--run-worker' in cmd_str or ('worker' in cmd_str and 'app/worker.py' in cmd_str)):
                try:
                    p.terminate()
                    p.wait(timeout=3)
                    stopped = True
                except psutil.TimeoutExpired:
                    logger.warning("Worker terminate timed out, killing process")
                    p.kill()
                    p.wait(timeout=1)
                    stopped = True
                except Exception as e:
                    logger.warning(f"Failed to terminate cleanly, killing worker: {e}")
                    p.kill()
                    p.wait(timeout=1)
                    stopped = True
                        
        if stopped:
            logger.info("[User Action] AI Worker process manually stopped by user")
            return {"status": "ok", "message": "Worker process stopped"}
        else:
            return {"status": "ok", "message": "Worker process was not running"}
    except Exception as e:
        logger.error(f"Failed to stop worker process: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Google Drive Auth — GET / POST
# ============================================================

@router.get("/auth/status")
async def get_gdrive_auth_status():
    """Check if Google Drive token.json exists and is valid."""
    status = get_auth_status()
    # logger.debug(f"Auth status check: {status['token_valid']}") # Too noisy for INFO
    return status


@router.post("/auth/reauth")
async def trigger_gdrive_reauth():
    """
    Trigger a full browser re-authentication flow.
    Note: This starts a local server in the backend to catch the callback.
    """
    logger.info("POST /auth/reauth triggered")
    try:
        # Import inside the function to ensure sys.path is already updated
        import setup_auth
        
        # Use functools.partial to pass arguments to run_in_executor
        import functools
        logger.info("Calling setup_auth.setup_auth(force=True) in executor...")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, functools.partial(setup_auth.setup_auth, force=True))
        
        logger.info("reauth flow completed")
        return {"status": "ok", "message": "Re-authentication task finished"}
    except ImportError as e:
        logger.error(f"Failed to import setup_auth: {e}")
        raise HTTPException(status_code=500, detail=f"Module import error: {e}")
    except Exception as e:
        logger.error(f"Re-authentication task failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# WebSocket — Live Logs from All Processes
# ============================================================

@router.websocket("/logs")
async def websocket_logs(websocket: WebSocket):
    """Stream live logs from aura.log to the admin dashboard."""
    await websocket.accept()
    logger.info("Admin log stream connected")

    try:
        log_file = dist_utils.get_logs_dir() / "aura.log"
    except (NameError, AttributeError):
        log_file = Path(__file__).parent.parent / "logs" / "aura.log"

    if not log_file.exists():
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.touch()

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            # Optionally grab the last 50 lines on connect
            import collections
            lines = collections.deque(f, 50)
            for line in lines:
                await _parse_and_send_log(websocket, line)

            # Seek to end after initial dump
            f.seek(0, os.SEEK_END)
            
            # Tail the file continuously
            while True:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.2)
                    continue
                await _parse_and_send_log(websocket, line)
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket log error: {e}")
    finally:
        logger.info("Admin log stream disconnected")


async def _parse_and_send_log(websocket: WebSocket, line: str):
    """Safely parse log string and send to frontend."""
    parts = line.strip().split(" | ")
    if len(parts) >= 4:
        try:
            # 2026-03-11 02:24:36 | INFO     | app.worker | msg...
            ts = parts[0].split(" ")[1] if " " in parts[0] else parts[0]
            lvl = parts[1].strip().lower()
            if lvl == "warning": lvl = "warn"
            if lvl == "critical": lvl = "error"
            
            entry = {
                "timestamp": ts,
                "level": lvl,
                "logger": parts[2].strip(),
                "message": " | ".join(parts[3:])
            }
        except IndexError:
            entry = {"timestamp": "", "level": "info", "logger": "raw", "message": line.strip()}
    else:
        entry = {"timestamp": "", "level": "info", "logger": "raw", "message": line.strip()}
        
    try:
        await websocket.send_json(entry)
    except Exception:
        pass


# ============================================================
# WebSocket — Process Status
# ============================================================

@router.websocket("/process-status")
async def websocket_process_status(websocket: WebSocket):
    """Stream live processing status every 2 seconds."""
    await websocket.accept()
    logger.info("Process status stream connected")

    try:
        while True:
            db = get_db()
            stats = db.get_stats()

            # Try to get progress from the worker's tracker
            progress_data = {}
            worker_states_data = {}
            try:
                from app.worker import progress, worker_states
                progress_data = progress.get_status()
                worker_states_data = worker_states.get_all_states()
            except Exception as e:
                logger.error(f"Error fetching worker states: {e}")

            # Upload stats
            upload_stats = {}
            try:
                upload_stats = db.get_upload_stats()
            except Exception:
                pass

            await websocket.send_json({
                "stats": stats,
                "progress": progress_data,
                "upload": upload_stats,
                "workers": worker_states_data,
            })

            await asyncio.sleep(1.0) # Faster updates for animations (1s)
    except WebSocketDisconnect:
        pass
    finally:
        logger.info("Process status stream disconnected")
