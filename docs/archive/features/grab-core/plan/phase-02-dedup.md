# Phase 02 — Cross-Tracker Dedup (`acquire/_dedup.py`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `TrackerRegistry.search_candidates(query, media_type, year) -> SearchOutcome`
raw seam + token-set title normalizer + dedup logic (info_hash primary key, fuzzy fallback) +
best-provenance picker. Golden-tested against the real `-QTZ` cross-tracker pair from the
sample fixtures.

**Architecture:** `acquire/_dedup.py` is layer-neutral (no sorter/scraper imports). It groups
`TrackerResult` objects by a computed string key — never by the mutable object itself.
`TrackerRegistry.search_candidates` is a new method on the existing registry; `search_all`
is untouched.

**Tech Stack:** Python 3.12, `re`, frozen dataclasses, existing `TrackerResult` from
`api/tracker/_base.py`, `MediaType` from `api/_contracts.py`.

---

## Gate (start of phase)

Previous phase produced: `acquire/desired.py` with `Resolution`, `QualityProfile`,
`SourceCriteria` and codec helpers.
Precondition: `api/tracker/_registry.py` (`TrackerRegistry`) and `api/tracker/_base.py`
(`TrackerResult`) exist unchanged.

---

## File Map

- **Create:** `personalscraper/acquire/_dedup.py`
- **Modify:** `personalscraper/api/tracker/_registry.py` — add `search_candidates` + `transports()`
- **Test:** `tests/acquire/test_dedup.py`

---

## Task 1: `SearchOutcome` dataclass + `search_candidates` seam on `TrackerRegistry`

**Files:**

- Create: `personalscraper/acquire/_dedup.py`
- Modify: `personalscraper/api/tracker/_registry.py`
- Test: `tests/acquire/test_dedup.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/acquire/test_dedup.py
"""Non-vacuous tests for the dedup engine and search_candidates seam."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._registry import TrackerRegistry
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api._units import ByteSize


def _make_registry(trackers: dict, priority: list[str]) -> TrackerRegistry:
    ranking = RankingConfig(min_seeders=0, criteria=[], bonuses=MagicMock(freeleech=0, silverleech=0))
    return TrackerRegistry(trackers=trackers, priority=priority, ranking=ranking)


def _make_result(
    provider: str,
    title: str,
    size: int,
    info_hash: str | None = None,
    seeders: int = 10,
    resolution: str | None = None,
) -> TrackerResult:
    return TrackerResult(
        provider=provider,
        tracker_id="t1",
        title=title,
        size=ByteSize(size),
        seeders=seeders,
        leechers=0,
        info_hash=info_hash,
        resolution=resolution,
    )


def test_search_candidates_happy_path() -> None:
    result = _make_result("lacale", "Inception 2010", 1_000_000)
    mock_client = MagicMock()
    mock_client.search.return_value = [result]
    registry = _make_registry({"lacale": mock_client}, ["lacale"])

    outcome = registry.search_candidates("Inception", MediaType.MOVIE, 2010)

    assert isinstance(outcome, SearchOutcome)
    assert len(outcome.results) == 1
    assert outcome.trackers_queried == 1
    assert outcome.trackers_errored == 0


def test_search_candidates_tracker_error_increments_errored() -> None:
    mock_client = MagicMock()
    mock_client.search.side_effect = ApiError(provider="lacale", http_status=500, message="down")
    registry = _make_registry({"lacale": mock_client}, ["lacale"])

    outcome = registry.search_candidates("Inception", MediaType.MOVIE, None)

    assert outcome.trackers_queried == 1
    assert outcome.trackers_errored == 1
    assert outcome.results == []


def test_search_candidates_all_errored_flag() -> None:
    mock_client = MagicMock()
    mock_client.search.side_effect = ApiError(provider="lacale", http_status=503, message="down")
    registry = _make_registry({"lacale": mock_client}, ["lacale"])

    outcome = registry.search_candidates("Inception", MediaType.MOVIE, None)

    assert outcome.all_errored  # queried == errored == 1 > 0
```

- [ ] **Step 2: Run to verify fails**

```bash
cd /Users/izno/dev/PersonnalScaper
python -m pytest tests/acquire/test_dedup.py::test_search_candidates_happy_path -v
```

Expected: `ImportError` or `AttributeError`.

- [ ] **Step 3: Create `_dedup.py` with `SearchOutcome`**

