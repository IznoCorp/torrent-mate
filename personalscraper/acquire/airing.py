"""Air-date set-poll service for the acquire lobe (RP9).

Exposes :func:`poll_aired` — a stateless function that, given a set of
followed TV series and a metadata ``ProviderRegistry``, returns the list of
episodes that have already aired (air-date <= today).

Mirrors :mod:`personalscraper.acquire.title_resolver` in structure:
no ``AcquireContext`` handle, no store/indexer import.

Import direction: ``api/metadata`` (downward) + ``acquire.domain`` +
``core.identity`` + stdlib ``datetime``.  Never imports store, indexer,
or any triage package.

Logging: ``personalscraper.logger.get_logger`` (NEVER ``structlog.get_logger``).
"""

from __future__ import annotations

from datetime import date, datetime

from personalscraper.logger import get_logger

log = get_logger("acquire.airing")


# ---------------------------------------------------------------------------
# Predicate helpers (phase 1)
# ---------------------------------------------------------------------------


def _parse_date(air_date: str) -> date | None:
    """Parse an ISO-8601 date string from a provider response.

    Args:
        air_date: Raw ``EpisodeInfo.air_date`` string (``"YYYY-MM-DD"`` or ``""``).

    Returns:
        A :class:`datetime.date` on success, ``None`` on empty string or any
        parse failure.  Never raises.
    """
    if not air_date:
        return None
    try:
        return datetime.strptime(air_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _is_aired(air_date: str, today: date) -> bool:
    """Return True iff *air_date* is a known past-or-today date.

    Implements the DESIGN §5 predicate:
    ``aired ⇔ air_date != "" AND parse_date(air_date) is not None AND parsed <= today``

    The ``<= today`` comparison is **inclusive**: an episode whose air-date is
    exactly today counts as aired (day-boundary ambiguity is acceptable for
    the calendar-trigger; documented in DESIGN §5).

    Args:
        air_date: Raw ``EpisodeInfo.air_date`` string.
        today: The reference date injected by the caller (no hidden ``date.today()``).

    Returns:
        ``True`` when the episode has aired; ``False`` for TBA / future / malformed.
    """
    parsed = _parse_date(air_date)
    return parsed is not None and parsed <= today


# poll_aired will be added in phase 2.
__all__ = ["_is_aired", "_parse_date"]
