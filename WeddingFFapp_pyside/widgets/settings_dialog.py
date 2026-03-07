"""
SettingsDialog — GUI for editing .env configuration variables.

A polished modal dialog organized into categorized sections:
  • Paths
  • Processing
  • Watcher
  • Modes
  • Google Drive / Cloud
  • Upload Settings
  • Phase Coordination

Each setting uses the appropriate input widget (spinbox, toggle, file picker,
text field) and changes are written back to the .env file on save.
"""

import os
import re
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QCheckBox, QFileDialog, QSizePolicy, QApplication,
    QMessageBox
)
from PySide6.QtGui import QCursor, QFont, QIcon
from PySide6.QtCore import Qt, Signal

from ..theme import c, COLORS


# ─────────────────────────────────────────────────────────
# .env file I/O helpers
# ─────────────────────────────────────────────────────────

def _find_env_path():
    """Locate the .env file — project root first, then backend."""
    try:
        import dist_utils
        return dist_utils.get_env_file_path()
    except ImportError:
        pass
    base = Path(__file__).parent.parent.parent.resolve()
    env_path = base / ".env"
    if env_path.exists():
        return env_path
    backend_env = base / "backend" / ".env"
    if backend_env.exists():
        return backend_env
    # Default to project root even if it doesn't exist yet
    return env_path


def _parse_env_file(env_path: Path) -> dict:
    """Parse a .env file into an ordered dict of {KEY: value}."""
    values = {}
    if not env_path.exists():
        return values
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            values[key.strip()] = value.strip()
    return values


def _write_env_file(env_path: Path, updates: dict):
    """
    Update the .env file in-place, preserving comments and structure.
    Only lines whose key matches a key in `updates` are changed.
    """
    if not env_path.exists():
        # Write fresh
        with open(env_path, "w", encoding="utf-8") as f:
            for key, val in updates.items():
                f.write(f"{key}={val}\n")
        return

    lines = []
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                continue
        new_lines.append(line)

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


# ─────────────────────────────────────────────────────────
# Setting field metadata
# ─────────────────────────────────────────────────────────

# Each setting: (env_key, label, description, field_type, default, extra)
# field_type: "path", "int", "float", "bool", "text", "loglevel", "extensions"
SETTINGS_SCHEMA = [
    # ── Paths ──
    {
        "section": "📂  Paths",
        "fields": [
            ("EVENT_ROOT", "Event Root", "Root folder for Incoming/Processed/People", "path", "./EventRoot", {}),
            ("DB_PATH", "Database Path", "SQLite database file location", "path", "./data/wedding.db", {}),
        ]
    },
    # ── Processing ──
    {
        "section": "⚡  Processing",
        "fields": [
            ("WORKER_COUNT", "Worker Count", "Number of parallel processing workers", "int", "6", {"min": 1, "max": 32}),
            ("CLUSTER_THRESHOLD", "Cluster Threshold", "Face similarity threshold (lower = stricter)", "float", "0.7", {"min": 0.1, "max": 1.0, "step": 0.05}),
            ("MAX_IMAGE_SIZE", "Max Image Size", "Maximum image dimension in pixels", "int", "2048", {"min": 512, "max": 8192}),
            ("THUMBNAIL_SIZE", "Thumbnail Size", "Generated thumbnail size in pixels", "int", "300", {"min": 64, "max": 1024}),
        ]
    },
    # ── Watcher ──
    {
        "section": "👁  Watcher",
        "fields": [
            ("SCAN_INTERVAL", "Scan Interval", "Seconds between folder scans for new photos", "int", "30", {"min": 1, "max": 300}),
            ("SUPPORTED_EXTENSIONS", "Supported Extensions", "Comma-separated file extensions to process", "extensions", ".jpg,.jpeg,.png,.webp,.avif,.heic,.heif,.bmp,.tiff,.tif,.gif,.cr2,.nef,.arw,.dng,.orf,.rw2,.raf,.pef", {}),
        ]
    },
    # ── Modes ──
    {
        "section": "🔧  Modes",
        "fields": [
            ("DRY_RUN", "Dry Run", "Preview mode — no files are actually moved", "bool", "false", {}),
            ("LOG_LEVEL", "Log Level", "Logging verbosity", "loglevel", "INFO", {}),
            ("USE_HARDLINKS", "Use Hardlinks", "Use filesystem hardlinks instead of copying files", "bool", "true", {}),
        ]
    },
    # ── Google Drive ──
    {
        "section": "☁  Google Drive",
        "fields": [
            ("GOOGLE_CREDENTIALS_FILE", "Credentials File", "Path to Google service account JSON", "path", "service_account.json", {}),
            ("DRIVE_ROOT_FOLDER_ID", "Drive Root Folder ID", "Google Drive folder ID for uploads", "text", "", {}),
        ]
    },
    # ── Upload Settings ──
    {
        "section": "📤  Upload Settings",
        "fields": [
            ("UPLOAD_TIMEOUT_CONNECT", "Connect Timeout", "Connection timeout in seconds", "int", "10", {"min": 1, "max": 120}),
            ("UPLOAD_TIMEOUT_READ", "Read Timeout", "Read timeout in seconds", "int", "30", {"min": 5, "max": 300}),
            ("UPLOAD_MAX_RETRIES", "Max Retries", "Number of upload retry attempts", "int", "3", {"min": 0, "max": 10}),
            ("UPLOAD_RETRY_DELAY", "Retry Delay", "Seconds between retries", "int", "2", {"min": 1, "max": 30}),
            ("UPLOAD_BATCH_SIZE", "Batch Size", "Photos per upload batch", "int", "5", {"min": 1, "max": 50}),
            ("UPLOAD_QUEUE_ENABLED", "Upload Queue", "Enable the upload queue", "bool", "true", {}),
        ]
    },
    # ── Phase Coordination ──
    {
        "section": "🔄  Phase Coordination",
        "fields": [
            ("FOLDER_SYNC_INTERVAL", "Folder Sync Interval", "Seconds between Drive folder sync checks", "int", "10", {"min": 1, "max": 120}),
            ("PROCESS_BATCH_SIZE", "Process Batch Size", "Photos to process before switching to upload", "int", "30", {"min": 1, "max": 200}),
            ("CLOUD_REFRESH_INTERVAL", "Cloud Refresh Interval", "Seconds between Drive connection refreshes", "int", "60", {"min": 10, "max": 600}),
        ]
    },
]


