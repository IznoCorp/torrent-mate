# grab-core — Download Orchestrator + Acquisition Service

RP5b (0.28.0) — gate of the acquire epic. Orchestration glue over the shipped
substrate primitives (search, fetch, add, dedup, hard-filters) with an atomic-claim
state machine and a first-class failure taxonomy.

## The grab flow

```
WantedItem (with id) ← store.wanted.list_pending() / list_stale_searching()
→ claim_for_search(id, now) ← ATOMIC UPDATE … WHERE status='pending' (BEGIN IMMEDIATE)
→ resolve QualityProfile ← effective_quality(series, item)
→ search_candidates(…) → SearchOutcome (raw, un-ranked)
→ HARD-FILTERS ← apply_hard_filters(results, profile)
→ DEDUP ← dedup(filtered)
→ rank(survivors, ranking) ← soft score
→ resolve_source(top, transports) ← fetch .torrent bytes
→ torrent_client.add(source) ← idempotent (TorrentAdder)
→ mark_grabbed(id, info_hash) ← persists hash for the idempotence guard
→ emit GrabSucceeded
```

## Module map

| Module                    | Role                                                                                       |
| ------------------------- | ------------------------------------------------------------------------------------------ |
| `acquire/desired.py`      | `Resolution` IntEnum, `QualityProfile`, `SourceCriteria`, JSON codecs, `effective_quality` |
| `acquire/_dedup.py`       | `SearchOutcome`, raw `search_candidates` seam, token-set normalizer, `dedup()`             |
| `acquire/_filters.py`     | `apply_hard_filters()` — resolution floor (fail-open None) + anchored audio language regex |
| `acquire/orchestrator.py` | `GrabOrchestrator` — single-item §1 chain, `GrabOutcome`, failure taxonomy, event emission |
| `acquire/service.py`      | `AcquisitionService` batch loop, `GrabCore` handle, `RunSummary`, `MAX_ATTEMPTS`           |

## Failure taxonomy (§6.2)

Catch order matters: `CircuitOpenError` is a **sibling** of `ApiError` (NOT a subclass
— see `core/_contracts.py`), so it is caught in a separate `except` clause. A bare
`except ApiError` would miss it and crash the whole batch.

| Failure                                  | Class     | Status transition         | Event                                |
| ---------------------------------------- | --------- | ------------------------- | ------------------------------------ |
| All trackers errored                     | RETRYABLE | `searching` → `pending`   | `GrabFailed('trackers_unavailable')` |
| `CircuitOpenError` (search or add)       | RETRYABLE | `searching` → `pending`   | `GrabFailed('circuit_open')`         |
| Transient / 5xx `ApiError` on add        | RETRYABLE | `searching` → `pending`   | `GrabFailed(…)`                      |
| `TorrentFetchError` (fetch bytes failed) | RETRYABLE | `searching` → `pending`   | `GrabFailed(…)`                      |
| `OperationalError` / db lock on write    | RETRYABLE | `searching` → `pending`   | `GrabFailed('db_lock…')`             |
| No torrent client configured             | RETRYABLE | `searching` → `pending`   | `GrabFailed('no_torrent_client')`    |
| No seeders after rank                    | RETRYABLE | `searching` → `pending`   | `GrabFailed('no_seeders')`           |
| Zero search results                      | TERMINAL  | `searching` → `abandoned` | `WantedAbandoned('no_candidates')`   |
| All hard-filtered                        | TERMINAL  | `searching` → `abandoned` | `WantedAbandoned('all_filtered')`    |
| `TrackerAuthError` (401/403)             | TERMINAL  | `searching` → `abandoned` | `WantedAbandoned('auth_failed:…')`   |
| `attempts >= MAX_ATTEMPTS`               | TERMINAL  | `searching` → `abandoned` | `WantedAbandoned('attempts_cap')`    |

## Atomic-claim state machine

The service **never** does get-then-set (which has a TOCTOU race). Instead:

