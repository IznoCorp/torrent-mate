# DESIGN — RP5b: shared grab core (download orchestrator + acquisition service)

| Field                        | Value                                                                                                                                                                                                 |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Codename (proposed)**      | `grab-core`                                                                                                                                                                                           |
| **Roadmap item**             | RP5b (P1, Vague 3, prérequis — **gate of the epic**) + RP3a fold-in (Decision A1)                                                                                                                     |
| **Type**                     | minor                                                                                                                                                                                                 |
| **Version bump**             | 0.27.0 → 0.28.0                                                                                                                                                                                       |
| **Date**                     | 2026-06-11                                                                                                                                                                                            |
| **Depends on (all shipped)** | RP5a registry wired, RP3 acquire.db store + VOs, RP5c acquire/ lobe, RP1 TorrentAdder.add, RP1a resolve_source/fetch, ranking, RP4 GrabSucceeded/GrabFailed/WantedAbandoned events + muted subscriber |
| **Unblocks**                 | Ratio C1, Follow D3, Renouvellement, E2                                                                                                                                                               |
| **Scope decisions**          | A1 (typed RP3a vocab + permissive defaults), B1 (raw `search_candidates` seam), C1 (one feature, RP3a folded)                                                                                         |
| **Hardened by**              | adversarial design review 2026-06-11 (3 blocking + 8 major folded in — see §15 changelog)                                                                                                             |

> RP5b is the **gate of the epic**. Every substrate primitive is shipped — RP5b is orchestration glue +
> two new stages (hard-filter, cross-tracker dedup) + the typed RP3a input contract. It builds NO new
> search/fetch/add primitives.

---

## 1. The grab flow (corrected stage order)

```
WantedItem (with rowid)                        [store.wanted.list_pending — now SELECTs id]
  → claim_for_search(id)  → bool               [ATOMIC: UPDATE…WHERE status='pending'; stamps attempts/last_search_at]
       (loser rowcount==0 → skip; winner proceeds)
  → resolve effective QualityProfile           [series default ← FollowedSeries; item SourceCriteria override (decode-only at RP5b)]
  → build (query, media_type, year)
  → search_candidates(...) → SearchOutcome      [NEW raw seam — un-ranked list + trackers_queried/errored]
       (errored==queried>0 → RETRYABLE: GrabFailed('trackers_unavailable'), reset→pending, STOP)
  → HARD-FILTERS  (min-resolution, audio)       [NEW — eliminatory, runs BEFORE dedup so a merge never drops the only passing variant]
       (zero survivors → TERMINAL: WantedAbandoned('all_filtered'), status→abandoned)
  → cross-tracker DEDUP                          [NEW — info_hash primary; fuzzy fallback key; preserves VF/VOSTFR distinctness]
  → rank(survivors, ranking)                     [SHIPPED — soft score]
  → pick top
  → resolve_source(top, transports) → TorrentSource   [SHIPPED — RP1a]
  → torrent_client.add(source, category=, tags=) → info_hash   [SHIPPED — RP1, idempotent]
  → store.wanted.mark_grabbed(id, info_hash)  + emit GrabSucceeded   [persists the hash for the idempotence guard]
```

**Failure routing is a first-class taxonomy (§6.2), not a flat GrabFailed.**

## 2. Goals / Non-goals

