"""Plex match coherence guard — align Plex's match with the pipeline's IDs.

The problem this closes: Plex's modern agents ignore the Kodi NFOs the pipeline
writes, so Plex matches on folder/file names alone — and its fuzzy match has
picked the WRONG entry for films the pipeline had identified exactly (an empty
IMDb stub for « The Gentlemen », a non-existent IMDb id for « On l'appelait
Robin des Bois », both 2026-08-24). Folder and file names are the settled Kodi
canonical contract and are NEVER modified to carry a match hint, so the
correction is applied over the Plex API instead:

- the section listing locates the item's Plex entry by path — movies via
  ``Media/Part.file``, shows via the episode listing (``?type=4``,
  ``grandparentRatingKey``), because a show-level listing carries no path;
- ``GET /library/metadata/{key}`` reads the item's provider ``Guid`` set;
- ``GET …/matches?manual=1&title={tmdb|tvdb}-{id}`` resolves the pipeline's
  canonical id — and only a resolution to EXACTLY ONE candidate is ever acted
  on, never ``candidates[0]`` on faith;
- ``PUT …/match?guid=…`` applies it — no prior ``unmatch`` needed, so a failed
  repair never leaves an item unmatched behind — and the item is re-read after
  the PUT: ``repaired`` is only reported when the canonical guid is there.

Fail-soft is the whole contract: a Plex outage, a read-only token or an item
Plex has not scanned yet must never break anything — the guard is an
operator-upkeep layer (maintenance family), not a dispatch gate. Every Plex
failure degrades to a reported per-item state; nothing raises.

Import direction: maintenance leaf — may import api/ and indexer/, nothing
imports this.
"""

from __future__ import annotations

import sqlite3
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from personalscraper.api.plex import PlexClient, PlexItem
from personalscraper.indexer.external_ids import ExternalIds
from personalscraper.logger import get_logger

log = get_logger("maintenance.plex_guard")

#: Canonical provider per media family, by indexer ``kind``. Movies are
#: identified by TMDB, shows by TVDB — the same authority the scraper's
#: provider resolution settles on. The provider name feeds the
#: ``{provider}-{id}`` match hint.
_PROVIDER_BY_KIND: dict[str, str] = {"movie": "tmdb", "show": "tvdb"}

#: Placeholder series ids the indexer refuses to treat as identity — the same
#: values as ``item_repo._PLACEHOLDER_PROVIDER_IDS``, applied the same way
#: (stripped and lowercased before the comparison).
_PLACEHOLDER_IDS = frozenset({"", "0", "none"})

#: Post-match verification: how many re-reads, how far apart. The live server
#: proved the match is eventual-consistent (first re-read still showed the old
#: guids while Plex had applied the match), so the verification waits a bounded
#: few seconds — bounded, because a guard that hangs on a broken server would
#: be the one thing the fail-soft contract forbids.
_VERIFY_ATTEMPTS = 5
_VERIFY_DELAY = 0.6

#: Finding states — a closed set so the CLI and the JSON output speak one
#: language and the tests can pin the transitions.
STATE_ALIGNED = "aligned"
STATE_MISALIGNED = "misaligned"
STATE_REPAIRED = "repaired"
STATE_REPAIR_FAILED = "repair_failed"
STATE_NOT_FOUND = "not_found"
STATE_NO_IDS = "no_ids"
STATE_PLEX_ERROR = "plex_error"
STATE_NO_CANDIDATE = "no_candidate"
STATE_AMBIGUOUS = "ambiguous"


def _norm_path(path: str) -> str:
    """Fold a path for comparison: NFC + casefold.

    The indexer stores NFC while macFUSE/NTFS directories can surface NFD
    (a documented divergence on these disks), and the same folder can come
    back with different casing after a rename — the repo's own linker joins
    with ``COLLATE NOCASE`` for exactly this reason. The guard compares
    paths the same way: comparing raw strings would report « not found »
    for an item Plex holds under a cosmetically different path.

    Args:
        path: Any absolute path.

    Returns:
        The folded form, for equality/prefix comparison only.
    """
    return unicodedata.normalize("NFC", path).casefold()


