"""
dist_utils — Centralized path resolution for dev mode AND frozen (PyInstaller) mode.

This module is the SINGLE SOURCE OF TRUTH for all directory paths in the
entire application.  Every file that currently uses `Path(__file__).parent...`
to find the project root should instead import from here:

    from dist_utils import get_project_root, get_backend_dir, ...

How it works:
  • DEV MODE (running `python run_pyside.py` directly):
      - `get_project_root()` → the folder containing `run_pyside.py`
      - All sub-paths resolve relative to that folder exactly as before.

  • FROZEN MODE (running AURA.exe via PyInstaller --onedir):
      - `sys.frozen` is set by PyInstaller.
      - `sys._MEIPASS` points to the temp extraction directory for bundled data.
      - `sys.executable` points to the .exe file itself.
      - We use the *directory of the .exe* as the "project root" for user data
        (EventRoot, .env, credentials, database, logs).
      - We use `sys._MEIPASS` for bundled *read-only* assets
        (source code, frontend HTML/CSS/JS, ONNX models, icons).

  • USER DATA (AppData):
      - Writable config (.env, database, credentials, logs) must NOT live in
        `C:\\Program Files\\...` because that's read-only on modern Windows.
      - We store user data under `%LOCALAPPDATA%\\AURA\\`.
      - On first launch, if no .env exists in AppData, we copy the bundled
        template from the install directory.

Directory map:

    get_project_root()     → project root (source root in dev, exe dir in frozen)
    get_backend_dir()      → backend/
    get_frontend_dir()     → frontend/
    get_whatsapp_dir()     → whatsapp_tool/
    get_assets_dir()       → WeddingFFapp_pyside/assets/
    get_models_dir()       → .insightface/models/buffalo_l/  (bundled models)
    get_user_data_dir()    → writable folder for .env, DB, credentials, logs
"""

import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# App identifier — used for AppData folder name
APP_NAME = "AURA"
COMPANY_NAME = "DARK intelligence"


# ─────────────────────────────────────────────────────────
# Core Detection
# ─────────────────────────────────────────────────────────

