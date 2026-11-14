"""
# AURA - Guest Web Server (by DARK intelligence)

Serves ONLY the guest page and the endpoints it needs. It listens on the
local network (0.0.0.0) because guests' phones must reach it, so nothing
here may expose admin actions or other guests' photos:

  - No admin API. The PySide6 desktop app reads the database directly and
    never calls this server. (The old /api/admin router, written for the
    archived Next.js dashboard, is in _archive_tauri_v3/.)
  - A guest sees only their own gallery: /api/enroll returns a gallery_token
    (HMAC of the person ID with a per-install secret), and every gallery
    endpoint checks it and only serves files inside that person's folder.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from io import BytesIO

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn

# Import backend modules
import sys
try:
    import dist_utils
    backend_path = dist_utils.get_backend_dir()
except ImportError:
    backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.config import get_config
from app.db import get_db
from app.enrollment import enroll_user, get_enrollment_status, EnrollmentResult

# Setup logging (aura.log rolls over at 5 MB, 3 old copies; was unbounded)
try:
    import dist_utils
    _file_handler = dist_utils.rotating_log_handler("aura.log")
except (NameError, ImportError, AttributeError):
    _log_file = Path(__file__).parent.parent / "logs" / "aura.log"
    _log_file.parent.mkdir(parents=True, exist_ok=True)
    _file_handler = logging.FileHandler(_log_file, mode="a", encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), _file_handler],
    force=True
)
logger = logging.getLogger(__name__)


# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title="AURA",
    description="AI-powered event photo matching and sharing",
    version="2.0.0",
    # No public API explorer on the venue network
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# No CORS middleware: the guest page is served from this same server, so
# browsers need no cross-origin access. Do not add an admin router here.

MAX_SELFIE_BYTES = 15 * 1024 * 1024
SELFIE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
GALLERY_SUFFIXES = {".jpg", ".jpeg", ".png"}


# ============================================================
# Guest gallery access tokens (shared with the desktop app)
# ============================================================
from app.gallery_access import make_gallery_token, token_is_valid


def _person_folder_for(person_id: int, token: str) -> Path:
    """Check the token and return that person's folder, or raise 404.
    Bad tokens get the same 404 as unknown people, so IDs can't be probed."""
    if not token_is_valid(person_id, token):
        raise HTTPException(status_code=404, detail="Gallery not found")
    person = get_db().get_person_by_id(person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Gallery not found")
    return get_config().people_dir / person.name


def _resolve_in_folder(folder: Path, relative: str) -> Path:
    """Resolve a gallery-relative path (e.g. 'Solo/x.jpg') and refuse anything
    outside the person's folder or with a non-photo extension."""
    base = folder.resolve()
    target = (base / relative).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=404, detail="Photo not found")
    if target.suffix.lower() not in GALLERY_SUFFIXES or not target.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")
    return target


# ============================================================
# Response Models
# ============================================================
class EnrollmentResponse(BaseModel):
    success: bool
    person_id: Optional[int] = None
    person_name: Optional[str] = None
    match_confidence: float = 0.0
    message: str
    solo_count: int = 0
    group_count: int = 0
    gallery_token: Optional[str] = None


class StatsResponse(BaseModel):
    total_photos: int
    total_faces: int
    total_persons: int
    total_enrolled: int
    photos_by_status: dict


class PhotoItem(BaseModel):
    path: str
    filename: str
    thumbnail: Optional[str] = None


# ============================================================
# API Endpoints
# ============================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "aura"}


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """Get processing statistics."""
    try:
        db = get_db()
        stats = db.get_stats()
        enrollment_status = get_enrollment_status()
        
        return StatsResponse(
            total_photos=sum(stats.get("photos_by_status", {}).values()),
            total_faces=stats.get("total_faces", 0),
            total_persons=stats.get("total_persons", 0),
            total_enrolled=enrollment_status.get("total_enrolled", 0),
            photos_by_status=stats.get("photos_by_status", {})
        )
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return StatsResponse(
            total_photos=0,
            total_faces=0,
            total_persons=0,
            total_enrolled=0,
            photos_by_status={}
        )