def _norm_title(title: str) -> str:
    """Fold a title for comparison: NFC + casefold + punctuation stripped.

    Titles on Plex and in the indexer can differ cosmetically (accents,
    case, apostrophes, punctuation). The guard never matches ON the title —
    the id is the identity — but it compares titles to SURFACE a suspicious
    pair, and that comparison must not cry wolf over cosmetics.

    Args:
        title: A stored or displayed title.

    Returns:
        The folded form.
    """
    folded = unicodedata.normalize("NFC", title).casefold()
    return "".join(ch for ch in folded if ch.isalnum())


@dataclass
class PlexGuardFinding:
    """One item's verdict against Plex.

    Attributes:
        item_id: Indexer ``media_item.id``.
        title: Stored title — logged and reported, never used for matching.
        state: One of the ``STATE_*`` constants.
        canonical_provider: Provider the pipeline identifies the item with
            (``"tmdb"`` / ``"tvdb"``), ``None`` when the item carries no
            usable id.
        canonical_id: The provider id itself, ``None`` when absent.
        rating_key: Plex item id, when Plex could be asked.
        plex_guids: The guids Plex reported for the item (empty when the item
            was not read).
        plex_title: The title Plex displays for the item — surfaced so the
            operator can spot a right-guid/wrong-title entry by eye.
        dispatch_path: The folder the guard looked for, as stored in the
            indexer — surfaced so a ``not_found`` is inspectable.
        title_suspect: True when the item is ALIGNED by guid but Plex's
            displayed title matches neither the stored title nor the original
            title. An informational flag, NOT a repair target: the id is the
            identity, and the repair API could not fix a title that already
            carries the right guid. The operator decides.
    """

    item_id: int
    title: str
    state: str
    canonical_provider: str | None = None
    canonical_id: str | None = None
    rating_key: str | None = None
    plex_guids: list[str] = field(default_factory=list)
    plex_title: str | None = None
    dispatch_path: str | None = None
    title_suspect: bool = False


@dataclass
class PlexGuardResult:
    """Top-level container for ``library_plex_guard.json`` (repair mode only).

    The dry-run writes NOTHING, the report included; a repair run persists the
    result so the operator can re-read what the run changed without trusting
    the console scrollback.

    Attributes:
        checked_at: ISO 8601 timestamp of the run.
        dry_run: Whether repairs were only reported (no ``match`` PUT).
        item_ids: The targeted item ids, or ``None`` for a full sweep.
        aligned_count: Items whose Plex guids already carry the canonical id.
        repaired_count: Items re-matched over the API AND verified after.
        skipped_count: Everything else: no usable ids, not found, Plex error,
            no/ambiguous candidate, repair failed, title mismatch, and — in
            dry-run — the misaligned items themselves (the CLI subtracts them
            for its « would repair » line).
        findings: Per-item verdicts, in indexer order.
    """

    checked_at: str
    dry_run: bool
    item_ids: list[int] | None
    aligned_count: int
    repaired_count: int
    skipped_count: int
    findings: list[PlexGuardFinding] = field(default_factory=list)


@dataclass(frozen=True)
class _Target:
    """One indexer item the guard must check (internal)."""

    item_id: int
    title: str
    kind: str
    dispatch_path: Path
    external_ids_json: str
    original_title: str | None = None


