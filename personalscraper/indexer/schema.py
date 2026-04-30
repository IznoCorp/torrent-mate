"""Dataclass row types and Pydantic JSON-column models for the indexer database.

Every table in the indexer schema (§6.2) is represented by a frozen dataclass
whose fields exactly mirror the column list.  JSON columns are stored as ``str``
in the dataclass (raw wire format) and validated via the companion Pydantic
models when the application *writes* a JSON column.

Custom exception:
- :class:`SchemaConventionError` — raised by convention tests when a field name
  violates the ``*_at → int`` / ``*_ns → int`` timestamp convention (§6.5).

Helper:
- :func:`_check_field_naming_convention` — called from ``tests/indexer/test_schema.py``
  to assert the suffix convention is upheld for every Row dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Literal aliases for stringly-typed enum columns
# ---------------------------------------------------------------------------
# These are the exact string sets enforced by SQLite ``CHECK`` constraints
# on the corresponding columns (see ``indexer/migrations/*.sql``).  Using
# :data:`typing.Literal` here is purely additive at runtime — call sites
# that already pass valid strings keep working — but it lets ``mypy`` /
# pyright catch typos in code that constructs these rows.

#: ``media_item.kind`` discriminator.
MediaItemKind: TypeAlias = Literal["movie", "show"]
#: ``media_item.nfo_status``; ``None`` means "not yet checked".
NfoStatus: TypeAlias = Literal["missing", "invalid", "valid"]
#: ``index_outbox.source`` — originating subsystem.
OutboxSource: TypeAlias = Literal["dispatch", "scraper", "trailers", "scanner", "pending_op"]
#: ``index_outbox.op`` — supported operation types.
OutboxOp: TypeAlias = Literal["move", "nfo_write", "artwork_write", "trailer_download"]
#: ``index_outbox.status`` — drainer lifecycle.
OutboxStatus: TypeAlias = Literal["pending", "done", "failed", "deferred"]
#: ``scan_run.mode``.
ScanMode: TypeAlias = Literal["quick", "incremental", "enrich", "full", "verify", "repair"]
#: ``scan_run.status``.
ScanStatus: TypeAlias = Literal["running", "ok", "failed", "aborted"]
#: ``repair_queue.scope``.
RepairScope: TypeAlias = Literal["file", "item", "release", "subtree", "path", "disk"]
#: ``repair_queue.status``.
RepairQueueStatus: TypeAlias = Literal["pending", "running", "done", "failed"]
#: ``deleted_item.kind`` — what was soft-deleted.
DeletedKind: TypeAlias = Literal["item", "file", "release"]
#: ``media_stream.kind``.
StreamKind: TypeAlias = Literal["video", "audio", "subtitle"]

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class SchemaConventionError(ValueError):
    """Raised when a dataclass field violates the timestamp suffix convention.

    Args:
        field_name: The name of the offending field.
        type_hint: The declared type of that field.
        reason: Human-readable explanation of the violation.
    """

    def __init__(self, field_name: str, type_hint: type, reason: str) -> None:
        """Initialize with field name, type hint, and reason."""
        self.field_name = field_name
        self.type_hint = type_hint
        self.reason = reason
        super().__init__(f"Schema convention violation on field '{field_name}' ({type_hint!r}): {reason}")


# ---------------------------------------------------------------------------
# Convention checker
# ---------------------------------------------------------------------------


def _check_field_naming_convention(field_name: str, type_hint: type) -> None:
    """Assert that timestamp-suffix fields use the correct type.

    Per DESIGN §6.5:
    - Fields ending with ``_at`` must be typed ``int`` (unix epoch seconds).
    - Fields ending with ``_ns`` must be typed ``int`` (unix epoch nanoseconds).

    Non-timestamp fields are silently ignored.

    Args:
        field_name: The dataclass field name to check.
        type_hint: The resolved type annotation of that field.

    Raises:
        SchemaConventionError: When a ``*_at`` or ``*_ns`` field is not typed
            ``int``.
    """
    # Only enforce the convention for exact-name suffix matches.
    if not (field_name.endswith("_at") or field_name.endswith("_ns")):
        return

    # Allow Optional[int] / int | None — the raw resolved hint will be int for
    # non-optional fields; for optional we skip enforcement because the DB schema
    # allows NULLs (Python side uses int | None).
    # We accept int directly; anything else is a violation.
    if type_hint is int:
        return  # compliant

    raise SchemaConventionError(
        field_name,
        type_hint,
        f"timestamp field must be typed 'int', got {type_hint!r}",
    )


# ---------------------------------------------------------------------------
# Row dataclasses — one per table, frozen + kw_only for immutable construction
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class DiskRow:
    """Row type for the ``disk`` table.

    Args:
        id: Primary key (auto-assigned by SQLite on insert; 0 = unset).
        uuid: Volume UUID from ``diskutil info -plist``.
        label: Display label, e.g. "Disk1".
        mount_path: Configured scan root for the disk (i.e. ``DiskConfig.path``).
            This is the directory the scanner walks and where ``rel_path`` values
            are computed against. It may be a **subdirectory** of the actual OS
            mount point (e.g. ``/Volumes/Disk1/medias`` while the volume mounts at
            ``/Volumes/Disk1``); the indexer resolves the underlying mount root on
            demand via :func:`personalscraper.indexer.merkle._resolve_volume_root`
            so ``diskutil`` calls and the per-disk sentinel file land at the
            volume root rather than the configured subdir. ``None`` when the
            disk has never been observed mounted.
        last_seen_at: Unix epoch seconds; ``None`` = never seen.
        merkle_root: xxh3_64 hex (16 chars); ``None`` until first scan.
        is_mounted: 0 or 1.
        unreachable_strikes: Consecutive scans where disk was unreachable.
    """

    id: int
    uuid: str
    label: str
    mount_path: str | None
    last_seen_at: int | None
    merkle_root: str | None
    is_mounted: int
    unreachable_strikes: int


@dataclass(frozen=True, kw_only=True)
class PathRow:
    """Row type for the ``path`` table.

    Args:
        id: Primary key.
        disk_id: FK → ``disk.id``.
        rel_path: Directory path relative to disk mount, e.g. ``001-MOVIES/Inception (2010)``.
        dir_mtime_ns: Directory mtime in nanoseconds; ``None`` = not yet captured.
        last_walked_at: Unix epoch seconds of last walk; ``None`` = never walked.
    """

    id: int
    disk_id: int
    rel_path: str
    dir_mtime_ns: int | None
    last_walked_at: int | None


@dataclass(frozen=True, kw_only=True)
class MediaItemRow:
    """Row type for the ``media_item`` table.

    Args:
        id: Primary key.
        kind: ``'movie'`` or ``'show'``.
        title: Display title.
        title_sort: Sort title (French articles stripped).
        original_title: Original-language title; ``None`` if same as title.
        year: Release year; ``None`` if unknown.
        category_id: Logical category ID from config.
        tmdb_id: TMDB numeric ID; ``None`` if not scraped.
        imdb_id: IMDb tt-id string; ``None`` if not scraped.
        tvdb_id: TVDB numeric ID; ``None`` if not applicable.
        nfo_status: ``'missing'``, ``'invalid'``, or ``'valid'``; ``None`` if unchecked.
        artwork_json: Raw JSON string (validated by :class:`ArtworkInventory`).
        date_created: Unix epoch seconds of first index entry.
        date_modified: Unix epoch seconds of last index update.
        date_metadata_refreshed: Unix epoch seconds of last TMDB/TVDB scrape; ``None`` = never.
        is_locked: 1 to skip auto-rescrape, 0 otherwise.
        preferred_lang: BCP-47 language code, default ``'fr'``.
    """

    id: int
    kind: MediaItemKind
    title: str
    title_sort: str
    original_title: str | None
    year: int | None
    category_id: str
    tmdb_id: int | None
    imdb_id: str | None
    tvdb_id: int | None
    nfo_status: NfoStatus | None
    artwork_json: str | None
    date_created: int
    date_modified: int
    date_metadata_refreshed: int | None
    is_locked: int
    preferred_lang: str


@dataclass(frozen=True, kw_only=True)
class ItemAttributeRow:
    """Row type for the ``item_attribute`` table.

    Args:
        item_id: FK → ``media_item.id`` (part of composite PK).
        key: Attribute key, e.g. ``'trailer_found'``.
        value: Attribute value as string; ``None`` allowed.
    """

    item_id: int
    key: str
    value: str | None


@dataclass(frozen=True, kw_only=True)
class SeasonRow:
    """Row type for the ``season`` table.

    Args:
        id: Primary key.
        item_id: FK → ``media_item.id``.  Must reference a ``kind='show'`` row
            (enforced by trigger ``trg_season_requires_show``).
        number: Season number (0 = specials).
        episode_count: Cached count of episodes in this season.
        has_poster: 1 if a season poster file exists, 0 otherwise.
        episodes_with_nfo: Cached count of episodes with a valid NFO.
    """

    id: int
    item_id: int
    number: int
    episode_count: int
    has_poster: int
    episodes_with_nfo: int


@dataclass(frozen=True, kw_only=True)
class EpisodeRow:
    """Row type for the ``episode`` table.

    Args:
        id: Primary key.
        season_id: FK → ``season.id``.
        number: Episode number within the season (0 = pilot/unnumbered).
        title: Episode title; ``None`` if unknown.
    """

    id: int
    season_id: int
    number: int
    title: str | None


@dataclass(frozen=True, kw_only=True)
class MediaReleaseRow:
    """Row type for the ``media_release`` table.

    Either ``item_id`` or ``episode_id`` is set, never both (CHECK constraint).

    Args:
        id: Primary key.
        item_id: FK → ``media_item.id``; ``None`` for episode releases.
        episode_id: FK → ``episode.id``; ``None`` for item releases.
        quality: Resolution label, e.g. ``'1080p'``, ``'2160p'``.
        edition: Cut label, e.g. ``"Director's Cut"``.
        primary_lang: Primary audio language (BCP-47).
    """

    id: int
    item_id: int | None
    episode_id: int | None
    quality: str | None
    edition: str | None
    primary_lang: str | None


@dataclass(frozen=True, kw_only=True)
class MediaFileRow:
    """Row type for the ``media_file`` table.

    ``release_id`` and ``oshash`` are NULLABLE to support the Stage A/Stage B
    split (§11): Stage A inserts file rows before any release exists or any
    content hash is computed. Both columns are populated by Stage B (``enrich``
    mode) once NFOs are parsed and OSHash is computed for non-symlink files.

    Args:
        id: Primary key.
        release_id: FK → ``media_release.id``; ``None`` during Stage A before release
            linkage is performed by the scraper phase.
        path_id: FK → ``path.id``.
        filename: Bare filename (no directory component).
        size_bytes: File size in bytes.
        mtime_ns: File mtime in nanoseconds (``st_mtime_ns``).
        ctime_ns: File ctime in nanoseconds; ``None`` if not captured.
        oshash: OpenSubtitles hash (16-char hex); ``None`` during Stage A before
            fingerprinting and for symlinks (which are never fingerprinted).
        xxh3_partial: Partial xxh3_64 hash; ``None`` until computed on racy/conflict.
        xxh3_full: Full xxh3_64 hash; ``None`` except on manual repair.
        scan_generation: Scan generation counter when this row was last updated.
        last_verified_at: Unix epoch seconds of last successful verification.
        enriched_at: Unix epoch seconds of last enrichment (mediainfo + NFO + artwork); ``None`` = never.
        miss_strikes: Consecutive scans where this file was not found on disk.
        deleted_at: Unix epoch seconds of soft-delete; ``None`` = not deleted.
    """

    id: int
    release_id: int | None
    path_id: int
    filename: str
    size_bytes: int
    mtime_ns: int
    ctime_ns: int | None
    oshash: str | None
    xxh3_partial: str | None
    xxh3_full: str | None
    scan_generation: int
    last_verified_at: int
    enriched_at: int | None
    miss_strikes: int
    deleted_at: int | None


@dataclass(frozen=True, kw_only=True)
class MediaStreamRow:
    """Row type for the ``media_stream`` table.

    Args:
        id: Primary key.
        file_id: FK → ``media_file.id``.
        idx: Stream index within the file (0-based).
        kind: ``'video'``, ``'audio'``, or ``'subtitle'``.
        codec: Codec name, e.g. ``'h264'``; ``None`` if unknown.
        lang: BCP-47 language code; ``None`` if unknown.
        channels: Audio channel count; ``None`` for non-audio streams.
        width: Video width in pixels; ``None`` for non-video streams.
        height: Video height in pixels; ``None`` for non-video streams.
        duration_ms: Stream duration in milliseconds; ``None`` if unknown.
        bitrate: Stream bitrate in bps; ``None`` if unknown.
    """

    id: int
    file_id: int
    idx: int
    kind: StreamKind
    codec: str | None
    lang: str | None
    channels: int | None
    width: int | None
    height: int | None
    duration_ms: int | None
    bitrate: int | None


@dataclass(frozen=True, kw_only=True)
class ItemIssueRow:
    """Row type for the ``item_issue`` table.

    Args:
        item_id: FK → ``media_item.id`` (part of composite PK).
        type: Issue type string, e.g. ``'junk_files'``, ``'ntfs_unsafe'``.
        detail: Optional free-form detail text.
        detected_at: Unix epoch seconds when the issue was detected.
    """

    item_id: int
    type: str
    detail: str | None
    detected_at: int


@dataclass(frozen=True, kw_only=True)
class IndexOutboxRow:
    """Row type for the ``index_outbox`` table.

    Args:
        id: Primary key.
        source: Originating subsystem: ``'dispatch'``, ``'scraper'``,
            ``'trailers'``, or ``'scanner'``.
        op: Operation type: ``'move'``, ``'nfo_write'``, ``'artwork_write'``,
            or ``'trailer_download'``.
        payload_json: Raw JSON payload (validated by :class:`OutboxPayload`).
        created_at: Unix epoch seconds of event creation.
        processed_at: Unix epoch seconds when drained; ``None`` = pending.
        status: ``'pending'``, ``'done'``, ``'failed'``, or ``'deferred'``.
    """

    id: int
    source: OutboxSource
    op: OutboxOp
    payload_json: str
    created_at: int
    processed_at: int | None
    status: OutboxStatus


@dataclass(frozen=True, kw_only=True)
class PendingOpRow:
    """Row type for the ``pending_op`` table.

    Args:
        id: Primary key.
        disk_id: FK → ``disk.id``.
        op: Operation type string.
        payload_json: Raw JSON payload.
        created_at: Unix epoch seconds of op creation.
        replayed_at: Unix epoch seconds when replayed on remount; ``None`` = not yet replayed.
    """

    id: int
    disk_id: int
    op: str
    payload_json: str
    created_at: int
    replayed_at: int | None


@dataclass(frozen=True, kw_only=True)
class RepairQueueRow:
    """Row type for the ``repair_queue`` table.

    Args:
        id: Primary key.
        scope: Scope of the repair: ``'file'``, ``'item'``, ``'release'``,
            ``'subtree'``, ``'path'``, or ``'disk'``.
        scope_id: Application-managed soft FK, interpretation depends on ``scope``.
        reason: Human-readable reason for the repair.
        payload_json: Optional JSON context (validated by :class:`RepairPayload`).
        enqueued_at: Unix epoch seconds when enqueued.
        status: ``'pending'``, ``'running'``, ``'done'``, or ``'failed'``.
        attempted_at: Unix epoch seconds of last attempt; ``None`` = never attempted.
        attempts: Number of repair attempts made so far.
    """

    id: int
    scope: RepairScope
    scope_id: int | None
    reason: str
    payload_json: str | None
    enqueued_at: int
    status: RepairQueueStatus
    attempted_at: int | None
    attempts: int


@dataclass(frozen=True, kw_only=True)
class ScanRunRow:
    """Row type for the ``scan_run`` table.

    Args:
        id: Primary key.
        generation: Monotonically increasing scan generation number.
        mode: Scan mode: ``'quick'``, ``'incremental'``, ``'enrich'``,
            ``'full'``, ``'verify'``, or ``'repair'``.
        disk_filter: Disk label when scoped to a single disk; ``None`` = all disks.
        started_at: Unix epoch seconds when the scan started.
        finished_at: Unix epoch seconds when the scan finished; ``None`` = still running.
        last_path: Last visited path (for crash-resume); ``None`` if not yet started.
        status: ``'running'``, ``'ok'``, ``'failed'``, or ``'aborted'``.
        stats_json: Raw JSON scan statistics (validated by :class:`ScanStats`).
    """

    id: int
    generation: int
    mode: ScanMode
    disk_filter: str | None
    started_at: int
    finished_at: int | None
    last_path: str | None
    status: ScanStatus
    stats_json: str | None


@dataclass(frozen=True, kw_only=True)
class ScanEventRow:
    """Row type for the ``scan_event`` table.

    Args:
        id: Primary key.
        scan_id: FK → ``scan_run.id``.
        ts: Unix epoch seconds of the event (high-frequency; named ``ts`` per §6.5).
        item_id: FK → ``media_item.id``; ``None`` if event is file-scoped or global.
        file_id: FK → ``media_file.id``; ``None`` if event is item-scoped or global.
        event: Structured event name, e.g. ``'indexer.scan.checkpoint'``.
        payload_json: Free-form JSON payload per event type; ``None`` if empty.
    """

    id: int
    scan_id: int
    ts: int
    item_id: int | None
    file_id: int | None
    event: str
    payload_json: str | None


@dataclass(frozen=True, kw_only=True)
class DeletedItemRow:
    """Row type for the ``deleted_item`` table.

    Args:
        id: Primary key.
        kind: What was deleted: ``'item'``, ``'file'``, or ``'release'``.
        original_id: PK of the deleted row in its original table.
        deleted_at: Unix epoch seconds of deletion.
        reason: Human-readable reason; ``None`` if not provided.
        payload_json: Row snapshot at delete time (validated by :class:`DeletedSnapshot`).
    """

    id: int
    kind: DeletedKind
    original_id: int
    deleted_at: int
    reason: str | None
    payload_json: str | None


@dataclass(frozen=True, kw_only=True)
class SchemaVersionRow:
    """Row type for the ``schema_version`` singleton table.

    Args:
        version: Current schema version integer (mirrors ``PRAGMA user_version``).
    """

    version: int


# ---------------------------------------------------------------------------
# Pydantic models for JSON column validation
# ---------------------------------------------------------------------------


class ArtworkInventory(BaseModel):
    """Validates the ``media_item.artwork_json`` column.

    Tracks which artwork types are present for a media item.

    Args:
        poster: Whether a poster image is available.
        fanart: Whether a fanart/backdrop image is available.
        landscape: Whether a landscape thumbnail is available.
        banner: Whether a banner image is available.
        clearlogo: Whether a clearlogo is available.
        clearart: Whether a clearart is available.
        discart: Whether a discart is available.
        characterart: Whether a characterart is available.
    """

    model_config = ConfigDict(extra="forbid")

    poster: bool = False
    fanart: bool = False
    landscape: bool = False
    banner: bool = False
    clearlogo: bool = False
    clearart: bool = False
    discart: bool = False
    characterart: bool = False


class OutboxPayload(BaseModel):
    """Validates ``index_outbox.payload_json`` and ``pending_op.payload_json``.

    Per DESIGN §9.3, the exact shape varies by ``op``; this model captures
    the common envelope fields and allows additional per-op fields via
    ``extra="allow"`` relaxation.  Full per-op validation is done at the
    outbox drainer level.

    Args:
        op: Operation type matching the parent row's ``op`` column.
        source_path: Source filesystem path involved in the operation; ``None`` if
            the op does not involve a source path.
        dest_path: Destination filesystem path; ``None`` if not applicable.
        item_id: Associated ``media_item.id``; ``None`` if not applicable.
        extra: Additional op-specific fields are allowed.
    """

    model_config = ConfigDict(extra="allow")

    op: str
    source_path: str | None = None
    dest_path: str | None = None
    item_id: int | None = None


class RepairPayload(BaseModel):
    """Validates ``repair_queue.payload_json``.

    Args:
        context: Human-readable description of what triggered the repair.
        discovered_at: Unix epoch seconds when drift was discovered.
        evidence: Free-form key-value evidence dict from the scanner/drift engine.
    """

    model_config = ConfigDict(extra="forbid")

    context: str
    discovered_at: int
    evidence: dict[str, Any] = {}


class ScanStats(BaseModel):
    """Validates ``scan_run.stats_json``.

    Args:
        items_added: Number of new ``media_item`` rows created.
        items_updated: Number of ``media_item`` rows updated.
        items_deleted: Number of items soft-deleted (``deleted_at`` set).
        files_walked: Total number of files visited by the scanner.
        bytes_read: Total bytes read for fingerprinting.
        budget_exhausted: Whether the scan was halted due to budget exhaustion.
    """

    model_config = ConfigDict(extra="forbid")

    items_added: int = 0
    items_updated: int = 0
    items_deleted: int = 0
    files_walked: int = 0
    bytes_read: int = 0
    budget_exhausted: bool = False


class ScanEventPayload(BaseModel):
    """Validates ``scan_event.payload_json``.

    Each event type may carry different keys; this model is intentionally
    permissive (``extra="allow"``) to avoid tight coupling between the
    schema layer and the per-event documentation in ``indexer-json-shapes.md``.

    Args:
        extra: All event-specific fields are allowed through.
    """

    model_config = ConfigDict(extra="allow")


class DeletedSnapshot(BaseModel):
    """Validates ``deleted_item.payload_json``.

    A snapshot of the deleted row's columns at the time of deletion.
    The exact fields depend on whether ``kind`` is ``'item'``, ``'file'``,
    or ``'release'``; this model is permissive to accommodate all three.

    Args:
        kind: What was deleted: ``'item'``, ``'file'``, or ``'release'``.
        snapshot: The full column dict of the deleted row.
    """

    model_config = ConfigDict(extra="allow")

    kind: str
    snapshot: dict[str, Any] = {}
