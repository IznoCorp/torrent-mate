"""Scan the staging tree into the OBJ2A/OBJ1 read-model.

``scan_staging_media`` walks the configured ``staging_dirs`` on the filesystem
and turns every media folder into a
:class:`~personalscraper.web.models.staging.StagingMediaItem` — NFO metadata,
matching state (joined from the live ``scrape_decision`` queue), trailer/poster
presence, season breakdown, and a per-media pipeline **timeline** (the nine
Flow Board stages, each with a derived state). ``resolve_media_dir`` re-derives
a folder from its stable id for the poster route, never trusting a client path.

Everything here is read-only and fail-soft: a missing staging root, an
unmounted disk, or a malformed NFO degrades gracefully rather than 500-ing, so
the read-only staging web instance can serve it (ENV-SEP).
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import folder_name, staging_path
from personalscraper.core.media_types import (
    VIDEO_EXTENSIONS,
    is_sample_path,
    is_trailer_filename,
)
from personalscraper.core.sqlite._pragmas import apply_pragmas as _apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.trailers.placement import find_existing_trailer
from personalscraper.web.models.staging import (
    StagingMediaItem,
    StagingMediaKind,
    StagingSeason,
    StagingStageStep,
)
from personalscraper.web.staging.nfo import (
    NfoMetadata,
    read_nfo_metadata,
)

logger = get_logger(__name__)

#: The nine pipeline stages, in board (left-to-right) order, with French labels.
#: Keys are aligned with the OBJ1 Flow Board (``routes/pipeline.py`` ``_STAGE_DEFS``).
STAGE_DEFS: tuple[tuple[str, str], ...] = (
    ("arrival", "Arrivée"),
    ("staging", "Staging"),
    ("cleaning", "Nettoyage"),
    ("sorting", "Tri"),
    ("matching", "Matching"),
    ("scraping", "Scraping"),
    ("trailers", "Trailers"),
    ("verify", "Vérification"),
    ("dispatch", "Dispatch"),
)

#: Live pipeline step name → stage key, so the item whose frontier stage matches
#: the currently-running step is shown ``active`` rather than ``pending``.
_STEP_TO_STAGE: dict[str, str] = {
    "ingest": "arrival",
    "sort": "staging",
    "clean": "cleaning",
    "cleanup": "cleaning",
    "enforce": "sorting",
    "scrape": "scraping",
    "trailers": "trailers",
    "verify": "verify",
    "dispatch": "dispatch",
}

#: FileType value → read-model media kind (kinds not listed fall back to ``other``).
_FILE_TYPE_TO_KIND: dict[str, StagingMediaKind] = {
    "movie": "movie",
    "tvshow": "tvshow",
    "ebook": "ebook",
    "audio": "audio",
    "app": "app",
    "other": "other",
}

#: Media kinds enriched with NFO + poster + trailer + seasons (and that flow
#: through match/scrape/trailer/verify). Other kinds skip those stages.
_SCRAPABLE_KINDS: frozenset[str] = frozenset({"movie", "tvshow"})

#: Timeline stages a non-scrapable kind skips entirely (shown ``skipped``).
_SCRAPABLE_STAGE_KEYS: frozenset[str] = frozenset({"matching", "scraping", "trailers", "verify"})

#: Poster file matcher — accepts the personalscraper name (``poster.jpg``), the
#: Kodi ``folder.jpg``, AND the MediaElch movie-prefixed form
#: (``{Movie Name}-poster.jpg``) so a media scraped via the MediaElch fallback
#: is not reported poster-less.
_POSTER_RE = re.compile(r"(?:^|.+-)(?:poster|folder)\.(?:jpe?g|png)$", re.IGNORECASE)

#: ``Saison NN`` season-folder pattern (French library convention).
_SEASON_RE = re.compile(r"^Saison\s+(\d+)$", re.IGNORECASE)

#: ``Title (Year)`` trailing-year pattern for folder-name fallbacks.
_FOLDER_YEAR_RE = re.compile(r"^(?P<title>.*?)\s*\((?P<year>\d{4})\)\s*$")


def _nfc(value: str) -> str:
    """Normalize a string to Unicode NFC (macOS/macFUSE yields NFD paths).

    Args:
        value: Any string (typically a filesystem path fragment).

    Returns:
        The NFC-normalized string, so DB-stored (NFC) and iterdir-yielded (NFD)
        paths compare equal.
    """
    return unicodedata.normalize("NFC", value)


def media_id_for(relative_path: str) -> str:
    """Derive the stable URL-safe id for a staged media from its relative path.

    Args:
        relative_path: ``category/folder`` path relative to the staging root.

    Returns:
        The first 16 hex chars of the SHA-1 of the NFC-normalized path — stable
        across requests and safe to embed in a URL (the poster route matches on
        it instead of accepting a path).
    """
    digest = hashlib.sha1(_nfc(relative_path).encode("utf-8")).hexdigest()  # noqa: S324 — id, not security
    return digest[:16]


def _kind_for_entry(file_type: str | None, role: str | None) -> StagingMediaKind:
    """Resolve the read-model media kind for a staging directory entry.

    Args:
        file_type: The entry's ``file_type`` (``"movie"``, ``"tvshow"``, …), or
            ``None`` for the ingest dir.
        role: The entry's role (``"ingest"`` or ``None``).

    Returns:
        The media kind: ``"unsorted"`` for the ingest dir, else the mapped kind
        (``"other"`` for an unknown file_type).
    """
    if role == "ingest":
        return "unsorted"
    if file_type is None:
        return "other"
    return _FILE_TYPE_TO_KIND.get(file_type, "other")


def _title_from_folder(folder: str) -> str:
    """Extract a display title from a media folder name (strip trailing year).

    Args:
        folder: The media folder name (e.g. ``"Fight Club (1999)"``).

    Returns:
        The title without the trailing ``(YYYY)``, or the folder name unchanged.
    """
    match = _FOLDER_YEAR_RE.match(folder)
    if match:
        return match.group("title").strip() or folder
    return folder


def _year_from_folder(folder: str) -> int | None:
    """Extract a release year from a media folder name, or ``None``.

    Args:
        folder: The media folder name.

    Returns:
        The trailing ``(YYYY)`` as an ``int``, or ``None`` when absent.
    """
    match = _FOLDER_YEAR_RE.match(folder)
    return int(match.group("year")) if match else None


def _find_poster(media_dir: Path) -> Path | None:
    """Return the first local poster file in a media folder, or ``None``.

    Matches ``poster.jpg`` / ``folder.jpg`` (personalscraper / Kodi) as well as
    the MediaElch ``{name}-poster.jpg`` form (see :data:`_POSTER_RE`). The
    canonical ``poster.*`` is preferred when several match.

    Args:
        media_dir: The media folder in staging.

    Returns:
        The poster ``Path``, or ``None`` when none match.
    """
    try:
        matches = [c for c in media_dir.iterdir() if c.is_file() and _POSTER_RE.match(c.name)]
    except OSError:
        return None
    if not matches:
        return None
    # Prefer the exact ``poster.*`` over a prefixed ``{name}-poster.*``.
    matches.sort(key=lambda p: (not p.name.lower().startswith("poster."), p.name))
    return matches[0]


def find_nfo(media_dir: Path, media_kind: str) -> Path | None:
    """Return the media's NFO file, tolerant of scraper naming variants.

    Uses the canonical :func:`~personalscraper.nfo_utils.glob_nfo_candidates`
    (any ``*.nfo`` at the folder root, AppleDouble-filtered). Prefers the
    canonical ``movie.nfo`` / ``tvshow.nfo`` when present, else falls back to the
    first root ``.nfo`` — so a MediaElch ``{name}.nfo`` is still detected. Only
    ``movie``/``tvshow`` carry an NFO; other kinds return ``None``.

    Args:
        media_dir: The media folder in staging.
        media_kind: ``"movie"`` or ``"tvshow"`` (other kinds → ``None``).

    Returns:
        The NFO ``Path``, or ``None`` when the kind has no NFO / none exists.
    """
    if media_kind not in _SCRAPABLE_KINDS:
        return None
    from personalscraper.nfo_utils import glob_nfo_candidates  # local: avoid import cycle

    candidates = glob_nfo_candidates(media_dir)
    if not candidates:
        return None
    canonical = "tvshow.nfo" if media_kind == "tvshow" else "movie.nfo"
    for candidate in candidates:
        if candidate.name == canonical:
            return candidate
    return candidates[0]


def _is_episode_video(path: Path) -> bool:
    """Whether a path is a countable episode/movie video (not trailer/sample).

    Args:
        path: A filesystem path.

    Returns:
        ``True`` for a regular video file that is neither a trailer nor a sample.
    """
    if not path.is_file():
        return False
    if path.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
        return False
    return not (is_trailer_filename(path.name) or is_sample_path(path))


def _parse_seasons(media_dir: Path) -> list[StagingSeason]:
    """Parse ``Saison NN`` subfolders of a TV show into season records.

    Args:
        media_dir: The show folder in staging.

    Returns:
        Season records sorted by season number (empty when there are no
        ``Saison NN`` folders — e.g. a single-root season pack).
    """
    seasons: list[StagingSeason] = []
    try:
        children = sorted(media_dir.iterdir())
    except OSError:
        return seasons
    for child in children:
        if not child.is_dir():
            continue
        match = _SEASON_RE.match(child.name)
        if not match:
            continue
        try:
            episode_count = sum(1 for f in child.iterdir() if _is_episode_video(f))
        except OSError:
            episode_count = 0
        seasons.append(StagingSeason(season=int(match.group(1)), label=child.name, episode_count=episode_count))
    seasons.sort(key=lambda s: s.season)
    return seasons


def _tree_stats(media_dir: Path) -> tuple[int, int, float | None]:
    """Compute ``(video_count, size_bytes, latest_mtime)`` for a media tree.

    Walks the folder once, summing regular-file sizes, counting episode/movie
    videos, and tracking the most recent mtime (drives the default sort).

    Args:
        media_dir: The media folder in staging.

    Returns:
        A ``(video_count, size_bytes, latest_mtime)`` tuple. ``latest_mtime`` is
        ``None`` for an empty/unreadable tree.
    """
    video_count = 0
    size_bytes = 0
    latest_mtime: float | None = None
    try:
        for path in media_dir.rglob("*"):
            try:
                if not path.is_file():
                    continue
                stat = path.stat()
            except OSError:
                continue
            size_bytes += stat.st_size
            if latest_mtime is None or stat.st_mtime > latest_mtime:
                latest_mtime = stat.st_mtime
            if _is_episode_video(path):
                video_count += 1
    except OSError:
        pass
    return video_count, size_bytes, latest_mtime


def _load_pending_decisions(db_path: Path) -> dict[str, tuple[int, str]]:
    """Load pending ``scrape_decision`` rows keyed by NFC-normalized path.

    Args:
        db_path: Absolute path to ``library.db``.

    Returns:
        Mapping ``nfc(staging_path) → (decision_id, trigger)`` for every
        ``status='pending'`` decision, or an empty mapping when the DB is
        absent/unreadable (fail-soft).
    """
    if not db_path.exists():
        return {}
    result: dict[str, tuple[int, str]] = {}
    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            _apply_pragmas(conn)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                'SELECT id, staging_path, "trigger" FROM scrape_decision WHERE status = ?',
                ("pending",),
            ).fetchall()
    except sqlite3.Error as exc:
        logger.debug("staging_decisions_query_failed", error=str(exc))
        return {}
    for row in rows:
        result[_nfc(row["staging_path"])] = (row["id"], row["trigger"])
    return result


def _compute_stages(
    *,
    in_ingest: bool,
    scrapable: bool,
    has_nfo: bool,
    has_poster: bool,
    is_ambiguous: bool,
    is_matched: bool,
    has_videos: bool,
    live_stage_key: str | None,
) -> list[StagingStageStep]:
    """Derive the nine-stage timeline for one staged media — strictly monotonic.

    States are inferred from filesystem artefacts + matching state (there is no
    per-item stage table), but the nine stages are ordered, so the timeline is
    kept monotonic: a stage is ``done`` only when every earlier (non-skipped)
    stage is ``done`` too. The first incomplete stage is the *frontier*
    (``blocked`` when a decision is pending, else ``pending``/``active``); every
    later stage is ``pending`` regardless of stray artefacts — a legacy folder
    that holds a poster or trailer but no NFO never shows ``trailers`` done while
    ``matching``/``scraping`` are still pending (the drift-unlink #3 symptom).

    ``trailers`` completion is gated on the scrape (NFO), **not** on a trailer
    file: the trailers step legitimately produces no file for most media, so its
    absence must not read as "not run" and strand ``verify`` behind it.
    ``cleaning``/``sorting`` are ``done`` once the item sits in a category dir
    (inferred from placement); ``dispatch`` is always ``pending`` (a staged item
    has not been dispatched). A ``pending`` stage flips to ``active`` when the
    live run's current step maps to it (``live_stage_key``).

    Args:
        in_ingest: Whether the item is still in the ingest dir (pre-sort).
        scrapable: Whether the kind flows through match/scrape/trailer/verify.
        has_nfo: Whether an NFO is present.
        has_poster: Whether a local poster is present.
        is_ambiguous: Whether a pending decision blocks matching.
        is_matched: Whether the media has a confident match.
        has_videos: Whether the tree contains at least one episode/movie video.
        live_stage_key: Stage key of the live run's current step, or ``None``.

    Returns:
        The ordered list of :class:`StagingStageStep` for the timeline.
    """
    # A confident scrape (matched + NFO on disk) is the gate for every downstream
    # stage — trailers/verify can only have run once the scrape produced an NFO.
    scraped = has_nfo and is_matched

    #: Per-stage "the pipeline has completed this stage" signal, in board order.
    completed: dict[str, bool] = {
        "arrival": True,
        "staging": True,
        "cleaning": not in_ingest,
        "sorting": not in_ingest,
        "matching": is_matched and not is_ambiguous,
        "scraping": scraped,
        "trailers": scraped,
        "verify": scraped and has_poster and has_videos,
        "dispatch": False,
    }

    steps: list[StagingStageStep] = []
    frontier_passed = False
    for key, label in STAGE_DEFS:
        if not scrapable and key in _SCRAPABLE_STAGE_KEYS:
            state = "skipped"
        elif frontier_passed:
            state = "pending"
        elif completed[key]:
            state = "done"
        else:
            # First incomplete stage: the frontier. A pending decision blocks it.
            state = "blocked" if (key == "matching" and is_ambiguous) else "pending"
            frontier_passed = True
        # The live run's current step lights up its (pending) stage as active.
        if state == "pending" and live_stage_key == key:
            state = "active"
        steps.append(StagingStageStep(key=key, label=label, state=state))  # type: ignore[arg-type]
    return steps


def _build_item(
    *,
    config: Config,
    category: str,
    media_dir: Path,
    media_kind: StagingMediaKind,
    in_ingest: bool,
    pending: dict[str, tuple[int, str]],
    live_stage_key: str | None,
) -> StagingMediaItem:
    """Assemble one :class:`StagingMediaItem` from a media folder.

    Args:
        config: The loaded config (unused directly but kept for symmetry with
            the dispatch preview which the route layers on).
        category: The staging subfolder name (e.g. ``"001-MOVIES"``).
        media_dir: The media folder path.
        media_kind: The resolved media kind.
        in_ingest: Whether the folder is in the ingest dir.
        pending: NFC-keyed pending-decision map from :func:`_load_pending_decisions`.
        live_stage_key: Stage key of the live run's current step, or ``None``.

    Returns:
        The fully-populated read-model item.
    """
    folder = media_dir.name
    relative_path = f"{category}/{folder}"
    media_id = media_id_for(relative_path)
    scrapable = media_kind in _SCRAPABLE_KINDS

    meta: NfoMetadata = NfoMetadata()
    has_nfo = False
    has_poster = False
    has_trailer = False
    seasons: list[StagingSeason] | None = None
    episode_count: int | None = None

    if scrapable:
        nfo_path = find_nfo(media_dir, media_kind)
        if nfo_path is not None:
            has_nfo = True
            meta = read_nfo_metadata(nfo_path)
        has_poster = _find_poster(media_dir) is not None
        has_trailer = find_existing_trailer(media_dir, folder, media_type=media_kind) is not None  # type: ignore[arg-type]
        if media_kind == "tvshow":
            seasons = _parse_seasons(media_dir)
            episode_count = sum(s.episode_count for s in seasons)

    video_count, size_bytes, latest_mtime = _tree_stats(media_dir)
    has_videos = video_count > 0

    decision = pending.get(_nfc(str(media_dir)))
    is_ambiguous = decision is not None
    is_matched = has_nfo and bool(meta.provider_ids)
    match: str = "ambiguous" if is_ambiguous else "matched" if is_matched else "absent"

    stages = _compute_stages(
        in_ingest=in_ingest,
        scrapable=scrapable,
        has_nfo=has_nfo,
        has_poster=has_poster,
        is_ambiguous=is_ambiguous,
        is_matched=is_matched,
        has_videos=has_videos,
        live_stage_key=live_stage_key,
    )

    return StagingMediaItem(
        id=media_id,
        category=category,
        folder=folder,
        relative_path=relative_path,
        media_kind=media_kind,
        title=meta.title or _title_from_folder(folder),
        year=meta.year if meta.year is not None else _year_from_folder(folder),
        overview=meta.overview,
        provider_ids=meta.provider_ids,
        match=match,  # type: ignore[arg-type]
        decision_id=decision[0] if decision else None,
        decision_trigger=decision[1] if decision else None,
        has_nfo=has_nfo,
        has_poster=has_poster,
        has_trailer=has_trailer,
        poster_url=f"/api/staging/media/{media_id}/poster" if has_poster else None,
        seasons=seasons,
        episode_count=episode_count,
        video_count=video_count,
        size_bytes=size_bytes,
        modified_at=latest_mtime,
        stages=stages,
    )


def scan_staging_media(
    config: Config,
    db_path: Path,
    *,
    live_step: str | None = None,
) -> list[StagingMediaItem]:
    """Scan the whole staging tree into read-model items.

    Iterates every configured ``staging_dirs`` entry, treats each first-level
    subdirectory as a media folder, and enriches it. Loose files at the root of
    a category dir are ignored (media is always foldered post-sort). Fail-soft:
    a missing staging root or an unreadable category yields fewer items, never
    an error.

    Args:
        config: The loaded config (staging layout + paths).
        db_path: Absolute path to ``library.db`` for the pending-decision join.
        live_step: Name of the live run's current step (e.g. ``"scrape"``), or
            ``None`` — used to mark the matching frontier stage ``active``.

    Returns:
        The unsorted, unfiltered list of staged media items.
    """
    pending = _load_pending_decisions(db_path)
    live_stage_key = _STEP_TO_STAGE.get(live_step) if live_step else None

    items: list[StagingMediaItem] = []
    for entry in config.staging_dirs:
        category = folder_name(entry)
        category_dir = staging_path(config, entry)
        if not category_dir.is_dir():
            continue
        media_kind = _kind_for_entry(entry.file_type, entry.role)
        in_ingest = entry.role == "ingest"
        try:
            children = sorted(category_dir.iterdir())
        except OSError as exc:
            logger.debug("staging_category_unreadable", category=category, error=str(exc))
            continue
        for child in children:
            if not child.is_dir():
                continue
            items.append(
                _build_item(
                    config=config,
                    category=category,
                    media_dir=child,
                    media_kind=media_kind,
                    in_ingest=in_ingest,
                    pending=pending,
                    live_stage_key=live_stage_key,
                )
            )
    return items


def resolve_media_dir(config: Config, media_id: str) -> tuple[str, Path] | None:
    """Re-derive a staged media folder from its stable id (for the poster route).

    Re-scans the staging tree's directory names only (no NFO/stat enrichment)
    and returns the folder whose id matches. Never accepts a client-supplied
    path — the id is matched against freshly-computed ids, so path traversal is
    impossible.

    Args:
        config: The loaded config.
        media_id: The stable media id from a list item.

    Returns:
        A ``(relative_path, media_dir)`` tuple, or ``None`` when no folder
        matches (404).
    """
    for entry in config.staging_dirs:
        category = folder_name(entry)
        category_dir = staging_path(config, entry)
        if not category_dir.is_dir():
            continue
        try:
            children = category_dir.iterdir()
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            relative_path = f"{category}/{child.name}"
            if media_id_for(relative_path) == media_id:
                return relative_path, child
    return None


def resolve_scrapable_item(config: Config, media_id: str) -> tuple[Path, str, str, int | None] | None:
    """Re-derive a scrapable staged item for the manual-resolve enqueue.

    Like :func:`resolve_media_dir` (id matched against freshly-computed ids — a
    client can never inject a path), but also carries the media kind (from the
    category's ``file_type``) and the folder-derived title/year. Returns ``None``
    when the id does not match, or the item is not a ``movie``/``tvshow`` (only
    those flow through a scrape decision).

    Args:
        config: The loaded config.
        media_id: The stable media id from a list item.

    Returns:
        A ``(media_dir, media_kind, title, year)`` tuple, or ``None``.
    """
    for entry in config.staging_dirs:
        category = folder_name(entry)
        category_dir = staging_path(config, entry)
        if not category_dir.is_dir():
            continue
        media_kind = _kind_for_entry(entry.file_type, entry.role)
        if media_kind not in _SCRAPABLE_KINDS:
            continue
        try:
            children = category_dir.iterdir()
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            if media_id_for(f"{category}/{child.name}") == media_id:
                folder = child.name
                return child, media_kind, _title_from_folder(folder), _year_from_folder(folder)
    return None


def resolve_other_item(config: Config, media_id: str) -> tuple[Path, str, int | None] | None:
    """Re-derive a staged item that landed in an ``other`` (unsorted / AUTRES) category.

    Mirror of :func:`resolve_scrapable_item` for items the sort could not type into
    movie/tvshow (they sit under a category whose ``file_type`` maps to ``"other"``,
    e.g. 098-AUTRES). The operator supplies the real kind at enqueue; this resolver
    only re-derives the folder + title/year (id matched against freshly-computed ids,
    so a client can never inject a path).

    Args:
        config: The loaded config.
        media_id: The stable media id from a list item.

    Returns:
        A ``(media_dir, title, year)`` tuple, or ``None`` when the id does not match an
        item in an ``other`` category.
    """
    for entry in config.staging_dirs:
        category = folder_name(entry)
        category_dir = staging_path(config, entry)
        if not category_dir.is_dir():
            continue
        if _kind_for_entry(entry.file_type, entry.role) != "other":
            continue
        try:
            children = category_dir.iterdir()
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            if media_id_for(f"{category}/{child.name}") == media_id:
                folder = child.name
                return child, _title_from_folder(folder), _year_from_folder(folder)
    return None


def poster_file_for(media_dir: Path) -> Path | None:
    """Return the servable local poster file in a media folder, or ``None``.

    Args:
        media_dir: The media folder resolved from an id.

    Returns:
        The poster ``Path`` to serve, or ``None`` when none exists (404).
    """
    return _find_poster(media_dir)
