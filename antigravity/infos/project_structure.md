# Project Structure: AURA (by DARK intelligence)

Updated 2026-11-14. The unfinished v3.0.0 Next.js + Tauri work (`aura_web/`, `sidecar/`, `backend_entry.py`, and its two plan docs) was moved to `_archive_tauri_v3/`, so the active app is the v2.0.0 PySide6 app (`aura_app/`, `run_pyside.py`, `aura.iss`).
Entries below marked [archived] are no longer in the active tree. The earlier version of this file described the customtkinter-era layout.

## Directory Tree

```text
antigravity/
├── backend/                  # Processing pipeline (Python)
│   ├── app/
│   │   ├── cloud.py          # Google Drive API integration
│   │   ├── cluster.py        # Incremental centroid face clustering
│   │   ├── config.py         # Settings loaded from .env
│   │   ├── db.py             # SQLite (WAL) access layer
│   │   ├── enrollment.py     # Guest selfie matching and folder renaming
│   │   ├── enroll_cli.py     # CLI for enrollment
│   │   ├── compute.py        # GPU (DirectML) vs CPU choice + one-time speed test (replaced gpu_manager.py, now in _archive_cuda_gpu/)
│   │   ├── phase.py          # Coordinates processing and upload phases
│   │   ├── processor.py      # RAW/JPEG normalization, thumbnails, InsightFace detection
│   │   ├── router.py         # Copies/links processed photos into People/Person_XXX/Solo|Group
│   │   ├── upload_queue.py   # Cloud upload queue with retries
│   │   ├── watcher.py        # Watches Incoming/ for new files
│   │   └── worker.py         # Worker pool that runs the pipeline
│   ├── setup_auth.py         # Google OAuth setup
│   ├── tests/                # test_cluster.py, test_db.py
│   └── requirements.txt
├── frontend/                 # FastAPI server + guest portal
│   ├── server.py             # Public API (enroll, photos, persons) and static guest page
│   ├── (admin_router.py)     # [archived in _archive_tauri_v3/frontend_admin_router.py] server.py is guest-only now
│   ├── index.html, css/, js/ # Guest portal (vanilla JS)
├── aura_web/                 # [archived in _archive_tauri_v3/] v3.0.0 desktop app
│   ├── src/                  # Next.js 16 + React 19 + Tailwind 4 admin dashboard
│   └── src-tauri/            # Tauri 2 shell (Rust), spawns the sidecar with --run-server / --run-worker / --run-whatsapp
├── sidecar/                  # [archived] Built backend executable (aura-backend)
├── backend_entry.py          # [archived] Headless entry point of the Tauri sidecar
├── dist_utils.py             # Paths for dev vs frozen/installed mode (%LOCALAPPDATA%\AURA)
├── aura.spec                 # PyInstaller spec for the sidecar
├── whatsapp_tool/            # Playwright-based WhatsApp sender
├── start_aura.py             # [archived in _archive_tauri_v3/launchers/] v3 dev launcher; use run_pyside.py
├── aura_app/, run_pyside.py, aura.iss   # v2.0.0 PySide6 app and Inno Setup script. Last version known to work well; keep until v3 is verified
├── git_automator.py          # Developer utility (PySide6 GUI for git)
├── checker_scripts/          # One-off debugging and diagnostic scripts
├── infos/, todo/             # Documentation and plans (see todo/future_improvements.md)
├── EventRoot/                # Event data created at runtime: Incoming/, Processed/, People/, Admin/
└── data/                     # SQLite databases (verify which is the real one: aura.db vs wedding.db)
```

## Key points

- Runtime data and settings live under `%LOCALAPPDATA%\AURA` in installed mode (see `dist_utils.py`).
- The desktop app reads the database directly; the FastAPI server is guest-only. Its port is the first free one from 8000 (`dist_utils.pick_guest_port`).
- The guest portal is served by the same FastAPI server and is separate from the admin dashboard.
- Open security work is tracked in `todo/future_improvements.md`.
