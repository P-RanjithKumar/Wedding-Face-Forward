"""
GPU Setup Wizard — A 3-step guided dialog for enabling GPU acceleration.

Step 1: GPU Detection — Shows detected GPU, asks user if they want to set up.
Step 2: CUDA & cuDNN — Guides user to install CUDA 12.6 + cuDNN 9.x.
Step 3: Enable GPU  — Swaps onnxruntime → onnxruntime-gpu, verifies, activates.

Each step only appears after the previous one is confirmed complete.
"""

import threading
import webbrowser

from PySide6.QtWidgets import (
    QDialog, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QProgressBar, QSizePolicy,
    QCheckBox, QApplication,
)
from PySide6.QtGui import QCursor, QFont
from PySide6.QtCore import Qt, Signal, QTimer

from ..theme import c

import sys
import os

# Add backend to path so we can import gpu_manager
try:
    import dist_utils  # sets up sys.path automatically
except ImportError:
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent))


def _get_gpu_manager():
    """Lazy import gpu_manager to avoid circular imports."""
    try:
        from backend.app.gpu_manager import (
            get_full_gpu_status, enable_gpu_acceleration,
            disable_gpu_acceleration, update_env_gpu_setting,
            GPU_RULEBOOK, GPUInfo
        )
        return {
            'get_full_gpu_status': get_full_gpu_status,
            'enable_gpu_acceleration': enable_gpu_acceleration,
            'disable_gpu_acceleration': disable_gpu_acceleration,
            'update_env_gpu_setting': update_env_gpu_setting,
            'GPU_RULEBOOK': GPU_RULEBOOK,
            'GPUInfo': GPUInfo,
        }
    except ImportError:
        try:
            # Try relative import path
            from backend.app import gpu_manager
            return {
                'get_full_gpu_status': gpu_manager.get_full_gpu_status,
                'enable_gpu_acceleration': gpu_manager.enable_gpu_acceleration,
                'disable_gpu_acceleration': gpu_manager.disable_gpu_acceleration,
                'update_env_gpu_setting': gpu_manager.update_env_gpu_setting,
                'GPU_RULEBOOK': gpu_manager.GPU_RULEBOOK,
                'GPUInfo': gpu_manager.GPUInfo,
            }
        except ImportError:
            return None


# ─────────────────────────────────────────────────────────
# Styled Helper Widgets
# ─────────────────────────────────────────────────────────

