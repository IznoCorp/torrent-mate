# Phase 2 — `trackers_degraded`: a partial outage is not an absence (D2)

**Defect.** `SearchOutcome.all_errored` is true only when **every** queried tracker failed. With
two active trackers, one erroring while the other legitimately returns zero yields an empty
result set that falls through to `no_candidates`, mapped to `("not_found", "no_candidates", 0)`
— a persisted "I looked, there is nothing" verdict built on an outage.

This violates the contract the module wrote for itself: `SearchVerdict.found` is documented as
*"None = not concluded (NEVER 0 on outage)"*.

Live proof: 2026-08-04 03:10, c411 returned HTTP 429 "Rate limit exceeded" three times for
`Widow's Bay S01E10`; the row persisted `no_candidates` / `found=0`. The same query replayed at
14:00 returns `raw=25, exact_episode=9`.

**Files:**
- Modify: `personalscraper/acquire/orchestrator.py` (`SEARCH_OUTCOMES`, `_search_chain` exit,
  the `mapping` dict in `search`)
- Modify: `personalscraper/acquire/_search_pass.py` (`SEARCH_OUTCOME_STATUS`,
  `_apply_search_verdict`)
- Modify: `personalscraper/acquire/_wanted_store.py` (new `refund_search_attempt`)
- Modify: `personalscraper/acquire/_ports.py` (declare `refund_search_attempt` on the port)
- Test: `tests/acquire/test_trackers_degraded.py` (create)

**Interfaces:**
- Consumes: nothing from phase 1.
- Produces: outcome literal `"trackers_degraded"` mapped to `("retryable", "trackers_degraded",
  None)` and status `"pending"`; store method
  `refund_search_attempt(wanted_id: int) -> bool`.

## Scope note (read before implementing)

This phase refunds the attempt **only** on `trackers_degraded`. The other non-concluded
outcomes (`trackers_unavailable`, `circuit_open`, `search_api_error`) still consume an attempt —
that is the pre-existing behaviour and changing it was **not** approved. It is a known, declared
limitation: after this phase `attempts` means "searches that concluded, plus full-outage
searches". Do not silently widen the refund; if it should be widened, that is an operator
decision recorded separately.

---

- [ ] **Step 1: Write the failing tests**

Create `tests/acquire/test_trackers_degraded.py`:

