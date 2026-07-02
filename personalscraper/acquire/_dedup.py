"""Cross-tracker dedup engine + raw search seam (RP5b).

``search_candidates`` is a new ``TrackerRegistry`` method (added in
``api/tracker/_registry.py``) returning a :class:`SearchOutcome` — an
un-ranked, un-deduped result list plus tracker bookkeeping (so the
orchestrator can distinguish "all trackers down" from "clean zero hits").

:func:`dedup` then collapses duplicates in two passes:

1. **info_hash primary key** — exact, mostly within-tracker re-announces.
2. **fuzzy fallback key** — token-set title core + year + resolution tier +
   release group, sub-clustered by size within a ~2 % tolerance window. This
   catches the same release re-packed per tracker (divergent info_hash,
   slightly divergent size) — the load-bearing ``-QTZ`` cross-tracker case.

VF/VOSTFR/VO language markers are PRESERVED in the token-set core (never
dropped) so a VF cut and a VOSTFR cut always produce distinct keys and never
merge — a hard requirement of DESIGN §4.

Layering: ``acquire/`` imports ``api/`` / ``core/`` downward only — never
``sorter`` / ``cleaner`` / ``scraper``. This module imports only
``api.tracker._base`` (TrackerResult), ``acquire.desired`` (Resolution —
stdlib-pure), and stdlib.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from personalscraper.acquire.desired import Resolution
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.logger import get_logger

log = get_logger("acquire.dedup")


# ---------------------------------------------------------------------------
# SearchOutcome — raw seam returned by TrackerRegistry.search_candidates
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class SearchOutcome:
    """Raw result of a multi-tracker search before hard-filter/dedup/ranking.

    Returned by :meth:`TrackerRegistry.search_candidates`. Unlike
    ``search_all`` (which ranks), this carries the un-ranked merged list plus
    enough bookkeeping for the failure taxonomy: an all-errored outcome is
    RETRYABLE (``trackers_unavailable``) whereas a clean zero-hit outcome is
    TERMINAL (``no_candidates``) — see DESIGN §6.2.

    Attributes:
        results: Un-ranked, un-deduped list of every tracker result collected.
        trackers_queried: Number of trackers that were attempted.
        trackers_errored: Number of trackers whose ``search()`` raised.
        errored_names: Names of the trackers that errored (so callers can
            distinguish which trackers succeeded vs failed, not just how many).
        queried_names: Names of the trackers that were actually queried
            (success OR error). A tracker absent from this list was never
            reached — either it is not in the per-media-type priority
            override, or its client was ``None`` at query time. Callers
            use this to avoid recording search history for never-queried
            trackers (which would produce a false 3-day lockout).
    """

    results: list[TrackerResult] = field(default_factory=list)
    trackers_queried: int = 0
    trackers_errored: int = 0
    errored_names: list[str] = field(default_factory=list)
    queried_names: list[str] = field(default_factory=list)

    @property
    def all_errored(self) -> bool:
        """Return ``True`` when every queried tracker errored.

        Distinguishes a transient outage (all trackers down → retry) from a
        clean empty search (zero hits → abandon). ``False`` for an empty
        registry (nothing queried) so an empty config never looks like an
        outage.

        Returns:
            ``True`` iff ``trackers_queried > 0`` and
            ``trackers_queried == trackers_errored``.
        """
        return self.trackers_queried > 0 and self.trackers_queried == self.trackers_errored


# ---------------------------------------------------------------------------
# Token-set title normalizer
# ---------------------------------------------------------------------------

# Format / encoding / container descriptors stripped before building the key.
# These vary freely between repacks of the *same* cut (a tracker may re-tag the
# same file with or without "10bit", "4KLight", "BluRay", …) so they must never
# block a merge. Language markers are deliberately ABSENT from this set — they
# are distinguishing tokens (see ``_LANGUAGE_TOKENS``).
_NOISE_TOKENS: frozenset[str] = frozenset(
    {
        # bit depth
        "10bit",
        "10bits",
        "8bit",
        # "light" encode tags
        "4klight",
        "4khdlight",
        "hdlight",
        # containers / extensions
        "mkv",
        "mp4",
        "avi",
        "iso",
        "bdmv",
        # source / medium descriptors
        "blu",
        "ray",
        "bluray",
        "uhd",
        "web",
        "dl",
        "webrip",
        "webdl",
        "bd",
        "rip",
        "bdrip",
        "hdtv",
        "remux",
        "bonus",
        # edition / repack flags
        "proper",
        "repack",
        "hybrid",
        "custom",
        "complete",
        # HDR / colour descriptors
        "hdr",
        "hdr10plus",
        "dv",
        "dolby",
        "vision",
        # audio channel-count fragments (5.1, 2.0 → "5" "1" "2" "0")
        "5",
        "1",
        "2",
        "0",
    }
)

# Language / audio-track markers — NEVER stripped. A VF cut and a VOSTFR cut
# share every other token yet must stay distinct, so these tokens are the
# discriminator. Kept lowercase to match the tokenizer output.
_LANGUAGE_TOKENS: frozenset[str] = frozenset(
    {
        "multi",
        "vff",
        "vfq",
        "vfi",
        "vf2",
        "vof",
        "vf",
        "truefrench",
        "french",
        "vostfr",
        "vost",
        "vo",
    }
)

# Multi-character token aliases applied (as substring replacements) BEFORE
# tokenizing, so that "he-aac" collapses to "aac" and "hdr10" to "hdr" even
# though the tokenizer would otherwise split / keep them differently. Ordered
# longest-first is not required (no key is a prefix of another's replacement).
_TOKEN_ALIASES: dict[str, str] = {
    "he-aac": "aac",
    "he aac": "aac",
    "heaac": "aac",
    "dts-hd": "dts",
    "dts hd": "dts",
    "ddp": "eac3",
    "dd+": "eac3",
    "hdr10": "hdr",
    "h265": "x265",
    "h264": "x264",
    "hevc": "x265",
    "avc": "x264",
}

# Single-token canonical aliases applied AFTER tokenizing (the token must match
# exactly, not as a substring — e.g. lone "ma" from "DTS-HD.MA" is noise).
_SINGLE_TOKEN_ALIASES: dict[str, str] = {
    "ma": "",  # leftover from "DTS-HD MA"
    "hd": "",  # leftover from "DTS-HD"
}

# Tokenizer: split on dots, spaces, hyphens, underscores, parentheses, brackets.
_TOKEN_RE = re.compile(r"[.\s\-_()\[\]]+")


def normalize_title_core(title: str) -> frozenset[str]:
    """Build an order-independent token-set core from a torrent title.

    Steps:

    1. Lowercase, then apply multi-char :data:`_TOKEN_ALIASES`
       (``he-aac → aac``, ``hdr10 → hdr``, ``hevc → x265`` …).
    2. Tokenize on punctuation / whitespace.
    3. Drop empty tokens and :data:`_NOISE_TOKENS`; apply
       :data:`_SINGLE_TOKEN_ALIASES`.
    4. Return the remaining tokens as a :class:`frozenset` (order-independent,
       hashable — usable directly as a dict-key component).

    Language markers (``vff``, ``vostfr`` …) are intentionally NOT stripped, so
    a VF cut and a VOSTFR cut yield different cores and never merge.

    Args:
        title: Raw torrent title from a :class:`TrackerResult`.

    Returns:
        Order-independent ``frozenset`` of the significant title tokens.
    """
    lowered = title.lower()
    for src, dst in _TOKEN_ALIASES.items():
        lowered = lowered.replace(src, dst)
    tokens = _TOKEN_RE.split(lowered)
    kept: set[str] = set()
    for raw in tokens:
        if not raw or raw in _NOISE_TOKENS:
            continue
        canonical = _SINGLE_TOKEN_ALIASES.get(raw, raw)
        if canonical:
            kept.add(canonical)
    return frozenset(kept)


# ---------------------------------------------------------------------------
# Dedup key computation
# ---------------------------------------------------------------------------

# Size tolerance window: two results whose sizes are within this fraction of
# each other are considered the same cut (padding / .nfo-injection differences).
_SIZE_TOLERANCE = 0.02  # 2 %

# Compiled once: a 4-digit release year (1900–2099) appearing as its own token.
_YEAR_RE = re.compile(r"(?:^|[.\s\-_(])((?:19|20)\d{2})(?:$|[.\s\-_)])")


def _extract_year(title: str) -> int | None:
    """Extract a 4-digit release year (19xx / 20xx) from a title, if present.

    Args:
        title: Raw torrent title.

    Returns:
        The year as an ``int``, or ``None`` when no plausible year token is found.
    """
    match = _YEAR_RE.search(title)
    if match:
        return int(match.group(1))
    return None


def _resolution_tier(result: TrackerResult) -> int:
    """Resolve a result's resolution tier as a numeric :class:`Resolution` ordinal.

    Prefers the structured ``result.resolution`` field; falls back to scanning
    the title for a resolution token when the field is unset. Folds
    ``4k`` / ``uhd`` / ``2160p`` onto a single ordinal (Resolution semantics).

    Args:
        result: The :class:`TrackerResult` to inspect.

    Returns:
        The numeric :class:`Resolution` ordinal (``0`` for UNKNOWN).
    """
    tier = Resolution.from_token(result.resolution)
    if tier is not Resolution.UNKNOWN:
        return int(tier)
    # Fall back to a title scan for a bare resolution token.
    for token in _TOKEN_RE.split(result.title.lower()):
        scanned = Resolution.from_token(token)
        if scanned is not Resolution.UNKNOWN:
            return int(scanned)
    return int(Resolution.UNKNOWN)


def _fuzzy_key(result: TrackerResult) -> tuple[frozenset[str], int | None, int]:
    """Build the size-agnostic fuzzy grouping key for one result.

    The key is ``(title_core, year, resolution_tier)``. Size is deliberately NOT
    part of this key — instead, members sharing a fuzzy key are sub-clustered by
    size within :data:`_SIZE_TOLERANCE` (see :func:`dedup`), so two sizes 1.9 %
    apart never fall on opposite sides of a fixed bucket boundary.

    The release group is intentionally **not** a separate key component: the
    group token already lives inside ``title_core`` (it is neither noise nor a
    language marker), so two releases from different groups already differ in
    their core. Re-extracting it as a standalone field is both redundant and
    fragile — a trailing ``-QTZ`` reads as the group token while a spaced
    ``- QTZ`` does not, which would split otherwise-identical releases. Folding
    it into ``title_core`` sidesteps that mismatch (the real ``-QTZ`` samples
    use both punctuation styles).

    Args:
        result: The :class:`TrackerResult` to key.

    Returns:
        A hashable ``(frozenset_core, year, resolution_ordinal)`` tuple.
    """
    core = normalize_title_core(result.title)
    year = _extract_year(result.title)
    tier = _resolution_tier(result)
    return (core, year, tier)


def _provenance_sort_key(result: TrackerResult) -> tuple[int, int, int]:
    """Deterministic best-provenance ranking key (higher tuple wins).

    Priority order, all max-wins:

    1. freeleech (``is_freeleech``) — free traffic beats anything.
    2. silverleech (``is_silverleech``) — partial-free next.
    3. seeders — more seeders = healthier swarm.

    Tracker priority is applied by the caller via stable ordering of the input
    list (the registry already yields results in tracker-priority order), so a
    fully-tied group keeps the highest-priority tracker's representative.

    Args:
        result: The :class:`TrackerResult` to score.

    Returns:
        A 3-tuple ranked descending by ``max``.
    """
    return (int(result.is_freeleech), int(result.is_silverleech), result.seeders)


def _best_provenance(group: list[TrackerResult]) -> TrackerResult:
    """Pick the best representative from a group of duplicate results.

    Uses :func:`_provenance_sort_key` (freeleech > silverleech > seeders).
    ``max`` is stable on ties — the first element wins — so the input order
    (tracker priority) is the final, deterministic tie-break.

    Args:
        group: Non-empty list of results sharing a dedup key.

    Returns:
        The best-provenance :class:`TrackerResult`.
    """
    return max(group, key=_provenance_sort_key)


def _cluster_by_size(group: list[TrackerResult]) -> list[list[TrackerResult]]:
    """Sub-cluster a fuzzy-key group into size-tolerance clusters.

    Sorts by size ascending, then greedily grows a cluster while each new member
    is within :data:`_SIZE_TOLERANCE` of the cluster's *anchor* (its smallest
    member). A larger gap starts a fresh cluster. This keeps near-identical sizes
    (re-pack padding) together while splitting genuinely different cuts that
    happen to share a title core.

    Args:
        group: Results sharing a fuzzy key (title core + year + tier + group).

    Returns:
        List of size-coherent clusters (each a non-empty list of results).
    """
    ordered = sorted(group, key=lambda r: r.size.bytes)
    clusters: list[list[TrackerResult]] = []
    for result in ordered:
        size = result.size.bytes
        if clusters:
            anchor = clusters[-1][0].size.bytes
            # Within tolerance of the current cluster's anchor → same cut.
            if anchor > 0 and (size - anchor) <= anchor * _SIZE_TOLERANCE:
                clusters[-1].append(result)
                continue
        clusters.append([result])
    return clusters


# ---------------------------------------------------------------------------
# Public dedup entry point
# ---------------------------------------------------------------------------


def dedup(results: list[TrackerResult]) -> list[TrackerResult]:
    """Collapse exact-hash and fuzzy duplicates; return best-provenance survivors.

    **Pass 1 — info_hash primary key.** Results sharing the same non-empty,
    lowercased ``info_hash`` are collapsed to their best-provenance member. This
    reliably folds exact within-tracker re-announces. Cross-tracker re-packs have
    *different* hashes, so they fall through to pass 2 (the whole point of the
    ``-QTZ`` golden).

    **Pass 2 — fuzzy fallback key.** The pass-1 survivors plus all hash-less
    results are grouped by :func:`_fuzzy_key` ``(title_core, year, tier)``, then
    each group is sub-clustered by size within ±2 % (:func:`_cluster_by_size`).
    Each size-cluster collapses to one best-provenance survivor.

    Because the token-set core preserves VF/VOSTFR/VO markers, a VF cut and a
    VOSTFR cut never share a fuzzy key and never merge — even at identical size.

    The output order follows first-seen fuzzy-key order (deterministic).

    Args:
        results: Raw :class:`TrackerResult` list from one or more trackers,
            in tracker-priority order.

    Returns:
        Deduplicated list — one best-provenance representative per detected
        release.
    """
    # --- Pass 1: exact info_hash (primary key) ------------------------------
    hash_groups: dict[str, list[TrackerResult]] = {}
    hash_order: list[str] = []
    no_hash: list[TrackerResult] = []
    for r in results:
        h = (r.info_hash or "").strip().lower()
        if h:
            if h not in hash_groups:
                hash_groups[h] = []
                hash_order.append(h)
            hash_groups[h].append(r)
        else:
            no_hash.append(r)

    pass1: list[TrackerResult] = [_best_provenance(hash_groups[h]) for h in hash_order]

    # --- Pass 2: fuzzy key + size-tolerance sub-clustering ------------------
    fuzzy_pool = pass1 + no_hash
    fuzzy_groups: dict[tuple[frozenset[str], int | None, int], list[TrackerResult]] = {}
    fuzzy_order: list[tuple[frozenset[str], int | None, int]] = []
    for r in fuzzy_pool:
        key = _fuzzy_key(r)
        if key not in fuzzy_groups:
            fuzzy_groups[key] = []
            fuzzy_order.append(key)
        fuzzy_groups[key].append(r)

    survivors: list[TrackerResult] = []
    for key in fuzzy_order:
        for cluster in _cluster_by_size(fuzzy_groups[key]):
            survivors.append(_best_provenance(cluster))

    log.debug(
        "dedup_complete",
        input_count=len(results),
        survivor_count=len(survivors),
    )
    return survivors


__all__ = [
    "SearchOutcome",
    "dedup",
    "normalize_title_core",
]
