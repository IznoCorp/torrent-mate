# Phase 5 — The operator action triggers the pass (D3)

**Defect.** `grab_season` inserts the `pending` season row, absorbs the live episode rows, and
then **triggers nothing**. The crons are `search 10 3,15` and `grab 20 3,15`, so a row created at
12:36 waits until 15:10 — up to ~12 h of "en cours d'acquisition" with nothing scheduled.
`create_follow` already calls `enqueue_prime_run` for exactly this reason; season-grab is the one
operator entry point that was left out.

**Operator requirement (verbatim):** « Tout devrait se déclencher au moment où je lance les
acquisitions. »

**Files:**
- Modify: `personalscraper/web/routes/acquisition_seasons.py` (created in phase 4)
- Modify: `frontend/openapi.json`, `frontend/src/api/schema.d.ts` (regenerated)
- Test: `tests/web/test_season_grab_trigger.py` (create)

**Interfaces:**
- Consumes: `acquisition_seasons_router` from phase 4;
  `enqueue_prime_run(db_path: Path | None, followed_id: int) -> PrimeOutcome` from
  `personalscraper/web/routes/acquisition_triggers.py`.
- Produces: the season-grab response gains a field reporting whether a run was queued.

## Constitution constraints (binding)

- **§6** — a legitimate operator action **never** answers 409. It executes or it queues
  visibly. The only permitted refusal is idempotence: the same action, same target, already in
  flight. `enqueue_prime_run` already implements exactly that and swallows its own failures.
- **§5** — a manual trigger **shows the run**: launched → in progress → numbered result. A
  success toast over a dead run is forbidden. The response must therefore report the real
  outcome of the enqueue, never an optimistic constant.
- **§2** — the state carries a clear French label.

---

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_season_grab_trigger.py`:

```python
"""A manual season grab must START, not wait up to 12 h for the next cron (D3).

``create_follow`` has always primed the chain; ``grab_season`` did not, so the operator's
click produced a queued row and no observable run — the UI said « en cours d'acquisition »
about work nothing had scheduled (product-intent §2).
"""

from __future__ import annotations


class TestSeasonGrabTriggersARun:
    """The action produces an observable run row."""

    def test_fresh_season_grab_enqueues_a_prime_run(self, client, store, monkeypatch):
        """Creating the season row also enqueues the scoped run."""
        calls: list[int] = []
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_seasons.enqueue_prime_run",
            lambda db_path, followed_id: calls.append(followed_id) or "spawned",
        )

        resp = client.post(
            f"/api/acquisition/follows/{FOLLOWED_ID}/seasons/15/grab",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert resp.status_code == 201
        assert calls == [FOLLOWED_ID], "the operator action must start the pass"

    def test_reused_live_row_does_not_double_enqueue(self, client, store, monkeypatch):
        """An existing LIVE season row is reused (200) and must not re-spawn a run."""
        calls: list[int] = []
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_seasons.enqueue_prime_run",
            lambda db_path, followed_id: calls.append(followed_id) or "spawned",
        )
        # first call creates
        client.post(URL, headers=HDRS)
        calls.clear()
        # second call reuses
        resp = client.post(URL, headers=HDRS)

        assert resp.status_code == 200
        assert resp.json()["reused"] is True
        assert calls == [], "the reused path must not queue a second identical run"


class TestConstitutionSix:
    """A legitimate action never answers « occupé »."""

    def test_never_returns_409_when_a_run_is_already_in_flight(self, client, monkeypatch):
        """An already-running prime yields a normal response, never a 409 (§6)."""
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_seasons.enqueue_prime_run",
            lambda db_path, followed_id: "already_running",
        )

        resp = client.post(URL, headers=HDRS)

        assert resp.status_code != 409, "§6: the only permitted refusal is idempotence, not a 409"
        assert resp.status_code in (200, 201)

    def test_failed_enqueue_is_reported_not_hidden(self, client, monkeypatch):
        """A dead enqueue must be visible in the payload — no success toast on a dead run (§5)."""
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_seasons.enqueue_prime_run",
            lambda db_path, followed_id: "failed",
        )

        resp = client.post(URL, headers=HDRS)

        assert resp.json()["run_started"] is False


