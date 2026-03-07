"""
Temporary Launcher for Wedding FaceForward (PySide6 version)
Run this file from the root directory: python run_pyside.py
"""

import sys
import multiprocessing

# Add the root directory to sys.path to resolve relative imports in the package
import dist_utils

if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    # Initialize AppData directories and copy user configuration files on first launch
    dist_utils.bootstrap_user_data()
    
    # --- Background Subprocess Router ---
    # PyInstaller uses sys.executable as the .exe file. When the GUI tries to launch
    # the worker/server/whatsapp using subprocess.Popen(sys.executable), it actually
    # just re-runs this file. We use flags to route execution to the right background task.
    if len(sys.argv) > 1:
        flag = sys.argv[1]
        if flag == "--run-worker":
            from app.worker import main as worker_main
            worker_main()
            sys.exit(0)
        elif flag == "--run-server":
            from frontend.server import app as fastapi_app
            import uvicorn
            uvicorn.run(fastapi_app, host='0.0.0.0', port=8000, log_level='warning')
            sys.exit(0)
        elif flag == "--run-whatsapp":
            try:
                import asyncio
                # Remove our routing flag so argparse inside the script doesn't choke
                sys.argv = [sys.argv[0]]
                
                # Tell Playwright where to find browser binaries.
                # When bundled by PyInstaller, playwright looks inside _internal/
                # for a .local-browsers folder that doesn't exist. Point it to the
                # system-wide location where 'playwright install' puts browsers.
                import os
                if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
                    default_browsers = os.path.join(
                        os.environ.get("LOCALAPPDATA", ""), "ms-playwright"
                    )
                    if os.path.isdir(default_browsers):
                        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = default_browsers
                
                # Add whatsapp_tool to path so db_whatsapp_sender's relative imports work
                wa_dir = str(dist_utils.get_whatsapp_dir())
                if wa_dir not in sys.path:
                    sys.path.insert(0, wa_dir)
                from whatsapp_tool.db_whatsapp_sender import main as wa_main
                asyncio.run(wa_main())
            except Exception as e:
                # Use errors='replace' to avoid cp1252 crash on Unicode chars
                print(f"WhatsApp launcher error: {e}".encode('ascii', errors='replace').decode(), flush=True)
                import traceback
                traceback.print_exc()
            sys.exit(0)
        elif flag == "--playwright-install":
            import sys
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

    # --- Main GUI Application ---
    from WeddingFFapp_pyside.main import run
    run()
