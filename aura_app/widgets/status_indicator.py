"""
StatusIndicator — Animated pulsing dot with status label.
Ported from CustomTkinter StatusIndicator class.
"""

from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PySide6.QtCore import QTimer

from ..theme import COLORS, c


class StatusIndicator(QWidget):
    """Animated status dot with label — shows Running/Starting/Stopping/Stopped."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "light"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.dot = QLabel("●")
        self.dot.setObjectName("status_dot")
        self.dot.setStyleSheet(f"color: {c('text_secondary', self._mode)};")
        layout.addWidget(self.dot)

        self.label = QLabel("Stopped")
        self.label.setObjectName("status_label")
        self.label.setStyleSheet(f"color: {c('text_secondary', self._mode)};")
        layout.addWidget(self.label)

        self._pulsing = False
        self._pulse_step = 0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(400)
        self._pulse_timer.timeout.connect(self._pulse)

    def set_running(self):
        self._pulsing = True
        color = c("success", self._mode)
        self.label.setText("Running")
        self.label.setStyleSheet(f"color: {color}; font-size: 13px;")
        self._pulse_timer.start()

    def set_starting(self):
        self._pulsing = True
        color = c("warning", self._mode)
        self.label.setText("Starting...")
        self.label.setStyleSheet(f"color: {color}; font-size: 13px;")
        self._pulse_timer.start()

    def set_stopping(self):
        self._pulsing = True
        color = c("warning", self._mode)
        self.label.setText("Stopping...")
        self.label.setStyleSheet(f"color: {color}; font-size: 13px;")
        self._pulse_timer.start()

    def set_stopped(self):
        self._pulsing = False
        self._pulse_timer.stop()
        sec = c("text_secondary", self._mode)
        self.dot.setStyleSheet(f"color: {sec}; font-size: 12px;")
        self.label.setText("Stopped")
        self.label.setStyleSheet(f"color: {sec}; font-size: 13px;")

    def _pulse(self):
        if not self._pulsing:
            self._pulse_timer.stop()
            return

        text = self.label.text()
        if "Stopping" in text or "Starting" in text:
            colors = [
                c("warning", self._mode), "#ffaa33",
                c("warning", self._mode), "#cc7700"
            ]
        else:
            colors = [
                c("success", self._mode), "#5fd47a",
                c("success", self._mode), "#2aa64a"
            ]

        color = colors[self._pulse_step % len(colors)]
        self.dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._pulse_step += 1

    def set_mode(self, mode: str):
        self._mode = mode.lower()