```python
# personalscraper/acquire/_dedup.py
"""Cross-tracker dedup engine + raw search seam (RP5b).

``search_candidates`` is a new ``TrackerRegistry`` method returning a
``SearchOutcome`` (un-ranked list + bookkeeping).  ``dedup`` then collapses
exact-hash and fuzzy-key duplicates, keeping the best-provenance representative.

Layering: ``acquire/`` imports ``api/`` downward only; never sorter/cleaner.

Import direction: api.tracker._base, api._contracts, api._units, stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from personalscraper.api.tracker._base import TrackerResult


# ---------------------------------------------------------------------------
# SearchOutcome — raw seam returned by search_candidates
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class SearchOutcome:
    """Raw result of a multi-tracker search before dedup/ranking.

    Attributes:
        results: Un-ranked, un-deduped list of all tracker results.
        trackers_queried: Number of trackers that were attempted.
        trackers_errored: Number of trackers that raised an error.
    """

    results: list[TrackerResult] = field(default_factory=list)
    trackers_queried: int = 0
    trackers_errored: int = 0

    @property
    def all_errored(self) -> bool:
        """True when every queried tracker errored (all_errored guard).

        Returns:
            ``True`` iff ``trackers_queried > 0`` and
            ``trackers_queried == trackers_errored``.
        """
        return self.trackers_queried > 0 and self.trackers_queried == self.trackers_errored
```

- [ ] **Step 4: Add `search_candidates` + `transports()` to `TrackerRegistry`**

In `personalscraper/api/tracker/_registry.py`, add two methods after `search_all`:

```python
    def search_candidates(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> "SearchOutcome":
        """Search all trackers and return a raw :class:`SearchOutcome`.

        Unlike :meth:`search_all` this method:
        - Returns results un-ranked (no call to ``rank()``).
        - Counts queried/errored trackers for the ``all_errored`` guard.
        - Is consumed by ``GrabOrchestrator`` which applies hard-filters +
          dedup + ranking itself.

        Args:
            query: Search query string.
            media_type: ``MediaType.MOVIE`` or ``MediaType.TV``.
            year: Optional release year.

        Returns:
            A :class:`~personalscraper.acquire._dedup.SearchOutcome` with
            the raw result list and tracker bookkeeping counts.
        """
        from personalscraper.acquire._dedup import SearchOutcome  # noqa: PLC0415

        all_results: list[TrackerResult] = []
        queried = 0
        errored = 0
        for name in self._priority_for(str(media_type)):
            client = self._trackers.get(name)
            if client is None:
                continue
            queried += 1
            try:
                all_results.extend(client.search(query, media_type, year))
            except (
                ApiError,
                requests.RequestException,
                ValueError,
                TypeError,
                xml.parsers.expat.ExpatError,
            ):
                log.warning("tracker_search_failed", tracker=name, exc_info=True)
                errored += 1
        return SearchOutcome(
            results=all_results,
            trackers_queried=queried,
            trackers_errored=errored,
        )

    def transports(self) -> "dict[str, HttpTransport]":
        """Return a map of tracker name → HttpTransport.

        Used by ``GrabOrchestrator`` to pass transports to
        ``resolve_source``.  Only trackers that have a ``_transport``
        attribute are included (all concrete tracker clients do).

        Returns:
            Dict mapping lowercase provider name to its transport.
        """
        result = {}
        for name, client in self._trackers.items():
            transport = getattr(client, "_transport", None)
            if transport is not None:
                result[name] = transport
        return result
```

Add necessary `TYPE_CHECKING` import for `HttpTransport`:

```python
if TYPE_CHECKING:
    from personalscraper.api.transport._http import HttpTransport
```

Also add the missing `import requests` and `import xml.parsers.expat` at the top
(they are already present in `_registry.py` — verify before adding).

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/acquire/test_dedup.py -v
```

Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```bash
git add personalscraper/acquire/_dedup.py personalscraper/api/tracker/_registry.py \
    tests/acquire/test_dedup.py
git commit -m "feat(grab-core): SearchOutcome + search_candidates seam + transports() accessor"
```

---

## Task 2: Token-set title normalizer

**Files:**

- Modify: `personalscraper/acquire/_dedup.py`
- Modify: `tests/acquire/test_dedup.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/acquire/test_dedup.py
from personalscraper.acquire._dedup import normalize_title_core


