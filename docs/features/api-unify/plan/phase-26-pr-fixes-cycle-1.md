# Phase 26 — PR Fixes Cycle 1

**Type**: fix
**Goal**: Address verified MAJOR/MEDIUM findings from PR #19 review cycle 1 (4 reviewers in
parallel: code-reviewer, silent-failure-hunter, type-design-analyzer, pr-test-analyzer).

## Context

Cycle 1 review surfaced ~30 raw findings; main session filtering retained 6 actionable bugs
that violate DESIGN contracts or hide errors that should be observable. All other findings
(test coverage gaps, type-design polish, naming nits) are deferred to follow-up — see Cycle 1
record in IMPLEMENTATION.md.

DESIGN refs:

- §1.1 — All providers raise `ApiError` (uniform contract).
- §7.1 — `HealthChecker` Protocol is the dead-man's-switch for crash alerting.
- §6 — Tracker ranking engine.
- §3 — `HttpTransport` and observability.

## Sub-phases

### 26.1 — Fix activation registry: `HEALTHCHECK_PING_URL` → `HEALTHCHECK_URL`

**Finding** (silent-failure #4, MAJOR): `personalscraper/api/_activation.py:30` declares
`"healthchecks": ["HEALTHCHECK_PING_URL"]` but the new `HealthcheckClient.REQUIRED_CREDS` is
`["HEALTHCHECK_URL"]` (matches `Settings.healthcheck_url` env binding). Future callers using
`resolve_active("notify", ...)` would warn about a "missing HEALTHCHECK_PING_URL" while
`is_configured()` returns True — silent disable with a misleading message.

**Fix**: in `_activation.py`, change the registry entry to `["HEALTHCHECK_URL"]`. Update any
test referencing the old value.

**Acceptance**: `rg "HEALTHCHECK_PING_URL" personalscraper/ tests/` returns 0; activation
registry value matches `HealthcheckClient.REQUIRED_CREDS`.

**Commit**: `fix(api-unify): align _activation.py healthchecks env var with HEALTHCHECK_URL`

---

### 26.2 — `tmdb._fetch_videos` — log warning on swallowed exception

**Finding** (silent-failure #1, MEDIUM): `tmdb.py:360-363` does `except Exception: return []`
with no log. Trailer scraping cannot distinguish "TMDB down" from "no videos exist". Every
other fail-soft site in the PR (`telegram.py`, `healthchecks.py`, `_registry.py`) at least
logs a warning.

**Fix**: narrow the catch to `(ApiError, CircuitOpenError, KeyError, TypeError, ValueError)`
and add `log.warning("tmdb_fetch_videos_failed", endpoint=..., error=str(exc))` before the
`return []`.

**Acceptance**: a thrown `ApiError` from `_fetch_videos_strict` produces a `tmdb_fetch_videos_failed`
log record (assert via `caplog` in `tests/unit/test_tmdb_videos.py`); empty-result path still
returns `[]` without warning.

**Commit**: `fix(api-unify): log warning on tmdb _fetch_videos swallowed errors`

---

### 26.3 — `transmission.is_seeding` — log warning on swallowed `TransmissionError`

**Finding** (silent-failure #3, MAJOR): `transmission.py:105-109` catches
`transmission_rpc.TransmissionError` and returns `False` with no log. Daemon outage looks
identical to "torrent finished seeding"; downstream cleanup could delete still-seeding
torrents. `qbittorrent.is_seeding()` is intentionally similar but logs and operates on a
different error surface — at minimum the transmission path must be observable.

**Fix**: add `log.warning("transmission_is_seeding_failed", hash=..., error=str(exc))` before
the `return False`. The fail-soft return is preserved (matches qbittorrent symmetric default
behavior); only observability is added.

**Acceptance**: a mocked `TransmissionError` in `tests/unit/test_transmission_client.py`
produces a `transmission_is_seeding_failed` log record; `is_seeding()` still returns `False`.

**Commit**: `fix(api-unify): log warning on transmission is_seeding swallowed errors`

---

### 26.4 — `qbittorrent.py` — wrap native exceptions in `ApiError`

**Finding** (silent-failure #5, MAJOR): `qbittorrent.py:164-166, 167-169, 208-209` re-raises
native `qbittorrentapi.LoginFailed`, `Forbidden403Error`, and `APIConnectionError`. DESIGN
§1.1 explicitly mandates "ALL providers raise `ApiError`". Consumers catching `ApiError`
under the unified contract will not catch these and the pipeline aborts with an unhandled
provider-specific exception.

**Fix**: in each `except qbittorrentapi.<X>: raise` site, replace with
`raise ApiError(provider="qbittorrent", http_status=<401|403|0>, message=str(exc)) from exc`.
Status mapping:

- `LoginFailed` → 401
- `Forbidden403Error` → 403
- `APIConnectionError` → 0 (network)

Update `tests/unit/test_qbittorrent.py` to assert `ApiError` is raised (with the appropriate
`http_status`) instead of native types.

**Acceptance**: `rg "raise qbittorrentapi" personalscraper/api/torrent/qbittorrent.py` returns
0; mocked `LoginFailed` produces an `ApiError(http_status=401)`.

**Commit**: `fix(api-unify): wrap qbittorrent native exceptions in ApiError per DESIGN §1.1`

---

### 26.5 — `_ranking.py` — implement `RankingCriterion.prefer="lower"` semantics

**Finding** (code-reviewer #1, MAJOR): `_ranking.py:122` hard-codes `numeric >= t.at`
(higher-is-better) regardless of `RankingCriterion.prefer`. A config setting `prefer: "lower"`
is silently scored backwards. Field is also documented in `config.example/ranking.json5`
(`@@:16,27`), so users can and will set it.

**Fix**: in the threshold-loop, branch on `prefer`:

- `"higher"` (default + `None`): keep existing `numeric >= t.at`, threshold list iterated in
  the natural order (highest first → highest pts wins).
- `"lower"`: invert to `numeric <= t.at`, sort thresholds ascending (lowest first → lowest
  pts wins). When numeric is below all thresholds, no points; when above all, the highest-pts
  threshold wins. Decision: **mirror** the higher-better semantics: lower numeric should
  produce higher pts only if the threshold says so.

Add `tests/unit/test_ranking.py` cases:

- `prefer="lower"` with a "size_max_GB" criterion (smaller-is-better).
- `prefer="higher"` regression test (existing behavior unchanged).
- `prefer=None` defaults to higher.

**Acceptance**: a `RankingCriterion(field="size", prefer="lower", ...)` scores a 700MB
torrent higher than a 7GB torrent. Higher-is-better remains the default.

**Commit**: `fix(api-unify): honor RankingCriterion.prefer="lower" in threshold scoring`

---

### 26.6 — `pipeline.py` — call `healthcheck.ping_fail()` on `pipeline.run()` exception

**Finding** (silent-failure #2, MAJOR): `personalscraper/commands/pipeline.py:362-365`
correctly calls `ping_fail()` when `report.has_errors()`, but if `pipeline.run()` raises
(`TrailerStepFailed`, unhandled exception, etc.), the `finally:` only releases the lock and
the healthchecks endpoint **never receives a fail ping**. The whole reason `HealthChecker`
exists per DESIGN §7.1 is dead-man's-switch alerting on crashes.

This is a pre-existing gap (the legacy `ping_healthcheck` had the same behavior) but the
notify migration is the right time to close it.

**Fix**: introduce a state flag `pipeline_outcome: Literal["success", "fail"] | None = None`
and move the healthcheck end-ping into a wrapping `try / finally` so it fires on any exit
path:

```python
pipeline_outcome: Literal["success", "fail"] | None = None
try:
    report = pipeline.run()
    # ...telegram + table...
    pipeline_outcome = "fail" if report.has_errors() else "success"
    if report.has_errors():
        raise typer.Exit(1)
finally:
    if healthcheck is not None:
        if pipeline_outcome == "success":
            healthcheck.ping_success()
        else:
            healthcheck.ping_fail()
```

The `TrailerStepFailed` branch already calls `typer.Exit(2)` — that path now also fires
`ping_fail()` via the new finally. The outer `finally` (lock release) is unchanged.

Update `tests/test_cli.py` to assert that an exception path calls `ping_fail` (mock
`HealthcheckClient.ping_fail` and verify it was invoked).

**Acceptance**: pipeline crash → `ping_fail()` invoked; success → `ping_success()` invoked;
report-with-errors → `ping_fail()` invoked.

**Commit**: `fix(api-unify): ensure healthcheck ping_fail on pipeline.run exception`

---

### 26.7 — Phase 26 gate

```bash
make check                 # ruff + mypy + module-size + typed-api
make test                  # 2786+ tests still pass
rg "HEALTHCHECK_PING_URL" personalscraper/ tests/  # → 0
rg "raise qbittorrentapi" personalscraper/api/  # → 0
```

**Commit**: `chore(api-unify): phase 26 gate — PR review cycle 1 fixes complete`
