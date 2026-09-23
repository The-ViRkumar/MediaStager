"""Core logic for MediaStager: parsing, sidecar matching, TMDB lookup, ledger.

No GUI imports here on purpose — keeps this testable and reusable headless.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
from guessit import guessit

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts"}
LEDGER_NAME = "mediastager_ledger.json"
FOLDER_RENAME_KEY = "__folder_rename__"
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')

MODE_SERIES = "series"
MODE_MOVIE = "movie"

TMDB_TV_SEARCH_URL = "https://api.themoviedb.org/3/search/tv"
TMDB_EPISODE_URL = "https://api.themoviedb.org/3/tv/{show_id}/season/{season}/episode/{episode}"
TMDB_MOVIE_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"


def sanitize(text: str) -> str:
    """Strip characters that are illegal in Windows/NTFS filenames."""
    return _INVALID_CHARS.sub("", text).strip()


# ---------------------------------------------------------------------------
# Config (recent directories, theme), stored next to the app.
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def remember_directory(cfg: dict, directory: str, limit: int = 8) -> dict:
    recent = [d for d in cfg.get("recent_dirs", []) if d != directory]
    recent.insert(0, directory)
    cfg["recent_dirs"] = recent[:limit]
    return cfg


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

@dataclass
class Parsed:
    title: str
    season: int
    episode: int
    year: Optional[int] = None


@dataclass
class MovieParsed:
    title: str
    year: Optional[int] = None


def parse_episode(video_path: Path) -> Optional[Parsed]:
    """Parse title/season/episode with guessit. Includes the parent folder
    name in the string handed to guessit so season-only-in-folder layouts
    (e.g. "Season 2/ep03.mkv") still resolve correctly."""
    hint = f"{video_path.parent.name}/{video_path.name}"
    info = guessit(hint, {"type": "episode"})

    title = info.get("title")
    episode = info.get("episode")
    if not title or episode is None:
        return None
    if isinstance(episode, list):
        episode = episode[0]

    season = info.get("season", 1)
    if isinstance(season, list):
        season = season[0]

    year = info.get("year")
    return Parsed(title=str(title), season=int(season), episode=int(episode),
                  year=int(year) if year else None)


def parse_movie(video_path: Path) -> Optional[MovieParsed]:
    info = guessit(video_path.name, {"type": "movie"})
    title = info.get("title")
    if not title:
        return None
    year = info.get("year")
    return MovieParsed(title=str(title), year=int(year) if year else None)


def build_filename(parsed: Parsed, ext: str, episode_title: Optional[str] = None,
                    title_override: Optional[str] = None) -> str:
    title = title_override.strip() if title_override else parsed.title
    base = f"{sanitize(title)} S{parsed.season:02d}E{parsed.episode:02d}"
    if episode_title:
        base += f" - {sanitize(episode_title)}"
    return f"{base}{ext}"


def build_movie_filename(parsed: MovieParsed, ext: str, title_override: Optional[str] = None) -> str:
    title = sanitize((title_override.strip() if title_override else parsed.title))
    if parsed.year:
        return f"{title} ({parsed.year}){ext}"
    return f"{title}{ext}"


def suggest_title_year_folder(title: str, year: Optional[int]) -> str:
    """Jellyfin folder convention: 'Title (Year)', or just 'Title' if unknown."""
    title = sanitize(title)
    return f"{title} ({year})" if year else title


def suggest_season_folder_name(season: int) -> str:
    """Jellyfin folder convention: 'Season 01', or 'Specials' for season 0."""
    return "Specials" if season == 0 else f"Season {season:02d}"


def find_sidecars(video_path: Path, siblings: list[Path]) -> list[Path]:
    """Files sharing the video's filename stem as a prefix (subtitles with
    language tags, .nfo, etc.), excluding other video files."""
    stem = video_path.stem
    out = []
    for f in siblings:
        if f == video_path or f.suffix.lower() in VIDEO_EXTS:
            continue
        if f.name == stem or f.name.startswith(stem + "."):
            out.append(f)
    return out


def sidecar_new_name(video_path: Path, new_video_name: str, sidecar_path: Path) -> str:
    """Reuse the same suffix (e.g. '.en.srt') on the renamed stem."""
    suffix = sidecar_path.name[len(video_path.stem):]
    new_stem = Path(new_video_name).stem
    return f"{new_stem}{suffix}"


# ---------------------------------------------------------------------------
# TMDB enrichment
# ---------------------------------------------------------------------------

def fetch_episode_title(api_key: str, show_title: str, season: int, episode: int,
                         timeout: float = 6.0) -> Optional[str]:
    try:
        search = requests.get(
            TMDB_TV_SEARCH_URL,
            params={"api_key": api_key, "query": show_title},
            timeout=timeout,
        )
        search.raise_for_status()
        results = search.json().get("results") or []
        if not results:
            return None
        show_id = results[0]["id"]

        ep = requests.get(
            TMDB_EPISODE_URL.format(show_id=show_id, season=season, episode=episode),
            params={"api_key": api_key},
            timeout=timeout,
        )
        ep.raise_for_status()
        return ep.json().get("name") or None
    except (requests.RequestException, KeyError, ValueError):
        return None


def fetch_movie_info(api_key: str, title: str, timeout: float = 6.0) -> Optional[MovieParsed]:
    """Looks up the canonical title/year for a movie. Used to correct sloppy
    filenames when TMDB lookups are enabled in movie mode."""
    try:
        r = requests.get(
            TMDB_MOVIE_SEARCH_URL,
            params={"api_key": api_key, "query": title},
            timeout=timeout,
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results:
            return None
        top = results[0]
        release = top.get("release_date") or ""
        year = int(release[:4]) if release[:4].isdigit() else None
        return MovieParsed(title=top.get("title") or title, year=year)
    except (requests.RequestException, KeyError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Ledger (undo support) — paths are stored RELATIVE to target_dir so a
# folder rename in the same batch doesn't strand the recorded paths.
# ---------------------------------------------------------------------------

def ledger_path(target_dir: Path) -> Path:
    return target_dir / LEDGER_NAME


def save_ledger(target_dir: Path, mapping: dict[str, str], folder_rename: Optional[dict] = None) -> None:
    data = dict(mapping)
    if folder_rename:
        data[FOLDER_RENAME_KEY] = folder_rename
    ledger_path(target_dir).write_text(json.dumps(data, indent=2), encoding="utf-8")


def undo_last_batch(target_dir: Path) -> tuple[int, list[str], Path]:
    """Reverse renames from the ledger (files, then a folder rename if one
    was recorded). Returns (undone_count, errors, resulting_dir)."""
    path = ledger_path(target_dir)
    if not path.exists():
        raise FileNotFoundError(f"No ledger found in {target_dir}")

    data: dict = json.loads(path.read_text(encoding="utf-8"))
    folder_rename = data.pop(FOLDER_RENAME_KEY, None)

    undone = 0
    errors = []
    for rel_original, rel_new in data.items():
        new_path = target_dir / rel_new
        original_path = target_dir / rel_original
        try:
            if new_path.exists() and not original_path.exists():
                new_path.rename(original_path)
                undone += 1
            else:
                errors.append(f"Skipped (state changed): {rel_new}")
        except OSError as exc:
            errors.append(f"{rel_new}: {exc}")

    path.unlink(missing_ok=True)

    result_dir = target_dir
    if folder_rename:
        restored = target_dir.with_name(folder_rename["from"])
        try:
            if target_dir.exists() and not restored.exists():
                target_dir.rename(restored)
                result_dir = restored
        except OSError as exc:
            errors.append(f"Folder rename undo failed: {exc}")

    return undone, errors, result_dir


# ---------------------------------------------------------------------------
# Row model, scan results, and the apply step
# ---------------------------------------------------------------------------

@dataclass
class Row:
    original: Path
    proposed: str
    row_type: str  # "Video" or "Sidecar"
    excluded: bool = False


@dataclass
class ScanResult:
    rows: list[Row]
    folder_name: Optional[str] = None       # suggested name for target_dir itself
    seasons: list[int] = field(default_factory=list)  # distinct seasons found (series only)


def scan_directory(target_dir: Path, mode: str, sync_sidecars: bool, tmdb_key: Optional[str] = None,
                    title_override: Optional[str] = None) -> ScanResult:
    all_files = [f for f in target_dir.rglob("*") if f.is_file() and f.name != LEDGER_NAME]
    videos = [f for f in all_files if f.suffix.lower() in VIDEO_EXTS]

    rows: list[Row] = []
    folder_title: Optional[str] = None
    folder_year: Optional[int] = None
    seasons_seen: set[int] = set()

    for video in videos:
        siblings = [f for f in all_files if f.parent == video.parent]

        if mode == MODE_MOVIE:
            parsed = parse_movie(video)
            if parsed is None:
                rows.append(Row(original=video, proposed="(could not detect movie)",
                                 row_type="Video", excluded=True))
                continue
            if tmdb_key:
                canonical = fetch_movie_info(tmdb_key, parsed.title)
                if canonical:
                    parsed = MovieParsed(title=canonical.title, year=canonical.year or parsed.year)

            if folder_title is None:
                folder_title = (title_override.strip() if title_override else parsed.title)
                folder_year = parsed.year

            new_name = build_movie_filename(parsed, video.suffix, title_override)
            rows.append(Row(original=video, proposed=new_name, row_type="Video"))

        else:
            parsed = parse_episode(video)
            if parsed is None:
                rows.append(Row(original=video, proposed="(could not detect episode)",
                                 row_type="Video", excluded=True))
                continue

            episode_title = None
            if tmdb_key:
                episode_title = fetch_episode_title(tmdb_key, parsed.title, parsed.season, parsed.episode)

            if folder_title is None:
                folder_title = (title_override.strip() if title_override else parsed.title)
                folder_year = parsed.year
            seasons_seen.add(parsed.season)

            new_name = build_filename(parsed, video.suffix, episode_title, title_override)
            rows.append(Row(original=video, proposed=new_name, row_type="Video"))

        if sync_sidecars:
            for sc in find_sidecars(video, siblings):
                rows.append(Row(
                    original=sc,
                    proposed=sidecar_new_name(video, new_name, sc),
                    row_type="Sidecar",
                ))

    folder_name = suggest_title_year_folder(folder_title, folder_year) if folder_title else None
    return ScanResult(rows=rows, folder_name=folder_name, seasons=sorted(seasons_seen))


def apply_rename(rows: list[Row], target_dir: Path, rename_folder_to: Optional[str] = None
                  ) -> tuple[int, list[str], Path]:
    """Renames included rows, then optionally renames target_dir itself.
    Returns (renamed_count, skipped_messages, resulting_target_dir)."""
    mapping: dict[str, str] = {}
    skipped: list[str] = []
    renamed = 0

    for row in rows:
        if row.excluded:
            continue
        dest = row.original.with_name(row.proposed)
        if dest.exists():
            skipped.append(f"{row.original.name} -> {row.proposed} (target exists)")
            continue
        try:
            row.original.rename(dest)
            mapping[str(row.original.relative_to(target_dir))] = str(dest.relative_to(target_dir))
            renamed += 1
        except OSError as exc:
            skipped.append(f"{row.original.name}: {exc}")

    result_dir = target_dir
    folder_rename_record = None
    if rename_folder_to and sanitize(rename_folder_to) != target_dir.name:
        new_dir = target_dir.with_name(sanitize(rename_folder_to))
        if new_dir.exists():
            skipped.append(f"Folder rename skipped: '{new_dir.name}' already exists")
        else:
            try:
                target_dir.rename(new_dir)
                folder_rename_record = {"from": target_dir.name, "to": new_dir.name}
                result_dir = new_dir
            except OSError as exc:
                skipped.append(f"Folder rename failed: {exc}")

    if mapping or folder_rename_record:
        save_ledger(result_dir, mapping, folder_rename_record)
    return renamed, skipped, result_dir


# ---------------------------------------------------------------------------
# Batch queue — several folders (each with its own mode/options), scanned
# and executed together.
# ---------------------------------------------------------------------------

@dataclass
class QueueItem:
    path: Path
    mode: str
    sync_sidecars: bool
    use_tmdb: bool
    title_override: Optional[str] = None
    rows: list[Row] = field(default_factory=list)
    folder_name: Optional[str] = None
    status: str = "Pending"
