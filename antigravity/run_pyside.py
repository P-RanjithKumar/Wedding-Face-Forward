"""
Temporary Launcher for AURA (by DARK intelligence) (PySide6 version)
Run this file from the root directory: python run_pyside.py
"""

import os
import sys
import multiprocessing

# Add the root directory to sys.path to resolve relative imports in the package
import dist_utils


def _ensure_std_streams():
    """Give the process real stdout/stderr when it has none.

    The installed AURA.exe is built without a console (console=False), so
    sys.stdout and sys.stderr are None unless the parent captures them.
    Libraries then crash: uvicorn's logging setup calls sys.stdout.isatty()
    and the guest server died with "Unable to configure formatter 'default'"
    (found 2026-11-14). Send stdout nowhere and stderr to a log file so
    crashes stay diagnosable.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    mode = sys.argv[1].lstrip("-") if len(sys.argv) > 1 else "app"
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        try:
            sys.stderr = open(dist_utils.get_logs_dir() / f"{mode}-errors.log", "a",
                              encoding="utf-8", buffering=1)
        except OSError:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _set_playwright_browsers_path():
    """Point Playwright at %LOCALAPPDATA%\\ms-playwright for BOTH launching and
    installing Chromium (WhatsApp sender).

    Bundled by PyInstaller, Playwright otherwise looks inside _internal/ for
    a .local-browsers folder. The old code only set this path when the folder
    already existed, and not at all for --playwright-install, so on a fresh
    PC the automatic browser download and the launch could use different
    folders (2026-11-14)."""
    if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ and os.environ.get("LOCALAPPDATA"):
        path = os.path.join(os.environ["LOCALAPPDATA"], "ms-playwright")
        os.makedirs(path, exist_ok=True)
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = path


if __name__ == "__main__":
    multiprocessing.freeze_support()
    _ensure_std_streams()

    # Initialize AppData directories and copy user configuration files on first launch
    dist_utils.bootstrap_user_data()
    
    # --- Background Subprocess Router ---
    # PyInstaller uses sys.executable as the .exe file. When the GUI tries to launch
    # the worker/server/whatsapp using subprocess.Popen(sys.executable), it actually
    # just re-runs this file. We use flags to route execution to the right background task.
    if len(sys.argv) > 1:
        flag = sys.argv[1]
        if flag == "--benchmark-compute":
            # One-time GPU vs CPU speed test, run in its own process so a
            # graphics driver crash cannot take AURA down (see app/compute.py)
            from app.compute import benchmark_cli
            sys.exit(benchmark_cli())
        elif flag == "--run-worker":
            from app.worker import main as worker_main
            worker_main()
            sys.exit(0)
        elif flag == "--run-server":
            from frontend.server import app as fastapi_app
            import uvicorn
            # Port chosen by the desktop app (first free from 8000), see dist_utils
            uvicorn.run(fastapi_app, host='0.0.0.0', port=dist_utils.get_guest_port(), log_level='warning')
            sys.exit(0)
        elif flag == "--run-whatsapp":
            try:
                import asyncio
                # Remove our routing flag so argparse inside the script doesn't choke
                sys.argv = [sys.argv[0]]
                
                # Launch and install must use the same browser folder
                _set_playwright_browsers_path()

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
            _set_playwright_browsers_path()  # install where --run-whatsapp looks
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
    from aura_app.main import run
    run()
