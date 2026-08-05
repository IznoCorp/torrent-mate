# Phase 3 — Escalate episode→season on search-failure evidence (D1)

**Defect.** Two escalation paths exist; neither reads search failure.

- DETECT (`detect.py:468-506`) gates on calendar + ownership only. Gate (c) `owned <= total/2`
  is anti-correlated with need: American Dad! S15 (20/22), S17 (22/24) and Widow's Bay S1 (9/10)
  were all blocked by it; Batman: Caped Crusader S2 by gate (b) `last_air >= 7 days`.
- SEARCH R2 (`_search_pass.py:139-146`) is armed only on `no_matching_episode`, which requires
  the episode-scoped query to have returned raw results. When it returns **zero**, the
  orchestrator exits earlier on `no_candidates` and R2 is unreachable.

Live proof: `American Dad! S15E21` → `raw=0` → `no_candidates` → R2 cannot fire, 17 attempts over
20 days. The season query `American Dad! S15` returns 4 covering packs, top 65 seeders.

**Files:**
- Modify: `personalscraper/acquire/_search_pass.py` (`_search_item`,
  `_enqueue_season_from_conversion`, two new helpers)
- Modify: `personalscraper/acquire/service.py:409` (pass the per-pass memo)
- Modify: `personalscraper/acquire/events.py` (new event)
- Test: `tests/acquire/test_starvation_escalation.py` (create)

**Interfaces:**
- Consumes: from phase 2, `attempts` no longer counts partial-outage searches.
- Produces: `SeasonEscalatedAfterEpisodeFailures` event;
  `_season_fully_aired(followed_id, season, today) -> bool`;
  `_probe_season_pack(episode_item, profile) -> bool`;
  `_search_item(..., *, cadence, season_probed: set[tuple[int, int]])`.

## Frozen threshold

`attempts >= 2` — **2 concluded searches** (operator decision A2). Phase 2 is what makes this
honest for the dominant partial-outage case.

---

- [ ] **Step 1: Add the event (no behaviour yet)**

In `personalscraper/acquire/events.py`, after `SeasonAbsorbedEpisodes`:

```python
@dataclass(frozen=True)
class SeasonEscalatedAfterEpisodeFailures(Event):
    """A season pack was enqueued because the per-episode route provably failed.

    Distinct from :class:`SeasonAbsorbedEpisodes`, which says WHAT happened but not
    WHY. The operator UI needs the reason to state, in plain French, that the
    episodes do not exist separately and the whole-season pack is being taken
    instead (product-intent §2 — every state carries a clear label).

    Attributes:
        season_wanted_id: Rowid of the season ``wanted`` row that now carries the work.
        media_ref: Provider identity of the series.
        season: Season number that was escalated.
        trigger_outcome: The episode verdict that armed the escalation —
            ``'no_candidates'`` or ``'no_matching_episode'``.
        starved_episode_ids: Rowids of the episode rows whose repeated failure
            motivated the escalation.
    """

    season_wanted_id: int
    media_ref: MediaRef
    season: int
    trigger_outcome: str
    starved_episode_ids: tuple[int, ...]
```

Export it in the module's `__all__` and in `personalscraper/events/__init__.py` alongside the
other acquire events.

- [ ] **Step 2: Write the failing tests**

Create `tests/acquire/test_starvation_escalation.py`:

