# Community fork — GUI + `ytsplit` upgrade

The original [redsolver/yt-splitter](https://github.com/redsolver/yt-splitter) repository is **archived** and no longer accepts pull requests or issues. This fork keeps the original idea alive and adds a few practical upgrades for modern systems.

## What was added

| Addition | What it does |
|----------|----------------|
| **PyQt6 GUI** | Paste a URL, pick a folder, watch progress, optional track-prefix checkbox |
| **`ytsplit` command** | `install.sh` registers a terminal command: GUI with no args, CLI with a URL |
| **Python splitter** | `splitter.py` mirrors chapter-splitting behavior using **yt-dlp** |
| **`bin/youtube-dl` wrapper** | Routes legacy `youtube-dl` calls to yt-dlp (often missing/broken today) |
| **Track prefix option** | `--track-prefix` / GUI checkbox → `01 - Track Name.mp3` filenames |
| **Updated README** | Quick install, GUI screenshot (`ytsplitgui.png`), usage notes |

The original **Dart CLI** (`bin/yt_splitter.dart`) is unchanged in spirit and still documented.

## Quick start

```bash
git clone https://github.com/platysonique/yt-splitter.git
cd yt-splitter
./install.sh
ytsplit
```

## Upstream author

Credit and thanks to **[redsolver](https://github.com/redsolver)** for the original yt-splitter tool.

If you're the author (or know them) and want to un-archive, adopt these changes, or point users here — this fork is offered in good faith as a community continuation, not a takeover.

## Share this fork

- **Repo:** https://github.com/platysonique/yt-splitter
- **Install:** `./install.sh` then `ytsplit`
- **Requirement:** YouTube videos with **chapters** (common on full-album uploads)

## Suggested message if sharing with the author

> Built a PyQt6 GUI, `ytsplit` install command, yt-dlp compatibility, and optional track-prefix filenames on top of yt-splitter. Tried to open a PR but the repo is archived. Fork here if useful: https://github.com/platysonique/yt-splitter
