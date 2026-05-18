"""Cross-reference helpers for the TV/movie scrape pipeline (DESIGN §5).

Hosts the free functions that drive the *xref enrichment* and
*external-ids resolution* passes. The TV and movie scrape mixins
expose them as thin methods that simply forward arguments — keeping
the actual logic here lets ``tv_service.py`` stay below the
module-size guardrail (DESIGN §10) without scattering near-duplicate
code between the TV and movie services.

Three responsibilities are bundled here :

- :func:`xref_enrichment` — sequential pass that backfills the non-
  canonical provider's per-episode IDs into the
  ``api_episodes`` payload, never overwriting an existing value
  (DESIGN §3 cross-contamination guard).
- :func:`resolve_external_ids` — series / movie level Q5=B
  re-validation : for every non-canonical family, ask the
  corresponding façade's ``validate_id`` ; drop the ID on rejection.
  Bundles the IMDb / Rotten-Tomatoes rating fetch in the same pass.
- :func:`augment_episode_nfo_with_xref` — recovery for NFOs already on
  disk : append xref ``<uniqueid>`` rows without touching the
  existing canonical / xref tags.

All functions are fail-soft. They log and return on the warning path
rather than raising, so a single provider hiccup never aborts the
canonical scrape.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Any

from personalscraper.api.metadata._base import Notations
from personalscraper.logger import get_logger

log = get_logger("scraper")


def safe_get_rating(client: Any, provider_id: str) -> list[Notations]:
    """Call ``client.get_rating`` returning ``[]`` on failure or empty payload."""
    try:
        result = client.get_rating(provider_id)
    except Exception as exc:  # noqa: BLE001 — fail-soft per DESIGN §4
        log.warning(
            "xref_get_rating_failed",
            client=type(client).__name__,
            provider_id=provider_id,
            error=str(exc),
        )
        return []
    if not result:
        return []
    return list(result)


def xref_enrichment(
    api_episodes: dict[tuple[int, int], dict[str, Any]],
    canonical_provider: str,
    tvdb_fetcher: Callable[[int, int], dict[int, dict[str, str]]],
    tmdb_fetcher: Callable[[int, int], dict[int, dict[str, str]]],
    tvdb_id: int | None,
    tmdb_id: int | None,
) -> None:
    """Backfill the non-canonical provider's per-episode IDs in place.

    See :meth:`TvServiceMixin._xref_enrichment` for the full contract ;
    the implementation lives here so the TV service module stays
    below the module-size guardrail.
    """
    if not api_episodes:
        return
    season_nums = sorted({s for s, _ in api_episodes.keys()})

    fetcher: Callable[[int, int], dict[int, dict[str, str]]]
    if canonical_provider == "tvdb":
        if tmdb_id is None:
            return
        fetcher = tmdb_fetcher
        xref_id = tmdb_id
    elif canonical_provider == "tmdb":
        if tvdb_id is None:
            return
        fetcher = tvdb_fetcher
        xref_id = tvdb_id
    else:
        log.warning("xref_unknown_canonical_provider", provider=canonical_provider)
        return

    for s_num in season_nums:
        try:
            xref_episodes = fetcher(xref_id, s_num)
        except Exception as exc:  # noqa: BLE001 — fail-soft contract
            log.warning(
                "xref_enrichment_failed",
                canonical=canonical_provider,
                xref_series_id=xref_id,
                season=s_num,
                error=str(exc),
            )
            continue
        for ep_num, external_ids in xref_episodes.items():
            key = (s_num, ep_num)
            payload = api_episodes.get(key)
            if payload is None:
                continue
            for provider_name, value in external_ids.items():
                if not value:
                    continue
                payload.setdefault(f"{provider_name}_episode_id", value)


def resolve_external_ids(
    canonical_provider: str,
    ids: dict[str, str],
    expected_title: str,
    expected_year: int | None,
    family_to_client: Callable[[str], Any | None],
    imdb_client: Any | None,
    rt_client: Any | None,
) -> tuple[dict[str, str], list[Notations]]:
    """Return ``(trusted_external_ids, ratings)`` after Q5=B re-validation.

    Shared body for both the TV and movie service mixins. The mixin
    methods supply the family→client mapping and the IMDb / RT clients
    (or ``None`` when the façade is not wired in the current setup).
    """
    trusted: dict[str, str] = {}
    ratings: list[Notations] = []

    for family, provider_id in ids.items():
        if not provider_id:
            continue
        if family == canonical_provider:
            trusted[family] = provider_id
            continue
        client = family_to_client(family)
        if client is None:
            log.warning("xref_no_client_for_family", family=family)
            continue
        try:
            accepted = client.validate_id(provider_id, expected_title, expected_year)
        except Exception as exc:  # noqa: BLE001 — fail-soft contract
            log.warning(
                "xref_validate_id_failed",
                family=family,
                provider_id=provider_id,
                error=str(exc),
            )
            continue
        if not accepted:
            log.info(
                "xref_validate_id_rejected",
                family=family,
                provider_id=provider_id,
                expected_title=expected_title,
                expected_year=expected_year,
            )
            continue
        trusted[family] = provider_id

    imdb_id = trusted.get("imdb")
    if imdb_id:
        if imdb_client is not None:
            ratings.extend(safe_get_rating(imdb_client, imdb_id))
        if rt_client is not None:
            ratings.extend(safe_get_rating(rt_client, imdb_id))

    return trusted, ratings


def augment_episode_nfo_with_xref(
    nfo_path: Path,
    info: dict[str, Any],
    *,
    dry_run: bool = False,
) -> None:
    """Append missing xref ``<uniqueid>`` rows to an existing episode NFO.

    Pure side-effecting helper — no return value. Logs and swallows
    parse / OS errors so the caller never sees an exception from a
    recovery step.
    """
    try:
        tree = ET.parse(nfo_path)  # noqa: S314 — trusted NFO we wrote earlier
    except (ET.ParseError, OSError) as exc:
        log.warning("xref_nfo_augment_parse_failed", path=str(nfo_path), error=str(exc))
        return
    root = tree.getroot()
    existing_families = {(u.get("type") or "").strip().lower() for u in root.findall("uniqueid")}

    candidates = {
        "tvdb": info.get("tvdb_episode_id"),
        "tmdb": info.get("tmdb_episode_id"),
        "imdb": info.get("imdb_episode_id"),
    }
    added = False
    for family, value in candidates.items():
        if not value:
            continue
        if family in existing_families:
            continue
        element = ET.SubElement(root, "uniqueid")
        element.set("type", family)
        element.text = str(value)
        added = True

    if not added or dry_run:
        return
    try:
        tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
    except OSError as exc:
        log.warning("xref_nfo_augment_write_failed", path=str(nfo_path), error=str(exc))
