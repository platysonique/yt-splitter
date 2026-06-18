"""Background worker that runs yt-splitter and streams output."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SplitWorker(QThread):
    line = pyqtSignal(str)
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        video_input: str,
        output_dir: str,
        bin_dir: Path,
        *,
        mode: str = "album",
        use_track_prefix: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._video_input = video_input.strip()
        self._output_dir = output_dir
        self._bin_dir = bin_dir
        self._mode = mode
        self._use_track_prefix = use_track_prefix
        self._process: subprocess.Popen[str] | None = None
        self._last_lines: list[str] = []

    def run(self) -> None:
        env = os.environ.copy()
        env["PATH"] = f"{self._bin_dir}{os.pathsep}{env.get('PATH', '')}"

        try:
            command = [
                sys.executable,
                str(PROJECT_ROOT / "splitter.py"),
                "--mode",
                self._mode,
                self._video_input,
                self._output_dir,
            ]
            if self._mode == "album" and self._use_track_prefix:
                command.append("--track-prefix")

            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                cwd=str(PROJECT_ROOT),
            )
        except OSError as exc:
            self.failed.emit(str(exc))
            return

        assert self._process.stdout is not None
        for line in self._process.stdout:
            cleaned = line.rstrip("\n")
            self._last_lines.append(cleaned)
            self.line.emit(cleaned)

        code = self._process.wait()
        if code == 0:
            self.succeeded.emit(self._output_dir)
        else:
            label = "Song download" if self._mode == "song" else "yt-splitter"
            detail = self._last_error_line()
            self.failed.emit(f"{label} failed: {detail}" if detail else f"{label} exited with code {code}")

    def _last_error_line(self) -> str:
        for line in reversed(self._last_lines):
            if "ERROR:" in line:
                return line.partition("ERROR:")[2].strip() or line.strip()
            if line.startswith("error:"):
                return line.partition(":")[2].strip() or line.strip()
        return self._last_lines[-1] if self._last_lines else ""

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
