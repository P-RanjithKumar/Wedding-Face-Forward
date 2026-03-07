"""
AuthDialog — Google Drive Auth Persistence Manager.

Provides a GUI to:
  - View current token status (valid / expired / missing)
  - Silently refresh the access token using the stored refresh_token
  - Trigger a full browser re-authentication flow if refresh fails
  - Save the updated token.json back to disk automatically
"""

import json
import threading
from pathlib import Path
from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QWidget, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QColor

from ..theme import c


# ─── Token search paths (mirrors cloud.py logic) ─────────────────────────────
try:
    import dist_utils
    BASE_DIR = dist_utils.get_user_data_dir()
except ImportError:
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()

TOKEN_SEARCH_PATHS = [
    BASE_DIR / "token.json",
    BASE_DIR / "backend" / "token.json",
]

CREDENTIALS_SEARCH_PATHS = [
    BASE_DIR / "credentials.json",
    BASE_DIR / "backend" / "credentials.json",
]

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _find_file(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def _load_token_info() -> dict:
    """Return a dict with keys: path, exists, valid, expired, expiry_str, has_refresh."""
    token_path = _find_file(TOKEN_SEARCH_PATHS)
    if token_path is None:
        return {
            "path": None,
            "exists": False,
            "valid": False,
            "expired": True,
            "expiry_str": "N/A",
            "has_refresh": False,
        }

    try:
        data = json.loads(token_path.read_text(encoding="utf-8"))
        has_refresh = bool(data.get("refresh_token"))

        expiry_raw = data.get("expiry") or data.get("token_expiry")
        expired = True
        expiry_str = "Unknown"

        if expiry_raw:
            # Token.json can store expiry in ISO 8601 or RFC 2822
            try:
                expiry_dt = datetime.fromisoformat(expiry_raw.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                expired = expiry_dt <= now
                # Human-readable local time
                local_expiry = expiry_dt.astimezone()
                expiry_str = local_expiry.strftime("%Y-%m-%d %H:%M:%S %Z")
            except Exception:
                expiry_str = expiry_raw

        # A token is "valid" if it's not expired OR can be refreshed
        valid = (not expired) or has_refresh

        return {
            "path": token_path,
            "exists": True,
            "valid": valid,
            "expired": expired,
            "expiry_str": expiry_str,
            "has_refresh": has_refresh,
        }
    except Exception as e:
        return {
            "path": token_path,
            "exists": True,
            "valid": False,
            "expired": True,
            "expiry_str": f"Parse error: {e}",
            "has_refresh": False,
        }


# ─── Worker that runs token operations in background ─────────────────────────

class _AuthWorker(QWidget):
    """Hidden worker widget that emits signals for auth operations."""

    result_signal = Signal(bool, str)   # success, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()

    def refresh_token(self, token_path: Path):
        """Run a silent refresh using the stored refresh_token."""
        def _run():
            try:
                from google.oauth2.credentials import Credentials
                from google.auth.transport.requests import Request

                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    # Save back to disk
                    token_path.write_text(creds.to_json(), encoding="utf-8")
                    self.result_signal.emit(True, "Token refreshed and saved successfully ✓")
                elif not creds.expired:
                    self.result_signal.emit(True, "Token is still valid — no refresh needed ✓")
                else:
                    self.result_signal.emit(False, "No refresh token available. Please re-authenticate.")
            except Exception as e:
                self.result_signal.emit(False, f"Refresh failed: {e}")

        threading.Thread(target=_run, daemon=True).start()

    def full_reauth(self, creds_path: Path, token_save_path: Path):
        """Run the full OAuth browser flow."""
        def _run():
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(creds_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
                token_save_path.write_text(creds.to_json(), encoding="utf-8")
                self.result_signal.emit(True, f"Re-authenticated successfully ✓\nToken saved to: {token_save_path}")
            except Exception as e:
                self.result_signal.emit(False, f"Re-authentication failed: {e}")

        threading.Thread(target=_run, daemon=True).start()


# ─── Auth Status Banner ───────────────────────────────────────────────────────

class _StatusBanner(QFrame):
    def __init__(self, mode="light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self.setObjectName("auth_status_banner")
        self.setMinimumHeight(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(4)

        row = QHBoxLayout()
        self._dot = QLabel("●")
        self._dot.setFixedWidth(20)
        self._dot.setFont(QFont("Segoe UI", 18))
        row.addWidget(self._dot)

        col = QVBoxLayout()
        self._status_label = QLabel("Checking...")
        self._status_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._expiry_label = QLabel("Expiry: —")
        self._expiry_label.setFont(QFont("Segoe UI", 10))
        col.addWidget(self._status_label)
        col.addWidget(self._expiry_label)

        row.addLayout(col)
        row.addStretch()
        layout.addLayout(row)

    def set_status(self, token_info: dict):
        mode = self._mode
        if not token_info["exists"]:
            dot_color = c("error", mode)
            status_text = "No token.json found"
            expiry_text = "You must re-authenticate to create one."
        elif not token_info["has_refresh"]:
            dot_color = c("error", mode)
            status_text = "Token missing refresh credentials"
            expiry_text = "Re-authenticate to generate a full token."
        elif token_info["expired"]:
            dot_color = c("warning", mode)
            status_text = "Access token is expired (refresh available)"
            expiry_text = f"Was valid until: {token_info['expiry_str']}"
        else:
            dot_color = c("success", mode)
            status_text = "Token is valid ✓"
            expiry_text = f"Expires: {token_info['expiry_str']}"

        self._dot.setStyleSheet(f"color: {dot_color};")
        self._status_label.setText(status_text)
        self._expiry_label.setText(expiry_text)
        self._expiry_label.setStyleSheet(f"color: {c('text_secondary', mode)};")

        # Banner background
        if not token_info["exists"] or not token_info["has_refresh"]:
            bg = "#fee2e2" if mode == "light" else "#3d1b1b"
            border = "#fca5a5" if mode == "light" else "#7f1d1d"
        elif token_info["expired"]:
            bg = "#fff7ed" if mode == "light" else "#3d2a1b"
            border = "#fdba74" if mode == "light" else "#9a3412"
        else:
            bg = "#ecfdf5" if mode == "light" else "#0d3d30"
            border = "#6ee7b7" if mode == "light" else "#065f46"

        self.setStyleSheet(
            f"QFrame#auth_status_banner {{ background-color: {bg}; border: 1px solid {border}; border-radius: 12px; }}"
        )


# ─── Main Dialog ──────────────────────────────────────────────────────────────

class AuthDialog(QDialog):
    """Google Drive Auth Persistence Manager dialog."""

    auth_updated = Signal()   # Emitted when token is successfully refreshed / re-authenticated

    def __init__(self, mode="light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self.setWindowTitle("Google Drive Auth Manager")
        self.setMinimumWidth(520)
        self.setMinimumHeight(440)
        self.setModal(True)

        self._token_info: dict = {}

        self._build_ui()
        self._worker = _AuthWorker(self)
        self._worker.result_signal.connect(self._on_auth_result)

        # Load token status on open
        QTimer.singleShot(0, self._reload_status)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # Title row
        title_row = QHBoxLayout()
        icon = QLabel("🔑")
        icon.setFont(QFont("Segoe UI", 22))
        title_row.addWidget(icon)

        title_col = QVBoxLayout()
        title = QLabel("Google Drive Auth Manager")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        subtitle = QLabel("Manage OAuth tokens without touching the terminal.")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet(f"color: {c('text_secondary', self._mode)};")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        title_row.addLayout(title_col)
        title_row.addStretch()
        root.addLayout(title_row)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {c('border', self._mode)};")
        root.addWidget(div)

        # Status banner
        self._banner = _StatusBanner(mode=self._mode)
        root.addWidget(self._banner)

        # File paths info
        paths_frame = QFrame()
        paths_frame.setObjectName("auth_paths_frame")
        paths_layout = QVBoxLayout(paths_frame)
        paths_layout.setContentsMargins(14, 10, 14, 10)
        paths_layout.setSpacing(4)

        self._token_path_label = QLabel("token.json: Searching...")
        self._token_path_label.setFont(QFont("Consolas", 9))
        self._token_path_label.setWordWrap(True)

        self._creds_path_label = QLabel("credentials.json: Searching...")
        self._creds_path_label.setFont(QFont("Consolas", 9))
        self._creds_path_label.setWordWrap(True)

        paths_layout.addWidget(self._token_path_label)
        paths_layout.addWidget(self._creds_path_label)

        bg = "#f5f5f7" if self._mode == "light" else "#2c2c2e"
        border = c("border", self._mode)
        paths_frame.setStyleSheet(
            f"QFrame#auth_paths_frame {{ background:{bg}; border:1px solid {border}; border-radius:8px; }}"
        )
        root.addWidget(paths_frame)

        # Result message box
        self._result_label = QLabel("")
        self._result_label.setFont(QFont("Segoe UI", 10))
        self._result_label.setWordWrap(True)
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_label.setMinimumHeight(36)
        root.addWidget(self._result_label)

        # Progress bar (hidden normally)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # Indeterminate
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.hide()
        root.addWidget(self._progress)

        root.addStretch()

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._refresh_btn = QPushButton("🔄  Refresh Token")
        self._refresh_btn.setObjectName("auth_refresh_btn")
        self._refresh_btn.setFixedHeight(42)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        btn_row.addWidget(self._refresh_btn)

        self._reauth_btn = QPushButton("🌐  Re-authenticate (Browser)")
        self._reauth_btn.setObjectName("auth_reauth_btn")
        self._reauth_btn.setFixedHeight(42)
        self._reauth_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reauth_btn.clicked.connect(self._on_reauth_clicked)
        btn_row.addWidget(self._reauth_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("auth_close_btn")
        close_btn.setFixedHeight(42)
        close_btn.setFixedWidth(90)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        root.addLayout(btn_row)

        self._apply_button_styles()

    def _apply_button_styles(self):
        mode = self._mode
        accent = c("accent", mode)
        success = c("success", mode)
        border_c = c("border", mode)
        text_p = c("text_primary", mode)
        card_bg = c("bg_card", mode)

        self._refresh_btn.setStyleSheet(f"""
            QPushButton#auth_refresh_btn {{
                background-color: {"#e8f5e9" if mode=="light" else "#1a3d2a"};
                color: {"#2e7d32" if mode=="light" else "#4caf50"};
                border: 1px solid {"#a5d6a7" if mode=="light" else "#4caf50"};
                border-radius: 12px;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 18px;
            }}
            QPushButton#auth_refresh_btn:hover {{
                background-color: {"#2e7d32" if mode=="light" else "#4caf50"};
                color: white;
            }}
            QPushButton#auth_refresh_btn:disabled {{
                background-color: {"#e0e0e0" if mode=="light" else "#3a3a3c"};
                color: {"#9e9e9e" if mode=="light" else "#666"};
                border-color: {"#bdbdbd" if mode=="light" else "#555"};
            }}
        """)

        self._reauth_btn.setStyleSheet(f"""
            QPushButton#auth_reauth_btn {{
                background-color: {"#e3f2fd" if mode=="light" else "#1a2a3d"};
                color: {"#1565c0" if mode=="light" else "#64b5f6"};
                border: 1px solid {"#90caf9" if mode=="light" else "#64b5f6"};
                border-radius: 12px;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 18px;
            }}
            QPushButton#auth_reauth_btn:hover {{
                background-color: {"#1565c0" if mode=="light" else "#64b5f6"};
                color: white;
            }}
            QPushButton#auth_reauth_btn:disabled {{
                background-color: {"#e0e0e0" if mode=="light" else "#3a3a3c"};
                color: {"#9e9e9e" if mode=="light" else "#666"};
                border-color: {"#bdbdbd" if mode=="light" else "#555"};
            }}
        """)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c("bg", mode)};
            }}
            QPushButton#auth_close_btn {{
                background-color: {c("bg_card", mode)};
                color: {text_p};
                border: 1px solid {border_c};
                border-radius: 12px;
                font-size: 12px;
                padding: 6px 18px;
            }}
            QPushButton#auth_close_btn:hover {{
                background-color: {border_c};
            }}
            QProgressBar {{
                background-color: {border_c};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {accent};
                border-radius: 3px;
            }}
        """)

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _reload_status(self):
        self._token_info = _load_token_info()
        self._banner.set_status(self._token_info)

        # Token path
        if self._token_info["path"]:
            self._token_path_label.setText(f"token.json:       {self._token_info['path']}")
        else:
            # Show where we searched
            searched = " | ".join(str(p) for p in TOKEN_SEARCH_PATHS)
            self._token_path_label.setText(f"token.json:       ✗ Not found (searched: {searched})")

        # Credentials path
        creds_path = _find_file(CREDENTIALS_SEARCH_PATHS)
        if creds_path:
            self._creds_path_label.setText(f"credentials.json: {creds_path}")
        else:
            searched = " | ".join(str(p) for p in CREDENTIALS_SEARCH_PATHS)
            self._creds_path_label.setText(f"credentials.json: ✗ Not found (searched: {searched})")

        # Enable / disable buttons
        can_refresh = self._token_info["exists"] and self._token_info["has_refresh"]
        self._refresh_btn.setEnabled(can_refresh)

        creds_exists = creds_path is not None
        self._reauth_btn.setEnabled(creds_exists)

        # Style path labels
        mode = self._mode
        token_color = c("success", mode) if self._token_info["exists"] else c("error", mode)
        creds_color = c("success", mode) if creds_exists else c("error", mode)
        self._token_path_label.setStyleSheet(f"color: {token_color};")
        self._creds_path_label.setStyleSheet(f"color: {creds_color};")

    def _set_busy(self, busy: bool):
        self._refresh_btn.setEnabled(not busy)
        self._reauth_btn.setEnabled(not busy)
        if busy:
            self._progress.show()
            self._result_label.setText("Working...")
            self._result_label.setStyleSheet(f"color: {c('text_secondary', self._mode)};")
        else:
            self._progress.hide()

    def _on_refresh_clicked(self):
        token_path = self._token_info.get("path")
        if not token_path:
            self._show_result(False, "No token.json found to refresh.")
            return

        self._set_busy(True)
        self._worker.refresh_token(token_path)

    def _on_reauth_clicked(self):
        creds_path = _find_file(CREDENTIALS_SEARCH_PATHS)
        if not creds_path:
            self._show_result(False, "credentials.json not found. Cannot open browser flow.")
            return

        # Decide where to save — prefer the location of existing token, else root
        token_save = self._token_info.get("path") or TOKEN_SEARCH_PATHS[0]

        self._set_busy(True)
        self._result_label.setText(
            "🌐 Opening browser for Google sign-in…\n"
            "Complete the authentication in your browser, then return here."
        )
        self._worker.full_reauth(creds_path, token_save)

    def _on_auth_result(self, success: bool, message: str):
        self._set_busy(False)
        self._show_result(success, message)
        # Reload status to reflect new token state
        QTimer.singleShot(300, self._reload_status)
        if success:
            self.auth_updated.emit()

    def _show_result(self, success: bool, message: str):
        color = c("success", self._mode) if success else c("error", self._mode)
        self._result_label.setText(message)
        self._result_label.setStyleSheet(f"color: {color}; font-weight: bold;")
