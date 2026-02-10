"""
Image processor module for Wedding Face Forward Phase 2 Backend.

Handles RAW→JPEG conversion, normalization, thumbnail generation,
face detection, and embedding extraction using InsightFace.
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ExifTags

from .config import get_config

logger = logging.getLogger(__name__)

# InsightFace imports (lazy loaded)
_face_analyzer = None


@dataclass
class DetectedFace:
    """Represents a detected face with bounding box and embedding."""
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    embedding: np.ndarray  # 512-dim vector
    confidence: float


def _get_face_analyzer():
    """Lazy load the InsightFace face analyzer."""
    global _face_analyzer
    if _face_analyzer is None:
        try:
            from insightface.app import FaceAnalysis
            
            logger.info("Loading InsightFace model (buffalo_l)...")
            _face_analyzer = FaceAnalysis(
                name="buffalo_l",
                providers=["CPUExecutionProvider"]
            )
            _face_analyzer.prepare(ctx_id=-1, det_size=(640, 640))
            logger.info("InsightFace model loaded successfully")
        except ImportError as e:
            logger.error(f"InsightFace not installed: {e}")
            raise RuntimeError("Please install insightface: pip install insightface onnxruntime")
    return _face_analyzer


def is_raw_file(file_path: Path) -> bool:
    """Check if the file is a RAW image format."""
    raw_extensions = {".cr2", ".nef", ".arw", ".dng", ".orf", ".rw2", ".raf", ".pef"}
    return file_path.suffix.lower() in raw_extensions


def convert_raw_to_jpeg(raw_path: Path, output_path: Path) -> bool:
    """
    Convert RAW file to JPEG using rawpy.
    Returns True on success, False on failure.
    """
    try:
        import rawpy
        
        logger.debug(f"Converting RAW: {raw_path}")
        with rawpy.imread(str(raw_path)) as raw:
            # Process with sensible defaults
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=False,
                no_auto_bright=False,
                output_bps=8
            )
        
        # Save as JPEG
        img = Image.fromarray(rgb)
        img.save(output_path, "JPEG", quality=95)
        logger.debug(f"RAW converted: {output_path}")
        return True
        
    except ImportError:
        logger.error("rawpy not installed. Install with: pip install rawpy")
        return False
    except Exception as e:
        logger.error(f"RAW conversion failed for {raw_path}: {e}")
        return False


def fix_orientation(image: Image.Image) -> Image.Image:
    """Fix image orientation based on EXIF data."""
    try:
        exif = image._getexif()
        if exif is None:
            return image
        
        # Find orientation tag
        orientation_key = None
        for key, val in ExifTags.TAGS.items():
            if val == "Orientation":
                orientation_key = key
                break
        
        if orientation_key is None or orientation_key not in exif:
            return image
        
        orientation = exif[orientation_key]
        
        # Apply rotation/flip based on orientation
        if orientation == 2:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            image = image.rotate(180)
        elif orientation == 4:
            image = image.transpose(Image.FLIP_TOP_BOTTOM)
        elif orientation == 5:
            image = image.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 6:
            image = image.rotate(-90, expand=True)
        elif orientation == 7:
            image = image.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 8:
            image = image.rotate(90, expand=True)
        
        return image
    except Exception as e:
        logger.debug(f"Could not fix orientation: {e}")
        return image


def normalize_image(
    input_path: Path,
    output_path: Path,
    max_size: int = 2048
) -> bool:
    """
    Normalize an image: resize to max dimension, fix orientation, save as JPEG.
    Returns True on success.
    """
    try:
        # Handle RAW files
        if is_raw_file(input_path):
            if not convert_raw_to_jpeg(input_path, output_path):
                return False
            # Re-open the converted file for further processing
            img = Image.open(output_path)
        else:
            img = Image.open(input_path)
        
        # Fix orientation
        img = fix_orientation(img)
        
        # Convert to RGB if necessary
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Resize if needed
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        # Save as JPEG
        img.save(output_path, "JPEG", quality=95)
        logger.debug(f"Normalized: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Normalization failed for {input_path}: {e}")
        return False


def create_thumbnail(
    input_path: Path,
    output_path: Path,
    size: int = 300
) -> bool:
    """Create a square thumbnail from an image."""
    try:
        img = Image.open(input_path)
        img = fix_orientation(img)
        
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Create square thumbnail (crop to center)
        width, height = img.size
        min_dim = min(width, height)
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim
        
        img = img.crop((left, top, right, bottom))
        img = img.resize((size, size), Image.LANCZOS)
        
        img.save(output_path, "JPEG", quality=85)
        logger.debug(f"Thumbnail created: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Thumbnail creation failed for {input_path}: {e}")
        return False


def detect_faces(image_path: Path) -> List[DetectedFace]:
    """
    Detect faces in an image and extract embeddings using InsightFace.
    Returns list of DetectedFace objects.
    """
    try:
        analyzer = _get_face_analyzer()
        
        # Read image with OpenCV (BGR format)
        img = cv2.imread(str(image_path))
        if img is None:
            logger.error(f"Could not read image: {image_path}")
            return []
        
        # Detect faces
        faces = analyzer.get(img)
        
        detected = []
        for face in faces:
            # Get bounding box (InsightFace returns [x1, y1, x2, y2])
            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            width = x2 - x1
            height = y2 - y1
            
            # Get embedding (512-dimensional)
            embedding = face.embedding
            
            # Get detection confidence
            confidence = float(face.det_score)
            
            detected.append(DetectedFace(
                bbox=(int(x1), int(y1), int(width), int(height)),
                embedding=embedding,
                confidence=confidence
            ))
        
        logger.debug(f"Detected {len(detected)} faces in {image_path.name}")
        return detected
        
    except Exception as e:
        logger.error(f"Face detection failed for {image_path}: {e}")
        return []


@dataclass
class ProcessingResult:
    """Result of processing a single photo."""
    success: bool
    processed_path: Optional[Path]
    thumbnail_path: Optional[Path]
    faces: List[DetectedFace]
    error: Optional[str] = None


def process_photo(
    input_path: Path,
    photo_id: int,
    config=None
) -> ProcessingResult:
    """
    Full processing pipeline for a single photo:
    1. Normalize (RAW→JPEG if needed, resize, orientation)
    2. Create thumbnail
    3. Detect faces and extract embeddings
    """
    config = config or get_config()
    
    try:
        # Generate output paths
        processed_dir = config.processed_dir
        processed_dir.mkdir(parents=True, exist_ok=True)
        
        base_name = f"{photo_id:06d}"
        processed_path = processed_dir / f"{base_name}.jpg"
        thumbnail_path = processed_dir / f"{base_name}_thumb.jpg"
        
        # Step 1: Normalize image
        if not normalize_image(input_path, processed_path, config.max_image_size):
            return ProcessingResult(
                success=False,
                processed_path=None,
                thumbnail_path=None,
                faces=[],
                error="Normalization failed"
            )
        
        # Step 2: Create thumbnail
        if not create_thumbnail(processed_path, thumbnail_path, config.thumbnail_size):
            logger.warning(f"Thumbnail creation failed for {input_path}")
            # Continue anyway, thumbnail is not critical
        
        # Step 3: Detect faces
        faces = detect_faces(processed_path)
        
        return ProcessingResult(
            success=True,
            processed_path=processed_path,
            thumbnail_path=thumbnail_path if thumbnail_path.exists() else None,
            faces=faces
        )
        
    except Exception as e:
        logger.error(f"Processing failed for {input_path}: {e}")
        return ProcessingResult(
            success=False,
            processed_path=None,
            thumbnail_path=None,
            faces=[],
            error=str(e)
        )
