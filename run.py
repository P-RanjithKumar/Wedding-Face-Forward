import os
import sys
import time
import multiprocessing
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | MAIN | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def run_backend_worker():
    """Start the photo processing background worker."""
    logger.info("Starting Backend Worker...")
    
    # Add backend directory to path
    base_dir = Path(__file__).parent.resolve()
    backend_dir = base_dir / "backend"
    sys.path.insert(0, str(backend_dir))
    
    # Import and run worker main
    from app.worker import main as worker_main
    worker_main()

def run_frontend_server():
    """Start the FastAPI web server."""
    logger.info("Starting Frontend Server...")
    
    # Add frontend and backend directories to path
    base_dir = Path(__file__).parent.resolve()
    frontend_dir = base_dir / "frontend"
    backend_dir = base_dir / "backend"
    
    sys.path.insert(0, str(frontend_dir))
    sys.path.insert(0, str(backend_dir))
    
    # Import app from server module
    import uvicorn
    from server import app
    
    # Run uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    logger.info("=" * 60)
    logger.info("  WEDDING FACE FORWARD - ALL-IN-ONE TRIAL RUN")
    logger.info("=" * 60)
    
    # Create processes
    backend_proc = multiprocessing.Process(target=run_backend_worker, name="BackendWorker")
    frontend_proc = multiprocessing.Process(target=run_frontend_server, name="FrontendServer")
    
    try:
        # Start backend first to ensure directories and DB are ready
        backend_proc.start()
        time.sleep(2)  # Give backend a moment to initialize
        
        # Start frontend
        frontend_proc.start()
        
        logger.info("-" * 60)
        logger.info("  SYSTEM RUNNING!")
        logger.info("  Web UI: http://localhost:8000")
        logger.info("  Drop photos in: EventRoot/Incoming/")
        logger.info("  Press Ctrl+C to stop everything.")
        logger.info("-" * 60)
        
        # Wait for both processes
        while backend_proc.is_alive() and frontend_proc.is_alive():
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down everything...")
    finally:
        # Terminate processes
        if backend_proc.is_alive():
            backend_proc.terminate()
        if frontend_proc.is_alive():
            frontend_proc.terminate()
        
        # Join to cleanup
        backend_proc.join(timeout=2)
        frontend_proc.join(timeout=2)
        
        logger.info("All services stopped.")
