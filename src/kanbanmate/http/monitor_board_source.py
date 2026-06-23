"""Placement source for the Monitoring board overview (keel STEP 2).

The Monitoring tab's ticket PLACEMENT must come from the LOCAL native board store
(``board.json``) — the same source the board VIEW reads (``board_routes._get_store`` →
``FsBoardStateStore.load``) — so a card's column reflects the daemon's auto-advance / an
operator drag within a single tick (<5 ms) instead of waiting on a 15 s-TTL GitHub snapshot
(the historical ~22.5 s placement lag, two-sources-of-truth asymmetry).

GitHub is consulted ONLY for ticket IDENTITY (issue number + title) — values the native store
does not hold — under a SEPARATE, LONGER-TTL identity-only cache (titles change rarely). The
two concerns are deliberately decoupled:

* **Placement freshness must NEVER depend on a GitHub call.** A GitHub outage (or a slow/raising
  identity fetch) degrades only titles/issue numbers — the column + per-card state still render
  from the local store. Once the identity cache is warmed, an outage keeps serving the
  last-known identity rather than dropping cards.

Layering: ``http`` may import ``adapters`` (the native store) — this module fetches; the pure
``app.monitor.build_board`` (signature unchanged) consumes the triples it produces.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

# Identity-only TTL cache (keel STEP 2): item_id → (issue_number, title), keyed by project_id.
# DELIBERATELY longer than the placement read (which is local + un-cached): titles change rarely,
# and a longer TTL means a GitHub blip is invisible to the board. The cache also acts as a
# last-known-good store across a GitHub outage — a raising fetch falls back to whatever is cached.
_IDENTITY_CACHE: dict[str, tuple[float, dict[str, tuple[int | None, str]]]] = {}
# 5 minutes: identity (title) is near-static; placement (local) is always fresh, so a stale title
# for a few minutes is harmless and keeps the board immune to GitHub latency/outages.
_IDENTITY_TTL_SECONDS = 300.0


def _cached_identity(
    project_id: str, fetcher: Callable[[], dict[str, tuple[int | None, str]]]
) -> dict[str, tuple[int | None, str]]:
    """Return the per-project ``item_id → (issue_number, title)`` identity map (TTL-cached).

    On a cache hit within the TTL, returns the cached map WITHOUT calling ``fetcher``. On a miss
    (or expiry), calls ``fetcher`` and stores the result. If ``fetcher`` RAISES, the last cached
    map (even if expired) is returned so a GitHub outage degrades to last-known identity rather
    than wiping titles; with no prior cache, an empty map is returned (placement still renders,
    titles blank).

    Args:
        project_id: The board's Project v2 node id (cache key).
        fetcher: A zero-arg callable returning the fresh identity map (does the GitHub I/O).

    Returns:
        The identity map (possibly stale / empty on a degraded fetch).
    """
    now = time.time()
    hit = _IDENTITY_CACHE.get(project_id)
    if hit is not None and (now - hit[0]) < _IDENTITY_TTL_SECONDS:
        return hit[1]
    try:
        identity = fetcher()
    except Exception:  # noqa: BLE001 — identity is best-effort; placement must never depend on it
        # Degrade to last-known identity (even if past TTL) so an outage keeps titles; else empty.
        return hit[1] if hit is not None else {}
    _IDENTITY_CACHE[project_id] = (now, identity)
    return identity


def native_board_triples(
    project_id: str,
    doc: dict[str, Any],
    identity_fetcher: Callable[[], dict[str, tuple[int | None, str]]],
) -> list[tuple[int, str, str]]:
    """Build the ``(issue_number, title, column_key)`` triples for ``build_board`` from local state.

    PLACEMENT (column_key, ordering) comes from the LOCAL ``board.json`` ``doc`` (``columns`` +
    ``order``) — never from GitHub. IDENTITY (issue_number, title) is JOINed from the TTL-cached
    ``identity_fetcher`` keyed by item_id. A card whose item_id has no known issue number (draft
    item, or first poll before the identity cache warms) is omitted — mirroring the legacy GitHub
    path, which filters ``issue_number is not None``. A known-but-untitled card keeps its number
    with an empty title.

    Args:
        project_id: The board's Project v2 node id (identity cache key).
        doc: The ``FsBoardStateStore.load()`` document (``{columns, order, ...}``).
        identity_fetcher: A zero-arg callable returning ``{item_id: (issue_number, title)}``.

    Returns:
        ``[(issue_number, title, column_key), ...]`` in board (column, index) order.
    """
    identity = _cached_identity(project_id, identity_fetcher)
    triples: list[tuple[int, str, str]] = []
    order = doc.get("order", {})
    for col in doc.get("columns", []):
        for item_id in order.get(col, []):
            issue_number, title = identity.get(item_id, (None, ""))
            # Placement is authoritative; a card with no resolvable issue number can't be keyed in
            # the monitoring view (build_board / the SPA key by number) → omit it (legacy parity).
            if issue_number is None:
                continue
            triples.append((issue_number, title, col))
    return triples
