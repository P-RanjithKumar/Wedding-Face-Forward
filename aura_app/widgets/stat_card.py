"""
StatCard — Big number + title label with accent flash animation.
Ported from CustomTkinter StatCard class.
"""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QTimer

from ..theme import COLORS, c


class StatCard(QFrame):
    """A stat card with big number and label — soft neutral background."""

    def __init__(self, title: str, value: str = "0", highlight: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("stat_card_highlight" if highlight else "stat_card")

        self._mode = "light"
        self._highlight = highlight

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 18, 12, 16)
        layout.setSpacing(4)

        # Big number
        self.value_label = QLabel(value)
        self.value_label.setObjectName("stat_value")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)

        # Title
        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("stat_title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self._last_value = value

    def update_value(self, value: str):
        """Update the displayed value with a brief accent flash."""
        if value != self._last_value:
            accent = c("accent", self._mode)
            primary = c("text_primary", self._mode)
            self.value_label.setStyleSheet(f"color: {accent}; font-size: 26px; font-weight: bold;")
            QTimer.singleShot(300, lambda: self.value_label.setStyleSheet(
                f"color: {primary}; font-size: 26px; font-weight: bold;"
            ))
            self.value_label.setText(value)
            self._last_value = value

    def set_mode(self, mode: str):
        """Update light/dark mode tracking."""
        self._mode = mode.lower()
