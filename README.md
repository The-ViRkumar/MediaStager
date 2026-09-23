<p align="center">
  <img src="assets/icon.png" width="120" alt="MediaStager logo">
</p>

# MediaStager

A desktop tool that renames messy TV episode and movie files into the exact
format Jellyfin and Plex expect (`Show Name S01E02.ext`, `Movie (Year).ext`),
proposes proper Jellyfin-style folder names too, and can process many folders
in one batch — with sidecar syncing, optional TMDB lookups, and a one-click
undo for everything it touches, including folder renames.

Rebuilt from the ground up on top of [`guessit`](https://github.com/guessit-io/guessit)
for filename parsing (title/season/episode/year detection is no longer regex
guesswork), with a redesigned Tkinter/ttk interface and a few extras. Inspired
by [BeckH26/Jellyfin-Renamer](https://github.com/BeckH26/Jellyfin-Renamer).

## Features

- **Series or Movie mode** — pick per folder. Series mode produces
  `Show Name S01E02.ext`; Movie mode produces `Movie Name (Year).ext`, both
  parsed with `guessit` hinted to the right type.
- **Jellyfin folder-name suggestions** — after a scan, each queued folder
  shows its correct Jellyfin folder name (`Show Name (Year)` for series,
  `Movie Name (Year)` for movies). Double-click it to copy, or check "Also
  rename folders" to have Execute Rename apply it automatically.
- **Batch queue across multiple folders** — add as many folders as you want
  (each keeping its own mode/options), scan them all in one pass, review
  every proposed name in one table, and execute the whole batch at once.
- **Sidecar sync** — optionally renames matching subtitles (`.srt`, including
  language-tagged ones like `.en.srt`) and `.nfo` files alongside their video.
- **TMDB enrichment** — Series mode can append the real episode title
  (`Show S01E02 - Pilot.mkv`); Movie mode can correct the title/year against
  TMDB's canonical record. Falls back to the plain guessed name if the lookup
  fails.
- **Undo, including folder renames** — every batch (files and any folder
  rename) is recorded to `mediastager_ledger.json` in the target folder;
  "Undo Last Batch" reverses all of it — across every queued folder at once
  if you're using the batch queue.
- **UNC / network share support** — built entirely on `pathlib.Path`, and the
  directory field accepts a pasted `\\Server\Share\...` path directly (no
  reliance on the OS folder picker mapping the drive).
- **Editable preview** — double-click any proposed name to fix it by hand
  before renaming; click the "Rename?" column to include/exclude a row.
- **Title override** — force a specific title across a folder's batch when
  the source filenames are too messy for automatic detection.
- **Recent folders, filter box, light/dark theme** — quality-of-life extras
  for working through large libraries.
- **Never overwrites** — a rename that would collide with an existing file or
  folder is skipped and reported, never clobbered.

## Getting started

```bash
pip install -r requirements.txt
python main.py
```

1. Pick **Series** or **Movie** mode, paste or browse to a folder, and click
   **+ Add to Queue** (repeat for as many folders as you're processing —
   mixing series and movie folders in the same batch is fine).
2. Toggle "Sync Sidecars" / "Fetch Titles (TMDB)" as needed before adding
   each folder — they're captured per folder. The first time you enable TMDB
   you'll be asked for a free API key from
   [themoviedb.org](https://www.themoviedb.org/settings/api) — it's kept in
   memory for that run only and is never written to disk.
3. Click **Scan Directory** — it scans everything queued (plus whatever's
   still in the text field) and fills the table with every proposed name
   from every folder.
4. Fix anything by hand (double-click a proposed name), exclude rows you
   don't want touched, and check **Also rename folders** if you want the
   queued folders renamed to their suggested Jellyfin names too — otherwise
   just double-click a folder's suggested name in the queue to copy it.
5. Click **Execute Rename**.
6. Made a mistake? **Undo Last Batch** reverses every queued folder's last
   batch — files and any folder rename — in one click. With an empty queue
   it falls back to asking you to pick a single folder to undo.

## Standalone executables (Windows / macOS / Linux)

Pushing a version tag builds and publishes a self-contained executable for
all three platforms — no Python install needed to run them:

```bash
git tag v1.1.0
git push origin v1.1.0
```

`.github/workflows/release.yml` then builds `MediaStager-v1.1.0-windows.exe`,
`MediaStager-v1.1.0-macos`, and `MediaStager-v1.1.0-linux` in parallel and
attaches all three to a GitHub Release. Each new push of a version tag ships
a new versioned release the same way.

To build one locally instead (on the matching OS):

```bash
pip install pyinstaller
COLLECT="--collect-all guessit --collect-all babelfish --collect-all sv_ttk"
pyinstaller --noconsole --onefile --name MediaStager --icon assets/icon.ico $COLLECT --add-data "assets;assets" main.py   # Windows
pyinstaller --noconsole --onefile --name MediaStager --icon assets/icon.icns $COLLECT --add-data "assets:assets" main.py  # macOS
pyinstaller --noconsole --onefile --name MediaStager $COLLECT --add-data "assets:assets" main.py                          # Linux
```

## Project layout

| File | Purpose |
|---|---|
| `core.py` | Parsing, sidecar matching, TMDB lookup, ledger — no GUI imports. |
| `gui.py` | Tkinter/ttk application window. |
| `main.py` | Entry point. |

## Author

Built by [**The.ViRkumar**](https://github.com/The-ViRkumar).

## License

MIT — see [LICENSE](LICENSE).
