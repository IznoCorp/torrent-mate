"""Per-episode NFO provider-ids checks (DISPATCH stage, TV-only).

Ported verbatim from ``verify/checker.py``:

- ``EpisodeNfo``                       — inline ``episode_nfo`` block.
- ``EpisodeCanonicalUniqueidPresent``  — ``_check_episode_canonical_uniqueid_present``.
- ``EpisodeXrefSecondaryIdPresent``    — ``_check_episode_xref_secondary_id_present``.
- ``EpisodeXrefImdbIdPresent``         — ``_check_episode_xref_imdb_id_present``.

The three provider-ids checks derive ``canonical_family`` from the
``tvshow.nfo`` root (``_canonical_family_from_nfo``); when the show NFO is
absent or unparseable, ``canonical_family`` is None and the canonical /
secondary checks are no-ops (``passed=True``), exactly as ``check_tvshow``.

Helpers (``_parse_nfo``, ``_extract_ids``, ``_canonical_family_from_nfo``,
``_episode_nfo_paths``) are copied verbatim; Phase 3 consolidates the
duplication.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger
from personalscraper.verify.checks.base import CheckResult, CheckStage, Severity
from personalscraper.verify.checks.registry import register_check

if TYPE_CHECKING:
    from pathlib import Path

    from personalscraper.verify.checks.base import CheckContext

log = get_logger("verify.checks.provider_ids")


@register_check
class EpisodeNfo:
    """Spot-check that at least some episodes have NFO files (TV-only)."""

    name = "episode_nfo"
    group = "provider_ids"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"tvshow"})
    default_severity = Severity.WARNING
    description = "At least some episodes should have NFO files"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]`` for the ``episode_nfo`` check.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the ``episode_nfo`` result.
        """
        episode_nfos = list(ctx.media_dir.rglob("S??E??*.nfo"))
        return [
            CheckResult(
                name="episode_nfo",
                passed=len(episode_nfos) > 0,
                severity=Severity.WARNING,
                message="" if episode_nfos else "No episode NFO files found",
            )
        ]


@register_check
class EpisodeCanonicalUniqueidPresent:
    """ERROR: every episode NFO must carry the canonical ``<uniqueid>`` (TV-only)."""

    name = "episode_canonical_uniqueid_present"
    group = "provider_ids"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"tvshow"})
    default_severity = Severity.ERROR
    description = "Every episode NFO must carry the canonical uniqueid"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]``; no-op (``passed=True``) when nothing to inspect.

        Passes silently when no canonical family can be derived from the
        show NFO, or when no episode NFO is on disk yet.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the result.
        """
        show_dir = ctx.media_dir
        canonical_family = _canonical_family(show_dir, ctx)
        if canonical_family is None:
            return [
                CheckResult(
                    name="episode_canonical_uniqueid_present",
                    passed=True,
                    severity=Severity.ERROR,
                    message="",
                )
            ]
        episode_nfos = _episode_nfo_paths(show_dir)
        if not episode_nfos:
            return [
                CheckResult(
                    name="episode_canonical_uniqueid_present",
                    passed=True,
                    severity=Severity.ERROR,
                    message="",
                )
            ]
        missing: list[str] = []
        for nfo_path in episode_nfos:
            root = _parse_nfo(nfo_path)
            if root is None:
                # Unparseable NFO ≡ missing canonical uniqueid for dispatch readiness.
                missing.append(f"{nfo_path.name} (unparseable)")
                continue
            ids = _extract_ids(root)
            if not ids.get(canonical_family):
                missing.append(nfo_path.name)
        return [
            CheckResult(
                name="episode_canonical_uniqueid_present",
                passed=not missing,
                severity=Severity.ERROR,
                message=(
                    f'Missing <uniqueid type="{canonical_family}"> on: {", ".join(missing[:3])}' if missing else ""
                ),
            )
        ]


@register_check
class EpisodeXrefSecondaryIdPresent:
    """WARNING: episodes should carry the non-canonical xref ID (TV-only)."""

    name = "episode_xref_secondary_id_present"
    group = "provider_ids"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"tvshow"})
    default_severity = Severity.WARNING
    description = "Episodes should carry the secondary (xref) uniqueid"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]``; no-op (``passed=True``) when not applicable.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the result.
        """
        show_dir = ctx.media_dir
        canonical_family = _canonical_family(show_dir, ctx)
        if canonical_family not in ("tvdb", "tmdb"):
            return [
                CheckResult(
                    name="episode_xref_secondary_id_present",
                    passed=True,
                    severity=Severity.WARNING,
                    message="",
                )
            ]
        secondary = "tmdb" if canonical_family == "tvdb" else "tvdb"
        episode_nfos = _episode_nfo_paths(show_dir)
        if not episode_nfos:
            return [
                CheckResult(
                    name="episode_xref_secondary_id_present",
                    passed=True,
                    severity=Severity.WARNING,
                    message="",
                )
            ]
        missing: list[str] = []
        for nfo_path in episode_nfos:
            root = _parse_nfo(nfo_path)
            if root is None:
                continue
            ids = _extract_ids(root)
            if not ids.get(secondary):
                missing.append(nfo_path.name)
        return [
            CheckResult(
                name="episode_xref_secondary_id_present",
                passed=not missing,
                severity=Severity.WARNING,
                message=(
                    f'Missing xref <uniqueid type="{secondary}"> on: {", ".join(missing[:3])}; '
                    "consider 'personalscraper indexer backfill-ids'"
                    if missing
                    else ""
                ),
            )
        ]


