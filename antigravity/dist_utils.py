"""
dist_utils — Centralized path resolution for dev mode AND frozen (PyInstaller) mode.
"""

APP_VERSION = "3.0.0"

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
    """Return the directory containing the .exe (frozen) or backend_entry.py (dev)."""
    if is_frozen():
        return Path(sys.executable).parent.resolve()
    else:
        # In dev mode, this is the project root (where backend_entry.py lives)
        return Path(__file__).parent.resolve()


# ─────────────────────────────────────────────────────────
# Project Structure Paths (read-only in frozen mode)
# ─────────────────────────────────────────────────────────

def get_project_root() -> Path:
    """
    Return the project root directory.

    In dev mode:  the folder containing this file (and backend_entry.py).
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
    """Return the aura_app/ package directory."""
    return get_bundled_root() / "aura_app"


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
        logger.info(f"[Paths] Checking bundled models at: {bundled_models}")
        if bundled_models.exists():
            return bundled_models
        else:
            logger.warning(f"[Paths] Bundled models MISSING at {bundled_models}")

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


# Google Drive permission AURA asks for (single source for cloud.py,
# setup_auth.py and the Connect Google Drive window).
# drive.file = only files and folders AURA itself created (2026-11-14; was
# the full "drive" scope, which Google only approves after a paid yearly
# security assessment). Sign-ins that already granted full "drive" keep
# working, since it includes drive.file. See infos/GOOGLE_DRIVE_SETUP.md.
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

SECRETS_DIR_NAME = "AURA-secrets"


def get_secrets_dir() -> Path:
    """Folder holding the private files: .env, credentials.json (Google
    sign-in client), token.json (Google sign-in), service_account.json.

    Installed app: the user data folder (%LOCALAPPDATA%\\AURA), as before.
    Development: %USERPROFILE%\\AURA-secrets when it exists, so the secrets
    are not inside the project folder (where git or a zip could pick them
    up). Override with the AURA_SECRETS_DIR environment variable.
    Falls back to the user data folder (= project root in development).
    """
    override = os.environ.get("AURA_SECRETS_DIR")
    if override:
        return Path(override)
    if not is_frozen():
        dev_dir = Path.home() / SECRETS_DIR_NAME
        if dev_dir.is_dir():
            return dev_dir
    return get_user_data_dir()


def get_env_file_path() -> Path:
    """Return the path to the .env file (in the secrets folder)."""
    return get_secrets_dir() / ".env"


# ─────────────────────────────────────────────────────────
# Guest web server port
# ─────────────────────────────────────────────────────────
# 8000 was hardcoded; if another program used it, the guest page silently
# never started. Now the first free port from 8000 up is picked when
# processing starts and recorded here, so the server, dashboard and setup
# wizard (QR code) all show the same address.

DEFAULT_GUEST_PORT = 8000
_GUEST_PORT_FILE = "guest_port.txt"


def port_is_free(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def pick_guest_port(preferred: int = DEFAULT_GUEST_PORT, tries: int = 50) -> int:
    """Find a free port (preferred first), remember it, and return it."""
    port = next((p for p in range(preferred, preferred + tries) if port_is_free(p)), preferred)
    try:
        (get_user_data_dir() / _GUEST_PORT_FILE).write_text(str(port), encoding="utf-8")
    except OSError:
        pass
    os.environ["AURA_GUEST_PORT"] = str(port)
    return port


def get_guest_port() -> int:
    """The guest page port: this process's setting, else the last one picked."""
    value = os.environ.get("AURA_GUEST_PORT")
    if not value:
        try:
            value = (get_user_data_dir() / _GUEST_PORT_FILE).read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
    try:
        return int(value)
    except ValueError:
        return DEFAULT_GUEST_PORT


def set_env_values(updates: dict) -> None:
    """Update keys in the user's .env (adding any that are missing) and in
    os.environ, keeping comments and other lines as they are."""
    env_path = get_env_file_path()
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    remaining = {k: str(v) for k, v in updates.items()}
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                continue
        out.append(line)
    out.extend(f"{k}={v}" for k, v in remaining.items())
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    for k, v in updates.items():
        os.environ[k] = str(v)


def get_db_path() -> Path:
    """Return the default database file path."""
    return get_user_data_dir() / "data" / "wedding.db"


def get_logs_dir() -> Path:
    """Return the logs directory."""
    logs = get_user_data_dir() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs


LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUPS = 3
SESSION_LOGS_KEPT = 30


def rotating_log_handler(filename: str):
    """File handler for logs/<filename> that rolls over at 5 MB, keeping 3 old
    copies (logs used to grow forever). Each log file must have one writer
    process only."""
    from logging.handlers import RotatingFileHandler
    return RotatingFileHandler(get_logs_dir() / filename, maxBytes=LOG_MAX_BYTES,
                               backupCount=LOG_BACKUPS, encoding="utf-8", delay=True)


def prune_session_logs(keep: int = SESSION_LOGS_KEPT) -> None:
    """Keep only the newest `keep` per-launch session logs."""
    try:
        logs = sorted(get_logs_dir().glob("session_*.txt"), key=lambda p: p.stat().st_mtime)
        for old in logs[:-keep]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError:
        pass


def get_credentials_dir() -> Path:
    """Return the directory for credential files (service_account.json, etc.)."""
    return get_secrets_dir()


def get_token_path() -> Path:
    """
    Return where THIS user's Google sign-in (token.json) is stored.

    It is created by the "Connect Google Drive" sign-in and is never shipped
    in the installer: every user signs in with their own Google account.
    """
    return get_secrets_dir() / "token.json"


def get_oauth_client_path() -> Optional[Path]:
    """
    Return the OAuth client file (credentials.json) used to open the Google
    sign-in page, or None if it is missing.

    This file identifies the AURA app to Google (a "Desktop app" OAuth client).
    Google treats it as non-secret for installed apps, so it is safe to ship
    in the installer. A copy in the user data folder takes priority, so a user
    can supply their own client if needed.
    """
    for candidate in (get_secrets_dir() / "credentials.json",
                      get_user_data_dir() / "credentials.json",
                      get_bundled_root() / "credentials.json"):
        if candidate.exists():
            return candidate
    return None


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

    # Only a clean settings template is copied. No credentials are copied:
    # the installer must never carry the developer's token.json,
    # service_account.json or personal .env. Each user connects their own
    # Google Drive from the app (Auth dialog), which writes get_token_path().
    env_template = bundled / ".env.template"
    env_dst = get_env_file_path()
    if not env_dst.exists():
        if env_template.exists():
            shutil.copy2(env_template, env_dst)
            logger.info(f"[Bootstrap] Created default settings: {env_dst}")
        else:
            logger.warning("[Bootstrap] .env.template missing from install; built-in defaults will be used")

    if get_oauth_client_path() is None:
        logger.warning("[Bootstrap] credentials.json (Google sign-in client) not found; "
                       "Google Drive sign-in will be unavailable")

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