- **`claim_for_search(id, now) -> bool`**: a single `UPDATE wanted SET status='searching', attempts=attempts+1, last_search_at=? WHERE id=? AND status='pending'` inside a `BEGIN IMMEDIATE` transaction. Returns `True` only when `cur.rowcount == 1`. A concurrent loser gets `False` and skips — no double-grab.
- **`mark_grabbed(id, info_hash)`**: persists `status='grabbed'` **and the info_hash**. On re-run, the service consults the persisted hash — if the hash matches, it short-circuits without re-emitting `GrabSucceeded`. This closes the crash-window between `add()` and the status write.
- **Failure recovery**: every failure branch transitions the row OUT of `'searching'`:
  - RETRYABLE → reset to `'pending'` (re-listed next run, bounded by `MAX_ATTEMPTS`).
  - TERMINAL → set to `'abandoned'` (won't self-heal — needs operator intervention or a new wanted row).
- **Stale-searching recovery**: `list_stale_searching(older_than)` finds rows stuck in `'searching'` longer than 1 hour (process killed mid-grab before any status write). These are folded into the same run alongside `list_pending()`.
- **Attempts cap**: `MAX_ATTEMPTS = 5`. A RETRYABLE item that has been claimed 5 times without success is escalated to TERMINAL → `WantedAbandoned('attempts_cap')`.

## Hard-filter defaults (permissive)

- **`min_resolution = None`** → no floor; None-resolution (REMUX, COMPLETE.BLURAY, WEB-DL pack) **passes** (fail-open by default). An unparseable resolution is usually a naming-style gap, not a low-quality signal — `rank()` soft-sorts them. Fail-closed is an opt-in per-profile `require_known_resolution: bool=False`.
- **`required_audio = frozenset()`** → no language requirement; English/VO content is grabbable out of the box.
- A French-only or ≥1080p policy is a per-profile **opt-in** (set by Follow D4), mirroring `encoding.json5`'s operator-configured `required_languages`.

## Audio language filter (`\b` boundary guard)

The audio filter parses **language markers from `result.title`** (NOT `result.audio` —
`TrackerResult.audio` is codec-only: DTS, AAC, etc.). The anchored regex:

```
\b(VFF|VFQ|VFI|VF2|VOF|TRUEFRENCH|MULTI|VOSTFR|VOST|VO)\b
```

`\b` prevents false-matches: `MULTILINGUAL` does NOT match `MULTI`, `ConVOSTed` does
NOT match `VOSTFR`. Raw markers are normalised to three canonical tiers: `VF` (all
French), `VOSTFR` (French subtitles), `VO` (original audio).

## Dedup strategy

1. **Primary key**: `info_hash.lower()` when present/non-empty — collapses exact within-tracker re-announces.
2. **Fuzzy fallback key**: `(title_core, year, resolution_tier, release_group)` where `title_core` is a **token-set** normalisation (tokenize → drop curated noise {4klight, hdlight, 10bit, container words} → canonicalize aliases {he-aac→aac, hdr10→hdr} → order-independent core), bucketed by **size within ~2% tolerance**. This collapses cross-tracker repacks of the same cut while keeping distinct cuts separate.
3. **VF/VOSTFR/VO language markers are preserved** as distinguishing tokens — the normalizer never merges a VF and a VOSTFR cut.
4. **Best-provenance selection** within each equivalence group: prefers freeleech over seeders count (keeps the easiest-to-grab copy).
5. **Honest scope note**: this is a best-effort heuristic — it collapses exact within-tracker dups always and cross-tracker dups whose token-core+size align. Perfect cross-tracker dedup (without a release-name parser) is out of scope.

## Seed-obligation separation (§9)

`record_dispatch` writes `seed_obligation` rows at **dispatch time** only. A grab-time
write would create a phantom row (no `dispatched_path`) poisoning `may_delete` VETO +
double-counting. RP5b's acquire-DB seam is `store.wanted.*` ONLY. The orchestrator has
**no store/seed dependency at all** — it has no path to write a seed obligation. This
negative invariant is load-bearing and enforced by a dedicated test
(`test_negative_seed_write_never_called_during_full_success`).

RP5b improves dispatch-time correlation by tagging the added torrent with its source
tracker — data enrichment, not obligation-writing.

## CLI

```bash
personalscraper grab                # process all pending + stale items
personalscraper grab --limit 5      # process at most 5 items
personalscraper grab --dry-run      # search + filter + dedup + rank, print top, no fetch/add
```

The `grab` command is registered with `build_torrent_client=True` — it fails loud
when no torrent client is configured (`GrabCore is None`). `--dry-run` can still
search+filter+rank via the registry without a torrent client.

## Non-goals (deferred)

- Wanted-queue producers (Follow D3 / Ratio C1) → waves 4-5
- Per-series QualityProfile producers (Follow D4) → waves 4-5
- Circuit-breaker wiring on tracker transports (cb_policy reserved)
- Telegram grab-notify activation (subscriber is muted, gated by `acquire_notify_enabled`)

## ACCEPTANCE criteria

See `docs/features/grab-core/ACCEPTANCE.md` for executable shell commands.