def test_normalize_strips_noise_tokens() -> None:
    """4klight, hdlight, 10bit, container words are stripped."""
    a = normalize_title_core("Inception.2010.MULTi.VFF.2160p.BluRay.4KLight.HDR.10bit.DTS.5.1.x265-QTZ")
    b = normalize_title_core("Inception (2010) MULTi VFF 2160p 10bit 4KLight HDR BluRay x265 DTS 5.1 - QTZ")
    assert a == b, f"Expected same core, got {a!r} vs {b!r}"


def test_normalize_preserves_vf_vostfr_as_distinct() -> None:
    """VF and VOSTFR must produce different cores."""
    vf = normalize_title_core("Inception.2010.MULTi.VFF.2160p.BluRay.x265-QTZ")
    vostfr = normalize_title_core("Inception.2010.VOSTFR.2160p.BluRay.x265-QTZ")
    assert vf != vostfr


def test_normalize_codec_alias_he_aac_to_aac() -> None:
    """HE-AAC is aliased to AAC for normalization purposes."""
    a = normalize_title_core("Movie.2020.AAC.5.1.x265-GRP")
    b = normalize_title_core("Movie.2020.HE-AAC.5.1.x265-GRP")
    assert a == b


def test_normalize_order_independent() -> None:
    """Token-set comparison: word order differences collapse to same core."""
    a = normalize_title_core("Movie.2020.1080p.BluRay.x264-GRP")
    b = normalize_title_core("Movie BluRay 2020 1080p x264 GRP")
    assert a == b
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/acquire/test_dedup.py::test_normalize_strips_noise_tokens -v
```

Expected: `ImportError`.

- [ ] **Step 3: Add normalizer to `_dedup.py`**

```python
# ---------------------------------------------------------------------------
# Token-set title normalizer
# ---------------------------------------------------------------------------

# Noise tokens stripped before building the dedup key.
# These are format/encoding descriptors that vary between repacks of the
# same cut and must not prevent merging.
_NOISE_TOKENS = frozenset({
    "4klight", "hdlight", "10bit", "8bit", "mkv", "mp4", "avi",
    "blu", "ray", "bluray", "web", "dl", "webrip", "web-dl",
    "h264", "h265", "hevc", "avc", "remux", "proper", "repack",
    "hybrid", "hdr", "hdr10", "dv", "dolby", "vision", "hdr10plus",
    "5", "1", "2", "0",  # channel suffixes (5.1, 2.0, etc.)
    "bd", "rip", "bdrip",
})

# Codec aliases: normalize to a canonical token before building the key.
_CODEC_ALIASES: dict[str, str] = {
    "he-aac": "aac",
    "heaac": "aac",
    "hdr10": "hdr",
    "truehd": "truehd",  # keep distinct (lossless vs lossy)
}

# Tokenizer: split on dots, spaces, hyphens, underscores, parentheses.
_TOKEN_RE = re.compile(r"[.\s\-_()]+")


def normalize_title_core(title: str) -> str:
    """Build an order-independent token-set key from a torrent title.

    Steps:
    1. Lowercase + apply codec aliases (he-aac → aac, hdr10 → hdr).
    2. Tokenize on punctuation/whitespace separators.
    3. Drop noise tokens (container words, bit-depth, etc.).
    4. Sort remaining tokens (order-independent).
    5. VF/VOSTFR/VO markers are NOT stripped — they make distinct cuts.

    Args:
        title: Raw torrent title from a :class:`TrackerResult`.

    Returns:
        Canonical space-joined token string for use as a dedup key component.
    """
    lowered = title.lower()
    # Apply codec aliases before tokenizing (handles multi-char tokens like "he-aac")
    for src, dst in _CODEC_ALIASES.items():
        lowered = lowered.replace(src, dst)
    tokens = _TOKEN_RE.split(lowered)
    kept = sorted(t for t in tokens if t and t not in _NOISE_TOKENS)
    return " ".join(kept)
```

- [ ] **Step 4: Run normalizer tests**

```bash
python -m pytest tests/acquire/test_dedup.py -k "normalize" -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/acquire/_dedup.py tests/acquire/test_dedup.py
git commit -m "feat(grab-core): token-set title normalizer with VF/VOSTFR preservation"
```

---

## Task 3: Dedup keys + `dedup()` + best-provenance pick — load-bearing `-QTZ` golden

**Files:**

- Modify: `personalscraper/acquire/_dedup.py`
- Modify: `tests/acquire/test_dedup.py`

> **LOAD-BEARING TEST:** The `-QTZ` cross-tracker golden is explicitly required by
> DESIGN §11. The test below uses real data from the sample fixtures (sizes verified
> against `docs/reference/_samples/`).

- [ ] **Step 1: Write the golden tests**

```python
# Add to tests/acquire/test_dedup.py
from personalscraper.acquire._dedup import dedup


