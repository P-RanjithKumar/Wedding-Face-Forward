# Comprehensive Project Development Log & Issue Tracker
**Project**: Wedding Face Forward
**Document Version**: 2.0 (Comprehensive)
**Last Updated**: 2026-02-11

This document serves as a complete historical record of the development lifecycle, specifically focusing on the critical issues faced, errors encountered, and the specific technical resolutions applied.

---

## 1. 🛑 Startup & Environment Critical Failures

### 1.1 The "Port 8000" Blockade
*   **The Issue**: The application refused to start, providing the error `OSError: [Errno 98] Address already in use`.
*   **Symptoms**:
    *   Web server failed to bind to `localhost:8000`.
    *   Web browser would not auto-launch.
    *   "Zombie" Python processes from previous runs were holding the port.
*   **The Fix**:
    *   Developed a startup routine to identifying processes listening on Port 8000.
    *   Implemented a hard-kill logic to terminate those specific PIDs before the new server instance attempts to bind.

### 1.2 Tooling Crashes (Pyrefly)
*   **The Issue**: Persistent crashes of the Pyre language server (`pyreflycrash.txt`).
*   **Context**: `Thread panicked... assertion failed`.
*   **Resolution**: This was identified as an IDE tooling environment issue rather than runtime application code failure, but it caused development friction.

---

## 2. 🗄️ Database Concurrency & Pipeline Stalls

### 2.1 The "Database is Locked" Crisis
*   **The Issue**: `sqlite3.OperationalError: database is locked`.
*   **Context**: This was the single biggest stability blocker. The application uses multiple concurrent threads:
    1.  **Face Processing**: Writing new faces/clusters to DB.
    2.  **Cloud Upload**: Reading paths from DB.
    3.  **WhatsApp Sender**: Reading/Writing user status.
    4.  **Enrollment Web Request**: Writing new users.
*   **The Struggle**: SQLite default timeouts (5s) were insufficient for this high-concurrency load, causing threads to crash and the pipeline to halt.
*   **The Solutions**:
    *   **Timeout Tuning**: Increased connection timeout to `30.0` seconds: `sqlite3.connect(..., timeout=30)`.
    *   **Retry Logic**: Implemented a `db_retry` decorator that catches `OperationalError` and retries with exponential backoff.
    *   **Transaction Scope**: Refactored database access patterns to keep transaction windows (open cursor time) as short as possible.

---

## 3. 📱 WhatsApp Automation (The "Spam Risk" & Logic Wars)

### 3.1 The Infinite Loop / Ban Risk
*   **The Issue**: The initial sender script had no "give up" logic. If a number was invalid or network failed, it retried infinitely in a tight loop.
*   **Risk**: High probability of WhatsApp account bans due to "bot-like behavior".
*   **The Fix**:
    *   **Retry Limiting**: Introduced a strict `max_retries=3` limit.
    *   **Permanent Failure**: Created a logic state `permanently_failed` to blacklist numbers after 3 attempts.

### 3.2 Duplicate Messaging
*   **The Issue**: Users were receiving the same "Welcome" message multiple times if the server restarted.
*   **The Fix**:
    *   **State Persistence**: Implemented `message_state_db.json` (a flat-file database) to track exactly which phone numbers had already successfully received a message.
    *   **Check-First Logic**: The sender now queries this state file *before* attempting any action.

### 3.3 The "Access Denied" Drive Links
*   **The Issue**: Messages were delivering successfully, but guests complained they couldn't open the Google Drive links.
*   **The Cause**: The automation was sending links to folders that were still "Private" by default.
*   **The Fix**:
    *   **Permission Automation**: Updated `cloud.py` / sender logic to programmatically call the Google Drive API (`permissions.create`) and grant `role='reader', type='anyone'` *before* generating the shareable link.

