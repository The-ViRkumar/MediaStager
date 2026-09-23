"""Core logic for MediaStager: parsing, sidecar/artwork matching, TMDB
lookup, ledger, batch queue, and update checks.

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

APP_VERSION = "1.1.0"
GITHUB_RELEASES_API = "https://api.github.com/repos/The-ViRkumar/MediaStager/releases/latest"

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
LEDGER_NAME = "mediastager_ledger.json"
FOLDER_RENAME_KEY = "__folder_rename__"
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')

MODE_SERIES = "series"
MODE_MOVIE = "movie"

# Loose artwork files (Show-poster.jpg, fanart.png, ...) mapped to the
# generic filename Jellyfin/Plex actually look for.
ARTWORK_KEYWORDS = {
    "poster": "poster", "cover": "poster",
    "fanart": "fanart", "backdrop": "backdrop", "background": "backdrop",
    "banner": "banner",
    "clearlogo": "logo", "logo": "logo",
    "clearart": "clearart",
}

TMDB_TV_SEARCH_URL = "https://api.themoviedb.org/3/search/tv"
TMDB_EPISODE_URL = "https://api.themoviedb.org/3/tv/{show_id}/season/{season}/episode/{episode}"
TMDB_MOVIE_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"


def sanitize(text: str) -> str:
    """Strip characters that are illegal in Windows/NTFS filenames."""
    return _INVALID_CHARS.sub("", text).strip()


# ---------------------------------------------------------------------------
# Config (recent directories, theme, last-used options), stored next to the app.
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
    episode_end: Optional[int] = None  # set for a detected multi-episode range
    year: Optional[int] = None


@dataclass
class MovieParsed:
    title: str
    year: Optional[int] = None


def parse_episode(video_path: Path, multi_episode: bool = True) -> Optional[Parsed]:
    """Parse title/season/episode with guessit. Includes the parent folder
    name in the string handed to guessit so season-only-in-folder layouts
    (e.g. "Season 2/ep03.mkv") still resolve correctly."""
    hint = f"{video_path.parent.name}/{video_path.name}"
    info = guessit(hint, {"type": "episode"})

    title = info.get("title")
    episode = info.get("episode")
    if not title or episode is None:
        return None

    episode_end = None
    if isinstance(episode, list):
        if multi_episode and len(episode) > 1:
            episode_end = int(max(episode))
        episode = int(min(episode))
    else:
        episode = int(episode)

    season = info.get("season", 1)
    if isinstance(season, list):
        season = season[0]

    year = info.get("year")
    return Parsed(title=str(title), season=int(season), episode=episode, episode_end=episode_end,
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
    ep_part = f"E{parsed.episode:02d}"
    if parsed.episode_end:
        ep_part += f"-E{parsed.episode_end:02d}"
    base = f"{sanitize(title)} S{parsed.season:02d}{ep_part}"
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
    language tags, .nfo, per-episode thumbs, etc.), excluding other videos."""
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


def find_folder_artwork(folder: Path) -> list[tuple[Path, str]]:
    """Loose artwork files (poster.jpg, Show-fanart.jpg, ...) that don't
    already match a video's own stem, mapped to Jellyfin's canonical name."""
    out = []
    for f in folder.iterdir():
        if not f.is_file() or f.suffix.lower() not in IMAGE_EXTS:
            continue
        stem_lower = f.stem.lower()
        for keyword, canonical in ARTWORK_KEYWORDS.items():
            if keyword in stem_lower:
                new_name = f"{canonical}{f.suffix.lower()}"
                if f.name != new_name:
                    out.append((f, new_name))
                break
    return out


# ---------------------------------------------------------------------------
# TMDB enrichment
# ---------------------------------------------------------------------------

def search_tv_candidates(api_key: str, query: str, limit: int = 5, timeout: float = 6.0) -> list[dict]:
    try:
        r = requests.get(TMDB_TV_SEARCH_URL, params={"api_key": api_key, "query": query}, timeout=timeout)
        r.raise_for_status()
        results = r.json().get("results") or []
    except (requests.RequestException, ValueError):
        return []
    out = []
    for x in results[:limit]:
        year_str = (x.get("first_air_date") or "")[:4]
        out.append({"id": x["id"], "title": x.get("name") or query,
                    "year": int(year_str) if year_str.isdigit() else None})
    return out


def search_movie_candidates(api_key: str, query: str, limit: int = 5, timeout: float = 6.0) -> list[dict]:
    try:
        r = requests.get(TMDB_MOVIE_SEARCH_URL, params={"api_key": api_key, "query": query}, timeout=timeout)
        r.raise_for_status()
        results = r.json().get("results") or []
    except (requests.RequestException, ValueError):
        return []
    out = []
    for x in results[:limit]:
        year_str = (x.get("release_date") or "")[:4]
        out.append({"id": x["id"], "title": x.get("title") or query,
                    "year": int(year_str) if year_str.isdigit() else None})
    return out


