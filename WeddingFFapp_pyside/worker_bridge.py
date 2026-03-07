"""
WorkerBridge — Thread-safe signal bridge between background threads and the UI.

Replaces all self.after(0, lambda: ...) hacks from the CustomTkinter version.
Background threads emit signals; PySide6's event loop automatically marshals
the calls onto the UI thread. No race conditions, no lambda closures.
"""

from PySide6.QtCore import QObject, Signal


class WorkerBridge(QObject):
    """Thread-safe bridge between ProcessManager threads and the PySide6 UI."""

    # Log output from subprocess readers
    log_received = Signal(str, str)       # (message, level)

    # Stats refresh from the background refresh loop
    stats_updated = Signal(dict)          # full stats dict from DB

    # System lifecycle events
    system_started = Signal()
    system_stopped = Signal()
    start_error = Signal(str)             # error message
    restart_requested = Signal()          # Re-launch application
