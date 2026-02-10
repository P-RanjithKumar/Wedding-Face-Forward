#!/usr/bin/env python3
import sys
import os
import subprocess
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTextEdit, QFileDialog, QMessageBox)
from PySide6.QtCore import QSettings, QObject, Signal, QThread
from PySide6.QtGui import QFont, QIcon

class GitWorker(QObject):
    output = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, repo_path, commit_msg):
        super().__init__()
        self.repo_path = repo_path
        self.commit_msg = commit_msg

    def run(self):
        cmds = [
            ['git', 'add', '.'],
            ['git', 'commit', '-m', self.commit_msg],
            ['git', 'push', '-u', 'origin', 'main']
        ]
        for cmd in cmds:
            self.output.emit(f"Running: {' '.join(cmd)}\n")
            try:
                # startupinfo to hide console window on Windows
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                proc = subprocess.Popen(cmd, cwd=self.repo_path, 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE, 
                                      text=True,
                                      startupinfo=startupinfo)
                
                stdout, stderr = proc.communicate()
                if stdout:
                    self.output.emit(stdout)
                if stderr:
                    self.output.emit(stderr)
                
                # Git commit returns 1 if there is nothing to commit, which isn't a fatal error for us usually,
                # but technically it is an error code. 
                # Git push might return non-zero if upstream is missing, etc.
                if proc.returncode != 0:
                    # Special handling: if commit failed because "nothing to commit", we can proceed or stop.
                    # Usually if add . worked, commit might fail if clean.
                    if cmd[1] == 'commit' and 'nothing to commit' in (stdout + stderr).lower():
                        self.output.emit("Nothing to commit, proceeding...\n")
                    else:
                        self.error.emit(f"Command {' '.join(cmd)} failed with exit code {proc.returncode}")
                        return
            except Exception as e:
                self.error.emit(str(e))
                return
        self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wedding Face Forward - Git Sync")
        self.resize(600, 450)
        
        # Hardcode specific path for this project or use current dir
        self.repo_path = os.path.dirname(os.path.abspath(__file__))
        
        self.settings = QSettings('WeddingGitApp', 'Settings')
        
        self._init_ui()
        self._apply_styles()
        
        # Verify it's a repo
        if not os.path.isdir(os.path.join(self.repo_path, '.git')):
             QMessageBox.warning(self, "Warning", f"The current directory ({self.repo_path}) is not a git repository.")

    def _init_ui(self):
        central = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        central.setLayout(layout)
        self.setCentralWidget(central)

        # Title / Status
        self.header_label = QLabel("Sync to GitHub")
        self.header_label.setObjectName("header")
        layout.addWidget(self.header_label)

        self.repo_label = QLabel(f"Repo: {self.repo_path}")
        self.repo_label.setStyleSheet("color: #666;")
        layout.addWidget(self.repo_label)

        # Message Input
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Enter commit message (e.g., 'Update user interface')...")
        self.msg_input.setMinimumHeight(40)
        layout.addWidget(self.msg_input)

        # Push Button
        self.push_button = QPushButton("💾  Save & Push to Cloud")
        self.push_button.setMinimumHeight(50)
        self.push_button.setCursor(sys.modules['PySide6.QtCore'].Qt.PointingHandCursor)
        self.push_button.clicked.connect(self.on_push_clicked)
        layout.addWidget(self.push_button)

        # Log Output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Log output will appear here...")
        layout.addWidget(self.log_output)

    def _apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f7;
            }
            QLabel#header {
                font-size: 24px;
                font-weight: bold;
                color: #1d1d1f;
            }
            QLineEdit {
                border: 1px solid #d2d2d7;
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 14px;
                background-color: #ffffff;
            }
            QLineEdit:focus {
                border: 2px solid #007aff;
            }
            QPushButton {
                background-color: #007aff;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #006add;
            }
            QPushButton:pressed {
                background-color: #005bb5;
            }
            QPushButton:disabled {
                background-color: #99c7ff;
            }
            QTextEdit {
                border: 1px solid #d2d2d7;
                border-radius: 8px;
                background-color: #ffffff;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                color: #333;
            }
        """)

    def on_push_clicked(self):
        commit_msg = self.msg_input.text().strip()
        if not commit_msg:
            QMessageBox.warning(self, "Validation", "Please enter a commit message describing your changes.")
            return
            
        # Disable UI
        self.push_button.setEnabled(False)
        self.push_button.setText("Syncing...")
        self.log_output.clear()
        
        # Start worker thread
        self.thread = QThread()
        self.worker = GitWorker(self.repo_path, commit_msg)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.output.connect(self.append_log)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def append_log(self, text):
        self.log_output.append(text)
        # Scroll to bottom
        sb = self.log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_error(self, err):
        self.append_log(f"❌ Error: {err}")
        QMessageBox.critical(self, "Sync Error", f"An error occurred:\n{err}\n\nCheck the logs for details.")
        self.reset_ui()

    def on_finished(self):
        self.append_log("✅ Operation completed successfully.")
        QMessageBox.information(self, "Success", "Project saved and synced to GitHub!")
        self.msg_input.clear()
        self.reset_ui()

    def reset_ui(self):
        self.push_button.setEnabled(True)
        self.push_button.setText("💾  Save & Push to Cloud")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Set app styling
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
