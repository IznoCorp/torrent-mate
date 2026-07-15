"""Provider-ID identity guard for destructive dispatch overwrites (§7).

Constitution §7 (Intégrité des médias): a REPLACE is permitted only after an
identity check by provider-ID — the right film by its ID, not by its name. A
same-named different movie on disk must NEVER be overwritten.

Before the movie-replace path destroys an existing library folder, this module
compares the incoming staging item's provider IDs (from its NFO) against the
target on-disk folder's own NFO IDs. It BLOCKS on a *positive* mismatch — a
provider present on BOTH sides whose IDs differ.

Judgment call (surfaced to the operator): when either side has no verifiable
provider ID (a legacy folder scraped before NFOs, an unscraped staging item),
the check is **fail-open** — it cannot prove the folders are different media,
and failing closed would break every legitimate replace of a legacy no-NFO
folder (e.g. the Obsession / Ferrari legacy items). The absence is logged so it
is visible, not silent (§8). Only a proven ID conflict blocks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from personalscraper.logger import get_logger
from personalscraper.nfo_utils import extract_nfo_metadata, is_nfo_complete

log = get_logger(__name__)

#: Providers compared for identity, in canonical confidence order.
_PROVIDERS: tuple[str, ...] = ("tvdb_id", "tmdb_id", "imdb_id")

#: Human labels for the reason string.
_PROVIDER_LABELS: dict[str, str] = {"tvdb_id": "TVDB", "tmdb_id": "TMDB", "imdb_id": "IMDB"}


def _movie_nfo_ids(movie_dir: Path) -> dict[str, Any] | None:
    """Return the provider IDs from a movie folder's NFO, or ``None``.

    The movie NFO is ``<title>.nfo`` (Kodi convention); the folder may hold
    other ``.nfo`` files, so we read every non-``tvshow.nfo`` NFO and take the
    first COMPLETE one that carries at least one provider ID.

    Args:
        movie_dir: Path to the movie folder.

    Returns:
        A dict with ``tmdb_id`` / ``imdb_id`` / ``tvdb_id`` (any may be
        ``None``) when a valid NFO with at least one ID exists, else ``None``.
    """
    try:
        candidates = sorted(p for p in movie_dir.glob("*.nfo") if p.name.lower() != "tvshow.nfo")
    except OSError:
        return None
    for nfo_path in candidates:
        if not is_nfo_complete(nfo_path):
            continue
        meta = extract_nfo_metadata(nfo_path)
        if any(meta.get(p) for p in _PROVIDERS):
            return meta
    return None


def replace_identity_conflict(staging_dir: Path, target_dir: Path) -> str | None:
    """Return a French reason when a REPLACE would overwrite a DIFFERENT media.

    Compares the staging item's provider IDs against the on-disk target's NFO
    IDs. Returns a reason string ONLY on a positive mismatch (a provider on
    both sides with differing IDs); returns ``None`` (allow) when the folders
    agree on every shared provider, or when either side has no verifiable ID
    (fail-open, logged — see module docstring).

    Args:
        staging_dir: The incoming staging movie folder (source of truth for the
            new media's identity).
        target_dir: The existing library folder the replace would destroy.

    Returns:
        A French block reason, or ``None`` to allow the replace.
    """
    staging_ids = _movie_nfo_ids(staging_dir)
    target_ids = _movie_nfo_ids(target_dir)
    if staging_ids is None or target_ids is None:
        # Cannot verify by ID — do not block a legacy no-NFO replace, but make
        # the unverifiability VISIBLE (§8) rather than silently trusting names.
        log.info(
            "dispatch.replace_identity_unverifiable",
            staging=str(staging_dir),
            target=str(target_dir),
            staging_has_ids=staging_ids is not None,
            target_has_ids=target_ids is not None,
        )
        return None

    for provider in _PROVIDERS:
        s_val = staging_ids.get(provider)
        t_val = target_ids.get(provider)
        if s_val and t_val and str(s_val) != str(t_val):
            label = _PROVIDER_LABELS[provider]
            reason = (
                f"Remplacement bloqué : le dossier cible est un autre média "
                f"({label} {t_val} ≠ {s_val}) — écrasement refusé par sécurité (§7)."
            )
            log.warning(
                "dispatch.replace_identity_conflict",
                staging=str(staging_dir),
                target=str(target_dir),
                provider=provider,
                staging_id=str(s_val),
                target_id=str(t_val),
            )
            return reason
    return None


__all__ = ["replace_identity_conflict"]
