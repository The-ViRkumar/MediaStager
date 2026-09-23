<p align="center">
  <img src="assets/icon.png" width="112" alt="MediaStager logo">
</p>

<h1 align="center">MediaStager</h1>

<p align="center">
  Batch-rename TV episodes and movies into filenames <em>and folders</em> that Jellyfin and Plex actually recognize.
</p>

<p align="center">
  <a href="https://github.com/The-ViRkumar/MediaStager/actions/workflows/release.yml"><img src="https://github.com/The-ViRkumar/MediaStager/actions/workflows/release.yml/badge.svg" alt="Release build status"></a>
  <a href="https://github.com/The-ViRkumar/MediaStager/releases"><img src="https://img.shields.io/github/v/release/The-ViRkumar/MediaStager?label=release" alt="Latest release"></a>
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-informational" alt="Platform support">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"></a>
</p>

Point it at a messy folder — or several at once — and it proposes correct
`Show Name S01E02.ext` / `Movie Name (Year).ext` filenames and correct
folder names, using [`guessit`](https://github.com/guessit-io/guessit) for
parsing instead of brittle regex. Review everything in one table, execute,
and undo it with one click if anything's wrong — folder renames included.

Rebuilt from the ground up, inspired by
[BeckH26/Jellyfin-Renamer](https://github.com/BeckH26/Jellyfin-Renamer).

## Contents

- [Features](#features)
- [Jellyfin naming reference](#jellyfin-naming-reference)
- [Download](#download)
- [Run from source](#run-from-source)
- [How to use it](#how-to-use-it)
- [Feature reference](#feature-reference)
- [Building your own executable](#building-your-own-executable)
- [Project layout](#project-layout)
- [Author](#author)
- [License](#license)

## Features

**Smart, format-aware renaming**
- **Series or Movie mode**, chosen per folder — `guessit` is hinted to the
  right type instead of guessing blind.
- **Multi-episode files** — `Show.S01E01-E02.mkv` is renamed correctly to
  `Show S01E01-E02.mkv` when the filename already states the range. (A
  season-pack file with *no* episode markers at all in its name can't be
  identified as "episodes 1-10" from the filename alone — that one still
  needs a manual fix via the inline editor.)
- **Jellyfin folder-name suggestions** for every folder you process
  (`Show Name (Year)` / `Movie Name (Year)`) — double-click to copy, or let
  Execute Rename apply it for you.
- **TMDB enrichment** — real episode titles in Series mode, canonical
  title/year correction in Movie mode. When a title has more than one
  plausible match, you're asked which one; otherwise it's fully automatic.
- **Sidecar & artwork sync** — subtitles (including language tags like
  `.en.srt`), `.nfo` files, and loose poster/fanart/banner/logo images are
  renamed or normalized to Jellyfin's expected names right alongside the
  video.

**Built for real libraries, not one file at a time**
- **Batch queue across multiple folders** — queue as many folders as you
  want, each keeping its own mode and options, scan them all, review one
  table, execute once. **+ Add Multiple...** lets you paste a whole list of
  paths (one per line) in one go.
- **Auto-split a library folder** — point it at a folder containing several
  shows/movies and it queues each one as its own item automatically, instead
  of merging them into one.
- **Editable preview** — fix any proposed name by hand, exclude rows you
  don't want touched.
- **Title override** for folders too messy for automatic detection.
- **Remembers your last-used Mode / Sync / TMDB / Multi-episode / Auto-split
  settings** between launches.
- **Export the rename table to CSV** (old name, new name, folder, type) for
  a dry-run review or an audit trail.
- **UNC / network share support** — paste a `\\Server\Share\...` path
  directly; no dependence on the OS folder picker mapping the drive.

**Safety first**
- **Undo Last Batch** reverses an entire batch — every renamed file *and*
  any folder rename — across every queued folder at once.
- **Never overwrites** — a collision is skipped and reported, never
  clobbered.
- The TMDB API key lives in memory for the session only; it's never written
  to disk.
- **In-app update notice** — checks GitHub Releases on launch and shows a
  link if a newer version is available; fails silently if you're offline.

## Jellyfin naming reference

This is exactly what MediaStager produces:

| | Folder | File |
|---|---|---|
| **Series** | `Show Name (2019)/Season 01/` | `Show Name S01E02.mkv` |
| **Movie** | `Movie Name (2008)/` | `Movie Name (2008).mkv` |

## Download

Grab a ready-to-run build from the
[**Releases**](https://github.com/The-ViRkumar/MediaStager/releases) page —
`MediaStager-<version>-windows.exe`, `-macos`, or `-linux`. No Python
required; just download and run.

## Run from source

```bash
pip install -r requirements.txt
python main.py
```

Requires Python 3.9+.

## How to use it

1. Pick **Series** or **Movie** mode, paste or browse to a folder, and click
   **+ Add to Queue** — or **+ Add Multiple...** to paste several paths at
   once (repeat/mix for every folder you're processing; series and movie
   folders can share the same batch). Check **Auto-split library folder**
   first if the folder you're adding actually contains several shows/movies.
2. Toggle **Sync Sidecars/Artwork** / **Fetch Titles (TMDB)** /
   **Multi-episode files** as needed before adding each folder — they're
   captured per folder. The first time you enable TMDB you'll be asked for a
   free API key from [themoviedb.org](https://www.themoviedb.org/settings/api).
3. Click **Scan Directory** — it scans everything queued and fills the table
   with every proposed name from every folder. If a title has multiple
   plausible TMDB matches, you'll be asked to pick the right one.
4. Fix anything by hand (double-click a proposed name), exclude rows you
   don't want touched, and check **Also rename folders** if you want the
   queued folders renamed to their suggested Jellyfin names too. **Export
   CSV** any time you want a record of what's about to change.
5. Click **Execute Rename**.
6. Made a mistake? **Undo Last Batch** reverses every queued folder's last
   batch — files and any folder rename — in one click.

## Feature reference

Every control in the app, what it's for, and how to use it. Click a name to
jump straight to its section.

| Feature | Does what |
|---|---|
| [Series or Movie mode](#series-or-movie-mode) | Picks the naming convention to apply |
| [Batch queue](#batch-queue) | Queue many folders, scan and execute together |
| [Auto-split library folder](#auto-split-library-folder) | Splits one library folder into one queue item per show/movie |
| [Add Multiple folders](#add-multiple-folders) | Paste many folder paths at once |
| [Sync Sidecars and Artwork](#sync-sidecars-and-artwork) | Renames subtitles, `.nfo`, and poster/fanart images alongside the video |
| [TMDB enrichment](#tmdb-enrichment) | Adds real episode titles / corrects movie title and year |
| [TMDB result picker](#tmdb-result-picker) | Lets you choose the right match when TMDB is ambiguous |
| [Multi-episode files](#multi-episode-files) | Names `S01E01-E02`-style files correctly |
| [Jellyfin folder renaming](#jellyfin-folder-renaming) | Suggests, and can apply, the correct folder name |
| [Title override](#title-override) | Forces a title when auto-detection guesses wrong |
| [Editable preview and exclude](#editable-preview-and-exclude) | Fix any proposed name by hand, or skip a row |
| [Filter box](#filter-box) | Live-searches the results table |
| [Export CSV](#export-csv) | Saves the rename table as a CSV report |
| [Undo Last Batch](#undo-last-batch) | Reverts an entire batch, folder renames included |
| [Remembered options](#remembered-options) | Last-used settings persist between launches |
| [UNC and network paths](#unc-and-network-paths) | Paste `\\Server\Share\...` paths directly |
| [Dark and light theme](#dark-and-light-theme) | Toggles the app's appearance |
| [In-app update check](#in-app-update-check) | Notifies you when a newer release is available |

### Series or Movie mode

Two radio buttons at the top: **Series** and **Movie**. This is *per
folder* — it's read when you click **+ Add to Queue**, so you can queue a
mix of both in the same batch by switching the mode between adds. Series
mode looks for a season/episode; Movie mode looks for a title/year. Picking
the right one matters — it changes both the parsing hints given to
`guessit` and the output filename pattern.

### Batch queue

The table under "Batch Queue" holds every folder you've added, each with
its own mode, options, and (after scanning) its suggested folder name and
status. Add folders with **+ Add to Queue** or **+ Add Multiple...**, remove
one with **Remove Selected**, or wipe it with **Clear Queue**. One **Scan
Directory** click scans every *Pending* folder in the queue; one **Execute
Rename** click applies every scanned folder's changes at once.

### Auto-split library folder

Checkbox next to Auto-split library folder. If it's on when you add a
folder, and that folder doesn't contain videos directly but has
subfolders that do (e.g. `TV Shows/Breaking Bad/...`, `TV Shows/The
Office/...`), each subfolder is queued as its **own** item instead of the
whole library being treated as one show. Turn it off if the folder you're
adding *is* already a single show/season/movie folder.

### Add Multiple folders

**+ Add Multiple...** opens a text box — paste as many folder paths as you
want, one per line, and click **Add All**. Every line is queued with
whatever Mode/Sync/TMDB/Multi-episode/Auto-split options are currently set.
Invalid paths are skipped and listed in a summary instead of stopping the
whole batch.

### Sync Sidecars and Artwork

Checkbox: **Sync Sidecars/Artwork**. When on, a scan also finds:
- Files sharing a video's exact filename (subtitles like `Show S01E01.srt`
  or `Show S01E01.en.srt`, `.nfo` files, per-episode thumbnails) — renamed
  to match the video's new name, suffix preserved.
- Loose artwork files anywhere in the folder whose name contains a keyword
  like `poster`, `fanart`, `backdrop`, `banner`, `logo`, or `clearart` (e.g.
  `Show-poster.jpg`) — renamed to Jellyfin/Plex's expected generic name
  (`poster.jpg`, `fanart.jpg`, ...).

### TMDB enrichment

Checkbox: **Fetch Titles (TMDB)**. The first time you enable it you're
asked for a free API key from
[themoviedb.org](https://www.themoviedb.org/settings/api) — kept in memory
for the session only, never written to disk. In Series mode it appends the
real episode title (`Show S01E02 - Pilot.mkv`); in Movie mode it corrects
the title/year against TMDB's record. If the lookup fails or finds nothing,
the plain `guessit`-based name is used instead — nothing breaks.

### TMDB result picker

When a searched title comes back with more than one plausible TMDB match
(e.g. "The Office" has a US and a UK version), a small dialog lists every
candidate — pick the right one, or click **Keep Guessed Name** to skip
enrichment for that title. This only appears when there's real ambiguity;
a single clear match is applied automatically with no prompt.

### Multi-episode files

Checkbox: **Multi-episode files** (on by default). When a filename already
states a range — `Show.S01E01-E02.mkv`, `Show.1x01x02.mkv`, and similar
patterns `guessit` recognizes — the proposed name becomes
`Show S01E01-E02.mkv` instead of just using the first episode number. A
file with *no* episode markers at all in its name (a raw "whole season in
one file" dump) can't be identified as covering multiple episodes from the
filename alone, so it's left flagged for you to rename by hand.

### Jellyfin folder renaming

After a scan, the Batch Queue table's "Suggested Folder Name" column shows
the correct Jellyfin folder name for each queued folder (`Show Name
(Year)` / `Movie Name (Year)`). Double-click it to copy that name to the
clipboard. Check **Also rename folders** before clicking **Execute Rename**
to have it applied automatically instead.

### Title override

Text field: **Title Override**. When set, it replaces the auto-detected
title for every file in the *next* folder(s) you add to the queue — useful
when the source filenames are too messy for `guessit` to get the show or
movie name right. Leave it blank to use whatever's auto-detected.

### Editable preview and exclude

In the results table: double-click any **Proposed Name** cell to type a
replacement by hand (Enter to save, Escape to cancel). Click a row's
**Rename?** cell to toggle it between ✓ (will be renamed) and ✗ (skipped).
Both apply per file, so you can hand-fix or exclude individual rows without
touching the rest of the batch.

### Filter box

Text field next to **Scan Directory**. Type anything and the table narrows
live to rows whose original or proposed name contains it — nothing about
the actual scan or rename changes, it's just a display filter. Clear it to
see everything again.

### Export CSV

**Export CSV** button saves the current results table — folder, original
name, proposed name, type, and whether it's included — to a `.csv` file you
choose. Useful as a dry-run record before executing, or an audit trail
afterward.

### Undo Last Batch

**Undo Last Batch** reverses the most recent Execute Rename for every
folder currently in the queue — every file rename and any folder rename —
in one click, reading each folder's `mediastager_ledger.json`. With an
empty queue, it instead asks you to pick a single folder to undo (for
reverting a batch from an earlier session).

### Remembered options

Mode, Sync Sidecars/Artwork, Fetch Titles (TMDB), Multi-episode files, and
Auto-split library folder all persist to `config.json` next to the app and
are restored the next time you launch it — along with your recent
directories list. The TMDB API key itself is *not* remembered (see
[TMDB enrichment](#tmdb-enrichment)).

### UNC and network paths

The Target Directory field is a normal text box, not just a folder picker —
paste a `\\Server\Share\...` path directly and it works, including for
network drives the Windows folder browser sometimes fails to map. Built
entirely on `pathlib.Path` under the hood.

### Dark and light theme

**Dark Mode** checkbox in the top-right, top bar. Switches the whole
interface between light and dark instantly; your choice is remembered
between launches.

### In-app update check

On launch, MediaStager quietly checks GitHub Releases for a newer version.
If one exists, a green **⬆ Update available: vX.Y.Z** link appears in the
top bar — click it to open the Releases page. If you're offline or GitHub
is unreachable, this fails silently and the app works exactly the same.

## Building your own executable

Push a version tag and CI builds all three platforms and publishes them to
Releases automatically. Bump `APP_VERSION` in `core.py` to match the tag
first, so the in-app update checker knows about the new version:

```bash
git tag v1.1.0
git push origin v1.1.0
```

`.github/workflows/release.yml` builds `MediaStager-v1.1.0-windows.exe`,
`-macos`, and `-linux` in parallel via PyInstaller and attaches them to a
GitHub Release. Repeat with the next version number whenever you're ready
to ship.

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
| `assets/generate_icon.py` | Regenerates the app icon (dev-time only). |
| `.github/workflows/release.yml` | Builds and publishes tagged multi-platform releases. |

## Author

Built by [**The.ViRkumar**](https://github.com/The-ViRkumar).

## License

MIT — see [LICENSE](LICENSE).