# ─────────────────────────────────────────────────────────
# Custom Toggle Switch widget
# ─────────────────────────────────────────────────────────

class ToggleSwitch(QPushButton):
    """A macOS-style animated toggle switch."""

    toggled_signal = Signal(bool)

    def __init__(self, checked=False, mode="light", parent=None):
        super().__init__(parent)
        self._checked = checked
        self._mode = mode
        self.setFixedSize(48, 26)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setCheckable(True)
        self.setChecked(checked)
        self.clicked.connect(self._on_click)
        self._update_style()

    def _on_click(self):
        self._checked = self.isChecked()
        self._update_style()
        self.toggled_signal.emit(self._checked)

    def _update_style(self):
        if self._checked:
            bg = c("success", self._mode)
            knob_pos = "margin-left: 22px;"
        else:
            bg = c("text_secondary", self._mode)
            knob_pos = "margin-left: 2px;"

        self.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {bg};"
            f"  border-radius: 13px;"
            f"  border: none;"
            f"  padding: 0;"
            f"}}"
        )

    def is_on(self):
        return self._checked

    def set_mode(self, mode):
        self._mode = mode
        self._update_style()

    def paintEvent(self, event):
        super().paintEvent(event)
        from PySide6.QtGui import QPainter, QColor
        from PySide6.QtCore import QRectF
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Knob
        knob_diameter = 20
        y = (self.height() - knob_diameter) / 2
        if self._checked:
            x = self.width() - knob_diameter - 3
        else:
            x = 3

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(x, y, knob_diameter, knob_diameter))
        painter.end()


# ─────────────────────────────────────────────────────────
# Section Header widget
# ─────────────────────────────────────────────────────────

class SectionHeader(QFrame):
    """A styled collapsible section header."""

    def __init__(self, title: str, mode: str = "light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self.setObjectName("settings_section_header")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        self.label = QLabel(title)
        self.label.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 14px; "
            f"font-weight: bold; background: transparent;"
        )
        layout.addWidget(self.label)
        layout.addStretch()

        self._apply_style()

    def _apply_style(self):
        accent = c("accent", self._mode)
        self.setStyleSheet(
            f"QFrame#settings_section_header {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f"    stop:0 {accent}22, stop:1 transparent);"
            f"  border-left: 3px solid {accent};"
            f"  border-radius: 6px;"
            f"}}"
        )

    def set_mode(self, mode):
        self._mode = mode
        self._apply_style()
        self.label.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 14px; "
            f"font-weight: bold; background: transparent;"
        )