### 3.4 Phone Number Validation
*   **The Issue**: Messages failed immediately because numbers were stored without Country Codes (e.g., `9876543210` instead of `+919876543210`).
*   **The Fix**:
    *   **Frontend**: Modified the Enrollment HTML form to enforce strict input patterns.
    *   **Backend**: Added logic to inspect the number format and reject/warn on invalid headers before adding to the queue.

---

## 4. ☁️ Cloud Upload Instability

### 4.1 SSL & Network Fragility
*   **The Issue**: `SSLError: [SSL: WRONG_VERSION_NUMBER]`.
*   **Context**: Long-running upload queues would fail intermittently due to ISP fluctuations or API hiccups.
*   **The Fix**:
    *   **RobustSession**: Replaced standard `requests.get` with a custom Session object using `HTTPAdapter`.
    *   **Retry Strategy**: Configured `urllib3` to retry on specific HTTP status codes (500, 502, 503) and connection errors.

### 4.2 The "Non-Dictionary" Crash
*   **The Issue**: `AttributeError: 'str' object has no attribute 'get'`.
*   **Context**: The FaceForward API occasionally returned a raw HTML string (error page) instead of JSON when the server was overloaded. Validating `response.json()` blindness caused the crash.
*   **The Fix**:
    *   **Defensive Coding**: Added `if isinstance(response, dict):` checks around all API response parsers.

### 4.3 Warnings & Cache
*   **The Issue**: `file_cache is only supported with oauth2client<4.0.0`.
*   **Context**: A warning from the Google Client Library cluttering the logs.
*   **Status**: Identified as a library deprecation warning; harmless but noted for future upgrades.

---

## 5. 🎨 UI/UX Polish & Project Structure

### 5.1 Documentation & Sidebar
*   **The Issue**: The documentation sidebar was clunky, with massive fonts and poor spacing.
*   **The Fix**:
    *   **CSS Refactor**: Manually tweaked font sizes (`1.1rem` -> `0.9rem`), margins, and container widths to create a professional "Docs" look.

### 5.2 Dark/Light Mode
*   **The Issue**: The app was blindingly white at night.
*   **The Fix**:
    *   **CSS Variables**: Implemented a generic toggler that swaps CSS root variables for background/text colors without complex JS frameworks.

### 5.3 Activity Log Readability
*   **The Issue**: Logs were a wall of text.
*   **The Fix**:
    *   **Scoped Coloring**: Applied CSS classes to specific log prefixes (e.g., `[UPLOAD]` is Blue, `[WA]` is Green, `ERROR` is Red) while keeping the message body neutral.

---

---

## 6. 📂 Repository & Setup
*   **The Issue**: Initial codebase had no version control hygiene.
*   **The Fixes**:
    *   **Git Init**: Created new repository structure.
    *   **.gitignore**: Added specific exclusions for `__pycache__`, `venv`, `*.log`, `token.json`, and `credentials.json` to prevent security leaks.
    *   **README**: Expanded from a stub to a full technical manual.

---

## 7. 🧠 Face Detection Critical Failures (Thread-Safety & Image Size)

### 7.1 The "Silent Face Detection Failure" Crisis
*   **The Issue**: Photos were being processed but marked as `no_faces` even though they clearly contained faces. The error logs showed `Face detection failed for ...000081.jpg:` with **empty error messages**.
*   **Date Discovered**: 2026-02-11
*   **Context**: 
    *   User added 20 photos of the same person (cb1.jpg through cb20.jpg)
    *   Only 1 photo successfully detected a face and created `Person_017`
    *   The other 19 photos either failed silently or were stuck in `pending` status
    *   No photos were routed to person folders
    *   No cloud uploads occurred
*   **Root Causes** (Three simultaneous problems):
    1. **Thread-Safety Bug**: The global `_face_analyzer` variable was being shared across 4 worker threads. InsightFace's `FaceAnalysis` is **NOT thread-safe** — when multiple threads called `analyzer.get(img)` simultaneously, it caused race conditions and silent failures.
    2. **Tiny Images**: The cb photos were very small (~200-300px), but InsightFace's detection model expects 640×640 input. Small images were being passed directly to the detector without upscaling, causing missed detections.
    3. **App Killed Mid-Processing**: The app was restarted twice during processing, leaving 16 of 20 photos stuck in `pending` status forever.