def fetch_episode_title_by_show_id(api_key: str, show_id: int, season: int, episode: int,
                                    timeout: float = 6.0) -> Optional[str]:
    try:
        ep = requests.get(
            TMDB_EPISODE_URL.format(show_id=show_id, season=season, episode=episode),
            params={"api_key": api_key}, timeout=timeout,
        )
        ep.raise_for_status()
        return ep.json().get("name") or None
    except (requests.RequestException, KeyError, ValueError):
        return None


def fetch_episode_title(api_key: str, show_title: str, season: int, episode: int,
                         timeout: float = 6.0) -> Optional[str]:
    candidates = search_tv_candidates(api_key, show_title, limit=1, timeout=timeout)
    if not candidates:
        return None
    return fetch_episode_title_by_show_id(api_key, candidates[0]["id"], season, episode, timeout)


def fetch_movie_info(api_key: str, title: str, timeout: float = 6.0) -> Optional[MovieParsed]:
    """Looks up the canonical title/year for a movie."""
    candidates = search_movie_candidates(api_key, title, limit=1, timeout=timeout)
    if not candidates:
        return None
    c = candidates[0]
    return MovieParsed(title=c["title"], year=c["year"])


# ---------------------------------------------------------------------------
# TMDB result picker — collected during a scan when a title has more than
# one plausible match, resolved by the GUI (or left as the guessed name).
# ---------------------------------------------------------------------------

@dataclass
class PendingResolve:
    row: "Row"
    ext: str
    title_override: Optional[str] = None
    parsed: Optional[Parsed] = None  # set for kind == "series"


@dataclass
class PendingChoice:
    key: str
    kind: str  # "series" | "movie"
    candidates: list[dict]
    items: list[PendingResolve] = field(default_factory=list)


def resolve_tmdb_choice(api_key: str, choice: PendingChoice, candidate: Optional[dict]) -> None:
    """Applies the user's pick to every row sharing this ambiguous title.
    candidate=None keeps each row's already-proposed (guessed) name."""
    if candidate is None:
        return
    for item in choice.items:
        if choice.kind == "movie":
            parsed = MovieParsed(title=candidate["title"], year=candidate["year"])
            item.row.proposed = build_movie_filename(parsed, item.ext, item.title_override)
        else:
            ep_title = fetch_episode_title_by_show_id(api_key, candidate["id"],
                                                        item.parsed.season, item.parsed.episode)
            resolved = Parsed(title=candidate["title"], season=item.parsed.season,
                               episode=item.parsed.episode, episode_end=item.parsed.episode_end)
            item.row.proposed = build_filename(resolved, item.ext, ep_title, item.title_override)


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
    row_type: str  # "Video", "Sidecar", or "Artwork"
    excluded: bool = False


@dataclass
class ScanResult:
    rows: list[Row]
    folder_name: Optional[str] = None       # suggested name for target_dir itself
    seasons: list[int] = field(default_factory=list)  # distinct seasons found (series only)
    pending: list[PendingChoice] = field(default_factory=list)  # ambiguous TMDB titles


def _append_sidecars(rows: list[Row], video: Path, new_video_name: str,
                      siblings: list[Path], claimed: set[Path]) -> None:
    for sc in find_sidecars(video, siblings):
        claimed.add(sc)
        rows.append(Row(original=sc, proposed=sidecar_new_name(video, new_video_name, sc), row_type="Sidecar"))


def split_into_shows(target_dir: Path) -> list[Path]:
    """For a library folder containing several shows/movies: returns one
    Path per immediate subfolder that (recursively) contains video files.
    If target_dir itself directly contains videos, it's already a single
    show/season/movie folder, so it's returned as-is (no split needed)."""
    has_direct_videos = any(f.is_file() and f.suffix.lower() in VIDEO_EXTS for f in target_dir.iterdir())
    if has_direct_videos:
        return [target_dir]

    subdirs = [d for d in target_dir.iterdir() if d.is_dir()]
    shows = [d for d in subdirs
             if any(f.suffix.lower() in VIDEO_EXTS for f in d.rglob("*") if f.is_file())]
    return shows if shows else [target_dir]


