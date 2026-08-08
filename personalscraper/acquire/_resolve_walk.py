"""The grab's resolve WALK — try ranked candidates until one fetches.

Extracted from :mod:`personalscraper.acquire.orchestrator` (module-size
ceiling). It owns ONE decision: which candidate's ``.torrent`` we actually
hold. It does NOT own the failure taxonomy — the orchestrator maps the
returned error onto its dispositions, because that mapping is the grab
contract and belongs with the rest of it.

Why a walk at all (operator report, 2026-08-08): a tracker's download
endpoint served the WRONG payload for the top-ranked release. The D5
info-hash cross-check refused it — correctly — but the failure was
classified transient, so every pass re-picked the same dead candidate while
a healthy sibling sat one rank below. Four identical failures, no
acquisition.

Attribution is the second half of the job. A tracker-wide failure (auth,
open circuit) raised while resolving candidate N belongs to THAT candidate's
tracker: reporting it against the ranked top would send the operator to fix
credentials on a tracker that is working.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from personalscraper.api._contracts import ApiError
from personalscraper.api.tracker._errors import TorrentFetchError
from personalscraper.api.tracker._fetch import resolve_source
from personalscraper.core._contracts import CircuitOpenError
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping

    from personalscraper.api.torrent._base import TorrentSource
    from personalscraper.api.tracker._base import TrackerResult
    from personalscraper.api.transport._http import HttpTransport

log = get_logger("acquire.orchestrator")

#: How many ranked candidates one grab pass may try to FETCH before giving up.
#: A fetch failure is candidate-specific (dead file, wrong payload behind the
#: download URL), so walking a few ranked siblings converts a deterministic
#: dead-end into an acquisition; the bound keeps a rotten pool from hammering
#: the tracker in a single pass.
FETCH_FALLBACK_CANDIDATES = 3


@dataclass(frozen=True)
class ResolveAttempt:
    """What the walk holds when it stops.

    Attributes:
        source: The validated torrent source, or ``None`` when nothing
            resolved.
        chosen: The candidate the caller must report — the one that RESOLVED
            when ``source`` is set, otherwise the one whose failure decided
            (falling back to the ranked top when the pool was empty).
        error: The failure that decided, when ``source`` is ``None``.
    """

    source: TorrentSource | None
    chosen: TrackerResult
    error: Exception | None


def resolve_first_available(
    ranked: list[tuple[TrackerResult, int]],
    transports: Mapping[str, HttpTransport],
    *,
    top: TrackerResult,
    limit: int = FETCH_FALLBACK_CANDIDATES,
) -> ResolveAttempt:
    """Fetch the first ranked candidate whose torrent actually resolves.

    Args:
        ranked: The ranked candidates, best first (``(result, score)``).
        transports: Provider → transport map, read FRESH by the caller.
        top: The ranked top — the candidate reported when the pool is empty.
        limit: How many candidates to try.

    Returns:
        A :class:`ResolveAttempt`. ``source`` set means a torrent is held and
        ``chosen`` is its candidate; ``source`` ``None`` means nothing
        resolved and ``error`` says why, attributed to ``chosen``.
    """
    # A tracker-wide error outranks a plain fetch failure when both happen:
    # « ce tracker refuse mes identifiants » is a bigger truth than « ce
    # fichier est mort », and only the first is worth alerting on.
    culprit: TrackerResult | None = None
    error: Exception | None = None

    for candidate, _score in ranked[:limit]:
        try:
            return ResolveAttempt(
                source=resolve_source(candidate, transports),
                chosen=candidate,
                error=None,
            )
        except TorrentFetchError as exc:
            log.warning(
                "acquire.grab.candidate_fetch_failed",
                provider=candidate.provider,
                title=candidate.title,
                error=str(exc)[:200],
            )
            if error is None:
                culprit, error = candidate, exc
        except (CircuitOpenError, ApiError) as exc:
            # Scoped to THIS candidate's tracker — a sibling served by a
            # healthy tracker must still be tried, and the verdict must name
            # the tracker that actually failed.
            log.warning(
                "acquire.grab.candidate_resolve_failed",
                provider=candidate.provider,
                title=candidate.title,
                error=str(exc)[:200],
            )
            culprit, error = candidate, exc

    return ResolveAttempt(source=None, chosen=culprit if culprit is not None else top, error=error)