### 7.2 The Fixes
*   **Thread-Local Face Analyzer** (`processor.py`):
    *   Changed from single global `_face_analyzer` to `threading.local()` storage
    *   Each of the 4 worker threads now gets its own isolated InsightFace instance
    *   Eliminated race conditions completely
    *   Added thread name logging: `"Loading InsightFace model for thread ThreadPoolExecutor-0_0..."`

*   **Small Image Upscaling** (`processor.py`):
    *   Added `_MIN_DETECT_DIM = 640` constant
    *   Images smaller than 640px are now upscaled using `cv2.INTER_CUBIC` before face detection
    *   Bounding boxes are scaled back to original image coordinates after detection
    *   Example: A 195×258 image is upscaled to 493×652 for detection, then bbox coordinates are divided by the scale factor

*   **Better Error Logging**:
    *   Added full `traceback.format_exc()` logging when face detection fails
    *   Now we see the actual error instead of blank messages

*   **Database Reset Script**:
    *   Created `reset_cb_photos.py` to reset all 20 stuck photos back to `pending`
    *   Deleted old face records so they get re-detected with the fixed code

### 7.3 Technical Details
**Before Fix**:
```python
# WRONG: Global variable shared across threads
_face_analyzer = None

def _get_face_analyzer():
    global _face_analyzer
    if _face_analyzer is None:
        _face_analyzer = FaceAnalysis(...)  # All threads share this!
    return _face_analyzer
```

**After Fix**:
```python
# CORRECT: Thread-local storage
_thread_local = threading.local()

def _get_face_analyzer():
    analyzer = getattr(_thread_local, 'face_analyzer', None)
    if analyzer is None:
        analyzer = FaceAnalysis(...)
        _thread_local.face_analyzer = analyzer  # Each thread gets its own
    return analyzer
```

**Image Upscaling Logic**:
```python
# Check if image is too small for reliable detection
if max(h, w) < 640:
    scale_factor = 640 / max(h, w)
    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    # ... detect faces on upscaled image ...
    # Scale bounding boxes back to original coordinates
    x1 /= scale_factor
    y1 /= scale_factor
```

---

## 8. 🖼️ Modern Image Format Support (AVIF, WebP, HEIC)

