"""Trailer attempt-ledger value model — pure data types, no I/O.

Split out of :mod:`personalscraper.trailers.state` (solidify — module-size
relief). This module holds the **attempt-ledger** side of the trailer state
subsystem: the status enum, the frozen ``TrailerState`` record, the composite
key builder and the retry-schedule helper. It is pure (no filesystem, no
``fcntl``, no ``subprocess``) so it never imports the store mechanics — the store
(:class:`~personalscraper.trailers.state.TrailerStateStore`) imports *these*.

Every name here is re-exported from :mod:`personalscraper.trailers.state`, so
existing ``from personalscraper.trailers.state import TrailerState`` call sites
keep working unchanged.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


def _validate_season_number(value: int | None, owner: str) -> None:
    """Raise ValueError when a season_number is non-None and negative.

    Shared by ``TrailerState.__post_init__`` and ``ScanItem.__post_init__``
    so both types accept the same domain (None for movies/show-level, ``0``
    for TMDB specials, ``>=1`` for regular seasons).

    Args:
        value: The season number to validate.
        owner: Class name used in the error message ("TrailerState" or
            "ScanItem").

    Raises:
        ValueError: If ``value`` is not None and is negative.
    """
    if value is not None and value < 0:
        raise ValueError(f"{owner}.season_number must be >= 0 (got {value})")


class TrailerStatus(Enum):
    """Status of a trailer DOWNLOAD ATTEMPT (the state JSON is an attempt ledger).

    Values are persisted as strings in the JSON state file. Do NOT rename
    members without a migration step.

    Single-truth (P6.4 / constitution P26): the filesystem is the truth for
    trailer *existence*; the state JSON is a download-attempt LEDGER — it records
    failures, cooldowns and bot-detection, never a presence claim. The
    attempt-ledger members are ``NO_TRAILER_AVAILABLE``, ``BOT_DETECTED``,
    ``HTTP_ERROR``, ``YTDLP_ERROR`` (all carry a retry/cooldown) plus the
    housekeeping ``ORPHAN`` / ``SKIPPED_BY_FILTER``.

    ``DOWNLOADED`` and ``ALREADY_PRESENT_ON_DISK`` were presence claims — an
    assertion that "a trailer exists". They are **no longer written** (P6.4): a
    successful download or an already-present detection clears the ledger entry
    instead, and presence questions route to the filesystem probe (the derived
    ``trailer_found`` index). The two members are retained only so pre-1.0 state
    files that still carry them deserialise without a migration; ``should_skip``
    no longer treats them as authoritative and ``auto_gc`` still reclaims any
    legacy ``DOWNLOADED`` rows.
    """

    # --- Attempt-ledger members (written; failures + cooldowns) ---
    NO_TRAILER_AVAILABLE = "no_trailer_available"
    BOT_DETECTED = "bot_detected"
    HTTP_ERROR = "http_error"
    YTDLP_ERROR = "ytdlp_error"
    SKIPPED_BY_FILTER = "skipped_by_filter"
    ORPHAN = "orphan"
    # --- Legacy presence-claim members (NO LONGER WRITTEN — P6.4 single-truth) ---
    # Retained for backward deserialisation of pre-1.0 state files only.
    DOWNLOADED = "downloaded"
    ALREADY_PRESENT_ON_DISK = "already_present_on_disk"


@dataclass(frozen=True, slots=True)
class TrailerState:
    """Persisted state for a single media item's trailer download lifecycle.

    Frozen and slotted: state mutations create a new instance via
    ``dataclasses.replace`` rather than in-place modification, which prevents
    accidental drift when references are passed around.

    Timestamps accept either UTC ISO 8601 strings (legacy callers) or
    tz-aware ``datetime`` objects. Naive datetimes are rejected at
    construction so DST/timezone bugs surface immediately rather than at
    serialisation time. ``media_path`` and ``trailer_path`` are absolute
    filesystem paths.

    Attributes:
        last_attempt: UTC ISO 8601 string of the most recent download attempt.
            A tz-aware ``datetime`` is converted to ISO 8601 at construction.
        attempts: Total number of download attempts (incremented on each try).
        status: Current lifecycle status (see ``TrailerStatus``).
        media_path: Absolute path to the media directory on disk. Used by GC to
            detect orphaned entries when the media has been deleted or moved.
        next_retry_at: UTC ISO 8601 string after which a retry is allowed.
            ``None`` means retry immediately (e.g. status ``DOWNLOADED``).
        trailer_path: Absolute path to the downloaded trailer file, or ``None``
            if the trailer has not been successfully downloaded yet.
        source: Originating source of the trailer URL — ``"tmdb"`` or
            ``"youtube"`` — or ``None`` when not applicable.
        youtube_url: Full YouTube watch URL used for the download, or ``None``.
        notes: Free-form human-readable note (e.g. error message summary).
        bot_detected_consecutive_attempts: Counter for consecutive
            ``BOT_DETECTED`` outcomes. Incremented before writing a
            ``BOT_DETECTED`` state; reset to ``0`` before writing any other
            status (DESIGN §5 counter semantics).
        season_number: ``None`` for movies and show-level TV trailers;
            positive 1-indexed integer for season-level entries (DESIGN §4).
    """

    last_attempt: str | datetime
    attempts: int
    status: TrailerStatus
    media_path: str
    next_retry_at: str | datetime | None = None
    trailer_path: str | None = None
    source: str | None = None
    youtube_url: str | None = None
    notes: str | None = None
    bot_detected_consecutive_attempts: int = 0
    season_number: int | None = None

    def __post_init__(self) -> None:
        """Validate timestamps and coerce datetime inputs to ISO 8601.

        Naive datetimes are silently corrupted across DST transitions, so we
        reject them at construction. tz-aware datetimes are coerced to ISO
        strings (frozen dataclass — coercion via ``object.__setattr__``).

        Raises:
            ValueError: If a timestamp string is naive, malformed, or a
                datetime is naive.
            TypeError: If a timestamp is neither str nor datetime.
        """
        for attr in ("last_attempt", "next_retry_at"):
            raw = getattr(self, attr)
            if raw is None:
                continue
            if isinstance(raw, datetime):
                if raw.tzinfo is None:
                    raise ValueError(f"TrailerState.{attr} datetime must be tz-aware (got naive: {raw!r})")
                # Coerce to ISO string in-place (frozen dataclass — use object.__setattr__).
                object.__setattr__(self, attr, raw.isoformat())
                continue
            if not isinstance(raw, str):
                raise TypeError(f"TrailerState.{attr} must be str or datetime, got {type(raw).__name__}")
            try:
                parsed = datetime.fromisoformat(raw)
            except ValueError as exc:
                raise ValueError(f"TrailerState.{attr} is not valid ISO 8601: {raw!r}") from exc
            if parsed.tzinfo is None:
                raise ValueError(f"TrailerState.{attr} ISO string must include timezone offset (got naive: {raw!r})")
        _validate_season_number(self.season_number, "TrailerState")


def _normalize_title(title: str) -> str:
    """Apply NFC normalization, casefold, and whitespace collapse to a title.

    This stable normalization ensures that ``"Fight Club"`` and
    ``"fight  club"`` (extra space + case) produce the same manual key.

    Args:
        title: Raw title string from any source.

    Returns:
        NFC-normalized, casefolded, and whitespace-collapsed title.
    """
    nfc = unicodedata.normalize("NFC", title)
    return " ".join(nfc.casefold().split())


def make_state_key(
    media_type: str,
    ids: dict[str, int | str | None],
    title: str | None = None,
    year: int | None = None,
    season_number: int | None = None,
) -> str:
    """Build a composite state key for a media item.

    Precedence:
        1. ``ids["tmdb"]``  → ``"{media_type}:tmdb:{id}"``
        2. ``ids["tvdb"]``  → ``"{media_type}:tvdb:{id}"``
        3. Fallback         → ``"manual:{sha256(NFC+casefold(title)|year|media_type)}"``

    When ``season_number`` is provided **and** a TMDB/TVDB id is present, the
    season suffix is appended::

        "tv:tmdb:{id}:season:{N}"
        "tv:tvdb:{id}:season:{N}"

    Manual keys do NOT receive a season suffix — season-level trailers without
    external IDs are out of scope in this initial trailer feature release.

    The manual key hashes the NORMALIZED title (NFC + casefold + collapsed
    whitespace) concatenated with year and media_type, separated by ``|``.
    This makes the key stable across re-scrape runs that correct the folder
    name capitalisation.

    Args:
        media_type: ``"movie"`` or ``"tv"``.
        ids: Dict with optional ``"tmdb"`` and/or ``"tvdb"`` integer IDs.
            Values that are ``None`` or ``0`` are treated as absent.
        title: Human-readable title used only for the manual fallback.
        year: Release year (integer) used only for the manual fallback.
        season_number: When not ``None``, appends a ``:season:{N}`` suffix
            to TMDB/TVDB keys (1-indexed, per TMDB convention).

    Returns:
        A stable string key such as ``"movie:tmdb:550"``,
        ``"tv:tmdb:1399:season:3"``, or ``"manual:{hex-digest}"``.

    Raises:
        ValueError: If no external ID is present and ``title`` is ``None``.
    """
    # Primary: TMDB id
    tmdb_id = ids.get("tmdb")
    if tmdb_id is not None and tmdb_id != 0:
        base = f"{media_type}:tmdb:{tmdb_id}"
        if season_number is not None:
            return f"{base}:season:{season_number}"
        return base

    # Secondary: TVDB id
    tvdb_id = ids.get("tvdb")
    if tvdb_id is not None and tvdb_id != 0:
        base = f"{media_type}:tvdb:{tvdb_id}"
        if season_number is not None:
            return f"{base}:season:{season_number}"
        return base

    # Fallback: manual hash of normalized title + year + media_type
    if title is None:
        raise ValueError("Cannot build manual state key: title is required when no external ID is present.")
    normalized = _normalize_title(title)
    payload = f"{normalized}|{year}|{media_type}"
    digest = hashlib.sha256(payload.encode(), usedforsecurity=False).hexdigest()
    return f"manual:{digest}"


def compute_next_retry_at(
    attempts: int,
    policy: list[int],
    *,
    last_attempt: datetime,
) -> datetime:
    """Return the next retry datetime using the configured policy.

    Clock reference is always ``last_attempt`` (DESIGN §7) — NOT the time of
    the first failure. This means a stuck entry keeps pushing the retry window
    forward; a recovered entry resets ``attempts = 1`` on its next successful
    result.

    Args:
        attempts: Number of attempts made so far (1-indexed).
        policy: List of retry intervals in days
            (e.g. ``[1, 7, 30]``). The last element repeats for all
            subsequent attempts.
        last_attempt: UTC-aware datetime of the most recent attempt.

    Returns:
        A UTC-aware datetime representing the earliest acceptable next retry.
    """
    days = policy[min(attempts - 1, len(policy) - 1)]
    return last_attempt + timedelta(days=days)
