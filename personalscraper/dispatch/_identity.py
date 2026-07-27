"""Provider-ID identity guard for destructive dispatch overwrites (§7).

Constitution §7 (Intégrité des médias): a REPLACE is permitted only after an
identity check by provider-ID — the right film by its ID, not by its name. A
same-named different movie on disk must NEVER be overwritten.

Before a destructive dispatch overwrites existing library content — a movie
REPLACE that destroys a folder in place, or a TV MERGE that supersedes existing
episodes — this module compares the incoming staging item's provider IDs (from
its NFO) against the target on-disk folder's own NFO IDs. It BLOCKS on a
*positive* mismatch — a provider present on BOTH sides whose IDs differ. The
movie side reads the ``<title>.nfo`` (:func:`replace_identity_conflict`); the TV
side reads the show-root ``tvshow.nfo`` (:func:`merge_identity_conflict`, TVDB
primary). Both share the same comparison and fail-open doctrine.

Judgment call (surfaced to the operator): when either side has no verifiable
provider ID (a legacy folder scraped before NFOs, an unscraped staging item),
the check is **fail-open** — it cannot prove the folders are different media,
and failing closed would break every legitimate replace/merge of a legacy
no-NFO folder (e.g. the Obsession / Ferrari legacy items). The absence is logged
so it is visible, not silent (§8). Only a proven ID conflict blocks.
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


def _tvshow_nfo_ids(show_dir: Path) -> dict[str, Any] | None:
    """Return the provider IDs from a show folder's ``tvshow.nfo``, or ``None``.

    A TV show's identity lives in the Kodi-convention ``tvshow.nfo`` at the show
    folder root (unlike a movie, whose NFO is ``<title>.nfo``). Reads that single
    file and returns its provider IDs when it is a COMPLETE NFO carrying at least
    one provider ID.

    Args:
        show_dir: Path to the show folder.

    Returns:
        A dict with ``tvdb_id`` / ``tmdb_id`` / ``imdb_id`` (any may be
        ``None``) when ``tvshow.nfo`` is valid and carries at least one ID, else
        ``None`` (a legacy show scraped before NFOs, or an unscraped staging
        show).
    """
    nfo_path = show_dir / "tvshow.nfo"
    if not is_nfo_complete(nfo_path):
        return None
    meta = extract_nfo_metadata(nfo_path)
    if any(meta.get(p) for p in _PROVIDERS):
        return meta
    return None


def _first_provider_conflict(staging_ids: dict[str, Any], target_ids: dict[str, Any]) -> tuple[str, str, str] | None:
    """Return the first positive provider-ID mismatch, or ``None`` if none.

    Walks :data:`_PROVIDERS` in canonical confidence order and reports the first
    provider present on BOTH sides whose IDs differ — the single fact that makes
    two same-named folders provably DIFFERENT media. Shared by the movie replace
    and TV merge guards so the comparison stays identical across both paths.

    Args:
        staging_ids: Provider IDs from the incoming staging item's NFO.
        target_ids: Provider IDs from the existing on-disk target's NFO.

    Returns:
        A ``(provider, staging_id, target_id)`` tuple (IDs as strings) for the
        first conflicting provider, or ``None`` when the two agree on every
        shared provider.
    """
    for provider in _PROVIDERS:
        s_val = staging_ids.get(provider)
        t_val = target_ids.get(provider)
        if s_val and t_val and str(s_val) != str(t_val):
            return provider, str(s_val), str(t_val)
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

    conflict = _first_provider_conflict(staging_ids, target_ids)
    if conflict is not None:
        provider, s_val, t_val = conflict
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
            staging_id=s_val,
            target_id=t_val,
        )
        return reason
    return None


def merge_identity_conflict(staging_dir: Path, target_dir: Path) -> str | None:
    """Return a French reason when a MERGE would write into a DIFFERENT show.

    TV counterpart of :func:`replace_identity_conflict`. A merge writes the
    staging show's episodes into an existing on-disk folder resolved by NAME
    (an exact-name hit or a name-based disk-scan fallback), which can match a
    same-named but DIFFERENT series and overwrite its episodes (§7). Compares
    the two shows' ``tvshow.nfo`` provider IDs (TVDB primary, then TMDB, IMDB)
    and returns a reason ONLY on a positive mismatch (a provider on both sides
    with differing IDs); returns ``None`` (allow) when the shows agree on every
    shared provider, or when either side has no verifiable ID (fail-open,
    logged — same doctrine as the movie guard, see module docstring).

    Args:
        staging_dir: The incoming staging show folder (source of truth for the
            new media's identity).
        target_dir: The existing library show folder the merge would write into.

    Returns:
        A French block reason, or ``None`` to allow the merge.
    """
    staging_ids = _tvshow_nfo_ids(staging_dir)
    target_ids = _tvshow_nfo_ids(target_dir)
    if staging_ids is None or target_ids is None:
        # Cannot verify by ID — do not block a legacy no-NFO merge, but make the
        # unverifiability VISIBLE (§8) rather than silently trusting names.
        log.info(
            "dispatch.merge_identity_unverifiable",
            staging=str(staging_dir),
            target=str(target_dir),
            staging_has_ids=staging_ids is not None,
            target_has_ids=target_ids is not None,
        )
        return None

    conflict = _first_provider_conflict(staging_ids, target_ids)
    if conflict is not None:
        provider, s_val, t_val = conflict
        label = _PROVIDER_LABELS[provider]
        reason = (
            f"Fusion bloquée : le dossier cible est une autre série "
            f"({label} {t_val} ≠ {s_val}) — écrasement refusé par sécurité (§7)."
        )
        log.warning(
            "dispatch.merge_identity_conflict",
            staging=str(staging_dir),
            target=str(target_dir),
            provider=provider,
            staging_id=s_val,
            target_id=t_val,
        )
        return reason
    return None


__all__ = ["merge_identity_conflict", "replace_identity_conflict"]