```python
"""An episode the trackers do not carry separately must escalate to the season pack (D1).

Regression for American Dad! S15E21: the episode query returned 0 results (so R2, armed on
``no_matching_episode``, could never fire), the DETECT gate ``owned <= total/2`` blocked the
calendar path at 20/22 owned, and the row was re-searched 17 times over 20 days while a
4-pack, 65-seeder season release sat on the trackers.
"""

from __future__ import annotations

from personalscraper.acquire.events import SeasonEscalatedAfterEpisodeFailures


class TestEscalatesOnConcludedFailures:
    """The trigger is EVIDENCE of failure, not the calendar."""

    def test_no_candidates_at_threshold_enqueues_the_season(self, service, store, bus_events):
        """2 concluded failures + fully aired season + covering pack ⇒ season enqueued."""
        # episode row with attempts == 2, season fully aired, season probe returns a pack
        ...
        season_row = store.wanted.find(
            followed_id=FOLLOWED_ID, kind="season", season=15, episode=None,
        )
        assert season_row is not None, "the season pack must be enqueued"
        assert season_row.status == "pending"
        assert store.wanted.get(EPISODE_ID).status == "absorbed"
        assert any(isinstance(e, SeasonEscalatedAfterEpisodeFailures) for e in bus_events)

    def test_below_threshold_does_not_escalate_and_makes_no_extra_tracker_call(
        self, service, store, tracker_calls,
    ):
        """attempts == 1 ⇒ no escalation AND no season probe (cost guard)."""
        ...
        assert store.wanted.find(followed_id=FOLLOWED_ID, kind="season", season=15) is None
        assert not any(c.is_season_query for c in tracker_calls)

    def test_season_not_fully_aired_does_not_escalate(self, service, store):
        """A future episode means no season pack can cover it — do not probe."""
        ...
        assert store.wanted.find(followed_id=FOLLOWED_ID, kind="season", season=3) is None

    def test_probe_without_covering_pack_leaves_the_episode_live(self, service, store):
        """No covering pack ⇒ the episode keeps its own verdict and stays queued."""
        ...
        row = store.wanted.get(EPISODE_ID)
        assert row.status == "pending"
        assert row.last_search_outcome == "no_candidates"

    def test_no_matching_episode_also_arms_the_escalation(self, service, store):
        """Both concluded not_found shapes trigger it, not just the empty one."""
        ...
        assert store.wanted.find(followed_id=FOLLOWED_ID, kind="season", season=15) is not None


class TestProbeIsBounded:
    """One probe per (follow, season) per pass — ten starved episodes are not ten queries."""

    def test_two_starved_episodes_same_season_probe_once(self, service, tracker_calls):
        """The per-pass memo collapses siblings onto a single season query."""
        ...
        season_queries = [c for c in tracker_calls if c.is_season_query]
        assert len(season_queries) == 1, f"expected 1 season probe, got {len(season_queries)}"


class TestRegressionAmericanDadS15E21:
    """The exact live shape that motivated this feature."""

    def test_episode_query_empty_season_query_has_packs_escalates(self, service, store):
        """Episode query 0 results, season query 4 covering packs ⇒ escalation."""
        ...
```

Fill each `...` with the harness already used by the existing season-conversion tests — look for
the R2 conversion tests under `tests/acquire/` and reuse their fixtures. `tracker_calls` must be
a recording double over the tracker registry so the cost assertions are real.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `command python -m pytest tests/acquire/test_starvation_escalation.py -v`
Expected: FAIL — no escalation happens on `no_candidates`; the event does not reach the bus.

- [ ] **Step 4: Add the "fully aired" helper**

In `_search_pass.py`, next to `_aired_episodes_for_season`:

```python
    def _season_fully_aired(self, followed_id: int, season: int, today: date) -> bool:
        """Return True when every catalogued episode of the season has aired.

        A season with a future episode cannot be covered by a complete pack, so
        probing for one would be wasted and could grab a partial release. Mirrors
        DETECT gate (a), deliberately WITHOUT its calendar quarantine and ownership
        gates — this path is armed by proven search failure, not by the calendar.

        An empty catalog answers False: unknown coverage is never treated as
        complete (the same conservative reading ``filter_to_season`` applies).

        Args:
            followed_id: FK to the ``followed_series`` row.
            season: Season number to test.
            today: Reference date (injected — no hidden clock).

        Returns:
            True iff the catalog lists at least one episode for the season and
            none of them airs after *today*.
        """
        rows = [r for r in self._store.aired.list_for_followed(followed_id) if r.season == season]
        if not rows:
            return False
        return all(date.fromisoformat(str(r.air_date)) <= today for r in rows)
```

Add `from datetime import date` to the module imports.

- [ ] **Step 5: Add the season probe**

```python
    def _probe_season_pack(self, episode_item: WantedItem, profile: QualityProfile) -> bool:
        """Ask the trackers whether a COVERING season pack exists for this episode's season.

        Runs one season-scoped search through the ordinary orchestrator path, using a
        transient (never persisted) season-shaped item so the query builder, the
        aired-count resolver and ``filter_to_season`` all behave exactly as they would
        for a real season row. Nothing is written and nothing is grabbed — the verdict
        is only used to decide whether enqueuing a season row is worthwhile.

        Args:
            episode_item: The starved episode row (supplies media_ref, followed_id, season).
            profile: The effective quality profile for the search.

        Returns:
            True iff the season search concluded ``available`` — i.e. at least one pack
            survived coverage verification, hard filters and ranking.
        """
        probe = WantedItem(
            media_ref=episode_item.media_ref,
            kind="season",
            status="pending",
            enqueued_at=episode_item.enqueued_at,
            followed_id=episode_item.followed_id,
            season=episode_item.season,
            episode=None,
        )
        verdict = self._orchestrator.search(probe, profile)
        return verdict.outcome == "available"
```

