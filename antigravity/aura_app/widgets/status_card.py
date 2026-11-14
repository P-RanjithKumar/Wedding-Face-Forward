"""
StatusCard — Bordered status display with title, value, and detail labels.
Ported from CustomTkinter StatusCard class.
"""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from PySide6.QtCore import Qt

from ..theme import c


class StatusCard(QFrame):
    """Status card with border, title, bold value, and detail text."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("status_card")
        self._mode = "light"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(4)

        # Title
        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("card_title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.title_label)

        # Value
        self.value_label = QLabel("—")
        self.value_label.setObjectName("card_value")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)

        # Detail
        self.detail_label = QLabel("")
        self.detail_label.setObjectName("card_detail")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.detail_label)

    def set_status(self, value: str, detail: str = "", color=None):
        """Update the status display."""
        self.value_label.setText(value)
        if color:
            self.value_label.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold;")
        else:
            primary = c("text_primary", self._mode)
            self.value_label.setStyleSheet(f"color: {primary}; font-size: 22px; font-weight: bold;")
        self.detail_label.setText(detail)

    def set_mode(self, mode: str):
        self._mode = mode.lower()