@register_check
class EpisodeXrefImdbIdPresent:
    """WARNING: episodes should carry an IMDb ``<uniqueid>`` (TV-only)."""

    name = "episode_xref_imdb_id_present"
    group = "provider_ids"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"tvshow"})
    default_severity = Severity.WARNING
    description = "Episodes should carry an IMDb uniqueid"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]``; no-op (``passed=True``) when no episode NFOs.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the result.
        """
        show_dir = ctx.media_dir
        episode_nfos = _episode_nfo_paths(show_dir)
        if not episode_nfos:
            return [
                CheckResult(
                    name="episode_xref_imdb_id_present",
                    passed=True,
                    severity=Severity.WARNING,
                    message="",
                )
            ]
        missing: list[str] = []
        for nfo_path in episode_nfos:
            root = _parse_nfo(nfo_path)
            if root is None:
                continue
            ids = _extract_ids(root)
            if not ids.get("imdb"):
                missing.append(nfo_path.name)
        return [
            CheckResult(
                name="episode_xref_imdb_id_present",
                passed=not missing,
                severity=Severity.WARNING,
                message=(f"Missing IMDb uniqueid on: {', '.join(missing[:3])}" if missing else ""),
            )
        ]


# --- module-level helpers (copied verbatim from checker.py) ---


def _canonical_family(show_dir: "Path", ctx: "CheckContext") -> str | None:
    """Derive the canonical family from ``show_dir/tvshow.nfo``.

    Mirrors ``check_tvshow``: parse the show NFO (None when absent or
    unparseable) and pull the canonical family from it.

    Args:
        show_dir: Path to the TV show directory.
        ctx: Shared check context (for the tvshow_nfo pattern).

    Returns:
        Canonical family string (e.g. ``"tvdb"``), or None.
    """
    nfo_path = show_dir / ctx.patterns.tvshow_nfo
    nfo_root = _parse_nfo(nfo_path) if nfo_path.exists() else None
    return _canonical_family_from_nfo(nfo_root) if nfo_root is not None else None


def _canonical_family_from_nfo(root: ET.Element) -> str | None:
    """Return the ``type`` of the ``<uniqueid default="true">`` row.

    Falls back to the first ``<uniqueid>`` ``type`` when no default flag is
    set (legacy NFOs). None only when the NFO has no ``<uniqueid>`` at all.

    Args:
        root: Parsed show NFO root element.

    Returns:
        Canonical family string, or None.
    """
    default = next((u for u in root.findall("uniqueid") if u.get("default") == "true"), None)
    if default is not None:
        kind = (default.get("type") or "").strip().lower()
        return kind or None
    first = root.find("uniqueid")
    if first is not None:
        kind = (first.get("type") or "").strip().lower()
        return kind or None
    return None


def _episode_nfo_paths(show_dir: "Path") -> "list[Path]":
    """Return every sibling episode NFO under ``show_dir/Saison NN/``.

    Args:
        show_dir: Path to the TV show directory.

    Returns:
        List of episode NFO paths.
    """
    return list(show_dir.rglob("S??E??*.nfo"))


def _parse_nfo(nfo_path: "Path") -> "ET.Element | None":
    """Parse an NFO XML file (copied verbatim from checker.py).

    Args:
        nfo_path: Path to the NFO file.

    Returns:
        Root Element, or None if parse fails.
    """
    try:
        tree = ET.parse(nfo_path)  # noqa: S314
        return tree.getroot()
    except (ET.ParseError, OSError) as exc:
        log.warning("verify_nfo_parse_failed", nfo=nfo_path.name, exc_info=True, error=str(exc))
        return None


def _extract_ids(root: ET.Element) -> dict[str, str]:
    """Extract uniqueid values by type from NFO root (copied from checker.py).

    Args:
        root: Parsed NFO root element.

    Returns:
        Dict mapping type to id value.
    """
    ids: dict[str, str] = {}
    for uid in root.findall("uniqueid"):
        uid_type = uid.get("type", "")
        uid_text = uid.text or ""
        if uid_type and uid_text:
            ids[uid_type] = uid_text
    return ids
