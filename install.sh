#!/usr/bin/env bash
# Install yt-splitter GUI/CLI and register the `ytsplit` terminal command.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
INSTALL_BIN="${INSTALL_BIN:-${HOME}/.local/bin}"
COMMAND_NAME="${COMMAND_NAME:-ytsplit}"

die() {
  echo "error: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

echo "Installing yt-splitter from: $ROOT"

need_cmd python3
need_cmd ffmpeg

if ! python3 -c 'import venv' >/dev/null 2>&1; then
  die "python3-venv is required. On Debian/Ubuntu: sudo apt install python3-venv"
fi

mkdir -p "$INSTALL_BIN"

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "Creating Python virtual environment..."
  python3 -m venv "$ROOT/.venv"
fi

echo "Installing Python dependencies..."
"$ROOT/.venv/bin/pip" install --upgrade pip
"$ROOT/.venv/bin/pip" install -r "$ROOT/requirements-gui.txt"

chmod +x "$ROOT/ytsplit" "$ROOT/bin/youtube-dl" "$ROOT/run_gui.sh" 2>/dev/null || true

TARGET="$INSTALL_BIN/$COMMAND_NAME"
ln -sf "$ROOT/ytsplit" "$TARGET"

echo ""
echo "Installed successfully."
echo "  Command: $COMMAND_NAME"
echo "  Linked:  $TARGET -> $ROOT/ytsplit"
echo ""
echo "Usage:"
echo "  $COMMAND_NAME                         # open GUI"
echo "  $COMMAND_NAME <youtube-url> [folder]  # split in terminal"
echo "  $COMMAND_NAME <url> [folder] --track-prefix"
echo ""

if [[ ":$PATH:" != *":$INSTALL_BIN:"* ]]; then
  echo "Note: $INSTALL_BIN is not in your PATH."
  echo "Add this to your shell profile:"
  echo "  export PATH=\"$INSTALL_BIN:\$PATH\""
  echo ""
fi

if command -v yt-dlp >/dev/null 2>&1; then
  echo "yt-dlp: $(yt-dlp --version 2>/dev/null | head -1 || echo 'available')"
else
  echo "Tip: install yt-dlp globally for best results:"
  echo "  pipx install yt-dlp"
fi