def run_plex_guard(
    *,
    client: PlexClient,
    connection: sqlite3.Connection | None,
    repair: bool,
    item_ids: list[int] | None = None,
    now: str | None = None,
) -> PlexGuardResult:
    """Compare Plex's match against the pipeline's ids, and repair on request.

    The sweep requires the indexer DB (an open ``connection``): both the dispatch
    path and the canonical ids live there, and a filesystem walk cannot
    substitute — a folder name is exactly what must never carry the identity.
    With *item_ids* set, only those items are checked, bypassing no predicate
    (aligned items are checked too — that IS the check).

    Args:
        connection: Open indexer SQLite connection, or ``None`` (empty sweep —
            the CLI validates this before calling).
        client: Plex client whose methods are all fail-soft already.
        repair: When True, a misaligned item with an exact candidate gets the
            ``match`` PUT. When False, it is reported as ``misaligned`` and
            nothing is written.
        item_ids: Target exactly these indexer item ids (``--item-id`` is
            repeatable), or ``None`` for every dispatched item with canonical
            ids.
        now: ISO 8601 timestamp for the report (tests inject a fixed one;
            production passes ``datetime.now(timezone.utc).isoformat()``).

    Returns:
        The aggregated result. Never raises: a Plex failure is a per-item
        ``plex_error`` finding, not an exception.
    """
    targets = _collect_targets(connection, item_ids)

    # The path index is shared across the sweep: each section is listed once
    # (movies by their part paths, shows by their episode paths), and the
    # listing does not change between items of the same run.
    path_index: dict[str, PlexItem] = {}
    failed_sections: set[str] = set()
    listed_sections: set[str] = set()

    result = PlexGuardResult(
        checked_at=now or "unknown",
        dry_run=not repair,
        item_ids=item_ids,
        aligned_count=0,
        repaired_count=0,
        skipped_count=0,
    )

    for target in targets:
        finding = _check_target(client, target, path_index, failed_sections, listed_sections, repair)
        result.findings.append(finding)
        if finding.state == STATE_ALIGNED:
            result.aligned_count += 1
        elif finding.state == STATE_REPAIRED:
            result.repaired_count += 1
        else:
            result.skipped_count += 1

    log.info(
        "plex_guard_done",
        checked=len(result.findings),
        aligned=result.aligned_count,
        repaired=result.repaired_count,
        skipped=result.skipped_count,
        dry_run=result.dry_run,
    )
    return result


def _collect_targets(connection: sqlite3.Connection | None, item_ids: list[int] | None) -> list[_Target]:
    """Build the guard's target list from the indexer DB.

    Both paths require the DB — the CLI exits before calling when it is not
    openable. A target without a dispatch path is dropped here and reported
    nowhere: there is nothing Plex could be asked about it, and it must not
    inflate the skipped count as if a check had been attempted.

    Args:
        connection: Open indexer connection (``None`` yields an empty sweep).
        item_ids: Item fast-path, mirroring ``library-rescrape``'s ``--item-id``
            but repeatable — ``None`` means the full dispatched sweep.

    Returns:
        The targets to check, in indexer order (insertion order — the
        repository's listing query has no explicit ORDER BY).
    """
    if connection is None:
        return []
    from personalscraper.indexer.repos import item_repo as _item_repo  # noqa: PLC0415

    targets: list[_Target] = []
    if item_ids is not None:
        for item_id in item_ids:
            item = _item_repo.get_by_id(connection, item_id)
            if item is None:
                log.warning("plex_guard_item_id_not_found", item_id=item_id)
                continue
            path_attribute = _item_repo.get_attr(connection, item_id, _item_repo._ATTR_DISPATCH_PATH)
            if path_attribute is None or not path_attribute.value:
                log.warning("plex_guard_item_id_no_dispatch_path", item_id=item_id, title=item.title)
                continue
            targets.append(
                _Target(
                    item_id=item.id,
                    title=item.title,
                    kind=item.kind,
                    dispatch_path=Path(path_attribute.value),
                    external_ids_json=item.external_ids_json or "",
                )
            )
        return targets

    for row_item, _dispatch_disk, dispatch_path in _item_repo.list_all_dispatch_items(connection):
        targets.append(
            _Target(
                item_id=row_item.id,
                title=row_item.title,
                kind=row_item.kind,
                dispatch_path=Path(dispatch_path),
                external_ids_json=row_item.external_ids_json or "",
                original_title=row_item.original_title,
            )
        )
    return targets


