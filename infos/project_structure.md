# Project Structure: AURA (by DARK intelligence)

This document provides a comprehensive overview of the files and folders in the AURA project.

## Directory Tree

```text
AURA/
├── backend/                # Server-side logic and processing pipeline
│   ├── app/                # Core application modules
│   │   ├── cloud.py        # Google Drive API integration
│   │   ├── cluster.py      # Face clustering logic
│   │   ├── config.py       # Configuration management (.env)
│   │   ├── db.py           # SQLite database interaction
│   │   ├── enrollment.py   # Person enrollment and face data
│   │   ├── phase.py        # System phase coordination (Face detection/Grouping/Uploading)
│   │   ├── processor.py    # Main photo processing logic (InsightFace)
│   │   ├── router.py       # API endpoints for web communication
│   │   ├── upload_queue.py # Cloud upload management and retry logic
│   │   ├── watcher.py      # File system watcher for 'Incoming' folder
│   │   └── worker.py       # Background task worker for photo processing
│   ├── requirements.txt    # Backend Python dependencies
│   └── tests/              # Unit and integration tests
├── frontend/               # Web-based administration interface
│   ├── css/                # Styling (Vanilla CSS)
│   ├── js/                 # Client-side logic (Vanilla JS)
│   ├── index.html          # Main web entry point
│   ├── server.py           # FastAPI server for the Web UI
│   ├── requirements.txt    # Frontend Python dependencies
│   └── vite.config.js      # Frontend build configuration
├── whatsapp_tool/          # WhatsApp notification integration
│   ├── db_whatsapp_sender.py # Script for sending messages via WhatsApp
│   └── README.md           # Setup instructions for WhatsApp automation
├── EventRoot/              # Default data directory (created at runtime)
│   ├── Incoming/           # Drop photos here to start processing
│   ├── Processed/          # Correctly identified and grouped photos
│   ├── People/             # Folders containing solo/group shots of people
│   └── Admin/              # Logs, errors, and unidentifiable faces
├── data/                   # Database and persistent storage
│   └── wedding.db          # Main SQLite database
├── logs/                   # System runtime logs
├── WeddingFFapp.py         # Main Visual Admin Dashboard (Desktop App)
├── run.py                  # All-in-one runner for Backend & Frontend
├── git_automator.py        # Utility for automated git operations
├── erase_all_data.py       # "Big Red Button" to reset everything for a new event
├── diagnose.py             # System health and diagnostic utility
├── reupload_cloud.py       # Tool to force-sync local processed files to cloud
├── system_architecture.md  # Detailed high-level architectural documentation
├── PROJECT_DEV_LOG.md      # Historical log of development and bug fixes
├── README.md               # Getting started and installation guide
├── .env                    # System environment variables (Critical)
├── credentials.json        # Google Cloud service account/OAuth credentials
└── check_*.py              # Various debugging and verification scripts (e.g., check_db.py)
```

## Key Files & Folders

- **[WeddingFFapp.py](WeddingFFapp.py)**: The primary desktop application built with `customtkinter`. Use this to monitor the system in real-time.
- **[backend/app/config.py](backend/app/config.py)**: Defines all system settings, paths, and limits. Modify the `.env` file to change these.
- **[backend/app/processor.py](backend/app/processor.py)**: The "brain" of the system that detects and identifies faces in new photos.
- **[backend/app/watcher.py](backend/app/watcher.py)**: Watches the `EventRoot/Incoming` directory and triggers the processing pipeline.
- **[frontend/index.html](frontend/index.html)**: The web interface for viewing and managing faces from any browser.
- **[erase_all_data.py](erase_all_data.py)**: Critical script for resetting the system database and folders between events.
- **[EventRoot/](EventRoot/)**: This is where all the physical photos go.
  - **Incoming**: Put your original photos here.
  - **People**: Photos will be sorted into folders for each person here.