**Goals**: grab orchestrator + acquisition service in `acquire/`; **hard-filters** (min-resolution, audio) eliminatory **before** dedup; **cross-tracker dedup** (info_hash primary + a tolerant fuzzy fallback, best-effort); typed **RP3a vocab** (QualityProfile + Resolution ordinal) with **permissive defaults**; GrabSucceeded/GrabFailed/**WantedAbandoned** emission; an **atomic-claim** idempotent state machine with retry/terminal recovery; a `personalscraper grab` CLI.

**Non-goals**: ❌ seed-obligation writes at grab time (dispatch concern, §9); ❌ Telegram activation; ❌ wanted-queue _producers_ (Follow D3/Ratio C1); ❌ per-series QualityProfile _producers_ (Follow D4 — RP5b decodes + defaults); ❌ circuit-breaker wiring on tracker transports (cb_policy reserved); ❌ new torrent-add field (already present); ❌ perfect cross-tracker dedup (impossible without a parser — best-effort heuristic, §4).

## 3. RP3a typed vocabulary (`acquire/desired.py` — NOT in store.py, protect its 684-LOC budget)

Frozen, **core+stdlib-pure** VOs (the TrackerResult-coupled predicate lives in the orchestrator layer, §5):

- **`Resolution`** — ordered IntEnum folding `4k`/`uhd`/`2160p` → one tier > `1080p` > `720p` > `480p` (so `>=` is numeric, never string compare).
- **`QualityProfile`** (decodes `FollowedSeries.quality_profile_json`): `min_resolution: Resolution | None`, `required_audio: frozenset[str]` (markers `{VF, VOSTFR, VO}`), `allowed_codecs`, `min_size`/`max_size`. **Load-bearing** — its defaults drive the hard-filters today.
- **`SourceCriteria`** (decodes `WantedItem.criteria_json`): per-item overrides. **decode/round-trip-only at RP5b** — no live producer until Follow D4; the effective-profile precedence (series default ← item override) ships covered by a round-trip unit test, explicitly **not** an exercised live path (don't mistake the phase-1 golden for proof of use).
- **Defaults (PERMISSIVE — corrected from the review)**: `min_resolution = None` (no floor) — see §5 rationale; `required_audio = frozenset()` (**no language requirement** — English/VO content is grabbable out of the box); no codec/size bound. A French-only or ≥1080p policy is an explicit per-profile **opt-in** (set by Follow D4), mirroring `encoding.json5`'s operator-configured `required_languages`.
- Encode/decode helpers live **in `acquire/desired.py`** (mirroring the _style_ of `store.py`'s `_media_ref_to_json`, kept out of the persistence module). Columns stay TEXT (no migration — pre-1.0).

## 4. Cross-tracker dedup (`acquire/_dedup.py`) — best-effort heuristic

**Reality (review-corrected)**: BOTH trackers populate `info_hash` (LaCale `infoHash`, c411 `guid`) — info_hash is the **primary** key. But the same release is **re-packed per tracker** → hashes differ cross-tracker (≈0 overlap on real samples), so info_hash alone only collapses **within-tracker** re-announces. Robust cross-tracker dedup needs a fuzzy key:

- **Primary key**: `info_hash.lower()` when present/non-empty (collapses exact dups; mostly within-tracker).
- **Fuzzy fallback key**: `(title_core, year, resolution_tier, release_group)` where `title_core` is a **token-SET** normalization (tokenize → drop a curated noise set {4klight, hdlight, 10bit, container words} → canonicalize aliases {he-aac→aac, hdr10→hdr} → order-independent core up to year/resolution), bucketed by **size within a tolerance window (~2%)** so padding/`.nfo` differences still merge while distinct cuts stay separate. **VF/VOSTFR/VO language markers are PRESERVED as distinguishing tokens** — the normalizer must never merge a VF and a VOSTFR cut.
- Built neutral in `acquire/` (layering bans `sorter/cleaner`). Golden-tested with the **real cross-tracker `-QTZ` pair** (byte-identical 4677887384, divergent titles) → must merge; and two different-cut same-size → must stay distinct.
- `TrackerResult` is mutable/non-hashable → group via the computed key, never the object.
- **Honest scope note**: this is a heuristic; perfect cross-tracker dedup is out of scope. Documented limit: it collapses exact within-tracker dups always, and cross-tracker dups whose token-core+size align.

## 5. Hard-filters (`acquire/_filters.py`) — eliminatory, BEFORE dedup

- **min-resolution**: map `result.resolution` (tokens `2160p/1080p/720p/480p/4k/uhd`, lowercase) → `Resolution`; drop `< profile.min_resolution`. **None-resolution = FAIL-OPEN (passes)** by default (corrected) — an unparseable resolution is usually a naming-style gap (REMUX/COMPLETE.BLURAY/WEB-DL all parse None and are often the _best_ source); `rank()` soft-sorts them. Fail-closed is an opt-in per-profile `require_known_resolution: bool=False`. When `profile.min_resolution is None`, the stage is a no-op.
- **required-audio** (the TRAP): `TrackerResult.audio` is **codec-only** (DTS/AAC) — never VF/VOSTFR. So the audio filter parses **language markers from `result.title`** with an **anchored** regex `r"\b(VFF|VFQ|VFI|VF2|VOF|TRUEFRENCH|MULTI|VOSTFR|VOST|VO)\b"` (re.IGNORECASE — `\b` prevents `MULTILINGUAL`/`ConVOSTed` false-matches), normalized to `{VF, VOSTFR, VO}` tiers; drop results matching **none** of `profile.required_audio`. **Default `required_audio = frozenset()` → no-op** (nothing dropped).
- Distinct from `rank()` (soft-score + `min_seeders` only). Never push per-item filters into global `RankingConfig`.

## 6. Orchestrator + service + wiring + failure taxonomy

### 6.1 Modules + single handle

- **`acquire/orchestrator.py` `GrabOrchestrator`** (phase 4a): the §1 chain for ONE claimed item → `GrabOutcome`. Narrow deps (NOT AppContext): `tracker_registry`, `transports`, `torrent_client`, `event_bus`, `ranking`.
- **`acquire/service.py` `AcquisitionService`** (phase 4b): `list_pending()` batch loop + the atomic-claim state machine (§7) + `RunSummary`.
- **Single sub-handle `GrabCore`** (orchestrator+service+transports) attached to `AcquireContext` via **ONE** new field `grab: GrabCore | None`. **Constructed inside `_factory.build_acquire_context`** (the only frame holding registry + `config.ranking` + `torrent_client` + `event_bus` + store together; transports via the new `TrackerRegistry.transports()` accessor). `GrabCore is None` when `torrent_client is None` (read-only/dry-run can still search+filter+rank, cannot add).
- **`TrackerRegistry.transports() -> dict[str, HttpTransport]`** — new public accessor (today only private `client._transport` via getattr in `close()`).

### 6.2 Failure taxonomy (review-mandated — RETRYABLE vs TERMINAL)

Catch order matters: **`CircuitOpenError` is NOT an `ApiError` subclass** (sibling) — catch it separately or it crashes the batch.

- **RETRYABLE** → reset wanted `searching→pending`, emit `GrabFailed(reason)`, item retried next run (bounded by attempts): `CircuitOpenError`; `trackers_unavailable` (all queried trackers errored, from `SearchOutcome`); transient/5xx `ApiError` on add; `OperationalError` (db lock) on the status write.
- **TERMINAL** → set wanted `→abandoned`, emit **`WantedAbandoned(reason)`** (the shipped distinct event, not just GrabFailed): `no_candidates` (clean search, zero hits); `all_filtered` (zero survivors after hard-filters); `TrackerAuthError` (401/403 — passkey/config broken, won't self-heal); attempts ≥ cap.
- **Success** → `GrabSucceeded` after `add()`.
- `event_bus.emit` is fire-and-forget + isolates subscriber errors → success/failure is decided by `add()`'s return/raise, never by emit.

## 7. State machine + idempotence (`store.wanted` only) — review-hardened

- **WantedItem gains `id: int | None`** and `list_pending()` SELECTs `id` + populates it via `_row_to_wanted` (pre-1.0 in-place VO/query evolution, no migration). Without this the service has no rowid to call `set_status`/`get` — **was a blocking gap**. Golden test: `list_pending()[0].id` round-trips the rowid.
- **Atomic claim** (new `_WantedSubStore.claim_for_search(id, now) -> bool` + Protocol): one `_write_tx` running `UPDATE wanted SET status='searching', attempts=attempts+1, last_search_at=? WHERE id=? AND status='pending'`, returns `cur.rowcount == 1`. The orchestrator proceeds only on `True`; a concurrent loser gets `False` and skips. `BEGIN IMMEDIATE` makes this the single serialization point — closes the TOCTOU race that `get`-then-`set` left open. Stamps attempts/last_search_at atomically (no more dead columns; enables the attempts cap).
- **Terminal grab**: `mark_grabbed(id, info_hash)` persists status='grabbed' **and the info_hash**. The idempotence guard consults the **persisted info_hash**, not status alone — so a crash/lock between `add()` and the status write does NOT double-emit `GrabSucceeded` on re-run (the re-run sees the hash and short-circuits).
- **Failure recovery**: every failure branch transitions the row OUT of 'searching' per the §6.2 taxonomy (→pending retryable / →abandoned terminal). No stuck-'searching' orphan — **was a data-loss gap** (list_pending only returns 'pending').
- **Stale-searching recovery query** `list_stale_searching(older_than)` feeds back into the run alongside `list_pending` (covers a process killed mid-grab before any status write).
- **NEGATIVE invariant** (load-bearing): orchestrator MUST NOT call `store.seed.add` / `record_dispatch` at grab time (§9).

## 8. CLI entry (`personalscraper grab`)

New command, built `build_torrent_client=True` (else `GrabCore`/`torrent_client` is None → fail loud). `--dry-run` runs search+filter+dedup+rank, prints the ranked top candidate, **no fetch/add** (pipeline-dry-run-first rule). `--limit N` bounds the batch.

## 9. Seed-obligation separation (do NOT violate)

`record_dispatch` writes `seed_obligation` rows at **dispatch time** only. A grab-time write = phantom row (no `dispatched_path`) poisoning `may_delete` VETO + double-counting. RP5b's acquire-DB seam is `store.wanted.*` ONLY. (RP5b improves dispatch-time correlation by tagging the added torrent with its source tracker — data, not obligation-writing.)

## 10. Layering, risks, residue

- `acquire/` imports api/core/conf/events downward only (verified vs `test_layering.py`); orchestrator takes narrow services, NOT AppContext (boundary test).
- **Residual risks**: cross-tracker dedup is best-effort (§4 honest limit); hard-filters default permissive to avoid false-rejects (a stricter policy is per-profile opt-in); cb_policy not threaded → tracker search/fetch NOT circuit-protected (out of scope); module-size budget split across phases (§12).

## 11. Verification (non-vacuous)

**Golden**: (1) within-tracker same info_hash → one survivor; (2) the **real `-QTZ` cross-tracker pair** (divergent titles, equal size) → merges via fuzzy key; two different-cut same-size → stay distinct; (3) hard-filter — a 720p result dropped when profile floors 1080p; a None-resolution REMUX **passes** (fail-open); an audio-required profile drops a no-marker title while keeping a `MULTi` one; (4) fetch+add happy path — real `.torrent` bytes → mocked `TorrentAdder` → info_hash → `mark_grabbed` + exact `GrabSucceeded` payload. **Adversarial / concurrency (load-bearing gate)**: (a) two `claim_for_search` on one row → exactly one `True`, exactly one `GrabSucceeded`; (b) failure after 'searching' → row back to 'pending' (retryable) and re-listed; (c) attempts ≥ cap → 'abandoned' + `WantedAbandoned`; (d) `add()` succeeds then `mark_grabbed` raises `OperationalError` → re-run does NOT emit a 2nd `GrabSucceeded` (hash-guard) and does not orphan; (e) all trackers error → `GrabFailed('trackers_unavailable')`, row stays 'pending' (≠ clean no_candidates → 'abandoned'); (f) `CircuitOpenError` caught separately → retryable, not a batch crash; (g) **NEGATIVE**: `seed.add`/`record_dispatch` call_count == 0 during grab; (h) audio filter passes `.audio="DTS"` title-`MULTi` (proves title-parse); (i) regex `\b` — `MULTILINGUAL`/`ConVOSTed` do NOT match. Resolution-ordinal unit test (`720p<1080p`, `4k==uhd==2160p`).

## 12. Phase decomposition (Decision C1, phase 4 split per review → 7 phases)

1. **RP3a vocab** — `acquire/desired.py`: `Resolution` + `QualityProfile` + `SourceCriteria` (decode-only) + json codec + permissive defaults + precedence round-trip test.
2. **Dedup** — `acquire/_dedup.py`: `TrackerRegistry.search_candidates` raw seam + `SearchOutcome` + token-set normalizer + info_hash/fuzzy keys + size-tolerance + best-provenance + `-QTZ` golden.
3. **Hard-filters** — `acquire/_filters.py`: resolution-ordinal (fail-open None) + anchored title language parser + the `_base.py` `audio` docstring fix + tests.
   4a. **Orchestrator** — `acquire/orchestrator.py`: the §1 chain + failure taxonomy + emission + `GrabOutcome` + golden fetch+add + adversarial auth/Conflict/Circuit + NEGATIVE seed-write assert.
   4b. **Service + state machine + wiring** — `acquire/service.py` + `WantedItem.id` + `list_pending` SELECT id + `claim_for_search`/`mark_grabbed`/`list_stale_searching` store methods + Protocol + `GrabCore` handle + `_factory` construction + `TrackerRegistry.transports()` + concurrency/recovery tests.
4. **CLI** — `personalscraper grab` (build_torrent_client, --dry-run, --limit, None-handling) + e2e.
5. **Docs + ACCEPTANCE + gate** — architecture.md, grab-core reference, ACCEPTANCE.md, make check + design-gaps.

## 13. ACCEPTANCE preview (executable)

- pytest: within-tracker same-hash dedup → one survivor; `-QTZ` cross-tracker pair merges.
- pytest: sub-floor resolution filtered; None-resolution passes (fail-open); mocked add → `GrabSucceeded`.
- pytest: two concurrent `claim_for_search` → exactly one wins; failure → row retriable; `record_dispatch` never called during grab.
- `personalscraper grab --dry-run` over a seeded wanted item prints the ranked candidate without adding.
- `make check` green.

## 14. Deferred (not gaps)

Wanted-queue producers (Follow D3/Ratio C1) → waves 4-5; per-series QualityProfile producers (Follow D4) → waves 4-5; Telegram grab-notify activation; circuit wiring on tracker transports; **config-correction**: the `ranking.json5` **VFF/VFQ** audio entries are silent no-ops (codec-only field) — `TrueHD` still scores; fix only the dead VF entries in a separate config change.

## 15. Adversarial-review changelog (what the 2026-06-11 review changed)

- **Stage order** flipped to hard-filter **before** dedup (was dedup-first → could drop the only profile-passing variant).
- **info_hash** is the **primary** dedup key (was wrongly "always None for LaCale"); fuzzy fallback redesigned as a tolerant token-set+size-window key (naive title+size merged nothing on real data); honest best-effort scope.
- **Hard-filter defaults** flipped **permissive**: `min_resolution=None` + None=fail-**open** (was 1080p + fail-closed → dropped REMUX/BluRay best copies); `required_audio=∅` (was {VF,VOSTFR} → dropped English/VO); French/quality policy = per-profile opt-in. Anchored audio regex (`\b`).
- **State machine** made implementable + safe: `WantedItem.id` added (was unimplementable — no rowid); **atomic `claim_for_search`** (was TOCTOU-racy get-then-set); failure recovery searching→pending/abandoned (was stuck-'searching' data loss); hash-guard for the add→status gap (was double-emit/orphan); attempts/last_search_at stamping.
- **Failure taxonomy** RETRYABLE vs TERMINAL with `WantedAbandoned` + `SearchOutcome(trackers_errored)` (was a flat GrabFailed conflating transient outage with permanent no-source; `CircuitOpenError` caught separately).
- **Phase 4 split** 4a/4b (was one over-budget gate vs the 734-LOC trailers orchestrator precedent).
- **RP3a `SourceCriteria`** marked decode-only (no live producer until D4); helpers in `desired.py` not `store.py`; `TrackerResult.audio` docstring fix.

### PR-fixes cycle 1 (2026-06-11) — emit-ordering decision + error isolation

- **C1 — emit-after-persist (chosen over the pragmatic retry fallback).** The hash-guard
  (`grabbed_hash`) was persisted but never **consulted**, and the orchestrator emitted
  `GrabSucceeded` **before** the service called `mark_grabbed` — so a `mark_grabbed` crash
  left the row `'searching'` and the §11(d) stale-recovery re-grab emitted a **second**
  `GrabSucceeded`. Fix: the orchestrator NO LONGER emits `GrabSucceeded`; it returns the
  success payload on `GrabOutcome` (`info_hash` / `category` / `tags`), and the **service**
  emits `GrabSucceeded` **after** `mark_grabbed` persists. A `mark_grabbed` crash now means
  **no emit happened** — the single re-grab (idempotent `add`, same `info_hash`) emits
  **exactly once**. **Emission asymmetry is deliberate**: the orchestrator still emits the
  FAILURE events (`GrabFailed` / `WantedAbandoned`) itself because no irreversible external
  side-effect precedes them (no persist-then-crash window); **success is special** — the
  torrent `add()` is the only irreversible side-effect that precedes persistence, so its
  emit must follow persistence. A belt-and-suspenders **hash-guard consultation** also
  short-circuits any row re-listed while already carrying a `grabbed_hash` (no re-grab, no
  re-emit). Regression: §11(d) crash-window test asserts exactly ONE `GrabSucceeded` across
  the crash + stale-recovery and an idempotent double-`add`.
- **C2 — per-item error isolation (DESIGN §6.2).** Each item's body runs under a narrow
  try/except: `sqlite3.OperationalError` (DB lock — RETRYABLE) is logged
  (`acquire.service.item_db_locked`), counted skipped, and the row left `'searching'` for the
  stale-searching sweep; `json.JSONDecodeError` (corrupt `criteria_json` /
  `quality_profile_json`) abandons just that row (`acquire.service.item_bad_criteria_json`).
  NO bare `except Exception` — a genuine programming bug still surfaces. ONE bad row never
  aborts the batch; `run_complete` always fires.
