# 📦 AURA — Windows Distribution Plan (v2.0.0)

> **Status:** Planning Phase (Distribution Ready)  
> **Target Version:** v2.0.0 (PySide6 + GPU Support)  
> **Goal:** Single download `Setup.exe` that "just works" on any Windows machine.

---

## 🚀 The Strategy: One-Dir Bundle + Pro Installer

We will use the professional "standard" for shipping Python AI apps:

1. **PyInstaller (`--onedir`)**: Freezes your Python code, libraries, and models into a single folder.
2. **Inno Setup**: Wraps that folder into a polished `AURA_Setup.exe` with shortcuts and an uninstaller.

---

## 1. Distribution Rules (The UX Design)

| Rule | Implementation |
|:---|:---|
| **No Python Install** | App bundles its own private Python runtime. |
| **No internet needed for AI** | ML models (InsightFace) are bundled inside the app. |
| **Smart GPU Handling** | Bundles `onnxruntime-gpu` (works on CPU too). Shows the GPU Wizard if compatible hardware found. |
| **Persistent Config** | Settings (.env) and local DB go to `%LOCALAPPDATA%`, not `Program Files` (to avoid permission errors). |
| **Launch Speed** | Use `--onedir` mode so the app starts in < 2 seconds. |

---

## 2. Phase 1: PyInstaller Configuration (`.spec` file)

We need a custom `.spec` file to handle the "heavy lifting" of AI libraries.

### Key Bundled Assets

- **ML Models**: `buffalo_l` models (`det_10g.onnx`, `w600k_r50.onnx`)
- **Backend Source**: `backend/` folder
- **Frontend Source**: `frontend/` folder (for the web server)
- **Icons**: `assets/logo.ico`

### Hidden Imports (Modules PyInstaller misses)

- `onnxruntime-gpu` providers
- `insightface` components
- `uvicorn` loop auto-selection
- `rawpy` / `libraw` binaries

---

## 3. Phase 2: Building the Bundle

**Command:**

```powershell
pyinstaller --name "AURA" --windowed --onedir run_pyside.py
```

### The "Clean Root" Trick

We will make the app smart enough to detect if it's "frozen" (running as an EXE).

- If Frozen: Look for assets relative to `sys._MEIPASS`.
- If Dev: Look for assets relative to the project root.

---

## 4. Phase 3: The Inno Setup Script (`.iss`)

We will create a script for **Inno Setup** that creates the professional installer.

**Features of the Installer:**

1. **Desktop Shortcut**: ⚡ AURA
2. **Start Menu**: Adds a shortcut under "AURA".
3. **Admin Rights**: Requests permission to install to `C:\Program Files`.
4. **Cleanup**: Removes all files automatically when uninstalled.

---

## 5. Phase 4: Test on a "Clean Machine"

Before giving it to users, we must test on a computer that **never had Python installed**.

- **Test Tool**: Windows Sandbox (Free on Windows 10/11 Pro).
- **Checklist**:
  - [x] App opens without any "DLL Missing" errors.
  - [x] UI displays correctly (fonts, colors).
  - [x] Face detection works (models loaded correctly).
  - [x] GPU Wizard correctly detects "No compatible GPU" on a standard VM.

---

## 6. Implementation Order

- [x] **Step 1**: Create `dist_utils.py` — Helper to handle file paths when the app is an EXE vs Script.
- [ ] **Step 2**: Create `aura.spec` — The master configuration for the build.
- [ ] **Step 3**: Compile the bundle using PyInstaller.
- [ ] **Step 4**: Install Inno Setup and create the `setup.iss` script.
- [ ] **Step 5**: Export the first `Setup.exe`.

---

## 📋 Summary of Files Affected

| File | Purpose |
|:---|:---|
| `backend/app/config.py` | Update to support `%LOCALAPPDATA%` paths. |
| `WeddingFFapp_pyside/app_window.py` | Add "Frozen" path detection. |
| `infos/WINDOWS_DISTRIBUTION_PLAN.md` | **(This File)** The master roadmap. |
| `setup.iss` | The installer script (to be created). |
| `aura.spec` | The bundler script (to be created). |
