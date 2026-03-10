"""
ActivityLog — Dark terminal-style log with colored entries.
Ported from CustomTkinter ActivityLog class.
"""

from datetime import datetime

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QTextEdit
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor
from PySide6.QtCore import Qt

from ..theme import c


# Log category colors (same in both modes — terminal always dark)
TAG_COLORS = {
    "proc":     "#5ac8fa",
    "db":       "#ffcc00",
    "cloud":    "#af52de",
    "whatsapp": "#34c759",
    "server":   "#007aff",
    "error":    "#ff3b30",
    "timestamp": "#888888",
    "info":     "#c0c0d0",
}


class ActivityLog(QFrame):
    """Activity log with dark grey bg and black terminal — per design guide."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("log_outer")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Title
        title = QLabel("ACTIVITY LOG")
        title.setObjectName("log_title")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        # Terminal text area
        self.textbox = QTextEdit()
        self.textbox.setObjectName("log_terminal")
        self.textbox.setReadOnly(True)
        self.textbox.setMinimumHeight(120)
        layout.addWidget(self.textbox)

    def add_log(self, message: str, level: str = "info"):
        """Add a log entry with icon and color coding."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        icon = "•"
        tag = "info"
        display_msg = message
        lower_msg = message.lower()

        if "app.processor" in lower_msg or "processing" in lower_msg:
            icon = "⚙️"
            tag = "proc"
            display_msg = message.replace("app.processor |", "").strip()
            if display_msg.startswith("[Worker]"):
                display_msg = display_msg.replace("[Worker]", "").strip()
            display_msg = f"Processor | {display_msg}"

        elif "app.db" in lower_msg or "database" in lower_msg:
            icon = "🗄️"
            tag = "db"
            display_msg = message.replace("app.db |", "").strip()
            if display_msg.startswith("[Worker]"):
                display_msg = display_msg.replace("[Worker]", "").strip()
            display_msg = f"Database | {display_msg}"

        elif "app.cloud" in lower_msg or "drive" in lower_msg:
            icon = "☁️"
            tag = "cloud"
            display_msg = message.replace("app.cloud |", "").strip()
            if display_msg.startswith("[Worker]"):
                display_msg = display_msg.replace("[Worker]", "").strip()
            display_msg = f"Cloud | {display_msg}"

        elif "whatsapp" in lower_msg:
            icon = "💬"
            tag = "whatsapp"
            if display_msg.startswith("[WhatsApp]"):
                display_msg = display_msg.replace("[WhatsApp]", "").strip()
            display_msg = f"WhatsApp | {display_msg}"

        elif "server" in lower_msg:
            icon = "🌐"
            tag = "server"
            if display_msg.startswith("[Server]"):
                display_msg = display_msg.replace("[Server]", "").strip()
            display_msg = f"Server | {display_msg}"

        elif level == "error":
            icon = "✗"
            tag = "error"
        elif level == "success":
            icon = "✓"
            tag = "whatsapp"

        # Build the formatted line and prepend to the top
        color = TAG_COLORS.get(tag, TAG_COLORS["info"])
        prefix = f"{timestamp}  {icon}  "

        cursor = self.textbox.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)

        # Insert message in tag color
        fmt_msg = QTextCharFormat()
        fmt_msg.setForeground(QColor(color))
        cursor.insertText(f"{display_msg}\n", fmt_msg)

        # Insert prefix (timestamp + icon) at the very start of the line
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        fmt_prefix = QTextCharFormat()
        fmt_prefix.setForeground(QColor(color))
        cursor.insertText(prefix, fmt_prefix)

        # Ensure cursor stays at top
        self.textbox.setTextCursor(cursor)
        self.textbox.moveCursor(QTextCursor.MoveOperation.Start)
