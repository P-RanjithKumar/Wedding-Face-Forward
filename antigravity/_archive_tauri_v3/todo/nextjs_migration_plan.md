# AURA UI Migration Plan: PySide6 → Next.js + Tauri Desktop App

> **Status (updated 2026-11-14):** In progress. `aura_web/`, the Tauri shell and the sidecar exist; the component checklists below were not kept up to date, so verify each page in `aura_web/src/app/` before trusting an unticked box.  
> **Goal:** Replace the PySide6 admin dashboard with a Next.js + Tauri desktop app — a single downloadable `.exe` installer.  
> **Decisions:** Tauri (confirmed), WebSocket/SSE for real-time, guest portal stays separate.

---

## 🏗️ Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│  AURA Desktop App (.exe built by Tauri)                  │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Next.js React Frontend (Admin Dashboard)          │   │
│  │  Stats, People, Settings, Health, WhatsApp, etc.   │   │
│  │  Connects to localhost:8000 via fetch + WebSocket   │   │
│  └──────────────────────────▲─────────────────────────┘   │
│                             │                             │
│  ┌──────────────────────────▼─────────────────────────┐   │
│  │  Tauri Rust Core                                   │   │
│  │  - Spawns embedded Python + backend on startup     │   │
│  │  - Manages Worker, FastAPI server, WhatsApp procs  │   │
│  │  - Native window, tray icon, auto-updater          │   │
│  └────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
           │ subprocess (embedded Python)
┌──────────▼───────────────────────────────────────────────┐
│  Python Backend (bundled, unchanged)                      │
│  FastAPI :8000  ·  Worker  ·  WhatsApp  ·  DB/Cloud/GPU  │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  Guest Portal (SEPARATE — frontend/index.html)            │
│  Served by FastAPI on :8000 — works for guests even      │
│  while the admin dashboard is running.                    │
└──────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> The guest portal (`frontend/`) stays completely separate. It's served by the FastAPI server and guests access it via a browser. It works independently of the admin dashboard.

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **UI Framework** | Next.js 15 (React 19) | Admin dashboard |
| **Styling** | Tailwind CSS v4 + custom CSS | "Liquid Glass" aesthetic |
| **Animations** | Framer Motion | Smooth transitions, micro-animations |
| **State** | Zustand | Global state (stats, system status) |
| **Data Fetching** | TanStack Query + WebSocket | Real-time stats & log streaming |
| **Desktop Shell** | Tauri v2 | Native `.exe`, process management |
| **Icons** | Lucide React | Modern iconography |
| **Charts** | Recharts | Stats visualization |
| **Backend** | FastAPI (existing) | REST API + WebSocket on :8000 |

---

## 📋 Components to Migrate (PySide6 → React)

### Core Dashboard

- [ ] Stat cards (`stat_card.py`, `status_card.py`) — 5 top-row stats
- [ ] Processing widget (`processing_widget.py`) — progress monitor
- [ ] Activity log (`activity_log.py`) — real-time log via WebSocket
- [ ] People list (`people_list.py`) — enrolled persons
- [ ] Status indicator (`status_indicator.py`) — system on/off

### Cloud & Sync

- [ ] Cloud widget (`cloud_widget.py`) — upload status
- [ ] Sync status card (`sync_status_card.py`) — cloud/local sync
- [ ] Stuck photos (`stuck_photos.py`) — stuck processing

### Dialogs → Pages/Modals

- [ ] Settings (`settings_dialog.py`) — full config management
- [ ] Merge dialog (`merge_dialog.py`) — cluster merge tool
- [ ] Health monitor (`health_monitor.py`) — process health
- [ ] Self-healing (`self_healing_dialog.py`) — DB repair
- [ ] GPU wizard (`gpu_wizard.py`) — GPU configuration
- [ ] Auth dialog (`auth_dialog.py`) — authentication
- [ ] Folder popup (`folder_popup.py`) — folder picker (via Tauri native dialog)

### Other

- [ ] WhatsApp tracker (`whatsapp_tracker.py`) — sending status
- [ ] System health (`system_health.py`) — overall health indicator
- [ ] Splash screen (`splash_screen.py`) — intro/loading
- [ ] Process manager (`process_manager.py`) → Tauri sidecar management

---

## � API Changes Required

### Existing endpoints (no changes)

`/api/health`, `/api/stats`, `/api/persons`, `/api/enroll`, `/api/photos`, `/api/photo`, `/api/thumbnail`

### New endpoints needed for admin dashboard

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/admin/settings` | GET/PUT | Read/update app config (.env) |
| `/api/admin/merge` | POST | Merge person clusters |
| `/api/admin/self-heal` | POST | Run DB self-healing |
| `/api/admin/gpu` | GET/PUT | GPU config & detection |
| `/api/admin/logs` | WebSocket | Real-time log streaming |
| `/api/admin/process-status` | WebSocket | Live process health |
| `/api/admin/stuck-photos` | GET/POST | View/fix stuck photos |
| `/api/admin/whatsapp/status` | GET | WhatsApp sending status |

---

## 🚀 Migration Phases

### Phase 0: Project Setup

1. Install Node.js v20 LTS and Rust toolchain
2. Create `aura_web/` with `create-next-app` + `cargo tauri init`
3. Set up Tailwind CSS, Framer Motion, Zustand, TanStack Query

### Phase 1: Core Dashboard (MVP)

1. Layout shell (sidebar + header) with "Liquid Glass" theme
2. Stat cards with live polling from `/api/stats`
3. Activity log with WebSocket real-time streaming
4. System start/stop via Tauri commands → Python subprocess
5. Dark mode, glassmorphism, blur effects, gradients

### Phase 2: Management Features

1. People list with search and photo counts
2. Processing monitor with progress bars
3. Cloud sync status + stuck photos

### Phase 3: Admin Tools (Dialogs → Pages)

1. Settings page
2. Cluster merge tool
3. Health monitor
4. Self-healing database tool
5. GPU wizard
6. WhatsApp tracker

### Phase 4: Desktop Packaging & Distribution

1. Configure Tauri sidecar to bundle embedded Python + backend
2. Build `.exe` installer with Tauri's NSIS bundler
3. Add splash screen, tray icon, auto-updater
4. Test on clean Windows machine (Windows Sandbox)

### Phase 5: Cleanup

1. Phase out `aura_app/` PySide6 code
2. Update distribution plan and `aura.spec`
3. Full end-to-end testing

---

## 📁 Proposed Folder Structure

```
aura_web/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx          # Root layout + sidebar
│   │   ├── page.tsx            # Dashboard home
│   │   ├── people/page.tsx     # People management
│   │   ├── processing/page.tsx # Processing monitor
│   │   ├── settings/page.tsx   # Settings config
│   │   ├── cloud/page.tsx      # Cloud sync
│   │   ├── whatsapp/page.tsx   # WhatsApp tracker
│   │   └── health/page.tsx     # System health
│   ├── components/
│   │   ├── ui/                 # Base primitives
│   │   ├── dashboard/          # Stat cards, widgets
│   │   ├── dialogs/            # Modals
│   │   └── layout/             # Sidebar, header
│   ├── lib/
│   │   ├── api.ts              # FastAPI client
│   │   ├── ws.ts               # WebSocket manager
│   │   └── store.ts            # Zustand stores
│   └── styles/                 # Global CSS + Liquid Glass theme
├── src-tauri/
│   ├── src/main.rs             # Process management, Tauri commands
│   ├── tauri.conf.json         # Window config, app metadata
│   ├── sidecar/                # Bundled Python + backend
│   └── icons/                  # App icons
├── package.json
└── next.config.js
```