@app.post("/api/enroll", response_model=EnrollmentResponse)
async def enroll(
    selfie: UploadFile = File(...),
    name: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    consent: bool = Form(True)
):
    """
    Enroll a user by matching their selfie to existing photo clusters.
    """
    config = get_config()
    
    # Validate file type
    if not (selfie.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Read with a size cap so one upload can't fill the disk
    content = await selfie.read(MAX_SELFIE_BYTES + 1)
    if len(content) > MAX_SELFIE_BYTES:
        raise HTTPException(status_code=413, detail="Photo is too large (max 15 MB)")

    # Save uploaded selfie temporarily
    temp_dir = config.event_root / "Admin" / "Uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Server-generated filename: never use the phone's filename in the path
    import uuid
    suffix = Path(selfie.filename or "").suffix.lower()
    if suffix not in SELFIE_SUFFIXES:
        suffix = ".jpg"
    temp_path = temp_dir / f"selfie_{uuid.uuid4().hex}{suffix}"

    result = None
    try:
        with open(temp_path, "wb") as f:
            f.write(content)
        
        logger.info(f"Processing enrollment for: {name}")
        
        # Process enrollment
        result: EnrollmentResult = enroll_user(
            selfie_path=temp_path,
            user_name=name,
            phone=phone if phone else None,
            email=email if email else None,
            consent_given=consent
        )
        
        # Count photos
        solo_count = 0
        group_count = 0
        
        if result.success and result.person_name:
            person_folder = config.people_dir / result.person_name
            solo_folder = person_folder / "Solo"
            group_folder = person_folder / "Group"
            
            if solo_folder.exists():
                solo_count = len([f for f in solo_folder.iterdir() if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png']])
            if group_folder.exists():
                group_count = len([f for f in group_folder.iterdir() if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png']])
        
        return EnrollmentResponse(
            success=result.success,
            person_id=result.person_id,
            person_name=result.person_name,
            match_confidence=result.match_confidence,
            message=result.message,
            solo_count=solo_count,
            group_count=group_count,
            gallery_token=make_gallery_token(result.person_id)
            if result.success and result.person_id is not None else None,
        )

    except Exception as e:
        logger.exception(f"Enrollment error: {e}")
        # Details go to the log, not to the guest's phone
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")
    
    finally:
        # Delete the uploaded selfie (privacy; it used to be kept forever).
        # On success a resized copy is kept as 00_REFERENCE_SELFIE.jpg in the
        # guest's folder and recorded in the DB; if that copy is missing, the
        # DB points at this file, so keep it in that one case.
        try:
            reference = None
            if result is not None and result.success and result.person_name:
                reference = config.people_dir / result.person_name / "00_REFERENCE_SELFIE.jpg"
            if reference is None or reference.exists():
                temp_path.unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"Could not delete uploaded selfie {temp_path.name}: {e}")


@app.get("/api/gallery/{person_id}/photos")
async def get_gallery_photos(
    person_id: int,
    token: str = Query(""),
    category: str = Query("solo", pattern="^(solo|group)$"),
):
    """List one guest's photos. Requires the gallery_token from /api/enroll.
    Paths are returned relative to the guest's folder (e.g. 'Solo/x.jpg')."""
    person_folder = _person_folder_for(person_id, token)
    category_folder = person_folder / category.capitalize()
    if not category_folder.is_dir():
        return []

    return [
        PhotoItem(path=f"{category_folder.name}/{f.name}", filename=f.name)
        for f in sorted(category_folder.iterdir())
        if f.is_file() and f.suffix.lower() in GALLERY_SUFFIXES
    ]


@app.get("/api/gallery/{person_id}/info")
async def get_gallery_info(person_id: int, token: str = Query("")):
    """Name shown at the top of a gallery opened from a direct link."""
    folder = _person_folder_for(person_id, token)
    return {"person_id": person_id, "person_name": folder.name}


@app.get("/api/gallery/{person_id}/photo")
async def get_gallery_photo(person_id: int, path: str = Query(...), token: str = Query("")):
    """Serve one full-resolution photo from the guest's own folder."""
    photo_path = _resolve_in_folder(_person_folder_for(person_id, token), path)
    return FileResponse(photo_path, media_type="image/jpeg", filename=photo_path.name)


@app.get("/api/gallery/{person_id}/thumbnail")
async def get_gallery_thumbnail(person_id: int, path: str = Query(...), token: str = Query("")):
    """Serve a thumbnail of one photo from the guest's own folder.
    Uses the pre-made thumbnail in Processed/ when there is one."""
    photo_path = _resolve_in_folder(_person_folder_for(person_id, token), path)

    thumbnail_path = get_config().processed_dir / f"{photo_path.stem}_thumb.jpg"
    if thumbnail_path.exists():
        return FileResponse(thumbnail_path, media_type="image/jpeg")

    try:
        from PIL import Image
        with Image.open(photo_path) as img:
            img.thumbnail((400, 400), Image.LANCZOS)
            if img.mode != "RGB":
                img = img.convert("RGB")
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="image/jpeg")
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        return FileResponse(photo_path, media_type="image/jpeg")


# Removed on purpose (2026-11-14): /api/persons, /api/photos/{name},
# /api/photo?path=, /api/thumbnail?path=. They let anyone on the network list
# every person and view anyone's photos. Use the /api/gallery/... endpoints.


# ============================================================
# Static Files
# ============================================================
try:
    frontend_dir = dist_utils.get_frontend_dir()
except (NameError, AttributeError):
    frontend_dir = Path(__file__).parent

def _static_file(subdir: str, filename: str) -> Path:
    """Return frontend/<subdir>/<filename> only if it is a plain file in that folder."""
    folder = (frontend_dir / subdir).resolve()
    target = (folder / filename).resolve()
    if target.parent != folder or not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return target

# Serve CSS files
@app.get("/css/{filename}")
async def serve_css(filename: str):
    return FileResponse(_static_file("css", filename), media_type="text/css")

# Serve JS files
@app.get("/js/{filename}")
async def serve_js(filename: str):
    return FileResponse(_static_file("js", filename), media_type="application/javascript")

# Serve index.html for root and all non-API routes
@app.get("/")
async def serve_index():
    return FileResponse(frontend_dir / "index.html", media_type="text/html")

@app.get("/{path:path}")
async def serve_catch_all(path: str):
    # Don't serve API routes
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    # Serve index.html for SPA routing
    return FileResponse(frontend_dir / "index.html", media_type="text/html")


# ============================================================
# Main Entry Point
# ============================================================
def main():
    """Run the guest web server standalone (developer use).

    The desktop app starts it itself (process_manager / run_pyside.py
    --run-server). 0.0.0.0 is intentional: guests' phones on the venue
    Wi-Fi must reach it. That is only safe because this server has no admin
    endpoints; keep it that way.
    """
    # Change to backend directory for proper imports
    os.chdir(str(backend_path))

    logger.info("Starting AURA Guest Web Server (by DARK intelligence)...")
    logger.info(f"Backend path: {backend_path}")

    port = dist_utils.pick_guest_port()
    logger.info(f"Guest page on port {port}")
    uvicorn.run("server:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
