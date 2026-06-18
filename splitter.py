"""Download and split a YouTube video into chapter MP3 tracks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent
BIN_DIR = PROJECT_ROOT / "bin"


def parse_video_id(video_input: str) -> str:
    parsed = urlparse(video_input)
    if parsed.scheme and parsed.netloc:
        if parsed.netloc == "www.youtube.com":
            query = parse_qs(parsed.query)
            video_id = query.get("v", [None])[0]
            if not video_id:
                raise ValueError("YouTube URL is missing a video id.")
            return video_id
        if parsed.netloc == "youtu.be":
            segment = parsed.path.strip("/").split("/")[-1]
            if not segment:
                raise ValueError("YouTube short URL is missing a video id.")
            return segment
    return video_input.strip()


def strip_unsafe(text: str) -> str:
    return text.strip().replace("/", "_")


def render_duration(seconds: int) -> str:
    secs = seconds % 60
    mins = (seconds % 3600) // 60
    hours = seconds // 3600
    body = f"{mins:02d}:{secs:02d}"
    return f"{hours}:{body}" if hours else body


def track_prefix(number: int, total: int) -> str:
    width = max(2, len(str(total)))
    return str(number).zfill(width)


def cache_dir(video_id: str) -> Path:
    base = os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
    return Path(base) / "yt-splitter" / video_id


def downloader_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{BIN_DIR}{os.pathsep}{env.get('PATH', '')}"
    return env


def log_line(message: str, emit=print) -> None:
    if message:
        emit(message)


def download_audio(video_id: str, work_dir: Path, emit=print) -> None:
    mp3_path = work_dir / "output.mp3"
    if mp3_path.exists():
        return

    log_line("Downloading and converting audio file from YouTube...", emit)
    process = subprocess.Popen(
        [
            "youtube-dl",
            "--write-info-json",
            "--write-thumbnail",
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--output",
            "output.%(ext)s",
            f"https://www.youtube.com/watch?v={video_id}",
        ],
        cwd=work_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=downloader_env(),
    )
    assert process.stdout is not None
    for line in process.stdout:
        log_line(line.rstrip("\n"), emit)

    if process.wait() != 0:
        raise RuntimeError("YouTube download failed.")


def split_tracks(
    video_input: str,
    output_parent: Path | None = None,
    *,
    use_track_prefix: bool = False,
    emit=print,
) -> Path:
    video_id = parse_video_id(video_input)
    log_line(f"YT video: {video_id}...", emit)

    work_dir = cache_dir(video_id)
    work_dir.mkdir(parents=True, exist_ok=True)

    mp3_path = work_dir / "output.mp3"
    json_path = work_dir / "output.info.json"

    download_audio(video_id, work_dir, emit=emit)

    if not json_path.exists():
        raise RuntimeError("Missing output.info.json after download.")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    chapters = data.get("chapters") or []
    if not chapters:
        raise RuntimeError(
            "This video does not contain chapters. Use yt-dlp for a single-file download."
        )

    album = strip_unsafe(data["title"])
    artist = data.get("artist") or data.get("uploader") or ""
    output_dir = (
        output_parent / album if output_parent is not None else Path(album)
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    log_line(f"Tracks will be saved to {output_dir}", emit)
    log_line("Splitting mp3 file...", emit)

    total_tracks = len(chapters)
    seen_titles: set[str] = set()

    for index, chapter in enumerate(chapters, start=1):
        chapter_title = chapter["title"]
        duplicate = 1
        unique_title = chapter_title
        while unique_title in seen_titles:
            duplicate += 1
            unique_title = f"{chapter_title} ({duplicate})"
        seen_titles.add(unique_title)

        safe_title = strip_unsafe(unique_title)
        prefix = track_prefix(index, total_tracks)
        total_label = track_prefix(total_tracks, total_tracks)
        if use_track_prefix:
            filename = f"{prefix} - {safe_title}.mp3"
            log_label = f"{prefix} - {safe_title}"
        else:
            filename = f"{safe_title}.mp3"
            log_label = safe_title
        output_file = output_dir / filename

        log_line(f"[splitting] {log_label}...", emit)

        result = subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(mp3_path),
                "-vn",
                "-acodec",
                "copy",
                "-ss",
                render_duration(round(chapter["start_time"])),
                "-to",
                render_duration(round(chapter["end_time"])),
                "-metadata",
                f"title={safe_title}",
                "-metadata",
                f"album={album}",
                "-metadata",
                f"artist={artist}",
                "-metadata",
                f"track={prefix}/{total_label}",
                "-y",
                f"file:{output_file}",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log_line("Error while converting mp3 file:", emit)
            if result.stdout:
                log_line(result.stdout, emit)
            if result.stderr:
                log_line(result.stderr, emit)
            raise RuntimeError(f"ffmpeg failed for track {prefix}.")

    return output_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download and split a YouTube video into chapter MP3 tracks."
    )
    parser.add_argument("video", help="YouTube URL or video ID")
    parser.add_argument(
        "directory",
        nargs="?",
        help="Parent folder where the album subfolder will be created",
    )
    parser.add_argument(
        "--track-prefix",
        action="store_true",
        help="Prefix exported filenames with zero-padded track numbers",
    )
    args = parser.parse_args(argv)

    output_parent = Path(args.directory) if args.directory else None
    try:
        split_tracks(
            args.video,
            output_parent,
            use_track_prefix=args.track_prefix,
        )
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
