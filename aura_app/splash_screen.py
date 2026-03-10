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
        self.video_widget.show()
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
        else:
            # If no video found, skip the splash screen entirely
            QTimer.singleShot(0, self._finish)

        # When the video finishes or fails, start fade-out
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.errorOccurred.connect(self._on_error)

        self._started = False

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _find_video():
        """Locate the intro video — check known locations."""
        candidates = []
        target_name = "intro-video.mp4"

        def _scan_dir(d):
            if not os.path.isdir(d):
                return
            for f in os.listdir(d):
                f_lower = f.lower()
                if f_lower == target_name:
                    candidates.insert(0, os.path.join(d, f)) # Highest priority
                elif f_lower.endswith(('.mp4', '.avi', '.mkv', '.mov', '.webm')):
                    candidates.append(os.path.join(d, f))

        # 1. Check bundled root (PyInstaller _internal where 'datas' are placed)
        bundled_root = dist_utils.get_bundled_root()
        _scan_dir(os.path.join(str(bundled_root), "logo"))

        # 2. Check project root (dev mode or beside exe)
        project_root = dist_utils.get_project_root()
        _scan_dir(os.path.join(str(project_root), "logo"))

        # 3. Fallback: assets folder (for packaged app)
        _scan_dir(str(dist_utils.get_assets_dir()))

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
        # Also finish on InvalidMedia so we don't hang if codec is missing
        if status in (QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.InvalidMedia):
            self._start_fade_out()

    def _on_error(self, error, error_string):
        print(f"Splash player error: {error} - {error_string}")
        self._start_fade_out()

    def _start_fade_out(self):
        """Fade the entire overlay out over ~600ms."""
        self.overlay_opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.overlay_opacity)
        self.overlay_opacity.setOpacity(1.0)

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
