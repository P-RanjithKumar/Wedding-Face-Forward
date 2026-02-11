# 💍 Wedding Face Forward (WeddingFF)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0055ff?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![InsightFace](https://img.shields.io/badge/AI-InsightFace-red.svg)](https://github.com/deepinsight/insightface)

**Wedding Face Forward** is an enterprise-grade, privacy-first automated photography ecosystem. It is designed to take photos from the moment they are captured by a professional camera, process them using cutting-edge AI for facial recognition, and deliver personalized galleries to guests via WhatsApp—all without human intervention.

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
*   **Zero-Training Clustering**: Automatically groups faces into "Person" clusters using the **Buffalo_L** model (InsightFace). No pre-collected guest list required.
*   **Pro RAW Engine**: Integrated support for professional formats (`.CR2`, `.NEF`, `.ARW`) using `rawpy`, converting them to high-quality normalized JPEGs.
*   **Selfie-Matching**: Guests "claim" their entire gallery just by uploading one selfie. The system matches the selfie embedding to the existing event clusters with high confidence thresholds.

### � Multi-Stage Automation
*   **Real-time File Watcher**: Monitors `Incoming` folders using the `watchdog` library for instant trigger-based processing.
*   **Dynamic Cloud Sync**: Automatically creates Google Drive folders, uploads photos in chunks, and manages public sharing permissions on-the-fly.
*   **WhatsApp Personalization**: An automated worker that waits for guest enrollment and immediately pushes their personal Google Drive link to their WhatsApp number.

### 🎨 Premium User Experience
*   **Guest Portal**: A high-fidelity, mobile-responsive web app featuring glassmorphism, smooth animations, and a secure download-ready gallery.
*   **Visual Admin App**: A professional desktop dashboard built with `customtkinter` for localized monitoring of statistics, queue health, and activity logs.

---

## 🏗️ Technical Architecture

### The AI Engine
The system uses **InsightFace's Buffalo_L** model powered by **ONNX Runtime** for high-efficiency CPU execution.
- **Detection**: Sub-100ms face detection per frame using RetinaFace.
- **Embeddings**: 512-dimensional feature vector extraction.
- **Clustering**: Incremental Centroid-based clustering. Each new face is compared using **Cosine Distance** to existing centroids. If a match is found, the centroid is updated via a running average; otherwise, a new cluster is spawned.

### Reliability Layer
- **SQLite with WAL Mode**: Uses Write-Ahead Logging to support heavy concurrent reads/writes from the processing worker, web server, and WhatsApp sender.
- **Atomic Operations**: Photos are moved/copied only after database records are safely committed.
- **Resumability**: A global `file_hash` prevents redundant processing of the same image across sessions.

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
| **Backend** | Python 3.10+, FastAPI, Pydantic, SQLAlchemy/SQLite |
| **Frontend** | Vanilla JS, HTML5, CSS (Rose Gold Glassmorphism), Vite |
| **Desktop GUI** | CustomTkinter, PySide6 (Git Automator) |
| **Automation** | Playwright (WhatsApp), Google Drive API (Cloud) |
| **Image Ops** | Pillow (PIL), rawpy (RAW handling) |

---

## 📦 Installation & Setup

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

# Interface
LOG_LEVEL=INFO
```

---

## � Project Structure

*   **/backend**: Core logic. Includes `worker.py` (pipeline runner), `processor.py` (AI), and `cloud.py` (Drive interaction).
*   **/frontend**: The FastAPI server (`server.py`) and the web assets for the guest portal.
*   **/whatsapp_tool**: Playwright script for automated WhatsApp messaging.
*   **/EventRoot**: Default location for generated data.
    *   `/Incoming`: Where you drop raw photos.
    *   `/Processed`: Normalized JPEGs for web delivery.
    *   `/People`: AI-generated folders per identified person.
*   `WeddingFFapp.py`: The main desktop monitoring application.
*   `git_automator.py`: A utility to quickly sync local changes to your git repo.

---

## 🖥️ Dashboard & Tools

### WeddingFFapp (Main Dashboard)
Running `python WeddingFFapp.py` launches the "Mission Control" for your event:
*   **Real-time Stats**: Track total photos, faces detected, and guest enrollment status.
*   **Process Management**: Click-to-start the background workers and web servers.
*   **Live Activity**: A color-coded log showing exactly what the AI and Cloud workers are doing.

### Git Automator
For developers, `python git_automator.py` provides a GUI for quick Git staging, committing, and pushing, ensuring your project history is always up to date.

---

## 🛡️ Privacy & Performance
*   **Security**: Biometric data (embeddings) is stored in a local SQLite DB, never sent to external servers. Only processed JPEGs are uploaded to your private Google Drive.
*   **Efficiency**: The system is tuned for multi-core CPUs. A standard modern laptop can process roughly 1000 photos an hour.

---

## 📝 License
Distributed under the MIT License. See `LICENSE` for more information.

---

## 👤 Author
**P-Ranjith Kumar**
- GitHub: [@P-RanjithKumar](https://github.com/P-RanjithKumar)
- Project: [Wedding Face Forward](https://github.com/P-RanjithKumar/Wedding-Face-Forward)