# Real QTZ cross-tracker pair from docs/reference/_samples/
# lacale: "Inception (2010) MULTi VFF 2160p 10bit 4KLight HDR BluRay x265 DTS 5.1 - QTZ"
#   info_hash=5a3b9563fe21c5a11b8feeb40c2c7f46a1a8b1a6  size=7352098468
# c411:   "Inception.2010.MULTi.VFF.2160p.BluRay.4KLight.HDR.10bit.DTS.5.1.x265-QTZ"
#   info_hash=b08b70d0855318efa71aeccce0ae42b3e4493113  size=7396633907  (diff=0.60%)
_QTZ_LACALE = _make_result(
    "lacale",
    "Inception (2010) MULTi VFF 2160p 10bit 4KLight HDR BluRay x265 DTS 5.1 - QTZ",
    7352098468,
    info_hash="5a3b9563fe21c5a11b8feeb40c2c7f46a1a8b1a6",
    seeders=50,
    resolution="2160p",
)
_QTZ_C411 = _make_result(
    "c411",
    "Inception.2010.MULTi.VFF.2160p.BluRay.4KLight.HDR.10bit.DTS.5.1.x265-QTZ",
    7396633907,
    info_hash="b08b70d0855318efa71aeccce0ae42b3e4493113",
    seeders=141,
    resolution="2160p",
)


def test_dedup_same_info_hash_within_tracker_collapses() -> None:
    """Exact same info_hash on two results → one survivor (within-tracker re-announce)."""
    r1 = _make_result("lacale", "Movie 2020", 1_000_000, info_hash="aaaa")
    r2 = _make_result("lacale", "Movie 2020 repack", 1_000_000, info_hash="aaaa")
    survivors = dedup([r1, r2])
    assert len(survivors) == 1


def test_dedup_qtz_cross_tracker_merges() -> None:
    """LOAD-BEARING: real QTZ pair (divergent hashes, ~0.6% size diff) must merge."""
    survivors = dedup([_QTZ_LACALE, _QTZ_C411])
    assert len(survivors) == 1, (
        f"Expected QTZ cross-tracker pair to merge into 1 survivor, got {len(survivors)}: "
        + str([(r.provider, r.title[:50]) for r in survivors])
    )


def test_dedup_qtz_best_provenance_higher_seeders() -> None:
    """Best-provenance pick: c411 has more seeders → kept."""
    survivors = dedup([_QTZ_LACALE, _QTZ_C411])
    assert len(survivors) == 1
    assert survivors[0].provider == "c411"  # 141 seeders > 50


def test_dedup_different_cut_same_size_stays_distinct() -> None:
    """Two different-cut results that happen to have similar size must NOT merge."""
    # VFF vs VOSTFR: same year/resolution/group but different language = distinct cut
    vff = _make_result(
        "lacale",
        "Inception 2010 MULTi VFF 2160p BluRay x265 QTZ",
        7_000_000_000,
        resolution="2160p",
    )
    vostfr = _make_result(
        "c411",
        "Inception 2010 VOSTFR 2160p BluRay x265 QTZ",
        7_000_000_000,
        resolution="2160p",
    )
    survivors = dedup([vff, vostfr])
    assert len(survivors) == 2, "VFF and VOSTFR must remain distinct"


def test_dedup_no_info_hash_uses_fuzzy_key() -> None:
    """Two results with no info_hash but matching fuzzy key → deduplicated."""
    r1 = _make_result("lacale", "Movie 2020 1080p BluRay x265 GRP", 2_000_000_000)
    r2 = _make_result("c411", "Movie.2020.1080p.BluRay.x265-GRP", 2_010_000_000)  # ~0.5% diff
    survivors = dedup([r1, r2])
    assert len(survivors) == 1
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/acquire/test_dedup.py::test_dedup_qtz_cross_tracker_merges -v
```

Expected: `ImportError` — `dedup` not defined yet.

- [ ] **Step 3: Add dedup key helpers and `dedup()` to `_dedup.py`**

```python
# ---------------------------------------------------------------------------
# Dedup key computation
# ---------------------------------------------------------------------------

# Size tolerance window: two results within this fraction of each other's size
# are considered the same cut (handles padding / .nfo injection differences).
_SIZE_TOLERANCE = 0.02  # 2%