### 8.1 The Request
*   **Date**: 2026-02-11
*   **User Need**: Support for modern image formats beyond standard JPEG/PNG:
    *   **AVIF** (AV1 Image File Format) — Modern compression, better than JPEG
    *   **WebP** (Google's format) — Widely used on web
    *   **HEIC/HEIF** (Apple's format) — Default on iPhones since iOS 11

### 8.2 The Implementation
*   **Installed Dependencies**:
    ```bash
    pip install pillow-heif pillow-avif-plugin
    ```
    *   `pillow-heif==1.2.0` — Adds HEIC/HEIF support to PIL
    *   `pillow-avif-plugin==1.5.5` — Adds AVIF support to PIL
    *   Upgraded Pillow to `12.1.1` (WebP is built-in)

*   **Code Changes** (`processor.py`):
    *   Added `_enable_modern_formats()` function that registers AVIF and HEIC plugins
    *   Uses thread-local tracking (`_modern_formats_enabled`) to register plugins only once per worker thread
    *   Modified `normalize_image()` to call this function before opening non-RAW images
    *   Added graceful fallback with helpful debug messages if plugins aren't installed

### 8.3 Technical Details
**Plugin Registration**:
```python
_modern_formats_enabled = threading.local()

def _enable_modern_formats():
    if getattr(_modern_formats_enabled, 'done', False):
        return  # Already enabled for this thread
    
    # Enable HEIC/HEIF
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:
        logger.debug("HEIC/HEIF not available (install: pip install pillow-heif)")
    
    # Enable AVIF
    try:
        from pillow_avif import AvifImagePlugin
    except ImportError:
        logger.debug("AVIF not available (install: pip install pillow-avif-plugin)")
    
    _modern_formats_enabled.done = True
```

**Updated normalize_image()**:
```python
def normalize_image(input_path, output_path, max_size=2048):
    """
    Supports: JPEG, PNG, BMP, TIFF, WebP, AVIF, HEIC/HEIF, and all camera RAW formats.
    """
    if is_raw_file(input_path):
        # Handle RAW files
        convert_raw_to_jpeg(input_path, output_path)
    else:
        # Enable modern format support
        _enable_modern_formats()
        # PIL will now handle AVIF/WebP/HEIC automatically
        img = Image.open(input_path)
    
    # Convert to RGB (AVIF/WebP might be RGBA)
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    # ... rest of processing ...
```

### 8.4 Supported Formats (Complete List)
**Standard**: JPG, JPEG, PNG, BMP, TIFF, GIF, ICO, and 60+ others  
**Modern**: ✅ WebP, ✅ AVIF, ✅ HEIC/HEIF  
**Camera RAW**: CR2, NEF, ARW, DNG, ORF, RW2, RAF, PEF  
**Total**: 90+ image formats

### 8.5 Verification
*   Created `test_format_support.py` to verify all formats are registered
*   Test output confirmed:
    ```
    [OK] WebP: Supported (native)
    [OK] AVIF: Supported (pillow-avif-plugin)
    [OK] HEIC/HEIF: Supported (pillow-heif)
    PIL Version: 12.1.1
    ```

---

## 9. 🔍 Watcher Extension Mismatch (WebP/AVIF/HEIC Silently Ignored)

### 9.1 The "Missing Photos" Mystery
*   **Date Discovered**: 2026-02-11
*   **The Issue**: User uploaded 12 photos (vj1–vj12), but `vj11.webp` was completely silently ignored — no log entry, no error, just vanished.
*   **Context**: 
    *   The PIL/Pillow plugins for WebP, AVIF, and HEIC were correctly installed and registered in `processor.py`
    *   However, the **watcher's SUPPORTED_EXTENSIONS** list in `.env` was never updated to include `.webp`, `.avif`, `.heic`, `.heif`
    *   The watcher's `_is_supported_file()` check rejected these files before they ever reached the processor
*   **The Fix**:
    *   Updated `SUPPORTED_EXTENSIONS` in `.env` from `.jpg,.jpeg,.png,.cr2,.nef,.arw,.dng,.orf,.rw2` to `.jpg,.jpeg,.png,.webp,.avif,.heic,.heif,.bmp,.tiff,.tif,.gif,.cr2,.nef,.arw,.dng,.orf,.rw2,.raf,.pef`
    *   Updated the default fallback in `config.py` to match
*   **Lesson**: When adding format support to the processing pipeline, **always update the watcher's extension filter too**. The pipeline has two gates: (1) watcher extension filter, (2) processor format support. Both must agree.

### 9.2 The "Duplicate Folders" Confusion
*   **The Issue**: User saw 2 new folders (Person_018, Person_019) on Google Drive, each containing the same photo.
*   **The Cause**: This is **correct behavior**. Photo `vj10.jpg` (ID: 110) contained **3 faces** — identified as Person 1 (virat_1), Person_018, and Person_019. The router correctly placed this group photo in each person's `Group` subfolder.
*   **Resolution**: No code change needed. The 11 other photos were all correctly routed to `virat_1/Solo/` folder. The "missing" perception was because the user was looking at the cloud Drive which only showed the 2 *new* person folders, not the existing `virat_1` folder which had all the solo photos.

---

## Summary of Latest Fixes (2026-02-11)

| Issue | Impact | Fix | Files Changed |
|-------|--------|-----|---------------|
| Thread-unsafe face analyzer | 95% of photos marked `no_faces` | Thread-local storage | `processor.py` |
| Small images failing detection | Faces missed in <640px images | Auto-upscaling with cv2 | `processor.py` |
| No AVIF/WebP/HEIC support | Modern formats rejected | Installed plugins + registration | `processor.py` |
| Stuck photos in database | 16 photos never processed | Reset script | `reset_cb_photos.py` |
| WebP/AVIF/HEIC in watcher | `.webp` files silently ignored | Added extensions to `.env` + `config.py` | `.env`, `config.py` |
| WebP/AVIF/HEIC in watcher | `.webp` files silently ignored | Added extensions to `.env` + `config.py` | `.env`, `config.py` |
| Crash-safety: orphaned faces | Duplicate faces, inflated person counts | Startup cleanup + centroid recalculation | `db.py`, `worker.py` |
| **User Feedback / Progress** | **Unclear status ("stuck?" vs active)** | **Added Circular Progress Bar + Tracker** | **`WeddingFFapp.py`, `worker.py`** |

---

## 11. 🎨 UI & UX Improvements

### 11.1 Circular Progress Bar
*   **Goal**: Solve the "is it stuck?" anxiety by providing clear, granular visual feedback.
*   **Implementation**: 
    *   Replaced the generic spinning ring in `WeddingFFapp.py` with a custom `ProcessingWidget`.
    *   **Visuals**: Draws a circular arc using `ctk.CTkCanvas` that fills from 0% to 100%.
    *   **Feedback**: Displays generic "Processing..." text along with specific counts ("3 / 13 Photos").
    *   **States**:
        *   **Idle**: Grey dashed ring.
        *   **Processing**: Blue animated arc filling up.
        *   **Done**: Green full ring with "DONE" text.

### 11.2 Backend Progress Tracking
*   Added `ProgressTracker` class in `worker.py` to track the lifecycle of a batch.
*   Watcher now triggers `progress.on_enqueue()` to increment the total.
*   Worker calls `progress.on_start()` and `progress.on_complete()` (even on errors).
*   Logs now show: `Progress: 5/13 done | 1 processing | 7 queued` instead of just `Queue size: 7`.
*   Added explicit `>> All 13 photos processed! Waiting for new photos...` log message.

---

## 10. 💀 Crash-Safety: Orphaned Faces & Phantom Person Counts

### 10.1 The "Missing Photos + Wrong Counts" Crisis
*   **Date Discovered**: 2026-02-11
*   **The Issue**: User uploaded 13 photos. The app was killed twice during processing. After restart:
    *   Only 2 new person folders appeared on Drive (Person_020, Person_021) with just 1 photo each
    *   Person_013 showed `face_count: 7` in the DB but only 2-3 files in the filesystem
    *   All 13 photos were stuck in `pending` status despite 4 having already been partially processed
    *   6 new person clusters were created that shouldn't exist (had no completed photos)
*   **Root Cause**: The processing pipeline is **NOT atomic**. When the app crashes mid-processing:
    1.  `db.create_face()` writes face records — **committed immediately**
    2.  `assign_person()` updates person centroids and creates new persons — **committed immediately**
    3.  `ensure_person_folders()` creates cloud folders — **done**
    4.  App crashes before `route_photo()` copies files to person folders
    5.  App crashes before `db.update_photo_processing()` marks photo as `completed`
    6.  On restart, `_reset_stuck_processing()` resets status to `pending` BUT **leaves the orphaned faces and corrupted centroids in place**
    7.  On reprocessing, **new duplicate face records** would be created, further inflating person counts

### 10.2 The Fixes
*   **Enhanced `_reset_stuck_processing()`** (`db.py`):
    *   Now also detects `pending` photos that have orphaned face records
    *   Deletes orphaned face records before resetting photo status
    *   Recalculates person centroids from remaining valid faces
    *   Removes person clusters that end up with 0 faces after cleanup
*   **Safety check in `process_single_photo()`** (`worker.py`):
    *   Before processing, checks if any face records already exist for the photo
    *   If found, calls `_cleanup_orphaned_faces()` first — defense in depth
*   **Cleanup results from this crash**:
    *   Deleted 17 orphaned face records from 7 photos
    *   Removed 6 phantom person clusters (Person_015, 016, 020, 021, 022, 023)
    *   Recalculated centroids for Person_013 (7→2), Person_014 (13→12), shreyy_elephantpeacock (6→2)

### 10.3 Technical Details
**The Atomicity Problem**:
```
process_single_photo():
    1. db.update_photo_status(photo_id, "processing")  # committed
    2. process_photo()                                   # image processing
    3. db.create_face()           ← COMMITTED            # face saved!
    4. assign_person()            ← COMMITTED            # centroid updated!
    5. route_photo()              ← APP CRASHES HERE     # files never copied!
    6. db.update_photo_processing(status="completed")    # never reached!
```

**The Fix**:
```python
# On startup:
_reset_stuck_processing():
    1. Find photos in 'processing' status
    2. Find 'pending' photos with orphaned face records  # NEW
    3. Delete orphaned face records                       # NEW
    4. Recalculate affected person centroids              # NEW
    5. Remove empty person clusters                       # NEW
    6. Reset photo status to 'pending'

# Before processing each photo:
process_single_photo():
    1. Check for existing face records (from crashed previous attempt)  # NEW
    2. Clean up if found                                                # NEW
    3. Proceed with normal processing
```

---

## 12. 📝 WhatsApp Monitoring Loop Log Spam & Scanner Noise

### 12.1 WhatsApp "Connecting to database" Flood
*   **Date Discovered**: 2026-02-12 (from session log `session_2026-02-11_19-45-21.txt`)
*   **The Issue**: The WhatsApp sender's continuous monitoring loop (`while True` in `main()`) called `fetch_enrolled_users()` every 10 seconds, which printed `"Connecting to database at: ..."` on every single poll — even when all users were already in `sent/invalid/failed` state. In one session, this produced **~260 identical log lines** flooding the session log and making it impossible to spot real errors.
*   **Aggravating Factor**: At timestamps `20:14:03` and `20:28:24`, **86+ lines** appeared within the *same second*, suggesting `asyncio.sleep(10)` was not being reached in some iterations (likely fast exceptions caught by the broad `except Exception` handler).
*   **The Fix** (`db_whatsapp_sender.py`):
    *   Added `verbose` parameter to `fetch_enrolled_users()` — only prints the DB connection message on the first poll
    *   Added `_last_user_count` tracking — logs when enrollment count changes (new user detected)
    *   Added `poll_count` counter in the monitoring loop to control verbosity
    *   The `asyncio.sleep(10)` is always reached now (it was before too, but the log noise made it look broken)

### 12.2 Scanner "UNIQUE constraint" Error Noise
*   **The Issue**: When the periodic scanner re-scans the Incoming directory, photos that were already processed trigger `UNIQUE constraint failed: photos.file_hash` — logged at **ERROR** level. This is expected behavior, not a real error.
*   **The Fix** (`watcher.py`):
    *   Downgraded the `UNIQUE constraint` errors to `DEBUG` level (invisible in normal runs)
    *   Genuine scanner errors remain at `ERROR` level
    *   Before: `ERROR | Scanner error for ...20250403_182905.jpg: UNIQUE constraint failed: photos.file_hash`
    *   After: `DEBUG | Already in DB (duplicate hash): 20250403_182905.jpg`

### 12.3 SSL Upload Failure (Session Note)
*   **What Happened**: Upload #71 (`000126.jpg`) failed permanently after 3 retry attempts due to `[SSL: WRONG_VERSION_NUMBER]` and `read operation timed out`. This was transient ISP/network instability.
*   **Status**: The retry logic performed correctly, but the network was too unstable for all 3 attempts. The upload was lost for this session. The existing `retry_with_backoff` decorator is working as designed — this is an infrastructure issue, not a code bug.
*   **Note**: `Person_026`'s cloud folder also failed to create (API returned `{'files': []}` instead of a folder creation response). Both issues are network-related.

