# Acquisition stall diagnosis — season escalation never fires

**Date**: 2026-08-04 (observations taken 13:50–14:05 CEST)
**Reported symptom**: episode wanteds sat "waiting for a torrent" for weeks; the
operator had to enqueue season acquisitions by hand; those manual season rows then
appeared stuck with no torrent started.

Every claim below is backed by an executed, read-only observation on the LIVE
`.data/acquire.db` / `.data/library.db` / trackers / PM2 logs. Probe scripts are in
the session scratchpad (`probe_gates.py`, `probe_season_search.py`,
`probe_episode_search.py`, `probe_reconcile.py`, `probe_qbit.py`).

---

## 1. Observed state

`wanted` table, 2026-08-04 13:55:

| status   | kind                 | count      |
| -------- | -------------------- | ---------- |
| absorbed | episode              | 31         |
| done     | episode/movie/season | 44 / 5 / 1 |
| grabbed  | episode / season     | 4 / 1      |
| pending  | movie / season       | 1 / 4      |

The 4 `pending` season rows (#88 American Dad! S15, #89 American Dad! S17,
#90 Batman: Caped Crusader S2, #91 Widow's Bay S1) were all created at
**12:36 today by the operator**, `attempts = 0`.

Rows they absorbed, with their own search history:

| wanted  | series                 | S/E         | attempts | last outcome    | absorbed_by |
| ------- | ---------------------- | ----------- | -------- | --------------- | ----------- |
| #5, #6  | American Dad!          | S15E21, E22 | **17**   | `no_candidates` | #88         |
| #7, #8  | American Dad!          | S17E23, E24 | **17**   | `no_candidates` | #89         |
| #74–#83 | Batman: Caped Crusader | S02E01–E10  | 3        | `no_candidates` | #90         |
| #87     | Widow's Bay            | S01E10      | 2        | `no_candidates` | #91         |

Rows #5–#8 were enqueued 2026-07-14, searched 17 times over 20 days, and never
escalated. Cadence config: Hot 2h / Warm 1d / Cold 7d, `cutoff_days: 30`.

---

## 2. Defect D1 — episode→season escalation is blind to search failure

Two escalation paths exist. **Neither takes "the episode search keeps finding
nothing" as an input.**

### D1a — DETECT pass (`personalscraper/acquire/detect.py:468-506`)

Gates are purely calendar + ownership: (a) no future episode, (b) last air ≥ 7 days
ago, (c) `owned <= total/2`, (d) no live season row, (e) not fully owned.

Replaying those gates verbatim against live data (`probe_gates.py`):

```
f4  American Dad!           S15  owned=20/22 missing=2  -> c:OWNED_MAJORITY(20/22)
f4  American Dad!           S17  owned=22/24 missing=2  -> c:OWNED_MAJORITY(22/24)
f20 Batman: Caped Crusader  S2   owned=0/10  missing=10 -> b:LAST_AIR_TOO_RECENT(2026-07-31)
f21 Widow's Bay             S1   owned=9/10  missing=1  -> c:OWNED_MAJORITY(9/10)
```

Gate (c) is **anti-correlated with the need**: the more episodes already owned, the
more the season-pack escalation is blocked — which is exactly the "1–2 missing
episodes that only exist inside a pack" shape.

### D1b — SEARCH pass R2 conversion (`personalscraper/acquire/_search_pass.py:139-146`)

R2 converts episode→season, but is armed **only** on:

```python
verdict.outcome == "no_matching_episode"
```

`no_matching_episode` requires the _episode-scoped_ query to have returned raw
results that `filter_to_episode` then zeroed. When the episode query returns
**zero raw results**, the orchestrator exits earlier at `no_candidates`
(`orchestrator.py:676-677`) and R2 is unreachable.

Reproduced live (`probe_episode_search.py`), replaying the orchestrator's own
exit-path taxonomy:

```
#5  'American Dad!' S15E21          query='American Dad! S15E21'
    raw=0  exact=0  exit_path=no_candidates  R2_fires=False
#74 'Batman: Caped Crusader' S2E1   query='Batman: Caped Crusader S02E01'
    raw=0  exact=0  exit_path=no_candidates  R2_fires=False
```

Meanwhile the **season-scoped** query for the very same items returns healthy packs
(`probe_season_search.py`, real tracker calls):

```
#88 'American Dad!' S15           expected_eps=22 raw=4  kept=4   top seeders=65
#89 'American Dad!' S17           expected_eps=24 raw=4  kept=4   top seeders=74
#90 'Batman: Caped Crusader' S2   expected_eps=10 raw=1  kept=1   top seeders=178
#91 "Widow's Bay" S1              expected_eps=10 raw=26 kept=11  top seeders=710
```

**Root cause**: for a season whose episodes are simply not released individually,
the per-episode query returns nothing, so the only escalation trigger that reads
search evidence (R2) can never fire, and the calendar/ownership trigger (DETECT) is
blocked by gate (b) or (c). The queue retries the same doomed episode query on a
7-day cadence until the 30-day cutoff.

---

## 3. Defect D2 — a partial tracker outage is persisted as a definitive absence

`SearchOutcome.all_errored` (`personalscraper/acquire/_dedup.py:83-95`) is true only
when **every** queried tracker errored. With two active trackers (c411, tr4ker), if
one errors and the other legitimately returns zero, `all_errored` is False, the
empty result set falls through to `no_candidates`, and the taxonomy
(`orchestrator.py:797`) maps it to `("not_found", "no_candidates", 0)` — a
persisted "0 found" verdict.

Confirmed instance, PM2 log `personalscraper-search-error.log`, run of 03:10 today:

```
03:10:30  api_error_body_unparsable  provider=c411 status=429
          body='<error code="500" description="Rate limit exceeded..."/>'
          url='https://c411.org/api?apikey=<REDACTED>&t=tvsearch&q=Widow%27s+Bay+S01E10'
          (3 attempts, all 429)
03:10:34  tracker_search_failed  taxon=api  tracker=c411
```

Row #87 (Widow's Bay S01E10) recorded `last_search_outcome='no_candidates'`,
`last_search_found=0` at 03:10:29. Re-running the identical query at 14:00 returns
`raw=25, exact_episode=9`. The releases existed; c411 was rate-limited.

This violates the "panne ≠ absence" rule: an outage was written into the queue as
evidence of absence, and it burned an attempt.

---

## 4. Defect D3 — no on-demand pass; manual season grab waits for cron

`POST .../season-grab` (`personalscraper/web/routes/acquisition.py:1117-1147`)
inserts the `pending` row and absorbs live episode rows. **It never triggers a
search.** The row waits for the `personalscraper-search` cron.

PM2 cron schedule: `personalscraper-search` = `10 3,15 * * *`,
`personalscraper-grab` = `20 3,15 * * *`. Rows created 12:36 → first pass 15:10,
first grab 15:20. Up to ~12 h of "en cours d'acquisition" with nothing scheduled.

`personalscraper search --dry-run` at 13:57 confirms the rows are due and merely
unrun:

```
Search dry-run: 5 items in queue
  Would search: 5
    • MediaRef(tvdb_id=73141)  (season)   x2
    • MediaRef(tvdb_id=403170) (season)
    • MediaRef(tvdb_id=454109) (season)
```

The infrastructure to do better already exists: `personalscraper/web/acquisition/runner.py`
has a `prime` command chaining detect → search → grab scoped to one `followed_id`.
The season-grab route simply does not use it.

---

## 5. Non-defect — the 5 `grabbed` rows are not stuck

All 5 `grabbed` rows point at torrents that are **100 % complete and seeding**
(`probe_qbit.py`), and their media is already in `library.db`. `probe_reconcile.py`
replays the reconcile sweep's ownership decision:

```
wanted#86 episode S1E9  owned_now=True -> WOULD CLOSE done
wanted#85 episode S1E8  owned_now=True -> WOULD CLOSE done
wanted#62 season  S1    owned_now=True -> WOULD CLOSE done
wanted#55 episode S1E2  owned_now=True -> WOULD CLOSE done
wanted#54 episode S3E7  owned_now=True -> WOULD CLOSE done
```

The reconcile sweep runs only inside `follow detect` (03:00) and `grab` (03:20/15:20).
The media landed at 03:46:50 — after that morning's sweep — so the rows stay
visually "en cours" until 15:20. This is observation-point latency, self-healing,
not a state-machine stall. It is however the same truthfulness problem as D3: the
UI asserts "en cours" about work that is finished.

---

## 6. Proposed fix

### F1 — arm the escalation on search evidence (fixes D1)

Extend R2 in `_search_pass.py` into a starvation trigger. When an episode row
concludes `no_candidates` **or** `no_matching_episode`, has reached N concluded
not_found attempts, and every episode of its season has aired, run one
season-scoped probe search; if `filter_to_season` yields a covering pack, reuse the
existing `_enqueue_season_from_conversion` to enqueue the season row and absorb the
episode plus its live siblings.

Because the trigger is _evidence of failure_, it deliberately bypasses DETECT gates
(b) `last_air ≥ 7 days` and (c) `owned <= total/2` — both of which provably blocked
the four real cases.

Cost control: the extra tracker call happens only past the attempts threshold, once
per season (the season row then dedups via the existing live-row lookup).

### F2 — stop writing outages as absences (fixes D2)

In `orchestrator.py`, when `not outcome.results and outcome.trackers_errored > 0`
(and not `all_errored`), exit on a new `trackers_degraded` path mapped to
`("retryable", "trackers_degraded", None)` instead of
`("not_found", "no_candidates", 0)`. A degraded search must not burn an attempt and
must not persist "0 found".

### F3 — make a manual season grab actually start (fixes D3)

After the season row is created, the `season-grab` route enqueues the existing
acquisition runner scoped to that `followed_id` (search → grab), so the operator's
action produces an observable run row immediately instead of silently waiting for
the next cron.

### Test plan (written and failing BEFORE any implementation)

F1:

- episode concludes `no_candidates`, attempts ≥ N, season fully aired, season probe
  returns a covering pack → season row enqueued, episode absorbed, `SeasonAbsorbedEpisodes` emitted.
- below the attempts threshold → no escalation and **no** extra tracker call.
- season not fully aired → no escalation.
- probe finds no covering pack → episode keeps its own verdict and stays live.
- regression fixture reproducing #5: episode query 0 results / season query 4 packs.

F2:

- 1 of 2 trackers errors, other returns 0 → disposition `retryable`, `found is None`,
  attempts not incremented.
- 0 trackers error, 0 results → unchanged `not_found` / `no_candidates` / 0.
- all trackers error → unchanged `trackers_unavailable`.

F3:

- route creates the row AND enqueues a scoped run row; response still 201.
- reused (existing live season row) path does not double-enqueue a run.
- staging role still returns 403 (`require_not_staging` unchanged).

### Product-intent references

§2 (never assert progress that is not happening) for D2/D3/§5, and the acquisition
raison d'être for D1 — the queue must converge on the media, not retry a query that
provably cannot succeed.