# ─────────────────────────────────────────────────────────
# Settings Row widget
# ─────────────────────────────────────────────────────────

class SettingRow(QFrame):
    """A single setting row with label, description, and input widget."""

    value_changed = Signal()

    def __init__(self, env_key, label, description, field_type, default,
                 current_value, extra, mode="light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self._env_key = env_key
        self._field_type = field_type
        self._default = default
        self.setObjectName("settings_row")

        self._apply_row_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        # Left: label + description
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_label = QLabel(label)
        name_label.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 13px; "
            f"font-weight: bold; background: transparent;"
        )
        info_layout.addWidget(name_label)

        desc_label = QLabel(description)
        desc_label.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 10px; "
            f"background: transparent;"
        )
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)

        layout.addLayout(info_layout, 1)

        # Right: input widget
        self.input_widget = self._create_input(
            field_type, current_value or default, extra
        )
        layout.addWidget(self.input_widget)

        # Reset button (tiny)
        reset_btn = QPushButton("↻")
        reset_btn.setFixedSize(24, 24)
        reset_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        reset_btn.setToolTip(f"Reset to default: {default}")
        reset_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {c('stat_bg', self._mode)}; "
            f"  color: {c('text_secondary', self._mode)}; "
            f"  border-radius: 12px; font-size: 12px; border: none; "
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {c('warning', self._mode)}; color: white; "
            f"}}"
        )
        reset_btn.clicked.connect(lambda: self._reset_to_default())
        layout.addWidget(reset_btn)

        self._name_label = name_label
        self._desc_label = desc_label
        self._reset_btn = reset_btn

    def _apply_row_style(self):
        bg = c("bg_card", self._mode)
        border = c("border", self._mode)
        self.setStyleSheet(
            f"QFrame#settings_row {{"
            f"  background-color: {bg}; "
            f"  border: 1px solid {border}; "
            f"  border-radius: 12px; "
            f"}}"
        )

    def _create_input(self, field_type, value, extra):
        """Create the appropriate input widget for the field type."""
        input_style = (
            f"background: {c('stat_bg', self._mode)}; "
            f"color: {c('text_primary', self._mode)}; "
            f"border: 1px solid {c('border', self._mode)}; "
            f"border-radius: 8px; padding: 4px 8px; font-size: 12px;"
        )

        if field_type == "int":
            widget = QSpinBox()
            widget.setMinimum(extra.get("min", 0))
            widget.setMaximum(extra.get("max", 99999))
            widget.setValue(int(value) if value else 0)
            widget.setFixedWidth(120)
            widget.setStyleSheet(input_style)
            widget.valueChanged.connect(lambda: self.value_changed.emit())
            return widget

        elif field_type == "float":
            widget = QDoubleSpinBox()
            widget.setMinimum(extra.get("min", 0.0))
            widget.setMaximum(extra.get("max", 1.0))
            widget.setSingleStep(extra.get("step", 0.05))
            widget.setDecimals(2)
            widget.setValue(float(value) if value else 0.0)
            widget.setFixedWidth(120)
            widget.setStyleSheet(input_style)
            widget.valueChanged.connect(lambda: self.value_changed.emit())
            return widget

        elif field_type == "bool":
            checked = str(value).lower() == "true"
            toggle = ToggleSwitch(checked=checked, mode=self._mode)
            toggle.toggled_signal.connect(lambda: self.value_changed.emit())
            return toggle

        elif field_type == "loglevel":
            widget = QComboBox()
            levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            widget.addItems(levels)
            current = str(value).upper()
            if current in levels:
                widget.setCurrentIndex(levels.index(current))
            widget.setFixedWidth(120)
            widget.setStyleSheet(
                f"QComboBox {{ {input_style} }}"
                f"QComboBox::drop-down {{ border: none; width: 24px; }}"
                f"QComboBox::down-arrow {{ image: none; }}"
                f"QComboBox QAbstractItemView {{ "
                f"  background: {c('stat_bg', self._mode)}; "
                f"  color: {c('text_primary', self._mode)}; "
                f"  border: 1px solid {c('border', self._mode)}; "
                f"  selection-background-color: {c('accent', self._mode)}; "
                f"  selection-color: white; padding: 4px; }}"
            )
            widget.currentTextChanged.connect(lambda: self.value_changed.emit())
            return widget

        elif field_type == "path":
            container = QWidget()
            container.setStyleSheet("background: transparent;")
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)

            line = QLineEdit(str(value))
            line.setFixedWidth(200)
            line.setStyleSheet(input_style)
            line.textChanged.connect(lambda: self.value_changed.emit())
            h.addWidget(line)

            browse = QPushButton("📁")
            browse.setFixedSize(28, 28)
            browse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            browse.setStyleSheet(
                f"QPushButton {{ background: {c('accent', self._mode)}; "
                f"color: white; border-radius: 8px; font-size: 14px; border: none; }}"
                f"QPushButton:hover {{ background: #0066dd; }}"
            )
            browse.clicked.connect(lambda: self._browse_path(line))
            h.addWidget(browse)

            self._path_line = line
            return container

        elif field_type == "extensions":
            widget = QLineEdit(str(value))
            widget.setMinimumWidth(280)
            widget.setStyleSheet(input_style)
            widget.textChanged.connect(lambda: self.value_changed.emit())
            return widget

        else:  # text
            widget = QLineEdit(str(value))
            widget.setFixedWidth(220)
            widget.setStyleSheet(input_style)
            widget.textChanged.connect(lambda: self.value_changed.emit())
            return widget

    def _browse_path(self, line_edit):
        """Open a file/directory picker dialog."""
        current = line_edit.text()
        result = QFileDialog.getExistingDirectory(
            self, "Select Directory", current
        ) if not current.endswith((".db", ".json")) else QFileDialog.getOpenFileName(
            self, "Select File", current
        )[0]
        if result:
            line_edit.setText(result)

    def _reset_to_default(self):
        """Reset the input widget to its default value."""
        ft = self._field_type
        default = self._default

        if ft == "int":
            self.input_widget.setValue(int(default) if default else 0)
        elif ft == "float":
            self.input_widget.setValue(float(default) if default else 0.0)
        elif ft == "bool":
            checked = str(default).lower() == "true"
            self.input_widget.setChecked(checked)
            self.input_widget._checked = checked
            self.input_widget._update_style()
        elif ft == "loglevel":
            levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            val = str(default).upper()
            if val in levels:
                self.input_widget.setCurrentIndex(levels.index(val))
        elif ft == "path":
            self._path_line.setText(str(default))
        elif ft in ("text", "extensions"):
            self.input_widget.setText(str(default))

        self.value_changed.emit()

    def get_value(self) -> str:
        """Get the current value as a string for .env file."""
        ft = self._field_type
        if ft == "int":
            return str(self.input_widget.value())
        elif ft == "float":
            return str(self.input_widget.value())
        elif ft == "bool":
            return "true" if self.input_widget.is_on() else "false"
        elif ft == "loglevel":
            return self.input_widget.currentText()
        elif ft == "path":
            return self._path_line.text()
        elif ft in ("text", "extensions"):
            return self.input_widget.text()
        return ""

    @property
    def env_key(self):
        return self._env_key

    def set_mode(self, mode):
        self._mode = mode
        self._apply_row_style()


