# Wedding Face Forward - Phase 2 Backend

A robust, resumable photo processing pipeline for event photography with automatic face detection, clustering, and organization.

## Features

- 📷 **RAW Support**: Handles CR2, NEF, ARW, DNG, and other RAW formats
- 🧠 **Face Detection**: InsightFace with ONNX Runtime (CPU-optimized)
- 👥 **Smart Clustering**: Incremental centroid-based person grouping
- 📁 **Auto-Organization**: Solo and Group photo folders per person
- 🔄 **Resumable**: SQLite-backed state; never reprocesses files
- ⚡ **Real-time**: Watchdog file monitoring with fallback scanning

## Quick Start

### 1. Install Dependencies

```powershell
cd "c:\Users\ranji\Desktop\MYwork\Wedding Face Forward\backend"
pip install -r requirements.txt
```

### 2. Configure Environment

```powershell
copy .env.example .env
# Edit .env with your preferred settings
```

### 3. Run the Worker

```powershell
python -m app.worker
```

### 4. Drop Photos

Place photos in `EventRoot/Incoming/` and watch them get processed automatically!

## Folder Structure

```
EventRoot/
├── Incoming/          # Drop photos here
├── Processed/         # Normalized JPEGs + thumbnails
├── People/
│   ├── Person_001/    # Before enrollment
│   │   ├── Solo/      # Photos with only this person
│   │   └── Group/     # Photos with multiple people
│   └── John_Doe/      # After enrollment (renamed!)
│       ├── 00_REFERENCE_SELFIE.jpg  # User's enrollment selfie
│       ├── Solo/
│       └── Group/
└── Admin/
    ├── NoFaces/       # Photos with no detected faces
    └── Errors/        # Failed/corrupt files
```

## User Enrollment

The enrollment system allows guests to "claim" their photos by uploading a selfie. When enrolled:
1. Their face is matched to an existing cluster (e.g., `Person_003`)
2. The folder is renamed to their name (e.g., `John_Doe`)
3. Their selfie is saved as `00_REFERENCE_SELFIE.jpg` for easy identification

### Enroll via CLI

```powershell
# Basic enrollment
python -m app.enroll_cli path/to/selfie.jpg "John Doe"

# With contact info
python -m app.enroll_cli selfie.jpg "Jane Smith" --phone "+1234567890" --email "jane@email.com"

# Check enrollment status
python -m app.enroll_cli selfie.jpg "Dummy" --status
```

### Enroll via Python

```python
from app.enrollment import enroll_user

result = enroll_user(
    selfie_path="selfie.jpg",
    user_name="John Doe",
    phone="+1234567890",
    email="john@example.com"
)

if result.success:
    print(f"Enrolled! Photos in: {result.solo_folder}")
else:
    print(f"Failed: {result.message}")
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EVENT_ROOT` | `./EventRoot` | Base directory for all photos |
| `DB_PATH` | `./data/wedding.db` | SQLite database location |
| `WORKER_COUNT` | `4` | Number of parallel workers |
| `CLUSTER_THRESHOLD` | `0.6` | Face matching sensitivity (0.4-0.7) |
| `DRY_RUN` | `false` | Preview mode without copying files |

## Testing

```powershell
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=html
```

## Performance

- **Target**: 5-20 photos/minute on CPU
- **Face Detection**: ~100ms per face (InsightFace Buffalo_L)
- **Clustering**: O(n) per new face where n = number of persons

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌────────────────┐
│   Watcher   │───▶│  Job Queue   │───▶│  Worker Pool   │
└─────────────┘    └──────────────┘    └────────────────┘
                                              │
                         ┌────────────────────┼────────────────────┐
                         ▼                    ▼                    ▼
                   ┌──────────┐        ┌────────────┐       ┌──────────┐
                   │ RAW→JPEG │        │ Face Detect│       │ Cluster  │
                   └──────────┘        └────────────┘       └──────────┘
                                              │
                                              ▼
                                       ┌────────────┐
                                       │   Router   │
                                       └────────────┘
                                              │
                         ┌────────────────────┼────────────────────┐
                         ▼                    ▼                    ▼
                   ┌──────────┐        ┌────────────┐       ┌──────────┐
                   │   Solo   │        │   Group    │       │  Admin   │
                   └──────────┘        └────────────┘       └──────────┘
                                              │
                                              ▼
                                       ┌────────────┐
                                       │ Enrollment │  ◀── User selfie
                                       └────────────┘
                                              │
                                              ▼
                                    Rename Person_XXX → User_Name
```

## License

MIT
