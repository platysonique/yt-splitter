"""Persistent GUI settings stored under XDG config."""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "yt-splitter"
DEFAULT_OUTPUT_DIR = str(Path.home() / "Downloads")


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_path() -> Path:
    return _config_dir() / "settings.json"


def load_settings() -> dict:
    path = _config_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict) -> None:
    _config_path().write_text(
        json.dumps(settings, indent=2) + "\n",
        encoding="utf-8",
    )


def get_output_dir() -> str:
    saved = load_settings().get("output_dir", "")
    if isinstance(saved, str) and saved.strip() and Path(saved).is_dir():
        return saved
    return DEFAULT_OUTPUT_DIR


def set_output_dir(path: str) -> None:
    cleaned = path.strip()
    if not cleaned:
        return
    settings = load_settings()
    settings["output_dir"] = cleaned
    save_settings(settings)
