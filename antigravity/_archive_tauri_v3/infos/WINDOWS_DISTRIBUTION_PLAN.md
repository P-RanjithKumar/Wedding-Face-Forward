# 📦 AURA — Windows Distribution Plan (v3.0.0)

> **Status:** Planning Phase  
> **Target Version:** v3.0.0 (Next.js + Tauri Desktop App)  
> **Previous Version:** v2.0.0 (PySide6 + PyInstaller + Inno Setup)  
> **Goal:** Single download `AURA_Setup.exe` that "just works" on any Windows machine.

---

## 🔄 What Changed from v2.0.0

| Aspect | v2.0.0 (Old) | v3.0.0 (New) |
|--------|-------------|-------------|
| **Admin UI** | PySide6 (Python) | Next.js + React (Web) |
| **Desktop Shell** | PyInstaller `.exe` | Tauri native `.exe` |
| **Installer** | Inno Setup (`.iss`) | Tauri NSIS bundler (built-in) |
| **Python Backend** | Bundled via PyInstaller | Bundled as Tauri sidecar |
| **Guest Portal** | Served by FastAPI | Unchanged — still served by FastAPI |
| **App Size** | ~300-500 MB (PyInstaller) | ~150-300 MB (Tauri + embedded Python) |

---

## 🚀 The Strategy: Tauri + Embedded Python Sidecar

1. **Tauri v2**: Builds the Next.js admin dashboard into a native Windows `.exe` with a WebView2 window.
2. **Embedded Python Sidecar**: The entire Python backend (FastAPI, Worker, WhatsApp, ML models) is bundled inside the Tauri app as a sidecar binary.
3. **Tauri NSIS Bundler**: Generates a professional `AURA_Setup.exe` installer — no separate Inno Setup needed.

---

## 1. Distribution Rules (UX Design)

| Rule | Implementation |
|:---|:---|
| **No Python Install** | Python runtime is embedded as a sidecar (via PyInstaller `--onedir` or embedded Python). |
| **No Node.js Install** | Next.js is pre-built to static files, served by Tauri's WebView2. |
| **No internet needed for AI** | ML models (InsightFace `buffalo_l`) bundled inside the sidecar. |
| **Smart GPU Handling** | `onnxruntime-gpu` bundled, falls back to CPU. GPU Wizard available in UI. |
| **Persistent Config** | Settings (.env) and DB go to `%LOCALAPPDATA%\AURA\`, not `Program Files`. |
| **Single .exe installer** | User downloads one file, double-clicks, done. Desktop + Start Menu shortcuts. |
| **WebView2 Runtime** | Uses system WebView2 (pre-installed on Windows 10/11). Installer auto-installs if missing. |

---

## 2. Build Architecture

```
AURA_Setup.exe (NSIS installer, built by Tauri)
└── Installs to C:\Program Files\AURA\
    ├── AURA.exe                  # Tauri app (Next.js frontend + Rust core)
    ├── resources/
    │   └── sidecar/
    │       └── aura-backend/     # PyInstaller --onedir bundle
    │           ├── aura-backend.exe  # Python backend entry point
    │           ├── _internal/        # Python runtime + all packages
    │           │   ├── onnxruntime/
    │           │   ├── insightface/
    │           │   ├── uvicorn/
    │           │   └── ...
    │           └── data/
    │               └── models/       # buffalo_l ML models
    ├── frontend/                 # Guest portal (HTML/JS/CSS)
    │   ├── index.html
    │   ├── css/
    │   └── js/
    └── uninstall.exe             # Auto-generated uninstaller
```

---

## 3. How the App Starts

```
User double-clicks AURA.exe
    │
    ├── 1. Tauri opens native window (WebView2)
    │      Shows splash/loading screen
    │
    ├── 2. Tauri spawns sidecar: aura-backend.exe --run-server
    │      (FastAPI starts on localhost:8000)
    │
    ├── 3. Tauri spawns sidecar: aura-backend.exe --run-worker
    │      (Photo processing worker starts)
    │
    ├── 4. Tauri spawns sidecar: aura-backend.exe --run-whatsapp
    │      (WhatsApp sender starts)
    │
    └── 5. Next.js dashboard connects to localhost:8000
           (WebSocket for real-time + REST for data)