class _StatusRow(QFrame):
    """A single status row: icon + label + value."""

    def __init__(self, icon: str, label: str, value: str, 
                 value_color: str = None, mode: str = "light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        icon_label = QLabel(icon)
        icon_label.setFixedWidth(20)
        icon_label.setStyleSheet("font-size: 14px; background: transparent;")
        layout.addWidget(icon_label)

        name_label = QLabel(label)
        name_label.setStyleSheet(
            f"color: {c('text_secondary', mode)}; font-size: 12px; "
            f"font-weight: bold; background: transparent;"
        )
        layout.addWidget(name_label)

        layout.addStretch()

        self.value_label = QLabel(value)
        vc = value_color or c("text_primary", mode)
        self.value_label.setStyleSheet(
            f"color: {vc}; font-size: 12px; font-weight: bold; background: transparent;"
        )
        layout.addWidget(self.value_label)

    def set_value(self, value: str, color: str = None):
        self.value_label.setText(value)
        if color:
            self.value_label.setStyleSheet(
                f"color: {color}; font-size: 12px; font-weight: bold; background: transparent;"
            )


# ─────────────────────────────────────────────────────────
# GPU Setup Wizard Dialog
# ─────────────────────────────────────────────────────────

class GPUWizardDialog(QDialog):
    """
    3-step GPU setup wizard dialog.
    Emitted signals:
        gpu_enabled: GPU acceleration was successfully enabled.
        gpu_disabled: GPU acceleration was disabled.
    """

    gpu_enabled = Signal()
    gpu_disabled = Signal()

    def __init__(self, mode: str = "light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self._gpu_mgr = _get_gpu_manager()
        self._gpu_info = None
        self._is_installing = False

        self.setWindowTitle("⚡ GPU Acceleration Setup")
        self.setMinimumSize(560, 420)
        self.resize(600, 480)
        self.setModal(True)

        bg = c("bg", self._mode)
        self.setStyleSheet(f"QDialog {{ background: {bg}; }}")

        self._build_ui()

        # Run detection on load
        QTimer.singleShot(100, self._run_detection)

    def _build_ui(self):
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(28, 24, 28, 24)
        self._main_layout.setSpacing(16)

        # ── Title ──
        title_row = QHBoxLayout()
        title_icon = QLabel("⚡")
        title_icon.setStyleSheet("font-size: 28px;")
        title_row.addWidget(title_icon)

        title = QLabel("GPU Acceleration Setup")
        title.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 20px; font-weight: bold;"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        self._main_layout.addLayout(title_row)

        # ── Content area (replaced per step) ──
        self._content_frame = QFrame()
        self._content_frame.setObjectName("wizard_content")
        self._content_frame.setStyleSheet(
            f"QFrame#wizard_content {{ "
            f"  background: {c('bg_card', self._mode)}; "
            f"  border: 1px solid {c('border', self._mode)}; "
            f"  border-radius: 14px; "
            f"}}"
        )
        self._content_layout = QVBoxLayout(self._content_frame)
        self._content_layout.setContentsMargins(20, 20, 20, 20)
        self._content_layout.setSpacing(12)

        # Loading state
        self._loading_label = QLabel("🔍 Detecting GPU hardware...")
        self._loading_label.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 13px;"
        )
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content_layout.addWidget(self._loading_label)

        self._main_layout.addWidget(self._content_frame, 1)

        # ── Bottom buttons ──
        self._bottom_row = QHBoxLayout()
        self._bottom_row.setSpacing(12)
        self._bottom_row.addStretch()

        self._close_btn = QPushButton("Close")
        self._close_btn.setFixedSize(100, 38)
        self._close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: {c('stat_bg', self._mode)}; "
            f"color: {c('text_primary', self._mode)}; border-radius: 12px; "
            f"font-size: 13px; font-weight: bold; "
            f"border: 1px solid {c('border', self._mode)}; }}"
            f"QPushButton:hover {{ background: {c('border', self._mode)}; }}"
        )
        self._close_btn.clicked.connect(self.close)
        self._bottom_row.addWidget(self._close_btn)

        self._main_layout.addLayout(self._bottom_row)

    def _clear_content(self):
        """Remove all widgets from the content frame."""
        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                # Clear sub-layout
                while child.layout().count():
                    sub = child.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

    # ─────────────────────────────────────────────────────
    # STEP 0: Run Detection
    # ─────────────────────────────────────────────────────

    def _run_detection(self):
        """Run GPU detection (quick, synchronous since nvidia-smi is fast)."""
        if not self._gpu_mgr:
            self._show_error("GPU manager module not available. Check backend installation.")
            return

        try:
            self._gpu_info = self._gpu_mgr['get_full_gpu_status']()
            self._show_current_step()
        except Exception as e:
            self._show_error(f"GPU detection failed: {e}")

    def _show_current_step(self):
        """Show the appropriate UI based on GPU status."""
        info = self._gpu_info
        if info is None:
            self._show_error("GPU detection returned no result.")
            return

        if not info.gpu_found or not info.is_whitelisted:
            self._show_no_gpu()
        elif not info.cuda_version_ok or not info.cudnn_found:
            self._show_step2_cuda()
        elif not info.cuda_provider_available:
            self._show_step3_enable()
        else:
            self._show_gpu_active()

    # ─────────────────────────────────────────────────────
    # NO GPU / Unsupported
    # ─────────────────────────────────────────────────────

    def _show_no_gpu(self):
        """Show 'No compatible GPU' message."""
        self._clear_content()
        info = self._gpu_info

        if not info.gpu_found:
            icon = "🖥️"
            title = "No NVIDIA GPU Detected"
            message = (
                "No NVIDIA GPU was found on this system.\n\n"
                "AURA will run in CPU mode, which works great "
                "for most events. GPU acceleration is an optional performance boost "
                "for users with NVIDIA Turing (RTX 20-series) or newer GPUs."
            )
        else:
            icon = "⚠️"
            title = "GPU Not Supported"
            message = (
                f"Detected: {info.gpu_name}\n"
                f"Architecture: {info.gpu_architecture} (sm_{info.compute_capability:.0f})\n\n"
                f"{info.whitelist_reason}\n\n"
                "The app will continue to run perfectly in CPU mode."
            )

        title_label = QLabel(f"{icon}  {title}")
        title_label.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 16px; "
            f"font-weight: bold; background: transparent;"
        )
        self._content_layout.addWidget(title_label)

        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 12px; "
            f"line-height: 1.5; background: transparent;"
        )
        self._content_layout.addWidget(msg_label)
        self._content_layout.addStretch()

    # ─────────────────────────────────────────────────────
    # STEP 2: CUDA & cuDNN Installation
    # ─────────────────────────────────────────────────────

    def _show_step2_cuda(self):
        """Show CUDA/cuDNN installation guidance."""
        self._clear_content()
        info = self._gpu_info
        rulebook = self._gpu_mgr['GPU_RULEBOOK']

        # Step indicator
        step_label = QLabel("📦  Step 1/2 — Install CUDA & cuDNN")
        step_label.setStyleSheet(
            f"color: {c('accent', self._mode)}; font-size: 14px; "
            f"font-weight: bold; background: transparent;"
        )
        self._content_layout.addWidget(step_label)

        # GPU info row
        gpu_row = _StatusRow("🖥️", "GPU", 
                            f"{info.gpu_name} ({info.gpu_architecture}, {info.vram_mb} MB)",
                            c("success", self._mode), self._mode)
        self._content_layout.addWidget(gpu_row)

        # CUDA status
        if info.cuda_version_ok:
            cuda_row = _StatusRow("✅", "CUDA", f"v{info.cuda_version} Installed",
                                 c("success", self._mode), self._mode)
        else:
            cuda_color = c("error", self._mode) if not info.cuda_version or info.cuda_version == "Not Installed" else c("warning", self._mode)
            cuda_text = info.cuda_version if info.cuda_version != "Not Installed" else "Not Installed"
            cuda_row = _StatusRow("❌", "CUDA", cuda_text, cuda_color, self._mode)
        self._content_layout.addWidget(cuda_row)

        # cuDNN status
        if info.cudnn_found:
            cudnn_row = _StatusRow("✅", "cuDNN", f"v{info.cudnn_version} Installed",
                                  c("success", self._mode), self._mode)
        else:
            cudnn_row = _StatusRow("❌", "cuDNN", "Not Found",
                                  c("error", self._mode), self._mode)
        self._content_layout.addWidget(cudnn_row)

        # Instructions
        if not info.cuda_version_ok:
            instruction = QLabel(
                f"To use GPU acceleration, install CUDA Toolkit "
                f"{rulebook['cuda_version_recommended']} from NVIDIA:\n\n"
                f"1. Click 'Download CUDA' below to open the NVIDIA download page\n"
                f"2. Select: Windows → x86_64 → your Windows version → exe (local)\n"
                f"3. Run the installer (use 'Express' installation)\n"
                f"4. Restart your computer if prompted\n"
                f"5. Come back here and click 'Check Again'"
            )
        else:
            instruction = QLabel(
                f"CUDA is installed! Now install cuDNN {rulebook['cudnn_major_required']}.x:\n\n"
                f"1. Click 'Download cuDNN' below (free NVIDIA account required)\n"
                f"2. Download cuDNN {rulebook['cudnn_major_required']}.x for CUDA "
                f"{info.cuda_version.split('.')[0]}.x\n"
                f"3. Extract and copy files into your CUDA installation folder\n"
                f"   (Usually: C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\)\n"
                f"4. Come back here and click 'Check Again'"
            )
        instruction.setWordWrap(True)
        instruction.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 11px; "
            f"line-height: 1.5; background: transparent; padding: 8px 0;"
        )
        self._content_layout.addWidget(instruction)

        self._content_layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        # Download CUDA / cuDNN button
        if not info.cuda_version_ok:
            download_btn = QPushButton("🌐  Download CUDA 12.6")
            download_url = rulebook['cuda_download_url']
        else:
            download_btn = QPushButton("🌐  Download cuDNN 9.x")
            download_url = rulebook['cudnn_download_url']

        download_btn.setFixedHeight(36)
        download_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        download_btn.setStyleSheet(
            f"QPushButton {{ background: {c('accent', self._mode)}; "
            f"color: white; border-radius: 12px; "
            f"font-size: 12px; font-weight: bold; border: none; padding: 0 16px; }}"
            f"QPushButton:hover {{ background: #0066dd; }}"
        )
        download_btn.clicked.connect(lambda: webbrowser.open(download_url))
        btn_row.addWidget(download_btn)

        btn_row.addStretch()

        # Check Again button
        check_btn = QPushButton("🔄  Check Again")
        check_btn.setFixedHeight(36)
        check_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        check_btn.setStyleSheet(
            f"QPushButton {{ background: {c('stat_bg', self._mode)}; "
            f"color: {c('text_primary', self._mode)}; border-radius: 12px; "
            f"font-size: 12px; font-weight: bold; "
            f"border: 1px solid {c('border', self._mode)}; padding: 0 16px; }}"
            f"QPushButton:hover {{ background: {c('border', self._mode)}; }}"
        )
        check_btn.clicked.connect(self._run_detection)
        btn_row.addWidget(check_btn)

        self._content_layout.addLayout(btn_row)

    # ─────────────────────────────────────────────────────
    # STEP 3: Enable GPU (Install onnxruntime-gpu)
    # ─────────────────────────────────────────────────────

    def _show_step3_enable(self):
        """Show 'Ready to enable!' with install button."""
        self._clear_content()
        info = self._gpu_info

        step_label = QLabel("⚡  Step 2/2 — Enable GPU Acceleration")
        step_label.setStyleSheet(
            f"color: {c('accent', self._mode)}; font-size: 14px; "
            f"font-weight: bold; background: transparent;"
        )
        self._content_layout.addWidget(step_label)

        # Status rows — all green
        gpu_row = _StatusRow("✅", "GPU", f"{info.gpu_name} ({info.vram_mb} MB)",
                            c("success", self._mode), self._mode)
        cuda_row = _StatusRow("✅", "CUDA", f"v{info.cuda_version}",
                             c("success", self._mode), self._mode)
        cudnn_row = _StatusRow("✅", "cuDNN", f"v{info.cudnn_version}",
                              c("success", self._mode), self._mode)
        ort_row = _StatusRow("⬜", "Engine", f"onnxruntime {info.ort_version} (CPU only)",
                            c("text_secondary", self._mode), self._mode)

        self._content_layout.addWidget(gpu_row)
        self._content_layout.addWidget(cuda_row)
        self._content_layout.addWidget(cudnn_row)
        self._content_layout.addWidget(ort_row)

        # Description
        desc = QLabel(
            "Everything is ready! To enable GPU acceleration, we need to swap\n"
            "the AI engine to the GPU-optimized version.\n\n"
            "This will:\n"
            "  • Uninstall onnxruntime (CPU version)\n"
            "  • Install onnxruntime-gpu (~200 MB download)\n"
            "  • Verify GPU is working\n\n"
            "⚠️  The app will need to restart after this change."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 11px; "
            f"line-height: 1.5; background: transparent; padding: 8px 0;"
        )
        self._content_layout.addWidget(desc)

        self._content_layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        stay_cpu_btn = QPushButton("Stay on CPU")
        stay_cpu_btn.setFixedHeight(36)
        stay_cpu_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        stay_cpu_btn.setStyleSheet(
            f"QPushButton {{ background: {c('stat_bg', self._mode)}; "
            f"color: {c('text_primary', self._mode)}; border-radius: 12px; "
            f"font-size: 12px; font-weight: bold; "
            f"border: 1px solid {c('border', self._mode)}; padding: 0 16px; }}"
            f"QPushButton:hover {{ background: {c('border', self._mode)}; }}"
        )
        stay_cpu_btn.clicked.connect(self.close)
        btn_row.addWidget(stay_cpu_btn)

        btn_row.addStretch()

        enable_btn = QPushButton("⚡  Install && Enable")
        enable_btn.setFixedHeight(36)
        enable_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        enable_btn.setStyleSheet(
            f"QPushButton {{ background: {c('success', self._mode)}; "
            f"color: white; border-radius: 12px; "
            f"font-size: 13px; font-weight: bold; border: none; padding: 0 20px; }}"
            f"QPushButton:hover {{ background: #28a745; }}"
        )
        enable_btn.clicked.connect(self._start_installation)
        btn_row.addWidget(enable_btn)

        self._content_layout.addLayout(btn_row)

    # ─────────────────────────────────────────────────────
    # Installation Progress
    # ─────────────────────────────────────────────────────

    def _start_installation(self):
        """Begin the onnxruntime swap in a background thread."""
        if self._is_installing:
            return
        self._is_installing = True
        self._show_progress()

        # Run in background thread
        thread = threading.Thread(target=self._do_install, daemon=True)
        thread.start()

    def _show_progress(self):
        """Show installation progress UI."""
        self._clear_content()

        title = QLabel("⏳  Setting up GPU Acceleration...")
        title.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 15px; "
            f"font-weight: bold; background: transparent;"
        )
        self._content_layout.addWidget(title)

        # Progress steps
        self._progress_labels = []
        steps = [
            "Uninstalling onnxruntime (CPU)...",
            "Installing onnxruntime-gpu...",
            "Verifying GPU provider...",
            "Updating configuration...",
        ]
        for step_text in steps:
            lbl = QLabel(f"  ⬜  {step_text}")
            lbl.setStyleSheet(
                f"color: {c('text_secondary', self._mode)}; font-size: 12px; "
                f"background: transparent; padding: 4px 0;"
            )
            self._content_layout.addWidget(lbl)
            self._progress_labels.append(lbl)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 4)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ "
            f"  background: {c('stat_bg', self._mode)}; "
            f"  border-radius: 4px; border: none; "
            f"}}"
            f"QProgressBar::chunk {{ "
            f"  background: {c('success', self._mode)}; "
            f"  border-radius: 4px; "
            f"}}"
        )
        self._content_layout.addWidget(self._progress_bar)

        self._progress_status = QLabel("Please wait, this may take a few minutes...")
        self._progress_status.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 11px; "
            f"background: transparent;"
        )
        self._content_layout.addWidget(self._progress_status)

        self._content_layout.addStretch()

        # Disable close button during install
        self._close_btn.setEnabled(False)

    def _update_progress(self, step, total, message):
        """Update progress UI from any thread (uses QTimer for thread safety)."""
        def _update():
            if step <= len(self._progress_labels):
                # Mark previous steps as done
                for i in range(step - 1):
                    self._progress_labels[i].setText(
                        self._progress_labels[i].text().replace("⬜", "✅").replace("⏳", "✅")
                    )
                    self._progress_labels[i].setStyleSheet(
                        f"color: {c('success', self._mode)}; font-size: 12px; "
                        f"background: transparent; padding: 4px 0;"
                    )
                # Mark current step as in-progress
                if step <= len(self._progress_labels):
                    self._progress_labels[step - 1].setText(
                        self._progress_labels[step - 1].text().replace("⬜", "⏳")
                    )

            self._progress_bar.setValue(step)
            self._progress_status.setText(message)

        QTimer.singleShot(0, _update)

    def _do_install(self):
        """Run the actual installation (in background thread)."""
        try:
            result = self._gpu_mgr['enable_gpu_acceleration'](
                progress_callback=self._update_progress
            )

            if result.success:
                # Update .env
                self._gpu_mgr['update_env_gpu_setting']('GPU_ACCELERATION', 'true')
                self._gpu_mgr['update_env_gpu_setting']('GPU_WIZARD_STEP', 'complete')
                QTimer.singleShot(0, lambda: self._show_success(result.message))
            else:
                QTimer.singleShot(0, lambda: self._show_failure(result.error, result.message))

        except Exception as e:
            QTimer.singleShot(0, lambda: self._show_failure(str(e), "Unexpected error occurred."))
        finally:
            self._is_installing = False

    # ─────────────────────────────────────────────────────
    # SUCCESS
    # ─────────────────────────────────────────────────────

    def _show_success(self, message: str):
        """Show success state."""
        self._clear_content()

        title = QLabel("✅  GPU Acceleration is Now Active!")
        title.setStyleSheet(
            f"color: {c('success', self._mode)}; font-size: 16px; "
            f"font-weight: bold; background: transparent;"
        )
        self._content_layout.addWidget(title)

        info = self._gpu_info
        if info:
            gpu_row = _StatusRow("🖥️", "GPU", f"{info.gpu_name} ({info.vram_mb} MB)",
                                c("text_primary", self._mode), self._mode)
            self._content_layout.addWidget(gpu_row)

        engine_row = _StatusRow("⚡", "Engine", "onnxruntime-gpu (CUDAExecutionProvider)",
                               c("success", self._mode), self._mode)
        self._content_layout.addWidget(engine_row)

        speed_row = _StatusRow("🚀", "Speed", "Up to 10x faster face detection",
                              c("accent", self._mode), self._mode)
        self._content_layout.addWidget(speed_row)

        restart_note = QLabel(
            "\nThe app needs to restart to apply GPU acceleration.\n"
            "Please close and re-open the application."
        )
        restart_note.setWordWrap(True)
        restart_note.setStyleSheet(
            f"color: {c('warning', self._mode)}; font-size: 12px; "
            f"font-weight: bold; background: transparent; padding: 12px 0;"
        )
        self._content_layout.addWidget(restart_note)

        self._content_layout.addStretch()

        # Re-enable close
        self._close_btn.setEnabled(True)
        self._close_btn.setText("Done")

        self.gpu_enabled.emit()

    # ─────────────────────────────────────────────────────
    # FAILURE
    # ─────────────────────────────────────────────────────

    def _show_failure(self, error: str, message: str):
        """Show failure state with rollback confirmation."""
        self._clear_content()

        title = QLabel("❌  GPU Setup Failed")
        title.setStyleSheet(
            f"color: {c('error', self._mode)}; font-size: 16px; "
            f"font-weight: bold; background: transparent;"
        )
        self._content_layout.addWidget(title)

        error_label = QLabel(f"Error: {error[:300]}")
        error_label.setWordWrap(True)
        error_label.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 11px; "
            f"background: {c('stat_bg', self._mode)}; padding: 10px; "
            f"border-radius: 8px;"
        )
        self._content_layout.addWidget(error_label)

        restored = QLabel(
            "\n✅ onnxruntime (CPU) has been restored automatically.\n"
            "Your app will continue to work normally on CPU."
        )
        restored.setWordWrap(True)
        restored.setStyleSheet(
            f"color: {c('success', self._mode)}; font-size: 12px; "
            f"background: transparent; padding: 8px 0;"
        )
        self._content_layout.addWidget(restored)

        troubleshoot = QLabel(
            "Troubleshooting:\n"
            "  • Ensure CUDA 12.x is installed (not 11.x)\n"
            "  • Ensure cuDNN 9.x files are in your CUDA directory\n"
            "  • Try restarting your computer\n"
            "  • Check your internet connection"
        )
        troubleshoot.setWordWrap(True)
        troubleshoot.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 11px; "
            f"background: transparent; padding: 8px 0;"
        )
        self._content_layout.addWidget(troubleshoot)

        self._content_layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        ok_btn = QPushButton("OK (Use CPU)")
        ok_btn.setFixedHeight(36)
        ok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        ok_btn.setStyleSheet(
            f"QPushButton {{ background: {c('stat_bg', self._mode)}; "
            f"color: {c('text_primary', self._mode)}; border-radius: 12px; "
            f"font-size: 12px; font-weight: bold; "
            f"border: 1px solid {c('border', self._mode)}; padding: 0 16px; }}"
            f"QPushButton:hover {{ background: {c('border', self._mode)}; }}"
        )
        ok_btn.clicked.connect(self.close)
        btn_row.addWidget(ok_btn)

        btn_row.addStretch()

        retry_btn = QPushButton("🔄  Try Again")
        retry_btn.setFixedHeight(36)
        retry_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        retry_btn.setStyleSheet(
            f"QPushButton {{ background: {c('accent', self._mode)}; "
            f"color: white; border-radius: 12px; "
            f"font-size: 12px; font-weight: bold; border: none; padding: 0 16px; }}"
            f"QPushButton:hover {{ background: #0066dd; }}"
        )
        retry_btn.clicked.connect(self._run_detection)
        btn_row.addWidget(retry_btn)

        self._content_layout.addLayout(btn_row)

        # Re-enable close
        self._close_btn.setEnabled(True)

    # ─────────────────────────────────────────────────────
    # GPU Already Active
    # ─────────────────────────────────────────────────────

    def _show_gpu_active(self):
        """Show 'GPU is already active' with disable option."""
        self._clear_content()
        info = self._gpu_info

        title = QLabel("✅  GPU Acceleration is Active")
        title.setStyleSheet(
            f"color: {c('success', self._mode)}; font-size: 16px; "
            f"font-weight: bold; background: transparent;"
        )
        self._content_layout.addWidget(title)

        gpu_row = _StatusRow("🖥️", "GPU", f"{info.gpu_name} ({info.vram_mb} MB)",
                            c("text_primary", self._mode), self._mode)
        cuda_row = _StatusRow("✅", "CUDA", f"v{info.cuda_version}",
                             c("success", self._mode), self._mode)
        cudnn_row = _StatusRow("✅", "cuDNN", f"v{info.cudnn_version}",
                              c("success", self._mode), self._mode)
        ort_row = _StatusRow("⚡", "Engine",
                            f"onnxruntime-gpu {info.ort_version} (CUDA)",
                            c("success", self._mode), self._mode)

        self._content_layout.addWidget(gpu_row)
        self._content_layout.addWidget(cuda_row)
        self._content_layout.addWidget(cudnn_row)
        self._content_layout.addWidget(ort_row)

        desc = QLabel(
            "\nGPU acceleration is fully set up and working.\n"
            "Face detection and embedding extraction are running on your GPU."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 12px; "
            f"background: transparent; padding: 8px 0;"
        )
        self._content_layout.addWidget(desc)

        self._content_layout.addStretch()

        # Disable GPU button (subtle)
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        disable_btn = QPushButton("Disable GPU Acceleration")
        disable_btn.setFixedHeight(32)
        disable_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        disable_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; "
            f"color: {c('text_secondary', self._mode)}; border-radius: 8px; "
            f"font-size: 11px; border: 1px solid {c('border', self._mode)}; "
            f"padding: 0 12px; }}"
            f"QPushButton:hover {{ background: {c('error', self._mode)}; color: white; "
            f"border: none; }}"
        )
        disable_btn.clicked.connect(self._disable_gpu)
        btn_row.addWidget(disable_btn)

        self._content_layout.addLayout(btn_row)

    def _disable_gpu(self):
        """Disable GPU acceleration."""
        if not self._gpu_mgr:
            return

        result = self._gpu_mgr['disable_gpu_acceleration']()
        if result.success:
            self._gpu_mgr['update_env_gpu_setting']('GPU_ACCELERATION', 'false')
            self._gpu_mgr['update_env_gpu_setting']('GPU_WIZARD_STEP', 'not_started')
            self.gpu_disabled.emit()

        # Re-detect and show
        self._run_detection()

    # ─────────────────────────────────────────────────────
    # Error
    # ─────────────────────────────────────────────────────

    def _show_error(self, message: str):
        """Show a generic error."""
        self._clear_content()

        title = QLabel("❌  Error")
        title.setStyleSheet(
            f"color: {c('error', self._mode)}; font-size: 16px; "
            f"font-weight: bold; background: transparent;"
        )
        self._content_layout.addWidget(title)

        msg = QLabel(message)
        msg.setWordWrap(True)
        msg.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 12px; "
            f"background: transparent;"
        )
        self._content_layout.addWidget(msg)
        self._content_layout.addStretch()

    def set_mode(self, mode):
        self._mode = mode
        bg = c("bg", self._mode)
        self.setStyleSheet(f"QDialog {{ background: {bg}; }}")


