"""Download and split a YouTube video into chapter MP3 tracks."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
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


def find_node_binary() -> str | None:
    node = shutil.which("node")
    if node:
        return node

    nvm_versions = Path.home() / ".nvm" / "versions" / "node"
    if nvm_versions.is_dir():
        for version_dir in sorted(nvm_versions.iterdir(), reverse=True):
            candidate = version_dir / "bin" / "node"
            if candidate.is_file():
                return str(candidate)

    for candidate in (Path("/usr/local/bin/node"), Path("/usr/bin/node")):
        if candidate.is_file():
            return str(candidate)
    return None


def downloader_env() -> dict[str, str]:
    env = os.environ.copy()
    path_parts = [str(BIN_DIR)]
    node = find_node_binary()
    if node:
        path_parts.append(str(Path(node).parent))
    existing = env.get("PATH", "")
    if existing:
        path_parts.append(existing)
    env["PATH"] = os.pathsep.join(path_parts)
    return env


def log_line(message: str, emit=print) -> None:
    if message:
        emit(message)


def resolve_output_dir(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def yt_dlp_extra_args() -> list[str]:
    args = ["--remote-components", "ejs:github"]
    node = find_node_binary()
    if node:
        args.extend(["--js-runtimes", f"node:{node}"])
    return args


def last_yt_dlp_error(lines: list[str]) -> str:
    for line in reversed(lines):
        if "ERROR:" in line:
            return line.partition("ERROR:")[2].strip() or line.strip()
    return "Download failed. Check the log for details."


def run_yt_dlp(
    command_tail: list[str],
    emit=print,
    *,
    cwd: Path | None = None,
) -> tuple[int, list[str]]:
    command = ["youtube-dl", *yt_dlp_extra_args(), *command_tail]
    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=downloader_env(),
    )
    lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        cleaned = line.rstrip("\n")
        lines.append(cleaned)
        log_line(cleaned, emit)
    return process.wait(), lines


def newest_mp3(directory: Path, *, since: float | None = None) -> Path | None:
    mp3s = [
        path
        for path in directory.glob("*.mp3")
        if since is None or path.stat().st_mtime >= since
    ]
    mp3s.sort(key=lambda path: path.stat().st_mtime)
    return mp3s[-1] if mp3s else None


def download_audio(video_id: str, work_dir: Path, emit=print) -> None:
    mp3_path = work_dir / "output.mp3"
    watch_url = f"https://www.youtube.com/watch?v={video_id}"

    if mp3_path.exists():
        ensure_thumbnail(watch_url, work_dir, emit=emit)
        return

    log_line("Downloading and converting audio file from YouTube...", emit)
    code, lines = run_yt_dlp(
        [
            "--write-info-json",
            "--write-thumbnail",
            "--embed-metadata",
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--output",
            "output.%(ext)s",
            watch_url,
        ],
        emit,
        cwd=work_dir,
    )
    if code != 0:
        raise RuntimeError(last_yt_dlp_error(lines))


def find_thumbnail(work_dir: Path) -> Path | None:
    for ext in ("webp", "jpg", "jpeg", "png"):
        path = work_dir / f"output.{ext}"
        if path.is_file():
            return path
    return None


def ensure_thumbnail(watch_url: str, work_dir: Path, emit=print) -> None:
    if find_thumbnail(work_dir):
        return

    log_line("Fetching album artwork...", emit)
    code, _ = run_yt_dlp(
        [
            "--write-thumbnail",
            "--skip-download",
            "--output",
            "output.%(ext)s",
            watch_url,
        ],
        emit,
        cwd=work_dir,
    )
    if code != 0:
        log_line("Warning: could not download album artwork.", emit)


def track_metadata_args(
    data: dict,
    *,
    title: str,
    album: str,
    artist: str,
    track_label: str,
) -> list[str]:
    args: list[str] = [
        "-metadata",
        f"title={title}",
        "-metadata",
        f"album={album}",
        "-metadata",
        f"artist={artist}",
        "-metadata",
        f"track={track_label}",
    ]
    if artist:
        args.extend(["-metadata", f"album_artist={artist}"])

    upload_date = data.get("upload_date") or data.get("release_date") or ""
    if upload_date:
        date_str = str(upload_date)
        if len(date_str) >= 4:
            args.extend(["-metadata", f"date={date_str[:4]}"])

    genre = data.get("genre")
    if isinstance(genre, str) and genre.strip():
        args.extend(["-metadata", f"genre={genre.strip()}"])

    return args


def split_chapter_to_mp3(
    mp3_path: Path,
    thumbnail_path: Path | None,
    output_file: Path,
    *,
    start: int,
    end: int,
    metadata_args: list[str],
) -> subprocess.CompletedProcess[str]:
    command = [
        "ffmpeg",
        "-ss",
        render_duration(start),
        "-to",
        render_duration(end),
        "-i",
        str(mp3_path),
    ]
    if thumbnail_path is not None:
        command.extend(
            [
                "-i",
                str(thumbnail_path),
                "-map",
                "0:a:0",
                "-map",
                "1:0",
                "-c:a",
                "copy",
                "-id3v2_version",
                "3",
                "-metadata:s:v",
                "title=Album cover",
                "-metadata:s:v",
                "comment=Cover (front)",
                "-disposition:v:0",
                "attached_pic",
            ]
        )
    else:
        command.extend(["-vn", "-acodec", "copy"])

    command.extend(metadata_args)
    command.extend(["-y", f"file:{output_file}"])
    return subprocess.run(command, capture_output=True, text=True)


def download_song(
    video_input: str,
    output_dir: Path,
    emit=print,
) -> Path:
    """Download a single YouTube video as one tagged MP3 file."""
    output_dir = resolve_output_dir(output_dir)
    video_id = parse_video_id(video_input)

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Cannot write to output folder: {exc}") from exc

    log_line(f"YT video: {video_id}...", emit)
    log_line(f"Saving song to {output_dir}", emit)
    log_line("Downloading song as MP3...", emit)

    watch_url = (
        video_input.strip()
        if video_input.strip().startswith(("http://", "https://"))
        else f"https://www.youtube.com/watch?v={video_id}"
    )

    output_template = str(output_dir / "%(title)s.%(ext)s")
    started_at = time.time()

    attempts = [
        [
            "--no-playlist",
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--embed-metadata",
            "--embed-thumbnail",
            "--output",
            output_template,
            watch_url,
        ],
        [
            "--no-playlist",
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--embed-metadata",
            "--output",
            output_template,
            watch_url,
        ],
        [
            "--no-playlist",
            "-x",
            "--audio-format",
            "mp3",
            "--output",
            output_template,
            watch_url,
        ],
    ]

    code = 1
    lines: list[str] = []
    for index, args in enumerate(attempts):
        if index > 0:
            log_line("Retrying song download with simpler settings...", emit)
        code, lines = run_yt_dlp(args, emit)
        if code == 0:
            break
    if code != 0:
        saved = newest_mp3(output_dir, since=started_at)
        if saved:
            log_line(
                f"Warning: post-processing reported an error, but saved: {saved.name}",
                emit,
            )
            return output_dir
        raise RuntimeError(last_yt_dlp_error(lines))

    saved = newest_mp3(output_dir, since=started_at)
    if saved:
        log_line(f"Saved: {saved.name}", emit)
    return output_dir


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
    artist = (
        data.get("artist")
        or data.get("album_artist")
        or data.get("uploader")
        or data.get("channel")
        or ""
    )
    output_dir = (
        resolve_output_dir(output_parent) / album
        if output_parent is not None
        else Path(album)
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    thumbnail_path = find_thumbnail(work_dir)
    if thumbnail_path:
        log_line(f"Embedding album art from {thumbnail_path.name}", emit)
    else:
        log_line("Warning: no album artwork found; tracks will have tags only.", emit)

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

        metadata_args = track_metadata_args(
            data,
            title=safe_title,
            album=album,
            artist=artist,
            track_label=f"{prefix}/{total_label}",
        )
        result = split_chapter_to_mp3(
            mp3_path,
            thumbnail_path,
            output_file,
            start=round(chapter["start_time"]),
            end=round(chapter["end_time"]),
            metadata_args=metadata_args,
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
        description="Download YouTube audio as album chapters or a single song."
    )
    parser.add_argument("video", help="YouTube URL or video ID")
    parser.add_argument(
        "directory",
        nargs="?",
        help="Output folder (album parent dir or song save dir)",
    )
    parser.add_argument(
        "--mode",
        choices=("album", "song"),
        default="album",
        help="Album splits chaptered videos; song downloads one MP3 file",
    )
    parser.add_argument(
        "--track-prefix",
        action="store_true",
        help="Prefix exported album filenames with zero-padded track numbers",
    )
    args = parser.parse_args(argv)

    output_parent = resolve_output_dir(args.directory) if args.directory else None
    try:
        if args.mode == "song":
            if output_parent is None:
                raise ValueError("Song mode requires an output directory.")
            download_song(args.video, output_parent)
        else:
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
