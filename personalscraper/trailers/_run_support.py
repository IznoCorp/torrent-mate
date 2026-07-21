"""Support types + bookkeeping helpers for :class:`TrailersOrchestrator`.

Holds the pure/stateless pieces extracted from ``orchestrator.py`` during the
P6.5 decomposition of ``TrailersOrchestrator.run``: the per-run configuration
snapshot (:class:`RunContext`), the normalized per-item outcome record
(:class:`TrailerOutcome`), the terminal retry-state builder
(:func:`build_retry_state`), and the two lock-absorbing state-store writers
(:func:`_set_state_for_item` / :func:`_clear_state_for_item`).

Keeping these out of ``orchestrator.py`` holds that module under its size
budget without changing any observable behaviour; the orchestrator re-imports
the two writers so existing ``patch("...orchestrator._set_state_for_item")``
and ``..._clear_state_for_item`` mock targets keep resolving.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from personalscraper.api._contracts import CircuitOpenError
from personalscraper.logger import get_logger
from personalscraper.trailers.state import (
    TrailerState,
    TrailerStateLocked,
    TrailerStateStore,
    TrailerStatus,
    compute_next_retry_at,
)

if TYPE_CHECKING:
    from personalscraper.trailers.discovery.trailer_finder import TrailerFinder

log = get_logger(__name__)


@dataclass(frozen=True)
class RunContext:
    """Immutable snapshot of the config-derived knobs a single ``run()`` uses.

    Built once per run (``TrailersOrchestrator._build_run_context``) so the
    per-item stage helpers read plain typed values instead of re-walking the
    Pydantic config tree on every item.

    Attributes:
        min_size: Minimum trailer file size in bytes for ``trailer_exists``.
        required_free: Free-space floor (bytes) the disk pre-check enforces.
        retry_policy: ``retry_after_days`` schedule for cooldown computation.
        movies_check: Whether the library-aware SOT recheck runs for movies.
        tvshows_check: Whether the library-aware SOT recheck runs for TV shows.
        fallback_yt_search: Whether the same-run YouTube-search fallback fires.
        max_duration_sec: Step-budget ceiling in seconds.
        step_start: ``time.monotonic()`` captured at run start.
    """

    min_size: int
    required_free: float
    retry_policy: list[int]
    movies_check: bool
    tvshows_check: bool
    fallback_yt_search: bool
    max_duration_sec: int
    step_start: float


@dataclass(frozen=True)
class TrailerOutcome:
    """Normalized bookkeeping effect of one per-item branch of ``run()``.

    Collapses the effects every outcome branch repeated inline before the P6.5
    decomposition — the counter increment, the ``item_results`` append, an
    optional ``failed_items`` append, and a state-store write **or** clear —
    into one declarative record applied by
    ``TrailersOrchestrator._record_outcome``.

    Attributes:
        counts_key: The ``counts`` dict key incremented by one.
        item_result: ``(status, reason)`` appended to ``item_results`` (the
            item path is prefixed by the recorder). ``None`` for the two
            branches that append nothing (key error, generic finder error).
        failed_item: ``(ref, kind, notes)`` appended to ``failed_items``, or
            ``None`` for success / skip / already-present outcomes.
        state: A terminal ``TrailerState`` to persist, or ``None``.
        clear_state: When ``True``, clear any prior ledger entry instead of
            writing (mutually exclusive with ``state``; single-truth P6.4).
    """

    counts_key: str
    item_result: tuple[str, str] | None = None
    failed_item: tuple[str, str, str] | None = None
    state: TrailerState | None = None
    clear_state: bool = False


def build_retry_state(
    status: TrailerStatus,
    *,
    media_path: str,
    season_number: int | None,
    retry_policy: list[int],
    youtube_url: str | None = None,
    notes: str | None = None,
) -> TrailerState:
    """Build a terminal ``TrailerState`` with a computed ``next_retry_at`` cooldown.

    Shared by the four failure branches that back off with a retry window
    (finder error / no-trailer / HTTP error / yt-dlp error). ``attempts`` is
    fixed at 1: a same-run fallback re-download must not inflate the count.

    Args:
        status: The terminal ``TrailerStatus`` to persist.
        media_path: Stringified media path recorded on the state.
        season_number: Season number for season-level items, else ``None``.
        retry_policy: ``retry_after_days`` schedule for the cooldown.
        youtube_url: Resolved video URL, when one was found before the failure.
        notes: Free-text failure note (exception text / downloader message).

    Returns:
        A populated ``TrailerState`` whose ``next_retry_at`` cooldown is set.
    """
    now = datetime.now(timezone.utc)
    return TrailerState(
        last_attempt=now.isoformat(),
        attempts=1,
        status=status,
        media_path=media_path,
        next_retry_at=compute_next_retry_at(1, retry_policy, last_attempt=now).isoformat(),
        youtube_url=youtube_url,
        notes=notes,
        season_number=season_number,
    )


def youtube_search_fallback(finder: "TrailerFinder | None", item: Any) -> str | None:
    """Search YouTube for an alternative trailer URL when the first download fails.

    Delegates to ``finder._youtube_search.search(title, year)`` without calling
    ``finder.find()`` — avoids re-hitting the TMDB tier and avoids writing the
    ``__no_result__`` cache sentinel.

    Fail-soft: the broad ``except Exception`` is the real guard — any error
    raised by ``search`` (transport, schema, quota) is logged and turned into a
    clean None (no-fallback). The ``except CircuitOpenError`` branch is kept for
    parity with the finder call site; ``YoutubeSearch.search`` itself consults
    the breaker via ``can_proceed()`` and returns None on a tripped breaker
    rather than raising, so that branch is defensive, not the live path.

    Args:
        finder: The wired ``TrailerFinder`` (or ``None`` when unavailable).
        item: A ``ScanItem``-compatible object with ``title: str`` and
            ``year: int | None`` attributes.

    Returns:
        A YouTube video URL string, or None when the search fails, the circuit
        is open, or ``finder`` is not available.
    """
    if finder is None:
        return None
    try:
        return finder._youtube_search.search(item.title, item.year)
    except CircuitOpenError:
        log.warning("trailers_fallback_circuit_open", title=item.title)
        return None
    except Exception:  # noqa: BLE001
        log.warning("trailers_fallback_search_error", title=item.title, exc_info=True)
        return None


def _set_state_for_item(
    state_store: TrailerStateStore,
    key: str,
    state: TrailerState,
    counts: dict[str, int],
    title: str,
) -> bool:
    """Write a per-item state entry, absorbing ``TrailerStateLocked`` gracefully.

    A lock contention on a single item must not abort the entire orchestrator
    loop — it should log, increment the error counter, and let the loop
    continue to the next item.  The orchestrator-wide ``auto_gc()`` call that
    precedes the loop is deliberately *not* wrapped here (a contended GC is a
    real failure that propagates to ``step.py``).

    Args:
        state_store: The persistent state store to write to.
        key: Composite state key for this media item.
        state: The ``TrailerState`` to persist.
        counts: Running counters dict; ``counts["error"]`` is incremented on
            lock contention.
        title: Human-readable title used in the log event.

    Returns:
        ``True`` if the write succeeded, ``False`` if it was skipped due to
        lock contention (so the caller can skip any post-write work such as
        NFO updates that depend on a successful state write).
    """
    try:
        state_store.set(key, state)
        return True
    except TrailerStateLocked:
        log.warning(
            "trailers_state_locked_for_item",
            key=key,
            title=title,
        )
        counts["error"] += 1
        return False


def _clear_state_for_item(state_store: TrailerStateStore, key: str, title: str) -> None:
    """Best-effort clear of a per-item ledger entry, absorbing ``TrailerStateLocked``.

    Used on the success and already-present outcomes (P6.4 single-truth): the
    state JSON is a download-attempt ledger, never a presence claim, so an
    outcome that leaves a trailer in place records NOTHING and clears any prior
    failure/cooldown entry for the item. A lock contention is logged and
    swallowed — the trailer is already present, so a lingering stale entry is
    harmless and must neither abort the loop nor inflate the error counter.

    Args:
        state_store: The persistent state store to clear from.
        key: Composite state key for this media item.
        title: Human-readable title used in the log event.
    """
    try:
        state_store.clear(key)
    except TrailerStateLocked:
        log.warning(
            "trailers_state_locked_for_item",
            key=key,
            title=title,
        )