def _resolution_tier(resolution: str | None) -> str:
    """Map a result.resolution token to a canonical tier string.

    Args:
        resolution: Raw resolution token from TrackerResult (e.g. "2160p",
            "4k", "uhd", "1080p", "720p", "480p") or ``None``.

    Returns:
        Canonical tier string: "2160p", "1080p", "720p", "480p", or "unknown".
    """
    if not resolution:
        return "unknown"
    token = resolution.lower()
    if token in ("2160p", "4k", "uhd"):
        return "2160p"
    if token == "1080p":
        return "1080p"
    if token == "720p":
        return "720p"
    if token == "480p":
        return "480p"
    return "unknown"


def _extract_release_group(title: str) -> str:
    """Extract the release group tag (trailing token after last '-').

    Args:
        title: Raw torrent title.

    Returns:
        Lowercase release group token, or empty string if not found.
    """
    # Release group is the last dash-separated token (e.g. "-QTZ", "-NOTAG")
    parts = title.rstrip(")].").rsplit("-", 1)
    if len(parts) == 2:
        candidate = parts[1].strip().lower()
        # Sanity check: a group name is typically short and all-alnum/digits
        if 1 <= len(candidate) <= 20 and re.match(r"[a-z0-9]+", candidate):
            return candidate
    return ""


def _size_bucket(size_bytes: int) -> int:
    """Map a byte size to a 2%-tolerance bucket key.

    Two sizes within 2% of each other map to the same bucket.
    Bucket = floor(size / (size * 0.02)) = floor(1 / 0.02) = 50 buckets per
    doubling. We use integer division by 2% of the reference to group.

    Simple approach: bucket = size // (size // 50 + 1)

    Args:
        size_bytes: File size in bytes.

    Returns:
        Integer bucket identifier.
    """
    # Use 2% granularity: bucket 50 distinct slices per 2x range
    if size_bytes <= 0:
        return 0
    return size_bytes // max(size_bytes // 50, 1)


def _fuzzy_key(result: TrackerResult) -> str:
    """Build the fuzzy dedup key for a result without a usable info_hash.

    Key components (order-independent token core):
    - ``normalize_title_core(result.title)`` — token-set (VF/VOSTFR preserved)
    - ``_resolution_tier(result.resolution)``
    - ``_extract_release_group(result.title)``
    - ``_size_bucket(result.size.bytes)`` — 2% tolerance window

    Args:
        result: The :class:`TrackerResult` to key.

    Returns:
        String key for grouping purposes.
    """
    core = normalize_title_core(result.title)
    tier = _resolution_tier(result.resolution)
    group = _extract_release_group(result.title)
    bucket = _size_bucket(result.size.bytes)
    return f"{core}|{tier}|{group}|{bucket}"


def _best_provenance(group: list[TrackerResult]) -> TrackerResult:
    """Pick the best representative from a group of duplicate results.

    Tie-breaking priority: seeders (highest), then input order (stable sort).

    Args:
        group: Non-empty list of :class:`TrackerResult` that share a dedup key.

    Returns:
        The result with the highest seeder count.
    """
    return max(group, key=lambda r: r.seeders)


# ---------------------------------------------------------------------------
# Public dedup entry point
# ---------------------------------------------------------------------------


def dedup(results: list[TrackerResult]) -> list[TrackerResult]:
    """Collapse exact-hash and fuzzy-key duplicates; return best-provenance list.

    Pass 1 — info_hash primary key:
        Results sharing the same non-empty lowercase ``info_hash`` are grouped;
        the highest-seeder representative survives.  This collapses exact
        within-tracker re-announces reliably.

    Pass 2 — fuzzy fallback key:
        Remaining results (different hashes, or no hash) are keyed by
        ``_fuzzy_key``.  Groups sharing a fuzzy key are collapsed to the
        best-provenance representative.  Cross-tracker re-packs of the same
        release (same title-core + resolution + group + size ±2%) merge here.

    VF/VOSTFR/VO markers are preserved in the token-set core (never stripped),
    so a VFF cut and a VOSTFR cut always produce distinct fuzzy keys.

    Args:
        results: Raw :class:`TrackerResult` list from one or more trackers.

    Returns:
        Deduplicated list; order matches best-provenance input order.
    """
    # Pass 1: group by info_hash (primary key — exact dups only)
    hash_groups: dict[str, list[TrackerResult]] = {}
    no_hash: list[TrackerResult] = []
    for r in results:
        h = (r.info_hash or "").strip().lower()
        if h:
            hash_groups.setdefault(h, []).append(r)
        else:
            no_hash.append(r)

    # Survivors after pass 1
    survivors_pass1: list[TrackerResult] = [_best_provenance(g) for g in hash_groups.values()]

    # Pass 2: fuzzy key on survivors_pass1 + no_hash pool
    fuzzy_pool = survivors_pass1 + no_hash
    fuzzy_groups: dict[str, list[TrackerResult]] = {}
    for r in fuzzy_pool:
        k = _fuzzy_key(r)
        fuzzy_groups.setdefault(k, []).append(r)

    return [_best_provenance(g) for g in fuzzy_groups.values()]


