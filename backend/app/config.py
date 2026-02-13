"""
Configuration module for Wedding Face Forward Phase 2 Backend.

Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Tuple
from dotenv import load_dotenv

# Load .env file
# Try project root first, then backend folder
BASE_DIR = Path(__file__).parent.parent.parent
BACKEND_DIR = Path(__file__).parent.parent

if (BASE_DIR / ".env").exists():
    load_dotenv(BASE_DIR / ".env")
elif (BACKEND_DIR / ".env").exists():
    load_dotenv(BACKEND_DIR / ".env")
else:
    load_dotenv()


@dataclass
class Config:
    """Application configuration loaded from environment variables."""
    
    # Paths
    event_root: Path
    db_path: Path
    
    # Processing
    worker_count: int
    cluster_threshold: float
    max_image_size: int
    thumbnail_size: int
    
    # Watcher
    scan_interval: int
    supported_extensions: Tuple[str, ...]
    
    # Modes
    dry_run: bool
    log_level: str
    use_hardlinks: bool
    
    # Cloud
    google_credentials_file: Path
    drive_root_folder_id: str
    
    # Upload settings
    upload_timeout_connect: int
    upload_timeout_read: int
    upload_max_retries: int
    upload_retry_delay: int
    upload_batch_size: int
    upload_queue_enabled: bool
    folder_sync_interval: int  # Seconds between folder structure sync checks
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        # Get base paths
        event_root = Path(os.getenv("EVENT_ROOT", "./EventRoot")).resolve()
        db_path = Path(os.getenv("DB_PATH", "./data/wedding.db")).resolve()
        
        # Parse extensions
        ext_str = os.getenv("SUPPORTED_EXTENSIONS", ".jpg,.jpeg,.png,.webp,.avif,.heic,.heif,.bmp,.tiff,.tif,.gif,.cr2,.nef,.arw,.dng,.orf,.rw2,.raf,.pef")
        extensions = tuple(ext.strip().lower() for ext in ext_str.split(","))
        
        # Resolve credentials file path
        creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
        creds_path = Path(creds_file)
        if not creds_path.is_absolute():
            # Try current working directory
            if not creds_path.exists():
                # Try backend directory
                backend_creds = BACKEND_DIR / creds_file
                if backend_creds.exists():
                    creds_path = backend_creds
        
        return cls(
            event_root=event_root,
            db_path=db_path.resolve(), # Ensure db_path is resolved relative to CWD
            worker_count=int(os.getenv("WORKER_COUNT", "4")),
            cluster_threshold=float(os.getenv("CLUSTER_THRESHOLD", "0.6")),
            max_image_size=int(os.getenv("MAX_IMAGE_SIZE", "2048")),
            thumbnail_size=int(os.getenv("THUMBNAIL_SIZE", "300")),
            scan_interval=int(os.getenv("SCAN_INTERVAL", "30")),
            supported_extensions=extensions,
            dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            use_hardlinks=os.getenv("USE_HARDLINKS", "true").lower() == "true",
            google_credentials_file=creds_path.resolve(),
            drive_root_folder_id=os.getenv("DRIVE_ROOT_FOLDER_ID", ""),
            upload_timeout_connect=int(os.getenv("UPLOAD_TIMEOUT_CONNECT", "10")),
            upload_timeout_read=int(os.getenv("UPLOAD_TIMEOUT_READ", "30")),
            upload_max_retries=int(os.getenv("UPLOAD_MAX_RETRIES", "3")),
            upload_retry_delay=int(os.getenv("UPLOAD_RETRY_DELAY", "2")),
            upload_batch_size=int(os.getenv("UPLOAD_BATCH_SIZE", "5")),
            upload_queue_enabled=os.getenv("UPLOAD_QUEUE_ENABLED", "true").lower() == "true",
            folder_sync_interval=int(os.getenv("FOLDER_SYNC_INTERVAL", "10")),
        )
    
    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        directories = [
            self.event_root / "Incoming",
            self.event_root / "Processed",
            self.event_root / "People",
            self.event_root / "Admin" / "NoFaces",
            self.event_root / "Admin" / "Errors",
            self.db_path.parent,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    @property
    def incoming_dir(self) -> Path:
        return self.event_root / "Incoming"
    
    @property
    def processed_dir(self) -> Path:
        return self.event_root / "Processed"
    
    @property
    def people_dir(self) -> Path:
        return self.event_root / "People"
    
    @property
    def no_faces_dir(self) -> Path:
        return self.event_root / "Admin" / "NoFaces"
    
    @property
    def errors_dir(self) -> Path:
        return self.event_root / "Admin" / "Errors"


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reset_config() -> None:
    """Reset the global config (useful for testing)."""
    global _config
    _config = None
