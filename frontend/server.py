"""
Wedding Face Forward - FastAPI Web Server
Provides REST API endpoints for the frontend to interact with the photo processing backend.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from io import BytesIO

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn

# Import backend modules
import sys
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.config import get_config
from app.db import get_db
from app.enrollment import enroll_user, get_enrollment_status, EnrollmentResult

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title="Wedding Face Forward",
    description="AI-powered event photo matching and sharing",
    version="1.0.0"
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    return {"status": "healthy", "service": "wedding-face-forward"}


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
    if not selfie.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Save uploaded selfie temporarily
    temp_dir = config.event_root / "Admin" / "Uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    import uuid
    temp_filename = f"selfie_{uuid.uuid4().hex[:8]}_{selfie.filename}"
    temp_path = temp_dir / temp_filename
    
    try:
        # Save file
        content = await selfie.read()
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
            group_count=group_count
        )
        
    except Exception as e:
        logger.error(f"Enrollment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Clean up temp file (keep for debugging in development)
        # temp_path.unlink(missing_ok=True)
        pass


@app.get("/api/photos/{person_name}")
async def get_photos(
    person_name: str,
    category: str = Query("solo", pattern="^(solo|group)$")
):
    """
    Get list of photos for a person in a specific category (solo or group).
    """
    config = get_config()
    
    # Find person folder (could be Person_XXX or enrolled name)
    person_folder = config.people_dir / person_name
    
    if not person_folder.exists():
        raise HTTPException(status_code=404, detail=f"Person '{person_name}' not found")
    
    # Get photos from the appropriate subfolder
    category_folder = person_folder / category.capitalize()
    
    if not category_folder.exists():
        return []
    
    photos = []
    for file in sorted(category_folder.iterdir()):
        if file.is_file() and file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
            photos.append(PhotoItem(
                path=str(file),
                filename=file.name,
                thumbnail=None  # Will be fetched via thumbnail endpoint
            ))
    
    return photos


@app.get("/api/photo")
async def get_photo(path: str = Query(...)):
    """Serve a full-resolution photo."""
    photo_path = Path(path)
    
    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="Photo not found")
    
    # Security: ensure path is within event root
    config = get_config()
    try:
        photo_path.resolve().relative_to(config.event_root.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        photo_path,
        media_type="image/jpeg",
        filename=photo_path.name
    )


@app.get("/api/thumbnail")
async def get_thumbnail(path: str = Query(...)):
    """
    Serve a thumbnail for a photo.
    First checks if a thumbnail exists in Processed/, otherwise generates one on the fly.
    """
    photo_path = Path(path)
    config = get_config()
    
    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="Photo not found")
    
    # Security check
    try:
        photo_path.resolve().relative_to(config.event_root.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check for existing thumbnail in Processed folder
    # The thumbnail would have the same name but in the Processed folder
    thumbnail_name = f"{photo_path.stem}_thumb.jpg"
    thumbnail_path = config.processed_dir / thumbnail_name
    
    if thumbnail_path.exists():
        return FileResponse(thumbnail_path, media_type="image/jpeg")
    
    # Generate thumbnail on the fly
    try:
        from PIL import Image
        
        img = Image.open(photo_path)
        
        # Resize to thumbnail
        max_size = 400
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        
        # Convert to RGB if necessary
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Save to bytes
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        
        return StreamingResponse(buffer, media_type="image/jpeg")
        
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        # Fall back to serving the original
        return FileResponse(photo_path, media_type="image/jpeg")


@app.get("/api/persons")
async def list_persons():
    """List all person clusters with their enrollment status."""
    db = get_db()
    config = get_config()
    
    persons = db.get_all_persons()
    enrollments = {e.person_id: e for e in db.get_all_enrollments()}
    
    result = []
    for person in persons:
        enrollment = enrollments.get(person.id)
        
        # Count photos
        person_folder = config.people_dir / person.name
        solo_count = 0
        group_count = 0
        
        if person_folder.exists():
            solo_folder = person_folder / "Solo"
            group_folder = person_folder / "Group"
            
            if solo_folder.exists():
                solo_count = len([f for f in solo_folder.iterdir() if f.is_file()])
            if group_folder.exists():
                group_count = len([f for f in group_folder.iterdir() if f.is_file()])
        
        result.append({
            "id": person.id,
            "name": person.name,
            "face_count": person.face_count,
            "solo_photos": solo_count,
            "group_photos": group_count,
            "enrolled": enrollment is not None,
            "enrolled_name": enrollment.user_name if enrollment else None,
            "enrolled_at": str(enrollment.created_at) if enrollment else None
        })
    
    return result


# ============================================================
# Static Files
# ============================================================
frontend_dir = Path(__file__).parent

# Serve CSS files
@app.get("/css/{filename}")
async def serve_css(filename: str):
    css_path = frontend_dir / "css" / filename
    if css_path.exists():
        return FileResponse(css_path, media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS file not found")

# Serve JS files
@app.get("/js/{filename}")
async def serve_js(filename: str):
    js_path = frontend_dir / "js" / filename
    if js_path.exists():
        return FileResponse(js_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="JS file not found")

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
    """Run the web server."""
    # Change to backend directory for proper imports
    os.chdir(str(backend_path))
    
    logger.info("Starting Wedding Face Forward Web Server...")
    logger.info(f"Backend path: {backend_path}")
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(Path(__file__).parent)]
    )


if __name__ == "__main__":
    main()