def _canonical_ids(target: _Target) -> tuple[str, str] | None:
    """Extract the item's canonical (provider, id) pair.

    The provider is fixed by media family (:data:`_PROVIDER_BY_KIND`); the id
    is the series-level id of that family in ``external_ids_json``. A missing,
    placeholder or non-string id means « no identity » — the guard must not
    invent a hint out of it, so it returns ``None`` and the item is skipped.

    Args:
        target: The indexer item to read.

    Returns:
        ``(provider, id)``, or ``None`` when the item carries no usable id.
    """
    provider = _PROVIDER_BY_KIND.get(target.kind)
    if provider is None:
        # Not a movie or a show — the guard's scope is the two matchable
        # families; anything else is deliberately not checked.
        return None
    try:
        ids = ExternalIds.model_validate_json(target.external_ids_json)
    except Exception as exc:  # noqa: BLE001 — a broken payload skips the item, never the run
        log.warning(
            "plex_guard_external_ids_unparseable",
            item_id=target.item_id,
            title=target.title,
            error=type(exc).__name__,
        )
        return None
    raw_id = getattr(getattr(ids, provider), "series_id")
    if not isinstance(raw_id, str) or raw_id.strip().lower() in _PLACEHOLDER_IDS:
        return None
    return provider, raw_id.strip()


def _plex_item_for(
    target: _Target,
    client: PlexClient,
    path_index: dict[str, PlexItem],
    failed_sections: set[str],
    listed_sections: set[str],
) -> PlexItem | None:
    """Resolve the target's folder to its Plex item, by path.

    The dispatched folder is a directory; the join is a prefix test on a path
    boundary (same discipline as ``PlexClient.section_for`` — ``/medias`` must
    never match ``/medias-old``), and BOTH sides are NFC-casefolded before the
    comparison: the indexer stores NFC while these disks can surface NFD, and
    casing can drift after a rename. The section is resolved by the SAME
    method the refresh trigger uses (longest Location prefix), so the guard
    and the refresh can never disagree about which library a folder belongs
    to.

    The index is shared across the sweep and covers BOTH families: movies join
    by their ``Part.file`` paths from the plain listing; shows join by their
    episode paths from the ``?type=4`` listing (their own listing carries no
    path at all — verified live). A failed listing is remembered in
    *failed_sections* so a broken section is not re-queried once per item.

    Args:
        target: The indexer item to locate in Plex.
        client: Plex client (``sections`` is cached by the client itself).
        path_index: Mutable sweep-level ``folded path → PlexItem`` map, filled
            once per section.
        failed_sections: Mutable sweep-level set of section keys whose listing
            came back empty — the signal that re-asking is a waste.
        listed_sections: Mutable sweep-level set of section keys whose listing
            succeeded (their items already live in *path_index*).

    Returns:
        The Plex item, or ``None`` when Plex does not know the folder (the
        caller decides whether that is ``not_found`` or ``plex_error`` by
        looking at *failed_sections* and the target's own section).
    """
    wanted = str(target.dispatch_path)
    if not wanted:
        return None
    wanted_norm = _norm_path(wanted)

    section = client.section_for(target.dispatch_path)
    if section is None:
        return None
    if section.key not in listed_sections and section.key not in failed_sections:
        items = client.section_show_items(section) if target.kind == "show" else client.section_items(section)
        for item in items:
            for path in [*item.files, *item.locations]:
                path_index.setdefault(_norm_path(path), item)
        if not items:
            # An empty listing is the fail-soft shape of every failure
            # (unreachable, 401, unparseable): remember it so the same
            # broken section is not re-queried for every item it hosts.
            failed_sections.add(section.key)
        else:
            listed_sections.add(section.key)
    for folded_path, item in path_index.items():
        if folded_path == wanted_norm or folded_path.startswith(f"{wanted_norm}/"):
            return item
    return None


