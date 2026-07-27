"""Single executable definition of "scraped / dispatchable" for a staging item.

This is the ONE place that decides whether a staged media is complete enough to
dispatch, shared by:

* ``scripts/check-media-complete.py`` — the CLI guardrail (product-intent.md §méthode
  rule 6 + the executable garde-fou), and
* ``personalscraper.web.staging.read_model`` — so the web UI "Vérification" state
  reflects the **same** criteria the pipeline ``verify`` step uses to gate dispatch,
  never a looser one. The read-model used to call an item "verified" on a laxer
  signal (an NFO + a poster + *any* video), which let an item show "Vérification :
  Fait" while the pipeline ``verify`` still blocked its dispatch (unrenamed
  video/episodes). That divergence is exactly what §méthode rule 6 forbids.

Definition of complete = the pipeline ``verify`` step (DISPATCH-stage checks,
``dry_run=True``, ``fix=False``) returns status ``valid``/``fixed`` — the real gate
that authorizes dispatch. Since VERIFY-MAINTENANCE-04 the movie video-rename gate
(``Obsession.mkv``, never the raw release name) is itself a registered catalog check
(``movie_video_renamed``), so ``verify`` now enforces it directly — there is no
separate bolt-on layered on top here. ERROR-severity checks block; WARNING-severity
ones (landscape, ``<streamdetails>``) legitimately do not.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.verify.verifier import Verifier


def dispatch_completeness(verifier: Verifier, media_dir: Path, media_kind: str) -> tuple[str, list[str]]:
    """Return ``(status, errors)`` — the single verdict on whether *media_dir* dispatches.

    Runs the real pipeline ``verify`` (via *verifier*, which the caller builds once with
    ``dry_run=True, fix=False`` so this is pure/read-only). ``status`` is
    ``"valid"``/``"fixed"`` when the item is dispatchable and ``"blocked"`` when it is
    not; ``errors`` are the concrete verify messages — empty iff dispatchable. The
    movie video-rename gap surfaces here through the ``movie_video_renamed`` catalog
    check (VERIFY-MAINTENANCE-04), no longer as a separate step.

    Args:
        verifier: A :class:`~personalscraper.verify.verifier.Verifier` built with
            ``dry_run=True, fix=False`` (read-only). One instance is reused across items.
        media_dir: The staged media folder (``Title (Year)`` for movies, show root for TV).
        media_kind: ``"movie"`` or ``"tvshow"``.

    Returns:
        ``(status, errors)``. ``status='blocked'`` whenever *errors* is non-empty; else
        the verifier's own ``valid``/``fixed`` status.
    """
    if media_kind == "movie":
        result = verifier.verify_movie(media_dir)
    else:
        result = verifier.verify_tvshow(media_dir)

    errors: list[str] = list(result.errors or [])
    if result.status not in ("valid", "fixed") and not errors:
        # Blocked with no ERROR-severity message (defensive): surface the status.
        errors.append(f"verify status={result.status}")

    if errors:
        return "blocked", errors
    return result.status, []
