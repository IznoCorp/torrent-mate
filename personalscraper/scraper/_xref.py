"""Cross-reference helpers for the TV/movie scrape pipeline (DESIGN §5).

Hosts the free functions that drive the *xref enrichment* and
*external-ids resolution* passes. The TV and movie scrape mixins
expose them as thin methods that simply forward arguments — keeping
the actual logic here lets ``tv_service.py`` stay below the
module-size guardrail (DESIGN §10) without scattering near-duplicate
code between the TV and movie services.

Four responsibilities are bundled here :

- :func:`xref_enrichment` — sequential pass that backfills the non-
  canonical provider's per-episode IDs into the
  ``api_episodes`` payload, never overwriting an existing value
  (DESIGN §3 cross-contamination guard).
- :func:`family_to_client` — map a provider family name to the wired
  client / façade (or ``None``). Shared family→client resolver the TV
  and movie services feed into :func:`resolve_external_ids`.
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
from functools import partial
from pathlib import Path
from typing import Any

from personalscraper.api.metadata._base import Notations
from personalscraper.logger import get_logger

log = get_logger("scraper")


def safe_get_rating(client: Any, provider_id: str) -> list[Notations]:
    """Call ``client.get_rating`` returning ``[]`` on failure or empty payload.

    Raises:
        OmdbQuotaExhausted: Propagated unchanged so the caller can stop
            the rating pass entirely. Swallowing it here would defeat
            the OMDB façade re-raise discipline — every subsequent row
            would burn another HTTP round-trip on a known-dead quota.
    """
    from personalscraper.api.metadata.omdb import OmdbQuotaExhausted  # noqa: PLC0415

    try:
        result = client.get_rating(provider_id)
    except OmdbQuotaExhausted:
        raise
    except Exception as exc:  # noqa: BLE001 — fail-soft per DESIGN §4
        log.warning(
            "xref_get_rating_failed",
            client=type(client).__name__,
            source=getattr(client, "provider_name", "?"),
            provider_id=provider_id,
            error=str(exc),
            error_type=type(exc).__name__,
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


def family_to_client(
    family: str,
    *,
    registry: Any,
    imdb_client: Any | None,
) -> Any | None:
    """Map a provider family name to the wired client / façade (or ``None``).

    Shared body for both the TV and movie scrape services — the single
    family→client resolver that :func:`resolve_external_ids` is fed with
    (ACC-03). Transitional access via the registry (DESIGN §5.2): the
    registry raises ``UnknownProviderError`` for names it does not know ;
    we treat that as ``None`` to preserve the legacy fail-soft contract of
    this helper (xref enrichment and ratings resolution both consume the
    ``None`` branch).

    Args:
        family: Provider family name — e.g. ``"tmdb"``, ``"tvdb"`` or
            ``"imdb"``.
        registry: The provider registry owning the canonical
            ``"tmdb"`` / ``"tvdb"`` providers.
        imdb_client: The optional IMDb façade, or ``None`` when it is not
            wired in the current setup.

    Returns:
        The wired client / façade for ``family``, or ``None`` when the
        family is unknown or its façade is not wired.
    """
    from personalscraper.api.metadata.registry._errors import UnknownProviderError  # noqa: PLC0415

    # ``imdb`` / ``rotten_tomatoes`` remain optional companion façades
    # injected by other call sites ; the registry currently only owns the
    # canonical "tmdb"/"tvdb" providers (Phase 1 scope).
    if family in {"tmdb", "tvdb"}:
        try:
            return registry.get(family)
        except UnknownProviderError as e:
            # If boot validation passed but we reach here, this is a runtime
            # contract violation worth a forensic anchor (the registry's
            # config should already have caught an unwired family).
            log.warning(
                "xref_family_unwired",
                family=family,
                exc_type=type(e).__name__,
            )
            return None
    mapping: dict[str, Any] = {
        "imdb": imdb_client,
    }
    return mapping.get(family)


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

    Raises:
        OmdbQuotaExhausted: Propagated from :meth:`validate_id` or
            :func:`safe_get_rating` when the OMDb daily quota is gone.
            The scrape loop is the right level to disable the IMDb / RT
            façades for the remainder of the run — silently swallowing
            here would waste an HTTP round-trip per remaining family.
    """
    from personalscraper.api.metadata.omdb import OmdbQuotaExhausted  # noqa: PLC0415

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
        except OmdbQuotaExhausted:
            raise
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


def _nonblank_ids(ids: dict[str, str]) -> dict[str, str]:
    """Return ``ids`` with the blank/placeholder values dropped (fail-soft view)."""
    return {family: value for family, value in ids.items() if value}