def _check_target(
    client: PlexClient,
    target: _Target,
    path_index: dict[str, PlexItem],
    failed_sections: set[str],
    listed_sections: set[str],
    repair: bool,
) -> PlexGuardFinding:
    """Produce one item's verdict.

    Order matters: ids first (nothing to compare without them), then the
    Plex item (nothing to compare against), then the comparison. The
    ``plex_error`` state is reserved for « Plex could not be asked » — the
    target's OWN section could not be listed (or the sections call itself
    failed) — while ``not_found`` means « Plex answered, and it does not know
    this folder yet ». One section failing must never paint items of a healthy
    section with the same brush.

    Args:
        client: Plex client.
        target: The indexer item under check.
        path_index: Sweep-level path index (see :func:`_plex_item_for`).
        failed_sections: Sweep-level set of sections whose listing failed —
            re-listing them per item would multiply requests against a broken
            server for the same empty answer.
        listed_sections: Sweep-level set of sections whose listing succeeded
            (their items already live in *path_index*).
        repair: Whether a misaligned item may be re-matched.

    Returns:
        The finding. Never raises.
    """
    base = PlexGuardFinding(
        item_id=target.item_id,
        title=target.title,
        state=STATE_PLEX_ERROR,
        dispatch_path=str(target.dispatch_path) if target.dispatch_path else None,
    )
    ids = _canonical_ids(target)
    if ids is None:
        base.state = STATE_NO_IDS
        return base
    provider, canonical_id = ids
    base.canonical_provider = provider
    base.canonical_id = canonical_id

    item = _plex_item_for(target, client, path_index, failed_sections, listed_sections)
    if item is None:
        # Only the target's OWN section failing (or the sections call itself)
        # is « Plex could not be asked ». A healthy answer that does not know
        # the folder is not_found.
        section = client.section_for(target.dispatch_path)
        if not client.sections() or (section is not None and section.key in failed_sections):
            return base
        base.state = STATE_NOT_FOUND
        return base
    base.rating_key = item.rating_key

    # The path index entry may come from a LISTING (movies), which carries the
    # rating_key but never the provider guids — the item endpoint is the only
    # place they live. An index entry WITH guids (shows, read at listing time)
    # skips the re-read; otherwise this is step 2 of the design: locate, then
    # read.
    full_item = item if item.guids else client.item(item.rating_key)
    if full_item is None:
        return base
    base.plex_guids = full_item.guids
    base.plex_title = full_item.title or None

    expected_guid = f"{provider}://{canonical_id}"
    guid_aligned = any(guid == expected_guid for guid in full_item.guids)
    # A right guid on a wrong display title is a real phenomenon (a live item
    # carries the correct guid triple while displaying another entry's title).
    # The id IS the identity, so the item is aligned — but the operator must
    # see the pair. The flag compares against BOTH the stored title and the
    # original title, so Plex's own French localisations (« Frères d'armes »
    # for Band of Brothers) do not read as suspicious.
    if guid_aligned:
        base.state = STATE_ALIGNED
        if full_item.title and _norm_title(full_item.title):
            stored = {_norm_title(target.title)}
            if target.original_title:
                stored.add(_norm_title(target.original_title))
            if _norm_title(full_item.title) not in stored:
                base.title_suspect = True
        return base

    # Misaligned: resolve the canonical id to Plex's own candidate. Dry-run
    # reports; repair applies — and only an EXACT resolution (exactly ONE
    # candidate) is ever acted on, because applying the first of several
    # would be guessing, the failure class this guard exists to prevent.
    matches_ok, candidates = client.matches(item.rating_key, f"{provider}-{canonical_id}")
    if not matches_ok:
        return base
    if len(candidates) != 1:
        base.state = STATE_AMBIGUOUS if len(candidates) > 1 else STATE_NO_CANDIDATE
        return base
    candidate = candidates[0]
    if not repair:
        base.state = STATE_MISALIGNED
        return base
    if not client.match(item.rating_key, candidate):
        return base
    # The PUT was accepted — but « repaired » is claimed only after the item
    # is re-read and the canonical guid is really there. A match that does
    # not take is reported repair_failed, never green.
    #
    # The re-read is RETRIED, because the live server proved the match is
    # eventual-consistent: the first re-read right after the PUT still showed
    # the pre-match guids (19/19 items reported repair_failed while Plex had
    # applied every one of them). A single instant re-read measures the race,
    # not the outcome.
    for _attempt in range(_VERIFY_ATTEMPTS):
        verify = client.item(item.rating_key)
        if verify is not None and any(guid == expected_guid for guid in verify.guids):
            base.state = STATE_REPAIRED
            return base
        if _attempt < _VERIFY_ATTEMPTS - 1:
            time.sleep(_VERIFY_DELAY)
    base.state = STATE_REPAIR_FAILED
    return base