- [ ] **Step 6: Arm the escalation in `_search_item`**

Change the signature to accept the per-pass memo:

```python
    def _search_item(
        self,
        item: WantedItem,
        now: int,
        *,
        cadence: Cadence,
        season_probed: set[tuple[int, int]],
    ) -> _SearchItemOutcome:
```

Document it in the `Args:` block:

```
            season_probed: Per-PASS memo of ``(followed_id, season)`` pairs already
                probed for a season pack. Bounds the starvation escalation to ONE
                extra tracker query per season per pass — ten starved siblings must
                not produce ten identical queries.
```

Then, immediately after the existing R2 block and before `return self._apply_search_verdict(...)`:

```python
        # D1 — starvation escalation. R2 above only fires when the EPISODE query
        # returned something (``no_matching_episode``). When the trackers carry no
        # per-episode release at all the search exits on ``no_candidates`` and R2 is
        # unreachable — which is exactly the case where the season pack is the answer.
        # Armed by evidence (repeated concluded failure), so it deliberately bypasses
        # the DETECT calendar/ownership gates that provably blocked the real cases.
        if (
            verdict.outcome in ("no_candidates", "no_matching_episode")
            and current.kind == "episode"
            and current.season is not None
            and current.followed_id is not None
            and current.attempts >= _STARVATION_THRESHOLD
        ):
            key = (current.followed_id, current.season)
            if key not in season_probed:
                season_probed.add(key)
                if self._season_fully_aired(
                    current.followed_id, current.season, date.fromtimestamp(now)
                ) and self._probe_season_pack(current, profile):
                    self._store.wanted.record_search_outcome(wanted_id, verdict.outcome, 0)
                    starved_id = current.id
                    converted = self._enqueue_season_from_conversion(current, now)
                    if converted is not None:
                        self._event_bus.emit(
                            SeasonEscalatedAfterEpisodeFailures(
                                season_wanted_id=converted,
                                media_ref=current.media_ref,
                                season=current.season,
                                trigger_outcome=verdict.outcome,
                                starved_episode_ids=(starved_id,) if starved_id else (),
                            ),
                        )
                        log.info(
                            "acquire.service.starvation_escalated",
                            wanted_id=wanted_id,
                            season=current.season,
                            season_wanted_id=converted,
                            trigger=verdict.outcome,
                            attempts=current.attempts,
                        )
                        return "waiting"
```

Add the module constant near `SEARCH_OUTCOME_STATUS`:

```python
#: Concluded not_found searches required before an episode probes for a season pack.
#: Two, not one: a single failure can still be an unlucky tracker moment, and phase 2
#: guarantees a partial outage no longer counts here.
_STARVATION_THRESHOLD = 2
```

- [ ] **Step 7: Drop the two dead parameters of `_enqueue_season_from_conversion`**

The helper declares `raw_results` and `season_packs` but **never reads them** (verified: the body
references neither). It has exactly one existing caller and zero test references. Change:

```python
    def _enqueue_season_from_conversion(self, episode_item: WantedItem, now: int) -> int | None:
```

and make it return the season wanted id (or `None` when the conversion is refused by a terminal
row) instead of a bool — the escalation needs the id for its event. Update the docstring
`Args:`/`Returns:` accordingly, update the existing R2 call site at line ~164 to
`converted = self._enqueue_season_from_conversion(current, now)` and its `if converted:` guard to
`if converted is not None:`.

- [ ] **Step 8: Create the memo in the run loop**

In `personalscraper/acquire/service.py`, before the item loop in `run_search`:

```python
        # Per-pass memo bounding the D1 season probe to one query per season.
        season_probed: set[tuple[int, int]] = set()
```

and at line ~409:

```python
                outcome_tag = self._search_item(item, now, cadence=cadence, season_probed=season_probed)
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `command python -m pytest tests/acquire/ -v`
Expected: PASS, including the pre-existing R2 conversion tests (the signature change must not
regress them).

- [ ] **Step 10: Phase gate**

```bash
make lint
make test
make check
python3 scripts/check-module-size.py
```

- [ ] **Step 11: Commit**

```bash
git add personalscraper/acquire/_search_pass.py \
        personalscraper/acquire/service.py \
        personalscraper/acquire/events.py \
        personalscraper/events/__init__.py \
        tests/acquire/test_starvation_escalation.py
git commit -m "fix(acq-escalade): l'échec répété d'une recherche épisode arme l'escalade saison"
```