def is_frozen() -> bool:
    """Return True if running inside a PyInstaller bundle."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def _get_meipass() -> Path:
    """Return the PyInstaller extraction directory (bundled read-only assets)."""
    return Path(sys._MEIPASS)


def _get_exe_dir() -> Path:
    """Return the directory containing the .exe (frozen) or run_pyside.py (dev)."""
    if is_frozen():
        return Path(sys.executable).parent.resolve()
    else:
        # In dev mode, this is the project root (where run_pyside.py lives)
        return Path(__file__).parent.resolve()


# ─────────────────────────────────────────────────────────
# Project Structure Paths (read-only in frozen mode)
# ─────────────────────────────────────────────────────────

def get_project_root() -> Path:
    """
    Return the project root directory.

    In dev mode:  the folder containing this file (and run_pyside.py).
    In frozen mode: the folder where the .exe lives.

    This is used for paths that must be writable (EventRoot, logs, etc.)
    in dev mode, but in frozen mode those go to user_data_dir instead.
    """
    return _get_exe_dir()


def get_bundled_root() -> Path:
    """
    Return the root for bundled (read-only) assets.

    In dev mode:  same as project root.
    In frozen mode: sys._MEIPASS (the temp extraction folder).
    """
    if is_frozen():
        return _get_meipass()
    return get_project_root()


def get_backend_dir() -> Path:
    """Return the backend/ directory (contains app/ with all Python modules)."""
    return get_bundled_root() / "backend"


def get_frontend_dir() -> Path:
    """Return the frontend/ directory (contains server.py, HTML, CSS, JS)."""
    return get_bundled_root() / "frontend"


def get_whatsapp_dir() -> Path:
    """Return the whatsapp_tool/ directory."""
    return get_bundled_root() / "whatsapp_tool"


def get_pyside_package_dir() -> Path:
    """Return the WeddingFFapp_pyside/ package directory."""
    return get_bundled_root() / "WeddingFFapp_pyside"


def get_assets_dir() -> Path:
    """Return the assets/ directory inside the PySide package."""
    return get_pyside_package_dir() / "assets"


def get_icon_path() -> Path:
    """Return the path to the app icon (logo.png)."""
    return get_assets_dir() / "logo.png"


# ─────────────────────────────────────────────────────────
# InsightFace Models
# ─────────────────────────────────────────────────────────

def get_models_dir() -> Path:
    """
    Return the directory containing InsightFace ONNX models.

    In dev mode:  ~/.insightface/models/buffalo_l/  (standard cache)
    In frozen mode: <bundled_root>/models/buffalo_l/  (pre-packaged)
    """
    if is_frozen():
        bundled_models = get_bundled_root() / "models" / "buffalo_l"
        if bundled_models.exists():
            return bundled_models

    # Fall back to the default InsightFace cache location
    return Path.home() / ".insightface" / "models" / "buffalo_l"


def get_insightface_root() -> Path:
    """
    Return the root for InsightFace model storage.

    InsightFace expects a directory containing a 'models/' subfolder.
    In frozen mode we point it to our bundled models.
    In dev mode we use the standard ~/.insightface/ cache.
    """
    if is_frozen():
        bundled = get_bundled_root() / "models"
        if bundled.exists():
            return get_bundled_root()

    return Path.home() / ".insightface"


# ─────────────────────────────────────────────────────────
# User Data Directory (writable — for .env, DB, credentials, logs)
# ─────────────────────────────────────────────────────────

def get_user_data_dir() -> Path:
    """
    Return the writable user data directory.

    In dev mode:  same as project root (everything is in one place during dev).
    In frozen mode:  %LOCALAPPDATA%/WeddingFaceForward/
                     e.g. C:\\Users\\Ranjith\\AppData\\Local\\WeddingFaceForward\\

    This is where we store:
      • .env (user configuration)
      • data/wedding.db (SQLite database)
      • service_account.json (Google credentials)
      • credentials.json (OAuth client ID)
      • token.json (OAuth token — auto-generated)
      • logs/ (session logs)
      • EventRoot/ (if user hasn't configured a custom path)
    """
    if is_frozen():
        appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        user_dir = appdata / APP_NAME
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    return get_project_root()


def get_env_file_path() -> Path:
    """Return the path to the .env file (in user data dir)."""
    return get_user_data_dir() / ".env"


def get_db_path() -> Path:
    """Return the default database file path."""
    return get_user_data_dir() / "data" / "wedding.db"


def get_logs_dir() -> Path:
    """Return the logs directory."""
    logs = get_user_data_dir() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs


def get_credentials_dir() -> Path:
    """Return the directory for credential files (service_account.json, etc.)."""
    return get_user_data_dir()


# ─────────────────────────────────────────────────────────
# First-Launch Bootstrap (frozen mode only)
# ─────────────────────────────────────────────────────────

def bootstrap_user_data():
    """
    On first launch in frozen mode, copy template files from the bundled
    install directory to the user's writable AppData folder.

    This runs ONCE — subsequent launches find the files already in place.
    In dev mode this is a no-op.
    """
    if not is_frozen():
        return  # Nothing to do in dev mode

    user_dir = get_user_data_dir()
    bundled = get_bundled_root()

    # Files to bootstrap from the install bundle → user data
    files_to_copy = [
        (".env", ".env"),
        ("credentials.json", "credentials.json"),
        ("token.json", "token.json"),
        ("backend/service_account.json", "service_account.json"),
    ]

    for src_relative, dst_name in files_to_copy:
        src = bundled / src_relative
        dst = user_dir / dst_name

        if not dst.exists() and src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            logger.info(f"[Bootstrap] Copied {src_relative} → {dst}")

    # Ensure required subdirectories exist
    subdirs = ["data", "logs"]
    for subdir in subdirs:
        (user_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Ensure EventRoot exists (default location inside user data)
    event_root = user_dir / "EventRoot"
    for subfolder in ["Incoming", "Processed", "People",
                      "Admin/NoFaces", "Admin/Errors", "Admin/Uploads"]:
        (event_root / subfolder).mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────
# sys.path Setup (ensures imports work in both modes)
# ─────────────────────────────────────────────────────────

def setup_sys_path():
    """
    Add backend/ and frontend/ to sys.path so that `from app.xxx import ...`
    and `from server import ...` work correctly in both dev and frozen modes.
    """
    backend = str(get_backend_dir())
    frontend = str(get_frontend_dir())

    for path in [backend, frontend]:
        if path not in sys.path:
            sys.path.insert(0, path)


# ─────────────────────────────────────────────────────────
# Debug / Diagnostics
# ─────────────────────────────────────────────────────────

def print_diagnostics():
    """Print all resolved paths — useful for debugging distribution issues."""
    print("=" * 60)
    print("  AURA (by DARK intelligence) — Path Diagnostics")
    print("=" * 60)
    print(f"  Frozen:            {is_frozen()}")
    print(f"  sys.executable:    {sys.executable}")
    if is_frozen():
        print(f"  sys._MEIPASS:      {sys._MEIPASS}")
    print(f"  Project Root:      {get_project_root()}")
    print(f"  Bundled Root:      {get_bundled_root()}")
    print(f"  Backend Dir:       {get_backend_dir()}")
    print(f"  Frontend Dir:      {get_frontend_dir()}")
    print(f"  WhatsApp Dir:      {get_whatsapp_dir()}")
    print(f"  Assets Dir:        {get_assets_dir()}")
    print(f"  Models Dir:        {get_models_dir()}")
    print(f"  User Data Dir:     {get_user_data_dir()}")
    print(f"  .env Path:         {get_env_file_path()}")
    print(f"  DB Path:           {get_db_path()}")
    print(f"  Logs Dir:          {get_logs_dir()}")
    print(f"  Icon Path:         {get_icon_path()}")
    print("=" * 60)
    print()

    # Verify key files exist
    checks = [
        ("Backend dir exists",  get_backend_dir().exists()),
        ("Frontend dir exists", get_frontend_dir().exists()),
        (".env file exists",    get_env_file_path().exists()),
        ("Icon exists",         get_icon_path().exists()),
        ("Models dir exists",   get_models_dir().exists()),
    ]
    for label, ok in checks:
        status = "[OK]" if ok else "[MISSING]"
        print(f"  {status}  {label}")
    print()


# ─────────────────────────────────────────────────────────
# Module-level initialization
# ─────────────────────────────────────────────────────────

# Auto-setup sys.path on import so any file that does
# `import dist_utils` immediately gets correct import paths.
setup_sys_path()
