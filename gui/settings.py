"""Persistent GUI settings stored under XDG config."""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "yt-splitter"
DEFAULT_OUTPUT_DIR = str(Path.home() / "Downloads")
DOWNLOAD_MODES = frozenset({"album", "song"})


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


def _migrate_settings(settings: dict) -> dict:
    if "album_output_dir" not in settings:
        legacy = settings.get("output_dir", "")
        if isinstance(legacy, str) and legacy.strip():
            settings["album_output_dir"] = legacy.strip()
    if "song_output_dir" not in settings:
        album_dir = settings.get("album_output_dir", DEFAULT_OUTPUT_DIR)
        settings["song_output_dir"] = album_dir
    mode = settings.get("download_mode", "album")
    if mode not in DOWNLOAD_MODES:
        settings["download_mode"] = "album"
    return settings


def _settings() -> dict:
    settings = load_settings()
    migrated = _migrate_settings(dict(settings))
    if migrated != settings:
        save_settings(migrated)
    return migrated


def _valid_dir(path: str) -> str | None:
    cleaned = path.strip()
    if cleaned and Path(cleaned).is_dir():
        return cleaned
    return None


def get_download_mode() -> str:
    mode = _settings().get("download_mode", "album")
    return mode if mode in DOWNLOAD_MODES else "album"


def set_download_mode(mode: str) -> None:
    if mode not in DOWNLOAD_MODES:
        return
    settings = _settings()
    settings["download_mode"] = mode
    save_settings(settings)


def get_output_dir_for_mode(mode: str) -> str:
    if mode not in DOWNLOAD_MODES:
        mode = "album"
    key = f"{mode}_output_dir"
    saved = _valid_dir(str(_settings().get(key, "")))
    if saved:
        return saved
    return DEFAULT_OUTPUT_DIR


def set_output_dir_for_mode(mode: str, path: str) -> None:
    if mode not in DOWNLOAD_MODES:
        return
    cleaned = path.strip()
    if not cleaned:
        return
    settings = _settings()
    settings[f"{mode}_output_dir"] = cleaned
    save_settings(settings)


# Backward-compatible helpers used by older call sites.
def get_output_dir() -> str:
    return get_output_dir_for_mode(get_download_mode())


def set_output_dir(path: str) -> None:
    set_output_dir_for_mode(get_download_mode(), path)