```python
"""A partial tracker outage must not be persisted as a definitive absence (D2).

``all_errored`` only covers a UNANIMOUS failure. With one tracker down and the other
legitimately empty, the search used to conclude ``no_candidates`` / ``found=0`` — claiming
knowledge it did not have, and burning an attempt for it.
"""

from __future__ import annotations

from personalscraper.acquire._dedup import SearchOutcome


class TestPartialOutageIsRetryable:
    """Empty results + SOME tracker errors ⇒ degraded, never a clean not_found."""

    def test_one_of_two_trackers_errored_yields_trackers_degraded(self, orchestrator, episode_item, profile):
        """1 tracker down, 1 tracker empty ⇒ retryable / trackers_degraded / found is None."""
        orchestrator._tracker_registry.search_candidates = lambda *a, **k: SearchOutcome(
            results=[],
            trackers_queried=2,
            trackers_errored=1,
            errored_names=["c411"],
            queried_names=["c411", "tr4ker"],
            errors={"c411": "api"},
        )

        verdict = orchestrator.search(episode_item, profile)

        assert verdict.outcome == "trackers_degraded"
        assert verdict.disposition == "retryable"
        assert verdict.found is None, "found=0 on an outage is the exact lie this fixes"

    def test_clean_empty_search_is_unchanged(self, orchestrator, episode_item, profile):
        """0 trackers errored + 0 results ⇒ the historical not_found / no_candidates / 0."""
        orchestrator._tracker_registry.search_candidates = lambda *a, **k: SearchOutcome(
            results=[],
            trackers_queried=2,
            trackers_errored=0,
            errored_names=[],
            queried_names=["c411", "tr4ker"],
            errors={},
        )

        verdict = orchestrator.search(episode_item, profile)

        assert verdict.outcome == "no_candidates"
        assert verdict.disposition == "not_found"
        assert verdict.found == 0

    def test_all_trackers_errored_is_unchanged(self, orchestrator, episode_item, profile):
        """Unanimous failure keeps its own name — trackers_unavailable, not degraded."""
        orchestrator._tracker_registry.search_candidates = lambda *a, **k: SearchOutcome(
            results=[],
            trackers_queried=2,
            trackers_errored=2,
            errored_names=["c411", "tr4ker"],
            queried_names=["c411", "tr4ker"],
            errors={"c411": "api", "tr4ker": "api"},
        )

        verdict = orchestrator.search(episode_item, profile)

        assert verdict.outcome == "trackers_unavailable"
        assert verdict.found is None


class TestDegradedSearchDoesNotBurnAnAttempt:
    """A search that never concluded must not count toward the escalation threshold."""

    def test_attempts_unchanged_end_to_end(self, service, store, pending_episode_id):
        """claim +1 then refund −1 ⇒ attempts is identical before and after the pass."""
        before = store.wanted.get(pending_episode_id).attempts

        # drive one search pass whose verdict is trackers_degraded
        ...  # use the harness the other search-pass tests already use

        after = store.wanted.get(pending_episode_id)
        assert after.attempts == before
        assert after.status == "pending"

    def test_refund_never_goes_negative(self, store, pending_episode_id):
        """A refund on a row at attempts == 0 leaves it at 0."""
        assert store.wanted.get(pending_episode_id).attempts == 0
        store.wanted.refund_search_attempt(pending_episode_id)
        assert store.wanted.get(pending_episode_id).attempts == 0


class TestDegradedEpisodeReadsAsNotVerified:
    """The UI must not say « En attente » about a search that never concluded (§2)."""

    def test_state_is_non_verifie_not_en_attente(self):
        """A degraded last verdict yields 'non_verifie', never 'en_attente'.

        ``derive_episode_state`` routes every member of ``INCONCLUSIVE_OUTCOMES`` to
        'non_verifie'. Adding ``trackers_degraded`` to that frozenset is what stops a
        rate-limited tracker from being displayed as « searched, nothing exists ».
        """
        from personalscraper.web.acquisition.states import derive_episode_state

        state = derive_episode_state(
            owned=False,
            wanted_status="pending",
            last_search_outcome="trackers_degraded",
            last_search_found=None,
        )

        assert state == "non_verifie"
```

Check the exact name and signature of the state function in
`personalscraper/web/acquisition/states.py` before writing this test — call it with the same
keyword arguments its existing tests use.

Reuse the fixtures already used by `tests/acquire/test_search_verdicts.py` for `orchestrator`,
`episode_item`, `profile`, `service`, `store`. Do not invent new ones. Fill the `...` with the
same harness those tests use to drive one pass.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `command python -m pytest tests/acquire/test_trackers_degraded.py -v`
Expected: FAIL — `trackers_degraded` is not a known outcome; `refund_search_attempt` does not
exist (AttributeError).

- [ ] **Step 3: Add the outcome to the orchestrator's vocabulary**

In `personalscraper/acquire/orchestrator.py`, add to `SEARCH_OUTCOMES` (line ~97):

```python
        "trackers_degraded",
```

and to `INCONCLUSIVE_OUTCOMES` (line ~114):

```python
        "trackers_degraded",
```

**This second edit is load-bearing, not cosmetic.**
`personalscraper/web/acquisition/states.py:220` routes every member of
`INCONCLUSIVE_OUTCOMES` to `non_verifie`. Without it, an episode whose search was degraded
would display « En attente » — i.e. "I looked, nothing exists" — which is the very lie this
phase removes (§2). With it, the episode correctly reads « non vérifié ».

- [ ] **Step 4: Add the exit path in `_search_chain`**

In `_search_chain`, replace the bare empty-results guard (currently line ~676):

