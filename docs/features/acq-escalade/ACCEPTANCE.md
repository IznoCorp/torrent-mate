# acq-escalade — ACCEPTANCE

Feature: `fix/acq-escalade` · Version 0.78.0 → 0.78.2 · Exercised 2026-08-04.

Every criterion is an executable command with its observed output pasted below.
No criterion is satisfied by prose (§méthode).

---

## ACC-01 — acquisition coherence guard (BLOCKING)

```
$ python scripts/check-acquisition-coherence.py; echo $?
0 anomalies — 0 error, 0 warning, 0 info (0 counted).
0
```

**PASS.** Exit 0, zero anomalies.

Context for honesty: this check exited **4** at the start of the session, with four
`GRABBED_OWNED` phantoms (wanted #54, #55, #85, #86). They were cleared by the 15:20 `grab`
cron running the pre-existing reconcile sweep — i.e. the queue caught up on its own schedule,
which is exactly the ~12 h latency D4 was about. What this feature changes is that the
post-dispatch scan now reaches the reconcile subscriber immediately, so the phantoms should
not reappear. That claim is proven by the phase-1 tests, not by this run.

## ACC-02 — lint

```
$ make lint
python -m ruff check personalscraper/ tests/      → All checks passed!
python -m ruff format --check personalscraper/ tests/ → 1262 files already formatted
python -m mypy personalscraper/                   → Success: no issues found in 477 source files
python scripts/check_logging.py personalscraper/  → 0 finding(s): 0 error(s), 0 warning(s)
```

**PASS.**

## ACC-03 — full test suite

```
$ make test
===== 10293 passed, 7 skipped, 1 xfailed, 847 warnings in 82.74s (0:01:22) =====
```

**PASS.** 0 failed, 0 error. Baseline at branch creation was 10257 passed → **+36 tests**.

## ACC-04 — full check gate

```
$ make check
cli-coverage-report: OK — 0 ❌ on critical commands
Checking feature map freshness...      → ok
audit: 0 finding(s), 0 error(s).
version bump OK: 0.78.0 -> 0.78.2
```

**PASS.**

## ACC-05 — module-size ceiling

```
$ python3 scripts/check-module-size.py
  [WARN] personalscraper/web/routes/acquisition.py: 848 non-blank lines
```

**PASS.** `acquisition.py` went 995 → **848** (hard ceiling 1000). It remains a WARN, not a
BLOCK — the warn threshold is 800 and pre-dates this feature.

## ACC-06 — OpenAPI drift

```
$ python scripts/export-openapi.py && git diff --exit-code -- frontend/openapi.json
openapi: no drift
```

**PASS.** `frontend/openapi.json` and `frontend/src/api/schema.d.ts` are regenerated and
committed (phase 5 added `SeasonGrabResponse.run_started`).

`schema.d.ts` was generated with the main checkout's `openapi-typescript@7.13.0`
(`frontend/node_modules` is absent in the worktree). The resulting diff is confined to the
new field and the changed docstrings — no version churn.

## ACC-07 — dated real run proving the escalation (BLOCKING)

The four seasons the operator enqueued by hand were all **grabbed** by the 15:20 cron
before this criterion could be exercised on them, and no naturally-starved episode row
remained. The run below therefore reproduces the reported bug faithfully on a **copy** of
the live `acquire.db`, with **real tracker calls**, leaving production untouched
(`config.acquire.db_path` is redirected before the lobe opens; the script asserts the
opened path is the copy and aborts otherwise).

Pre-state restored on the copy — the exact shape of the reported incident:

```
$ sqlite3 acc07.db "SELECT id,followed_id,kind,season,episode,status,attempts,last_search_outcome
                    FROM wanted WHERE followed_id=4 AND season=15;"
5|4|episode|15|21|pending|1|no_candidates
6|4|episode|15|22|pending|1|no_candidates
   (season row #88 deleted — the operator's manual escalation removed)
```

Real run:

```
ACC07 run_at=2026-08-04 16:56:12 CEST
ACC07 db=…/scratchpad/acc07.db
ACC07 summary=SearchRunSummary(available=2, waiting=1, unverified=0, abandoned=0, skipped=1)
ACC07 EVENT SeasonAbsorbedEpisodes: season=15 absorbed=(5, 6)
ACC07 EVENT SeasonEscalatedAfterEpisodeFailures: season=15 trigger=no_candidates
ACC07 SEASON ROW #85 season=15 status=pending
ACC07 EPISODE #5 S15E21 status=absorbed absorbed_by=85
ACC07 EPISODE #6 S15E22 status=absorbed absorbed_by=85
```

**PASS.** The episode query concluded `no_candidates` (as measured live: raw=0 for
`American Dad! S15E21`), the season probe found covering packs, the season row was minted,
both starved episodes were absorbed, and the escalation announced **why**.

Before this feature the same input produced 17 fruitless attempts over 20 days.

---

## Known limitation (declared, not hidden)

Phase 2 refunds the search attempt **only** on `trackers_degraded`. The other
non-concluded outcomes (`trackers_unavailable`, `circuit_open`, `search_api_error`) still
consume an attempt — pre-existing behaviour, deliberately not widened without an operator
decision. After this feature `attempts` therefore means "concluded searches **plus**
full-outage searches", not strictly "concluded searches". This does not weaken the
threshold in the observed dominant case (a partial outage, which is what produced the live
incident), but it is not exact.