def scan_directory(target_dir: Path, mode: str, sync_sidecars: bool, tmdb_key: Optional[str] = None,
                    title_override: Optional[str] = None, multi_episode: bool = True) -> ScanResult:
    all_files = [f for f in target_dir.rglob("*") if f.is_file() and f.name != LEDGER_NAME]
    videos = [f for f in all_files if f.suffix.lower() in VIDEO_EXTS]

    rows: list[Row] = []
    folder_title: Optional[str] = None
    folder_year: Optional[int] = None
    seasons_seen: set[int] = set()
    claimed_sidecars: set[Path] = set()
    pending_by_key: dict[str, PendingChoice] = {}
    candidate_cache: dict[str, list[dict]] = {}

    for video in videos:
        siblings = [f for f in all_files if f.parent == video.parent]

        if mode == MODE_MOVIE:
            parsed = parse_movie(video)
            if parsed is None:
                rows.append(Row(original=video, proposed="(could not detect movie)",
                                 row_type="Video", excluded=True))
                continue

            if folder_title is None:
                folder_title = (title_override.strip() if title_override else parsed.title)
                folder_year = parsed.year

            candidates = None
            if tmdb_key:
                key = f"movie:{parsed.title.lower()}"
                candidates = candidate_cache.setdefault(key, search_movie_candidates(tmdb_key, parsed.title))
                if len(candidates) > 1:
                    new_name = build_movie_filename(parsed, video.suffix, title_override)
                    row = Row(original=video, proposed=new_name, row_type="Video")
                    choice = pending_by_key.setdefault(key, PendingChoice(key=key, kind="movie", candidates=candidates))
                    choice.items.append(PendingResolve(row=row, ext=video.suffix, title_override=title_override))
                    rows.append(row)
                    if sync_sidecars:
                        _append_sidecars(rows, video, new_name, siblings, claimed_sidecars)
                    continue
                if candidates:
                    parsed = MovieParsed(title=candidates[0]["title"], year=candidates[0]["year"] or parsed.year)

            new_name = build_movie_filename(parsed, video.suffix, title_override)
            rows.append(Row(original=video, proposed=new_name, row_type="Video"))

        else:
            parsed = parse_episode(video, multi_episode=multi_episode)
            if parsed is None:
                rows.append(Row(original=video, proposed="(could not detect episode)",
                                 row_type="Video", excluded=True))
                continue

            if folder_title is None:
                folder_title = (title_override.strip() if title_override else parsed.title)
                folder_year = parsed.year
            seasons_seen.add(parsed.season)

            episode_title = None
            if tmdb_key:
                key = f"series:{parsed.title.lower()}"
                candidates = candidate_cache.setdefault(key, search_tv_candidates(tmdb_key, parsed.title))
                if len(candidates) > 1:
                    new_name = build_filename(parsed, video.suffix, None, title_override)
                    row = Row(original=video, proposed=new_name, row_type="Video")
                    choice = pending_by_key.setdefault(key, PendingChoice(key=key, kind="series", candidates=candidates))
                    choice.items.append(PendingResolve(row=row, ext=video.suffix, title_override=title_override,
                                                         parsed=parsed))
                    rows.append(row)
                    if sync_sidecars:
                        _append_sidecars(rows, video, new_name, siblings, claimed_sidecars)
                    continue
                if candidates:
                    episode_title = fetch_episode_title_by_show_id(tmdb_key, candidates[0]["id"],
                                                                    parsed.season, parsed.episode)

            new_name = build_filename(parsed, video.suffix, episode_title, title_override)
            rows.append(Row(original=video, proposed=new_name, row_type="Video"))

        if sync_sidecars:
            _append_sidecars(rows, video, new_name, siblings, claimed_sidecars)

    if sync_sidecars:
        artwork_dirs = {target_dir} | {v.parent for v in videos}
        seen_artwork: set[Path] = set()
        for d in artwork_dirs:
            if not d.exists():
                continue
            for f, new_art_name in find_folder_artwork(d):
                if f in seen_artwork or f in claimed_sidecars:
                    continue
                seen_artwork.add(f)
                rows.append(Row(original=f, proposed=new_art_name, row_type="Artwork"))

    folder_name = suggest_title_year_folder(folder_title, folder_year) if folder_title else None
    return ScanResult(rows=rows, folder_name=folder_name, seasons=sorted(seasons_seen),
                       pending=list(pending_by_key.values()))


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
    multi_episode: bool = True
    rows: list[Row] = field(default_factory=list)
    folder_name: Optional[str] = None
    pending: list[PendingChoice] = field(default_factory=list)
    status: str = "Pending"


# ---------------------------------------------------------------------------
# Update check
# ---------------------------------------------------------------------------

def _version_tuple(v: str) -> tuple[int, ...]:
    v = v.lstrip("vV")
    parts = []
    for p in v.split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_for_update(current_version: str = APP_VERSION, timeout: float = 4.0) -> Optional[str]:
    """Returns the latest release tag on GitHub if it's newer than
    current_version, else None (including on any network failure)."""
    try:
        r = requests.get(GITHUB_RELEASES_API, timeout=timeout)
        r.raise_for_status()
        tag = r.json().get("tag_name")
        if tag and _version_tuple(tag) > _version_tuple(current_version):
            return tag
    except (requests.RequestException, ValueError, KeyError):
        pass
    return None
