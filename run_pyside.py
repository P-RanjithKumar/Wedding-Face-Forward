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
            import runpy
            runpy.run_path(str(dist_utils.get_whatsapp_dir() / "db_whatsapp_sender.py"))
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
