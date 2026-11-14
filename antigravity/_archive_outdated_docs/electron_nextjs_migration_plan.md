# Next.js + Electron Migration Plan for AURA

## Objective

Migrate the existing PySide6 frontend of the AURA application to a modern web stack (Next.js with Tailwind CSS and Framer Motion) and bundle it as a native desktop application using Electron. This will resolve the OS-level freezing issues caused by PySide6's frameless window styling while delivering the ultra-premium "Liquid Glass" UI.

## Why Next.js + Electron?

Electron is the industry standard for wrapping web technologies into fully-fledged, installable desktop applications (used by VS Code, Discord, Slack, etc.). Using Next.js enables us to easily write the UI with React and Tailwind CSS, giving us absolute control over the aesthetics and animations.

## High-Level Architecture

- **Backend (Existing)**: The current FastAPI server (`frontend/server.py`) and processing workers will remain exactly as they are. The Python backend will continue to handle database operations, file matching, and WhatsApp sending.
- **Frontend (New)**: A standard Next.js application that fetches data from `localhost:8000` (the FastAPI server).
- **Desktop Wrapper (New)**: An Electron main process that:
  1. Spawns the Python backend (`run_pyside.py --run-server`, `--run-worker`, etc.) as hidden background processes.
  2. Spawns the Next.js frontend (or loads the statically exported Next.js bundle).
  3. Displays a native, frameless window with absolute stability.

## Step-by-Step Execution Plan

### 1. Initialize the Web Frontend

- Create a new folder (e.g., `aura_frontend`) in the project root.
- Run `npx create-next-app@latest` inside `aura_frontend` (using TypeScript, Tailwind CSS, App Router).
- Install animation libraries (`framer-motion`, `lucide-react` for icons).

### 2. Port the PySide6 UI to React Components

- **Global Theme**: Setup Tailwind configuration to mirror the "Midnight Aura" and "Bright Glass" palettes.
- **Title Bar**: Create a custom window drag region component for Electron.
- **Components**: Recreate `HoverAnimCard`, `AuraButton`, and `GlassCard` using Tailwind utility classes (`backdrop-blur-xl`, `bg-white/10`, `shadow-[...]`) and Framer Motion for the cinematic bounce/hover effects.
- **Splash Screen**: Build a React component that renders the `intro-video.mp4` full screen and fades out when the backend is ready.

### 3. Connect Frontend to the Python Backend

- Expose the necessary endpoints on the FastAPI server if they don't already exist (e.g., `GET /api/stats`, `GET /api/health`, `POST /api/enroll`).
- Create a Next.js hook or utility file to poll `localhost:8000/api/stats` and update the dashboard in real-time.

### 4. Setup Electron Desktop App

- Install Electron and related builders (`electron`, `electron-builder`, `concurrently` for dev mode) inside the `aura_frontend` directory.
- Create an `electron/main.js` script that uses `child_process.spawn` to start the Python FastAPI server automatically when the app opens.
- Configure Electron to open a frameless browser window and load the Next.js interface.

### 5. Packaging and Distribution

- Update Inno Setup scripts to package the finished Electron build alongside the internal Python environment, creating a single massive `.exe` just like before, but vastly more stable rendering.