def _effective_ids(
    ids: dict[str, str],
    canonical_provider: str,
    trusted: dict[str, str],
    fam_to_client: Callable[[str], Any | None],
) -> dict[str, str]:
    """Fold the Q5=B validation result back into the id set the NFO should carry.

    The canonical family is always kept. A non-canonical family is:

    - **kept** when its façade CONFIRMED it (present in ``trusted``);
    - **dropped** when a wired façade was consulted but did not confirm it —
      rejected or errored (DESIGN §5 error table: *id non-écrit*);
    - **kept UNVALIDATED** when no façade is wired for it (``fam_to_client``
      returns ``None`` — the OMDb-absent *skip silencieux* path), so a working
      library's IMDb ids survive when ``OMDB_API_KEY`` is not provisioned.

    Args:
        ids: The original ``{family: provider_id}`` map fed to the pass.
        canonical_provider: The canonical family (never dropped).
        trusted: The confirmed-family map returned by :func:`resolve_external_ids`.
        fam_to_client: The same family→client resolver the pass was driven with;
            consulted (no HTTP) to tell "rejected" apart from "never checked".

    Returns:
        The ``{family: provider_id}`` map to write into the NFO.
    """
    effective: dict[str, str] = {}
    for family, provider_id in ids.items():
        if not provider_id:
            continue
        if family == canonical_provider or family in trusted:
            effective[family] = provider_id
            continue
        # Not confirmed. Drop only when a façade existed to attempt validation
        # (rejected/errored → non-écrit). No wired façade means the id was never
        # checked, so keep it unvalidated rather than silently losing it.
        if fam_to_client(family) is None:
            effective[family] = provider_id
    return effective


def run_external_ids_pass(
    *,
    canonical_provider: str,
    ids: dict[str, str],
    expected_title: str,
    expected_year: int | None,
    registry: Any,
    imdb_client: Any | None,
    rt_client: Any | None,
    base_notation: Notations | None,
) -> tuple[dict[str, str], list[Notations]]:
    """Drive the Q5=B external-ids pass at confirmed-write time (fail-soft).

    Wires :func:`resolve_external_ids` into the movie / TV confirmed-write flows
    (provider-ids DESIGN §5 steps 2-4): re-validate every non-canonical provider
    id and fetch the IMDb / Rotten-Tomatoes ratings, then fold both back into the
    shape the NFO generator consumes. Building the family→client resolver here
    (the ``functools.partial`` P4.2 pattern the tests wire) keeps the two service
    call sites down to one call each.

    Returns ``(effective_ids, notations)``:

    * ``effective_ids`` — the ids the NFO should carry (see :func:`_effective_ids`
      for the keep/drop split that honours Q5=B while staying safe when OMDb is
      not provisioned).
    * ``notations`` — ``base_notation`` (the canonical-provider rating, e.g. the
      TMDb ``vote_average`` row) followed by the resolved IMDb / RT ratings, or
      ``[]`` when the pass produced no external rating (the caller then leaves
      the legacy single-row ``<ratings>`` path untouched — no NFO change).

    Fail-soft (DESIGN §4): an :class:`OmdbQuotaExhausted` — or any unexpected
    error — degrades to "keep every id unvalidated, add no external rating" and
    never propagates, so a rating-provider hiccup can never abort a scrape.

    Args:
        canonical_provider: The match's canonical family (``"tmdb"`` for movies,
            usually ``"tvdb"`` for TV) — never re-validated, never dropped.
        ids: The ``{family: provider_id}`` map extracted from the confirmed match.
        expected_title: Title the façades re-validate the ids against.
        expected_year: Year the façades re-validate the ids against (or ``None``).
        registry: The provider registry owning the canonical providers.
        imdb_client: The wired IMDb façade, or ``None`` when OMDb is absent.
        rt_client: The wired Rotten-Tomatoes façade, or ``None`` when OMDb absent.
        base_notation: The canonical-provider rating to prepend to the NFO's
            ratings block, or ``None`` when the payload carried no rating.

    Returns:
        ``(effective_ids, notations)`` as described above.
    """
    from personalscraper.api.metadata.omdb import OmdbQuotaExhausted  # noqa: PLC0415

    fam_to_client = partial(family_to_client, registry=registry, imdb_client=imdb_client)
    try:
        trusted, ratings = resolve_external_ids(
            canonical_provider,
            ids,
            expected_title,
            expected_year,
            fam_to_client,
            imdb_client,
            rt_client,
        )
    except OmdbQuotaExhausted:
        # Quota gone mid-item — the docstring of resolve_external_ids flags the
        # scrape loop as the right level to stop burning round-trips. Keep every
        # id unvalidated and add no external rating; the scrape carries on.
        log.warning(
            "xref_pass_quota_exhausted_fail_soft",
            canonical=canonical_provider,
            expected_title=expected_title,
        )
        return _nonblank_ids(ids), []
    except Exception as exc:  # noqa: BLE001 — fail-soft: never abort a scrape (DESIGN §4)
        log.warning(
            "xref_pass_failed_fail_soft",
            canonical=canonical_provider,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return _nonblank_ids(ids), []

    effective = _effective_ids(ids, canonical_provider, trusted, fam_to_client)

    notations: list[Notations] = []
    if ratings:
        if base_notation is not None:
            notations.append(base_notation)
        notations.extend(ratings)
    return effective, notations


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