# ─────────────────────────────────────────────────────────
# First-Time GPU Prompt (lightweight popup)
# ─────────────────────────────────────────────────────────

class GPUDiscoveryPrompt(QDialog):
    """
    Lightweight first-time popup: 'We found a GPU, want to set it up?'
    If yes → opens GPUWizardDialog.
    If no → stores preference.
    """

    setup_requested = Signal()   # User wants to set up GPU
    dismissed = Signal()          # User declined

    def __init__(self, gpu_info, mode: str = "light", parent=None):
        super().__init__(parent)
        self._mode = mode
        self._gpu_info = gpu_info
        self._gpu_mgr = _get_gpu_manager()

        self.setWindowTitle("GPU Detected")
        self.setFixedSize(480, 300)
        self.setModal(True)

        bg = c("bg", self._mode)
        self.setStyleSheet(f"QDialog {{ background: {bg}; }}")

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # Title
        title = QLabel("⚡  High-Performance GPU Detected!")
        title.setStyleSheet(
            f"color: {c('text_primary', self._mode)}; font-size: 18px; font-weight: bold;"
        )
        layout.addWidget(title)

        # GPU info
        info = self._gpu_info
        info_text = (
            f"GPU:    {info.gpu_name} ({info.gpu_architecture})\n"
            f"VRAM:   {info.vram_mb} MB\n"
            f"Driver: {info.driver_version}\n\n"
            f"Your GPU can accelerate face detection and matching\n"
            f"by up to 10x. Would you like to set it up?"
        )
        info_label = QLabel(info_text)
        info_label.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 12px; "
            f"line-height: 1.6;"
        )
        layout.addWidget(info_label)

        layout.addStretch()

        # Don't ask again
        self._dont_ask = QCheckBox("Don't ask me again")
        self._dont_ask.setStyleSheet(
            f"color: {c('text_secondary', self._mode)}; font-size: 11px;"
        )
        layout.addWidget(self._dont_ask)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        not_now_btn = QPushButton("Not Now")
        not_now_btn.setFixedSize(120, 38)
        not_now_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        not_now_btn.setStyleSheet(
            f"QPushButton {{ background: {c('stat_bg', self._mode)}; "
            f"color: {c('text_primary', self._mode)}; border-radius: 12px; "
            f"font-size: 13px; font-weight: bold; "
            f"border: 1px solid {c('border', self._mode)}; }}"
            f"QPushButton:hover {{ background: {c('border', self._mode)}; }}"
        )
        not_now_btn.clicked.connect(self._on_dismiss)
        btn_row.addWidget(not_now_btn)

        btn_row.addStretch()

        setup_btn = QPushButton("⚡  Let's Set It Up")
        setup_btn.setFixedSize(160, 38)
        setup_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        setup_btn.setStyleSheet(
            f"QPushButton {{ background: {c('success', self._mode)}; "
            f"color: white; border-radius: 12px; "
            f"font-size: 13px; font-weight: bold; border: none; }}"
            f"QPushButton:hover {{ background: #28a745; }}"
        )
        setup_btn.clicked.connect(self._on_setup)
        btn_row.addWidget(setup_btn)

        layout.addLayout(btn_row)

    def _on_dismiss(self):
        if self._dont_ask.isChecked() and self._gpu_mgr:
            self._gpu_mgr['update_env_gpu_setting']('GPU_PROMPT_DISMISSED', 'true')
        self.dismissed.emit()
        self.close()

    def _on_setup(self):
        self.setup_requested.emit()
        self.close()