__all__ = [
    "SearchOutcome",
    "dedup",
    "normalize_title_core",
]
```

- [ ] **Step 4: Run all dedup tests**

```bash
python -m pytest tests/acquire/test_dedup.py -v
```

Expected: All 12+ tests PASSED — especially `test_dedup_qtz_cross_tracker_merges` and
`test_dedup_different_cut_same_size_stays_distinct`.

- [ ] **Step 5: Lint + size check**

```bash
python -m ruff check personalscraper/acquire/_dedup.py tests/acquire/test_dedup.py
python -m mypy personalscraper/acquire/_dedup.py
python scripts/check-module-size.py personalscraper/acquire/_dedup.py
```

Expected: zero errors; under 250 LOC.

- [ ] **Step 6: Run full test suite to confirm no regressions**

```bash
python -m pytest tests/ --type py -x -q 2>&1 | tail -10
```

Expected: passing summary, no failures introduced.

- [ ] **Step 7: Commit phase gate**

```bash
git add personalscraper/acquire/_dedup.py personalscraper/api/tracker/_registry.py \
    tests/acquire/test_dedup.py
git commit -m "feat(grab-core): dedup engine + QTZ cross-tracker golden + phase 02 gate"
```

---

## Plan-drift notes (execution, 2026-06-11)

Corrections made versus the verbatim Task pseudocode — each driven by a real bug
the plan code would have shipped, not by preference:

1. **`_size_bucket` was vacuous → replaced by a true tolerance window.** The
   plan's `size // max(size // 50, 1)` returns ~50 for _every_ size > 50, so AAC
   (4.68 GB) and DTS (7.35 GB) landed in the same bucket — size contributed
   nothing. Two sizes 1.9 % apart on opposite sides of any fixed bucket boundary
   would also wrongly split. Replaced with `_cluster_by_size`: group by the
   size-agnostic fuzzy key, then greedily sub-cluster members within ±2 % of the
   cluster anchor. This is what DESIGN §4 actually specifies ("size within a
   tolerance window"). A `test_dedup_size_beyond_tolerance_stays_distinct` pins
   the window as non-vacuous.

2. **`release_group` dropped from the fuzzy key (folded into `title_core`).** The
   plan keyed on `(core, year, tier, group)` with a `-GROUP`-only extractor.
   The real `-QTZ` samples mix `…x265-QTZ` (dashed) and `… 5.1 - QTZ` (spaced),
   so the extractor returned `"qtz"` for one and `""` for the other → false
   split. The group token already lives inside `title_core` (it is neither noise
   nor a language marker), so different groups still differ in the core. Key is
   now `(core, year, tier)`; `_extract_release_group` removed as dead code.

3. **`normalize_title_core` returns a `frozenset`, not a space-joined string.**
   Equivalent for `==` but directly hashable as a dict-key component and a
   clearer contract ("order-independent CORE" per the briefing).

4. **Golden seeders/winners use the REAL sample counts.** The plan's hardcoded
   seeders (lacale DTS = 50) were stale; the fixtures have lacale DTS = 175,
   lacale AAC = 101, c411 AAC = 110, c411 DTS = 141. So the DTS best-provenance
   winner is **lacale** (175 > 141), not c411. Tests assert the real winners.

5. **`transports()` accessor included** (plan Task 1) even though DESIGN §12
   assigns it to phase 4b — it lives in the in-scope `_registry.py`, is a trivial
   isolated accessor, and unblocks the phase-4b composition root early. Guarded
   by `TYPE_CHECKING` + `from __future__ import annotations` (the formatter
   strips a TYPE_CHECKING import unless future-annotations defers the usage).

6. **`RankingConfig` is a Pydantic model** — the plan's `_make_registry`
   `MagicMock(bonuses=…)` fails validation. Replaced with `RankingConfig(min_seeders=0)`
   (defaults suffice; `search_candidates` never ranks).
