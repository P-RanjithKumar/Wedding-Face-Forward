"""
AURA — Headless Backend Entry Point (by DARK intelligence)

This replaces run_pyside.py for the Tauri build.
No PySide6 dependency — just the background subprocess router.
Used as the PyInstaller entry point for the sidecar binary.
"""

import sys
import multiprocessing
import os

# Add the root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dist_utils

# Ensure the 'backend' directory is in sys.path so 'import app' works
backend_dir = str(dist_utils.get_backend_dir())
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Initialize AppData directories and copy user configuration files on first launch
    dist_utils.bootstrap_user_data()

    # --- Background Subprocess Router ---
    if len(sys.argv) > 1:
        flag = sys.argv[1]

        if flag == "--run-worker":
            from app.worker import main as worker_main
            worker_main()
            sys.exit(0)

        elif flag == "--run-server":
            import uvicorn
            # Use string import for reload support
            uvicorn.run("frontend.server:app", host='0.0.0.0', port=8000, log_level='info', reload=True)
            sys.exit(0)

        elif flag == "--run-whatsapp":
            try:
                import asyncio
                sys.argv = [sys.argv[0]]

                if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
                    default_browsers = os.path.join(
                        os.environ.get("LOCALAPPDATA", ""), "ms-playwright"
                    )
                    if os.path.isdir(default_browsers):
                        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = default_browsers

                wa_dir = str(dist_utils.get_whatsapp_dir())
                if wa_dir not in sys.path:
                    sys.path.insert(0, wa_dir)
                from whatsapp_tool.db_whatsapp_sender import main as wa_main
                asyncio.run(wa_main())
            except Exception as e:
                print(f"WhatsApp launcher error: {e}".encode('ascii', errors='replace').decode(), flush=True)
                import traceback
                traceback.print_exc()
            sys.exit(0)

        elif flag == "--playwright-install":
            try:
                from playwright._impl.__main__ import main
            except ImportError:
                try:
                    from playwright.__main__ import main
                except ImportError:
                    print("Playwright not found.")
                    sys.exit(1)
            sys.argv = ["playwright", "install", "chromium"]
            main()
            sys.exit(0)

    # No flag = print help and exit (no GUI in headless mode)
    print("AURA Backend (headless mode)")
    print("Usage:")
    print("  backend_entry.py --run-server     Start FastAPI on :8000")
    print("  backend_entry.py --run-worker     Start photo processing worker")
    print("  backend_entry.py --run-whatsapp   Start WhatsApp sender")
    sys.exit(0)