class TestStagingGuardUnchanged:
    """The write perimeter is not weakened by this change."""

    def test_staging_role_still_forbidden(self, staging_client):
        """PERSONALSCRAPER_WEB_ROLE=staging ⇒ 403, unchanged."""
        assert staging_client.post(URL, headers=HDRS).status_code == 403
```

Reuse the client / staging_client fixtures already used by the existing season-grab tests.
Replace `URL`, `HDRS`, `FOLLOWED_ID` with the module-level constants those tests already define.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `command python -m pytest tests/web/test_season_grab_trigger.py -v`
Expected: FAIL — `enqueue_prime_run` is not referenced by the seasons module; `run_started` is
not in the response.

- [ ] **Step 3: Extend the response model**

In the module that defines `SeasonGrabResponse`, add the field (keep it optional-safe for
clients that ignore it):

```python
    run_started: bool = False
    """Whether a scoped acquisition run was actually queued by this call.

    Reports the REAL outcome of the enqueue (§5 — a success toast over a dead run is
    forbidden). ``False`` when the indexer is unconfigured or the spawn failed; the
    season row still exists and the next cron will pick it up.
    """
```

- [ ] **Step 4: Wire the trigger**

In `acquisition_seasons.py`, import `enqueue_prime_run` and call it on the **fresh** path only:

```python
        # D3 — the operator's action must START, not wait up to 12 h for the next cron.
        # Same amorce create_follow already uses (detect → search → grab, scoped to this
        # follow). Fire-and-forget by contract: enqueue_prime_run logs and swallows every
        # failure, and its own idempotence guard is the ONLY refusal §6 permits — a
        # duplicate of the same action on the same target. It never raises, so a dead
        # spawn degrades to run_started=False instead of failing the enqueue.
        prime_outcome = enqueue_prime_run(config.indexer.db_path, followed.id)

        return SeasonGrabResponse(
            season_wanted_id=season_wid,
            season=season,
            absorbed_count=len(absorbed_ids),
            reused=False,
            run_started=prime_outcome in ("spawned", "already_running"),
        )
```

Leave the reused path returning `run_started=False` — a live season row already has its own run
history, and re-spawning would be the duplicate §6 forbids.

Mirror the outcome mapping `create_follow` uses (`acquisition.py:847` / `:902`) so the two
operator entry points report identically.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `command python -m pytest tests/web/test_season_grab_trigger.py tests/web/ -k "season" -v`
Expected: PASS.

- [ ] **Step 6: Regenerate the API contract**

```bash
make openapi
git diff --stat frontend/openapi.json frontend/src/api/schema.d.ts
```

Expected: both files change (the response model gained a field). Commit them — CI fails on drift.

> **Concurrency**: `fix/media-sheet-data` also regenerates these two files. If they conflict at
> merge, resolve by re-running `make openapi` on the merged tree — never hand-merge generated
> output.

- [ ] **Step 7: Phase gate**

```bash
make lint
make test
make check
python3 scripts/check-module-size.py
```

Expected: 0 errors; `acquisition.py` still absent from the size findings.

- [ ] **Step 8: Commit**

```bash
git add personalscraper/web/routes/acquisition_seasons.py \
        frontend/openapi.json frontend/src/api/schema.d.ts \
        tests/web/test_season_grab_trigger.py
git commit -m "fix(acq-escalade): l'acquisition manuelle d'une saison démarre immédiatement"
```

- [ ] **Step 9: Run the full ACCEPTANCE suite**

```bash
python scripts/check-acquisition-coherence.py; echo "ACC-01 exit=$?"
make lint    # ACC-02
make test    # ACC-03
make check   # ACC-04
python3 scripts/check-module-size.py                                        # ACC-05
make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts  # ACC-06
```

ACC-01 must print `exit=0`. If phantoms remain, phase 1 did not fully land — investigate before
declaring the feature done, and never record a "conforme" verdict without the zero-anomaly run
(§méthode).

- [ ] **Step 10: ACC-07 — dated real run**

Exercise the escalation against the live queue on a genuinely starved season, capture the
transcript (command, timestamp, resulting `wanted` rows), and paste it into
`docs/features/acq-escalade/ACCEPTANCE.md`. Prose is not admissible.
