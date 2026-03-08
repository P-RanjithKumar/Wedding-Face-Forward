"""
Premium Video Splash Screen for AURA (by DARK intelligence).
Plays an intro video as a full-window overlay, then fades out to reveal the app.
The video covers the ENTIRE app area — no gaps, no borders.
"""

import os
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, Signal, QUrl
from PySide6.QtGui import QColor, QPainter
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

import dist_utils


class PremiumSplashScreen(QWidget):
    """
    A full-window overlay that plays an intro video, then fades out.
    No layouts — everything is manually sized to guarantee full coverage.
    """
    animationFinished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── Video Widget — direct child, no layout ───────────────────────────
        self.video_widget = QVideoWidget(self)
        # KeepAspectRatioByExpanding = scale up to fill, cropping overflow
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)

        # ── Media Player ─────────────────────────────────────────────────────
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.5)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)

        # Resolve video path
        video_path = self._find_video()
        if video_path:
            self.player.setSource(QUrl.fromLocalFile(video_path))

        # When the video finishes, start fade-out
        self.player.mediaStatusChanged.connect(self._on_media_status)

        # ── Overall opacity effect for the smooth fade-out ───────────────────
        self.overlay_opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.overlay_opacity)
        self.overlay_opacity.setOpacity(1.0)

        self._started = False

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _find_video():
        """Locate the intro video — check known locations."""
        candidates = []

        project_root = dist_utils.get_project_root()
        logo_dir = os.path.join(str(project_root), "logo")
        if os.path.isdir(logo_dir):
            for f in os.listdir(logo_dir):
                if f.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.webm')):
                    candidates.append(os.path.join(logo_dir, f))

        # Fallback: assets folder (for packaged app)
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        if os.path.isdir(assets_dir):
            for f in os.listdir(assets_dir):
                if f.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.webm')):
                    candidates.append(os.path.join(assets_dir, f))

        return candidates[0] if candidates else None

    # ─────────────────────────────────────────────────────────────────────────
    # Events
    # ─────────────────────────────────────────────────────────────────────────
    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()
        # Force video widget to fill the entire overlay
        self.video_widget.setGeometry(0, 0, self.width(), self.height())
        if not self._started:
            self._started = True
            QTimer.singleShot(100, self._begin_playback)

    def resizeEvent(self, event):
        """Keep the video widget sized to fill the entire overlay at all times."""
        super().resizeEvent(event)
        self.video_widget.setGeometry(0, 0, self.width(), self.height())

    def paintEvent(self, event):
        """Paint a solid dark background behind the video (visible before first frame)."""
        painter = QPainter(self)
        painter.setBrush(QColor(10, 10, 12))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

    # ─────────────────────────────────────────────────────────────────────────
    # Playback
    # ─────────────────────────────────────────────────────────────────────────
    def _begin_playback(self):
        """Lock the main window size and start playing the video."""
        # Walk up to find the QMainWindow
        win = self.window()
        if win:
            self._saved_min = win.minimumSize()
            self._saved_max = win.maximumSize()
            win.setFixedSize(win.size())

        self.player.play()

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._start_fade_out()

    def _start_fade_out(self):
        """Fade the entire overlay out over ~600ms."""
        self.fade_out = QPropertyAnimation(self.overlay_opacity, b"opacity")
        self.fade_out.setDuration(600)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.Type.InQuart)
        self.fade_out.finished.connect(self._finish)
        self.fade_out.start()

    def _finish(self):
        """Clean up: restore window resizability, emit signal, remove self."""
        self.player.stop()

        # Restore the main window's original resize constraints
        win = self.window()
        if win and hasattr(self, '_saved_min'):
            win.setMinimumSize(self._saved_min)
            win.setMaximumSize(self._saved_max)

        self.animationFinished.emit()
        self.hide()
        self.deleteLater()
