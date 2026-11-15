# 💡 AURA (by DARK intelligence)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0055ff?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![InsightFace](https://img.shields.io/badge/AI-InsightFace-red.svg)](https://github.com/deepinsight/insightface)

**AURA** is an enterprise-grade, privacy-first automated photography ecosystem. It is designed to take photos from the moment they are captured by a professional camera, process them using cutting-edge AI for facial recognition, and deliver personalized galleries to guests via WhatsApp—all without human intervention.

---

## 📑 Table of Contents

1. [🌟 Features](#-features)

2. [🏗️ Technical Architecture](#️-technical-architecture)
3. [🚀 The Autonomous Pipeline](#-the-autonomous-pipeline)
4. [🛠️ Technology Stack](#️-technology-stack)
5. [📦 Installation & Setup](#-installation--setup)
6. [⚙️ Configuration (.env)](#️-configuration-env)
7. [📂 Project Structure](#-project-structure)
8. [🖥️ Dashboard & Tools](#️-dashboard--tools)
9. [🛡️ Privacy & Performance](#️-privacy--performance)
10. [📝 License](#-license)

---

## 🌟 Features

### 🧠 Advanced AI & Image Processing

* **Zero-Training Clustering**: Automatically groups faces into "Person" clusters using the **Buffalo_L** model (InsightFace). No pre-collected guest list required.
* **⚡ Automatic GPU Acceleration**: Uses the graphics card through DirectML (NVIDIA, AMD or Intel; nothing to install, no CUDA). A one-time speed test picks the graphics card or the processor, whichever is faster on that PC, and AURA falls back to the processor if the graphics card fails. Measured on an Intel Core Ultra laptop: 17.4 s per photo before, about 0.22 s on its built-in Intel Arc graphics and about 1 s on the processor.
* **Pro RAW Engine**: Integrated support for professional formats (`.CR2`, `.NEF`, `.ARW`) using `rawpy`, converting them to high-quality normalized JPEGs.
* **Selfie-Matching**: Guests "claim" their entire gallery just by uploading one selfie. The system matches the selfie embedding to the existing event clusters with high confidence thresholds.

### Multi-Stage Automation

* **Real-time File Watcher**: Monitors `Incoming` folders using the `watchdog` library for instant trigger-based processing.
* **Dynamic Cloud Sync**: Automatically creates Google Drive folders, uploads photos in chunks, and manages public sharing permissions on-the-fly.
* **WhatsApp Personalization**: An automated worker that waits for guest enrollment and immediately pushes their personal Google Drive link to their WhatsApp number.

### 🎨 Premium User Experience

* **Guest Portal**: A high-fidelity, mobile-responsive web app featuring glassmorphism, smooth animations, and a secure download-ready gallery.
* **Desktop Admin App**: A Windows app built with `PySide6` (`aura_app/`, started with `run_pyside.py`) for monitoring statistics, queue health and activity logs. A Tauri + Next.js rewrite (v3.0.0) is unfinished and archived in `_archive_tauri_v3/`.

---

## 🏗️ Technical Architecture

### The AI Engine

The system uses **InsightFace's Buffalo_L** model powered by **ONNX Runtime**. It runs on the graphics card via DirectML (`onnxruntime-directml`, `DmlExecutionProvider`) when a one-time speed test shows it is faster, otherwise on the CPU with the cores split between worker threads. Only the detection and recognition models are loaded. See `backend/app/compute.py`.

* **Detection**: Sub-100ms face detection per frame using RetinaFace.
* **Embeddings**: 512-dimensional feature vector extraction.
* **Clustering**: Incremental Centroid-based clustering. Each new face is compared using **Cosine Distance** to existing centroids. If a match is found, the centroid is updated via a running average; otherwise, a new cluster is spawned.

### Reliability Layer

* **SQLite with WAL Mode**: Uses Write-Ahead Logging to support heavy concurrent reads/writes from the processing worker, web server, and WhatsApp sender.

* **Atomic Operations**: Photos are moved/copied only after database records are safely committed.
* **Resumability**: A global `file_hash` prevents redundant processing of the same image across sessions.

---

## � The Autonomous Pipeline

```text
[ CAMERA ] ----> [ Incoming/ ]
                     |
         (1) WATCHER DETECTS NEW FILE
                     |
         (2) PROCESSOR (RAW -> JPEG + Normalize)
                     |
         (3) AI ANALYZER (Detect Faces + Embeddings)
                     |
         (4) CLUSTERER (Match to Centroids or New ID)
                     |
         (5) ROUTER (Copy to People/Person_XXX/Solo|Group)
                     |
         (6) CLOUD SYNCER (Upload to Google Drive)
                     |
         (7) GUEST ENROLLS (Web Portal + Selfie)
                     |
         (8) NOTIFIER (WhatsApp Push with Personal Link)
```

---

## �️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **AI / ML** | InsightFace (Buffalo_L), ONNX Runtime, OpenCV, NumPy |
| **Backend** | Python 3.10+, FastAPI, Pydantic, SQLite (`sqlite3`, WAL) |
| **Guest portal** | Vanilla JS, HTML5, CSS (Rose Gold Glassmorphism) |
| **Desktop GUI** | PySide6 (admin dashboard), packaged with PyInstaller + Inno Setup |
| **Automation** | Playwright (WhatsApp), Google Drive API (Cloud) |
| **Image Ops** | Pillow (PIL), rawpy (RAW handling) |

---

## 📦 Installation & Setup

### Build and test in one go

From the `antigravity` folder, double-click **`build_and_test.bat`**, or run:

```powershell
.\build_and_test.ps1               # tests, build, built-app check, installer (about 30 min)
.\build_and_test.ps1 -TestsOnly    # only the tests (about 5 min)
.\build_and_test.ps1 -SkipTests    # build + built-app check + installer
.\build_and_test.ps1 -Clean        # build from scratch (after changing Python packages)
.\build_and_test.ps1 -FullCheck    # also test the WhatsApp browser download (~150 MB)
```

The installer lands in `Output\AURA_Setup_<version>.exe`; logs of every step in `logs\build\<date-time>\`.
Tests use temporary folders and their own ports, so they are safe to run while AURA is open.
How to try the installed app: `HOW_TO_TEST_LOCALLY.md`.

### 1. Repository Setup

```powershell
git clone https://github.com/P-RanjithKumar/Wedding-Face-Forward.git
cd Wedding-Face-Forward
```

### 2. Dependency Management

We recommend using a virtual environment.

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
pip install -r whatsapp_tool/requirements.txt
```

### 3. Google Drive API Configuration

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable the **Google Drive API**.
3. Create **OAuth 2.0 Client IDs** and download the `credentials.json`.
4. Place `credentials.json` in the root directory.
5. Run the authentication tool:

   ```powershell
   python backend/setup_auth.py
   ```

### 4. WhatsApp Tool Setup

Installation of Playwright browsers is required:

```powershell
playwright install chromium
```

---

## ⚙️ Configuration (.env)

Create a `.env` file in the root based on this template:

```env
# Path Settings
EVENT_ROOT=C:/EventPhotos/MyWedding
DB_PATH=C:/EventPhotos/data/wedding.db

# Processing Logic
WORKER_COUNT=4                 # Parallel CPU workers
CLUSTER_THRESHOLD=0.6         # 0.4 (Strict) to 0.7 (Loose)
SCAN_INTERVAL=30             # Re-scan Incoming every X seconds

# Cloud Settings
GOOGLE_CREDENTIALS_FILE=credentials.json
DRIVE_ROOT_FOLDER_ID=your_id_here
UPLOAD_QUEUE_ENABLED=true

# Face matching speed: auto (speed test picks GPU or CPU) | gpu | cpu
COMPUTE_DEVICE=auto

# Interface
LOG_LEVEL=INFO
```

---

## � Project Structure

* **/backend**: Core logic. Includes `worker.py` (pipeline runner), `processor.py` (AI), and `cloud.py` (Drive interaction).
* **/frontend**: The guest-only FastAPI server (`server.py`) and the guest portal assets. There is no admin API; the desktop app reads the database directly.
* `/aura_app` and `run_pyside.py`: the PySide6 desktop app (`run_pyside.py` also routes `--run-server`, `--run-worker`, `--run-whatsapp`).
* `/_archive_tauri_v3`: the unfinished Tauri + Next.js rewrite, kept out of the active tree.
* **/whatsapp_tool**: Playwright script for automated WhatsApp messaging.
* **/EventRoot**: Default location for generated data.
  * `/Incoming`: Where you drop raw photos.
  * `/Processed`: Normalized JPEGs for web delivery.
  * `/People`: AI-generated folders per identified person.
* `git_automator.py`: A developer utility to quickly sync local changes to your git repo.
* See `infos/project_structure.md` for the full tree and `todo/future_improvements.md` for the roadmap.

---

## 🖥️ Dashboard & Tools

### AURA Dashboard

Running `python run_pyside.py` (or the installed AURA app) launches the "Mission Control" for your event:

* **Real-time Stats**: Track total photos, faces detected, and guest enrollment status.
* **Process Management**: Click-to-start the background workers and web servers.
* **Live Activity**: A color-coded log showing exactly what the AI and Cloud workers are doing.

### Git Automator

For developers, `python git_automator.py` provides a GUI for quick Git staging, committing, and pushing, ensuring your project history is always up to date.

---

## 🛡️ Privacy & Performance

* **Security**: Biometric data (embeddings) is stored in a local SQLite DB, never sent to external servers. Only processed JPEGs are uploaded to your private Google Drive.
* **Multi-Tier Performance**: The system is multi-threaded for CPUs and uses any DirectX 12 graphics card (NVIDIA RTX, AMD, Intel Arc) automatically when it is faster. A modern laptop on GPU can process thousands of photos with sub-second latency per image.

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 👤 Author

**P-Ranjith Kumar**

* GitHub: [@P-RanjithKumar](https://github.com/P-RanjithKumar)
* Project: [AURA](https://github.com/P-RanjithKumar/Wedding-Face-Forward)