```python
        if not outcome.results:
            return _SearchChainResult(exit_path="no_candidates", ranked=[], top=None)
```

with:

```python
        if not outcome.results:
            # A partial outage is NOT an absence: some tracker failed, so the empty
            # set is not evidence that nothing exists (panne ≠ absence). Only a
            # fully-healthy, fully-empty search may conclude no_candidates.
            # ``all_errored`` (unanimous failure) was already handled above.
            if outcome.trackers_errored > 0:
                return _SearchChainResult(exit_path="trackers_degraded", ranked=[], top=None)
            return _SearchChainResult(exit_path="no_candidates", ranked=[], top=None)
```

- [ ] **Step 5: Map the new exit path**

In `search`, add to the `mapping` dict (line ~793):

```python
            "trackers_degraded": ("retryable", "trackers_degraded", None),
```

Update the docstring outcome table just above it (line ~756) with the new row:

```
        Empty + SOME errored          ``retryable``   ``trackers_degraded`` None
```

- [ ] **Step 6: Map the status**

In `personalscraper/acquire/_search_pass.py`, add to `SEARCH_OUTCOME_STATUS` (line ~44):

```python
    "trackers_degraded": "pending",
```

Note: `tests/acquire/test_search_verdicts.py:258` asserts
`set(SEARCH_OUTCOME_STATUS) == set(SEARCH_OUTCOMES)`. Missing either edit fails that guard —
which is the guard working as intended.

- [ ] **Step 7: Add the store refund method**

In `personalscraper/acquire/_wanted_store.py`, next to `claim_for_search`:

```python
    def refund_search_attempt(self, wanted_id: int) -> bool:
        """Give back the attempt consumed by a claim whose search never concluded.

        ``claim_for_search`` stamps ``attempts + 1`` atomically with the transition to
        'searching', i.e. BEFORE the verdict is known. A search that ends on an outage
        must not count toward the escalation threshold, so the attempt is refunded
        explicitly here rather than conditionally skipped at claim time.

        Clamped at zero: a refund never drives ``attempts`` negative, whatever the
        interleaving.

        Args:
            wanted_id: Rowid of the ``wanted`` row.

        Returns:
            ``True`` if the row existed and was updated; ``False`` otherwise.
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                """
                UPDATE wanted
                SET attempts = MAX(attempts - 1, 0)
                WHERE id = ?
                """,
                (wanted_id,),
            )
            return cur.rowcount == 1
```

Declare it on the port in `personalscraper/acquire/_ports.py`, next to `claim_for_search`, with
the same docstring summary.

- [ ] **Step 8: Call the refund on the degraded verdict**

In `_apply_search_verdict` (`_search_pass.py`, around line 210 where `status` is resolved), after
the status write for this outcome, refund the attempt:

```python
        # A degraded search never concluded: give back the attempt claim_for_search
        # consumed, so `attempts` keeps meaning « searches that concluded » — the
        # counter the starvation escalation reads (phase 3).
        if verdict.outcome == "trackers_degraded":
            self._store.wanted.refund_search_attempt(wanted_id)
```

Place it after the status transition so a crash between the two leaves the row queued with a
fresh verdict (the module's existing verdict-before-status discipline).

- [ ] **Step 9: Run the tests to verify they pass**

Run: `command python -m pytest tests/acquire/test_trackers_degraded.py tests/acquire/test_search_verdicts.py -v`
Expected: PASS, including the set-equality guard.

- [ ] **Step 10: Phase gate**

```bash
make lint
make test
make check
python3 scripts/check-module-size.py
```

Expected: 0 errors; `orchestrator.py` still under 1000 (was 956, this phase adds ~12 lines).

- [ ] **Step 11: Commit**

```bash
git add personalscraper/acquire/orchestrator.py \
        personalscraper/acquire/_search_pass.py \
        personalscraper/acquire/_wanted_store.py \
        personalscraper/acquire/_ports.py \
        tests/acquire/test_trackers_degraded.py
git commit -m "fix(acq-escalade): une panne partielle de tracker n'est plus écrite comme une absence"
```
