"""Main window for the yt-splitter PyQt6 GUI."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.settings import get_output_dir, set_output_dir
from gui.worker import SplitWorker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = PROJECT_ROOT / "bin"

STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #e8e8e8;
}
QLineEdit {
    background-color: #2b2b2b;
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    padding: 8px 10px;
    selection-background-color: #3d7eff;
}
QPushButton {
    background-color: #3d7eff;
    border: none;
    border-radius: 6px;
    color: white;
    font-weight: 600;
    padding: 9px 16px;
}
QPushButton:hover {
    background-color: #5b93ff;
}
QPushButton:disabled {
    background-color: #3a3a3a;
    color: #888888;
}
QPushButton#secondary {
    background-color: #333333;
    color: #dddddd;
}
QPushButton#secondary:hover {
    background-color: #444444;
}
QTextEdit {
    background-color: #141414;
    border: 1px solid #333333;
    border-radius: 6px;
    font-family: "DejaVu Sans Mono", "Consolas", monospace;
    padding: 8px;
}
QProgressBar {
    background-color: #2b2b2b;
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    height: 10px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #3d7eff;
    border-radius: 5px;
}
QLabel#subtitle {
    color: #aaaaaa;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    background-color: #2b2b2b;
}
QCheckBox::indicator:checked {
    background-color: #3d7eff;
    border-color: #3d7eff;
}
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YT-Splitter")
        self.setMinimumSize(720, 520)
        self.setStyleSheet(STYLESHEET)

        self._worker: SplitWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("YT-Splitter")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel(
            "Download a YouTube video with chapters and split it into tagged MP3 tracks."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        url_label = QLabel("YouTube URL or video ID")
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://www.youtube.com/watch?v=…")

        layout.addWidget(url_label)
        layout.addWidget(self._url_input)

        out_label = QLabel("Save tracks to")
        out_row = QHBoxLayout()
        self._output_input = QLineEdit(get_output_dir())
        browse_btn = QPushButton("Browse…")
        browse_btn.setObjectName("secondary")
        browse_btn.clicked.connect(self._pick_output_dir)
        out_row.addWidget(self._output_input)
        out_row.addWidget(browse_btn)

        layout.addWidget(out_label)
        layout.addLayout(out_row)

        self._track_prefix = QCheckBox("Track Prefix")
        self._track_prefix.setToolTip(
            "Add zero-padded track numbers to exported filenames (e.g. 01 - Song Name.mp3)"
        )
        layout.addWidget(self._track_prefix)

        action_row = QHBoxLayout()
        self._split_btn = QPushButton("Split Album")
        self._split_btn.clicked.connect(self._start_split)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("secondary")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_split)
        action_row.addWidget(self._split_btn)
        action_row.addWidget(self._cancel_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = QLabel("Ready.")
        layout.addWidget(self._status)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("Progress output will appear here…")
        layout.addWidget(self._log, stretch=1)

    def _pick_output_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Choose output folder",
            self._output_input.text() or str(Path.home() / "Downloads"),
        )
        if chosen:
            self._output_input.setText(chosen)
            set_output_dir(chosen)

    def _persist_output_dir(self) -> None:
        set_output_dir(self._output_input.text())

    def _append_log(self, text: str) -> None:
        self._log.append(text)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    def _set_busy(self, busy: bool) -> None:
        self._split_btn.setEnabled(not busy)
        self._cancel_btn.setEnabled(busy)
        self._url_input.setEnabled(not busy)
        self._output_input.setEnabled(not busy)
        self._track_prefix.setEnabled(not busy)
        self._progress.setVisible(busy)

    def _start_split(self) -> None:
        video = self._url_input.text().strip()
        output_dir = self._output_input.text().strip()

        if not video:
            QMessageBox.warning(self, "Missing URL", "Paste a YouTube URL or video ID.")
            return
        if not output_dir:
            QMessageBox.warning(self, "Missing folder", "Choose where to save the tracks.")
            return

        output_path = Path(output_dir)
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Output folder", str(exc))
            return

        self._persist_output_dir()

        self._log.clear()
        self._append_log(f"Starting split for: {video}")
        self._append_log(f"Output parent folder: {output_path}")
        if self._track_prefix.isChecked():
            self._append_log("Track prefix: enabled")
        self._status.setText("Working…")
        self._set_busy(True)

        self._worker = SplitWorker(
            video,
            str(output_path),
            BIN_DIR,
            use_track_prefix=self._track_prefix.isChecked(),
            parent=self,
        )
        self._worker.line.connect(self._append_log)
        self._worker.succeeded.connect(self._on_success)
        self._worker.failed.connect(self._on_failure)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _cancel_split(self) -> None:
        if self._worker:
            self._append_log("Cancelling…")
            self._worker.stop()

    def _on_success(self, output_dir: str) -> None:
        self._status.setText("Done.")
        self._append_log("")
        self._append_log(f"Tracks saved under: {output_dir}")
        QMessageBox.information(
            self,
            "Split complete",
            f"Tracks were saved under:\n{output_dir}\n\n"
            "Look for a subfolder named after the video title.",
        )

    def _on_failure(self, message: str) -> None:
        self._status.setText("Failed.")
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(
            self,
            "Split failed",
            message
            + "\n\nTip: the video must have YouTube chapters (common on full-album uploads).",
        )

    def _on_worker_finished(self) -> None:
        self._set_busy(False)
        self._worker = None

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        self._persist_output_dir()
        super().closeEvent(event)