# ─────────────────────────────────────────────────────────
# Main Settings Dialog
# ─────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    """
    Full settings editor dialog — reads/writes .env variables.
    Organized into categorized, scrollable sections.
    """

    settings_saved = Signal()  # Emitted after successful save

    def __init__(self, mode: str = "light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self._setting_rows = []  # List of SettingRow widgets
        self._has_changes = False

        self.setWindowTitle("Settings — Wedding FaceForward")
        self.setMinimumSize(700, 550)
        self.resize(780, 640)
        self.setModal(True)

        bg = c("bg", self._mode)
        self.setStyleSheet(f"QDialog {{ background: {bg}; }}")

        # Load current values
        self._env_path = _find_env_path()
        self._current_values = _parse_env_file(self._env_path)

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # ── Title Row ──
        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        title_icon = QLabel("⚙")
        title_icon.setStyleSheet("font-size: 28px;")
        title_row.addWidget(title_icon)

        title = QLabel("Settings")
        title.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 22px; font-weight: bold;"
        )
        title_row.addWidget(title)

        title_row.addStretch()

        # Env file path badge
        env_badge = QLabel(f"📄 {self._env_path.name}")
        env_badge.setToolTip(str(self._env_path))
        env_badge.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 11px; "
            f"background: {c('stat_bg', self._mode)}; padding: 4px 10px; "
            f"border-radius: 10px;"
        )
        title_row.addWidget(env_badge)

        main_layout.addLayout(title_row)

        # ── Subtitle ──
        subtitle = QLabel(
            "Configure all application settings. Changes are written to the "
            ".env file. A restart may be required for some settings to take effect."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 12px; line-height: 1.4;"
        )
        main_layout.addWidget(subtitle)

        # ── Scrollable Settings Area ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("settings_scroll")
        scroll.setStyleSheet(
            f"QScrollArea#settings_scroll {{ "
            f"  background: transparent; border: none; "
            f"}}"
            f"QScrollArea#settings_scroll > QWidget > QWidget {{ "
            f"  background: transparent; "
            f"}}"
            # Scrollbar styling
            f"QScrollBar:vertical {{"
            f"  background: {c('bg', self._mode)}; width: 8px; border: none; "
            f"  border-radius: 4px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {c('text_secondary', self._mode)}40; "
            f"  min-height: 30px; border-radius: 4px;"
            f"}}"
            f"QScrollBar::handle:vertical:hover {{"
            f"  background: {c('accent', self._mode)}80;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
            f"  height: 0px;"
            f"}}"
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 8, 0)
        scroll_layout.setSpacing(8)

        # Build GPU section first (special handling, not from SETTINGS_SCHEMA)
        self._build_gpu_section(scroll_layout)

        # Build regular sections
        for section in SETTINGS_SCHEMA:
            header = SectionHeader(section["section"], mode=self._mode)
            scroll_layout.addWidget(header)

            for field in section["fields"]:
                env_key, label, desc, ftype, default, extra = field
                current_val = self._current_values.get(env_key, default)

                row = SettingRow(
                    env_key, label, desc, ftype, default,
                    current_val, extra, mode=self._mode
                )
                row.value_changed.connect(self._on_value_changed)
                scroll_layout.addWidget(row)
                self._setting_rows.append(row)

            # Add spacing between sections
            spacer = QWidget()
            spacer.setFixedHeight(4)
            spacer.setStyleSheet("background: transparent;")
            scroll_layout.addWidget(spacer)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)

        # ── Status + Button Row ──
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 12px;"
        )
        bottom_row.addWidget(self.status_label)

        bottom_row.addStretch()

        # Reset All button
        reset_all_btn = QPushButton("↻  Reset All")
        reset_all_btn.setFixedSize(110, 38)
        reset_all_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        reset_all_btn.setStyleSheet(
            f"QPushButton {{ background: {c('stat_bg', self._mode)}; "
            f"color: {c('text_primary', self._mode)}; border-radius: 12px; "
            f"font-size: 12px; font-weight: bold; "
            f"border: 1px solid {c('border', self._mode)}; }}"
            f"QPushButton:hover {{ background: {c('warning', self._mode)}; color: white; border: none; }}"
        )
        reset_all_btn.clicked.connect(self._reset_all)
        bottom_row.addWidget(reset_all_btn)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(90, 38)
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {c('stat_bg', self._mode)}; "
            f"color: {c('text_primary', self._mode)}; border-radius: 12px; "
            f"font-size: 13px; font-weight: bold; "
            f"border: 1px solid {c('border', self._mode)}; }}"
            f"QPushButton:hover {{ background: {c('border', self._mode)}; }}"
        )
        cancel_btn.clicked.connect(self._try_close)
        bottom_row.addWidget(cancel_btn)

        # Save button
        self.save_btn = QPushButton("💾  Save")
        self.save_btn.setFixedSize(120, 38)
        self.save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._style_save_btn(enabled=False)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_settings)
        bottom_row.addWidget(self.save_btn)

        main_layout.addLayout(bottom_row)

    def _style_save_btn(self, enabled=True):
        if enabled:
            self.save_btn.setStyleSheet(
                f"QPushButton {{ background: {c('accent', self._mode)}; "
                f"color: white; border-radius: 12px; "
                f"font-size: 14px; font-weight: bold; border: none; }}"
                f"QPushButton:hover {{ background: #0066dd; }}"
            )
        else:
            self.save_btn.setStyleSheet(
                f"QPushButton {{ background: {c('text_secondary', self._mode)}; "
                f"color: white; border-radius: 12px; "
                f"font-size: 14px; font-weight: bold; border: none; }}"
            )

    def _on_value_changed(self):
        """Called when any setting value changes."""
        self._has_changes = True
        self.save_btn.setEnabled(True)
        self._style_save_btn(enabled=True)
        self.status_label.setText("• Unsaved changes")
        self.status_label.setStyleSheet(
            f"color: {c('warning', self._mode)}; font-size: 12px; font-weight: bold;"
        )

    def _save_settings(self):
        """Write all current values to the .env file."""
        updates = {}
        for row in self._setting_rows:
            updates[row.env_key] = row.get_value()

        try:
            _write_env_file(self._env_path, updates)
            self._has_changes = False
            self.save_btn.setEnabled(False)
            self._style_save_btn(enabled=False)

            self.status_label.setText("✓  Settings saved successfully")
            self.status_label.setStyleSheet(
                f"color: {c('success', self._mode)}; font-size: 12px; font-weight: bold;"
            )

            self.settings_saved.emit()

        except Exception as e:
            self.status_label.setText(f"✕  Save failed: {e}")
            self.status_label.setStyleSheet(
                f"color: {c('error', self._mode)}; font-size: 12px; font-weight: bold;"
            )

    def _reset_all(self):
        """Reset all settings to their defaults."""
        reply = QMessageBox.question(
            self,
            "Reset All Settings",
            "Are you sure you want to reset ALL settings to their defaults?\n\n"
            "This will not save automatically — you'll still need to click Save.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for row in self._setting_rows:
                row._reset_to_default()

    def _try_close(self):
        """Close with unsaved changes warning."""
        if self._has_changes:
            reply = QMessageBox.warning(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Are you sure you want to close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.close()

    def closeEvent(self, event):
        """Override close event to check for unsaved changes."""
        if self._has_changes:
            reply = QMessageBox.warning(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Are you sure you want to close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()

    def set_mode(self, mode):
        self._mode = mode
        bg = c("bg", self._mode)
        self.setStyleSheet(f"QDialog {{ background: {bg}; }}")
        for row in self._setting_rows:
            row.set_mode(mode)

    # ─────────────────────────────────────────────────────
    # Hardware Acceleration (GPU) Section
    # ─────────────────────────────────────────────────────

    def _build_gpu_section(self, parent_layout):
        """Build the ⚡ Hardware Acceleration section at the top of settings."""
        header = SectionHeader("⚡  Hardware Acceleration", mode=self._mode)
        parent_layout.addWidget(header)

        # GPU status card
        gpu_card = QFrame()
        gpu_card.setObjectName("gpu_status_card")
        gpu_card.setStyleSheet(
            f"QFrame#gpu_status_card {{ "
            f"  background-color: {c('bg_card', self._mode)}; "
            f"  border: 1px solid {c('border', self._mode)}; "
            f"  border-radius: 12px; "
            f"}}"
        )
        card_layout = QVBoxLayout(gpu_card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(6)

        # Try to get GPU info
        try:
            from app.gpu_manager import get_full_gpu_status
            gpu_info = get_full_gpu_status()
        except Exception:
            gpu_info = None

        if gpu_info and gpu_info.gpu_found:
            # ── GPU Found ──
            # GPU row
            gpu_row = self._gpu_status_row(
                "🖥️", "GPU",
                f"{gpu_info.gpu_name} ({gpu_info.gpu_architecture}, {gpu_info.vram_mb} MB)",
                c("text_primary", self._mode)
            )
            card_layout.addWidget(gpu_row)

            # CUDA row
            if gpu_info.cuda_version_ok:
                cuda_row = self._gpu_status_row("✅", "CUDA", f"v{gpu_info.cuda_version}",
                                               c("success", self._mode))
            else:
                cuda_text = gpu_info.cuda_version if gpu_info.cuda_version != "Not Installed" else "Not Installed"
                cuda_row = self._gpu_status_row("🔴", "CUDA", cuda_text,
                                               c("error", self._mode))
            card_layout.addWidget(cuda_row)

            # cuDNN row
            if gpu_info.cudnn_found:
                cudnn_row = self._gpu_status_row("✅", "cuDNN", f"v{gpu_info.cudnn_version}",
                                                c("success", self._mode))
            else:
                cudnn_row = self._gpu_status_row("🔴", "cuDNN", "Not Found",
                                                c("error", self._mode))
            card_layout.addWidget(cudnn_row)

            # Engine row
            if gpu_info.cuda_provider_available:
                engine_row = self._gpu_status_row(
                    "⚡", "Engine",
                    f"onnxruntime-gpu {gpu_info.ort_version} (CUDA)",
                    c("success", self._mode)
                )
                status_text = "✅ GPU Acceleration ACTIVE"
                status_color = c("success", self._mode)
            else:
                engine_row = self._gpu_status_row(
                    "●", "Engine",
                    f"onnxruntime {gpu_info.ort_version} (CPU)",
                    c("text_secondary", self._mode)
                )
                status_text = "🟡 GPU setup incomplete"
                status_color = c("warning", self._mode)
            card_layout.addWidget(engine_row)

            # Status line
            status_label = QLabel(f"  Status:  {status_text}")
            status_label.setStyleSheet(
                f"color: {status_color}; font-size: 11px; "
                f"font-weight: bold; background: transparent; padding-top: 4px;"
            )
            card_layout.addWidget(status_label)

            # Action button
            if gpu_info.cuda_provider_available:
                btn_text = "⚡  GPU Active — Open Settings"
            else:
                btn_text = "⚡  Open GPU Setup Wizard"

            gpu_btn = QPushButton(btn_text)
            gpu_btn.setFixedHeight(34)
            gpu_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            gpu_btn.setStyleSheet(
                f"QPushButton {{ background: {c('accent', self._mode)}; "
                f"color: white; border-radius: 12px; "
                f"font-size: 12px; font-weight: bold; border: none; }}"
                f"QPushButton:hover {{ background: #0066dd; }}"
            )
            gpu_btn.clicked.connect(self._open_gpu_wizard)
            card_layout.addWidget(gpu_btn)

        elif gpu_info and not gpu_info.is_whitelisted and gpu_info.gpu_name != "N/A":
            # GPU found but not supported
            info_label = QLabel(
                f"🖥️  {gpu_info.gpu_name}\n"
                f"⚠️  {gpu_info.whitelist_reason}\n\n"
                f"Running in CPU mode."
            )
            info_label.setWordWrap(True)
            info_label.setStyleSheet(
                f"color: {c('text_secondary', self._mode)}; font-size: 11px; "
                f"line-height: 1.5; background: transparent;"
            )
            card_layout.addWidget(info_label)

        else:
            # No GPU detected
            info_label = QLabel(
                "●  No compatible NVIDIA GPU detected\n"
                "●  Engine: onnxruntime (CPU mode)\n\n"
                "GPU acceleration requires an NVIDIA Turing or newer GPU\n"
                "(RTX 2060+, GTX 1650+, RTX 3060+, RTX 4060+)."
            )
            info_label.setWordWrap(True)
            info_label.setStyleSheet(
                f"color: {c('text_secondary', self._mode)}; font-size: 11px; "
                f"line-height: 1.5; background: transparent;"
            )
            card_layout.addWidget(info_label)

        parent_layout.addWidget(gpu_card)

        # Spacing after GPU section
        spacer = QWidget()
        spacer.setFixedHeight(4)
        spacer.setStyleSheet("background: transparent;")
        parent_layout.addWidget(spacer)

    def _gpu_status_row(self, icon: str, label: str, value: str,
                        value_color: str) -> QWidget:
        """Create a single GPU status row widget."""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 1, 0, 1)
        h.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(18)
        icon_lbl.setStyleSheet("font-size: 12px; background: transparent;")
        h.addWidget(icon_lbl)

        name_lbl = QLabel(label)
        name_lbl.setFixedWidth(50)
        name_lbl.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 11px; "
            f"font-weight: bold; background: transparent;"
        )
        h.addWidget(name_lbl)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(
            f"color: {value_color}; font-size: 11px; "
            f"font-weight: bold; background: transparent;"
        )
        h.addWidget(val_lbl)
        h.addStretch()

        return row

    def _open_gpu_wizard(self):
        """Open the GPU setup wizard dialog."""
        try:
            from .gpu_wizard import GPUWizardDialog
            wizard = GPUWizardDialog(mode=self._mode, parent=self)
            wizard.exec()
        except ImportError as e:
            QMessageBox.warning(
                self, "GPU Wizard",
                f"Could not open GPU wizard: {e}"
            )