```

> The `aura-backend.exe` replaces the current `run_pyside.py` — same subprocess routing flags (`--run-server`, `--run-worker`, `--run-whatsapp`), but without PySide6.

---

## 4. Build Pipeline

### Step 1: Build the Python Sidecar

```powershell
# Uses the existing aura.spec (modified to remove PySide6 dependencies)
pyinstaller --name "aura-backend" --console --onedir backend_entry.py
```

- `backend_entry.py` = stripped version of `run_pyside.py` (subprocess routing only, no PySide6)
- Output: `dist/aura-backend/` folder

### Step 2: Build the Next.js Frontend

```powershell
cd aura_web
npm run build        # Static export of Next.js
```

- Output: `aura_web/out/` or `aura_web/.next/` (Tauri serves from this)

### Step 3: Build the Tauri Desktop App + Installer

```powershell
cd aura_web
cargo tauri build     # Compiles Rust, bundles everything, creates NSIS installer
```

- Output: `src-tauri/target/release/bundle/nsis/AURA_x.x.x_x64-setup.exe`

---

## 5. Tauri Configuration (`tauri.conf.json`)

Key settings:

```json
{
  "productName": "AURA",
  "version": "3.0.0",
  "identifier": "com.darkintelligence.aura",
  "bundle": {
    "active": true,
    "targets": ["nsis"],
    "icon": ["icons/icon.ico"],
    "windows": {
      "nsis": {
        "installMode": "perMachine",
        "displayLanguageSelector": false
      }
    },
    "externalBin": ["sidecar/aura-backend"]
  },
  "app": {
    "windows": [{
      "title": "AURA",
      "width": 1200,
      "height": 800,
      "minWidth": 900,
      "minHeight": 600,
      "decorations": true,
      "center": true
    }]
  }
}
```

---

## 6. Testing Checklist

Test on a clean Windows machine (Windows Sandbox):

- [ ] Installer runs without admin issues
- [ ] App opens without "DLL Missing" errors
- [ ] WebView2 loads the dashboard correctly
- [ ] Python sidecar starts (FastAPI on :8000)
- [ ] Worker process runs (photo processing works)
- [ ] WhatsApp sender starts (Chromium launches)
- [ ] Guest portal accessible at `localhost:8000` from browser
- [ ] GPU Wizard detects hardware correctly
- [ ] ML models load and face detection works
- [ ] Settings persist across app restarts (`%LOCALAPPDATA%`)
- [ ] Uninstaller cleanly removes everything

---

## 7. Implementation Order

- [x] **Step 1**: `dist_utils.py` — path helpers (already done for v2.0)
- [ ] **Step 2**: Build the Next.js admin dashboard (`aura_web/`)
- [ ] **Step 3**: Create `backend_entry.py` — headless backend entry point (no PySide6)
- [ ] **Step 4**: Set up Tauri project with sidecar configuration
- [ ] **Step 5**: Build Python sidecar with PyInstaller
- [ ] **Step 6**: Configure Tauri NSIS bundler
- [ ] **Step 7**: Build and test `AURA_Setup.exe`
- [ ] **Step 8**: Test on clean Windows machine

---

## 📋 Files Affected

| File | Purpose |
|:---|:---|
| `aura_web/` | [NEW] Next.js + Tauri project |
| `aura_web/src-tauri/` | [NEW] Tauri Rust core + config |
| `backend_entry.py` | [NEW] Headless backend entry (replaces `run_pyside.py`) |
| `aura_app/` | [DELETE] PySide6 code (phased out after migration) |
| `run_pyside.py` | [DELETE] Old PySide6 launcher |
| `aura.spec` | [MODIFY] Rebuild for sidecar-only (no PySide6) |
| `aura.iss` | [DELETE] No longer needed (Tauri has built-in NSIS) |
| `dist_utils.py` | [MODIFY] Update paths for Tauri sidecar structure |
| `frontend/server.py` | [MODIFY] Add admin WebSocket + new admin API endpoints |
| `infos/WINDOWS_DISTRIBUTION_PLAN.md` | **(This File)** Updated roadmap |
