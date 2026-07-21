# Phase 8 — API honesty + tracker symmetry + dry-run (standalone)

## Gate

```bash
make lint && make test && make check

# Dead machinery removed with no live caller left behind
rg -n "IDCrossRef" -g '*.py' personalscraper/ tests/               # 0 after deletion (or only a documented survivor)
rg -n "gather_cross_refs" -g '*.py' personalscraper/ tests/        # 0 — cross-ref flow uses external_ids

# ingest decoupled from qbittorrentapi exception types
rg -n "qbittorrentapi\." -g '*.py' personalscraper/ingest/         # 0 — family-level errors only

python -c "import personalscraper" && echo IMPORT-OK

# ACC hook (DESIGN §10 ACC-07 — dry-run truthfulness, F4)
command python -m pytest tests -k "dry_run and rank" -q --no-header | grep -E "passed" && echo ACC-07-OK
```

## Objective

Restore honesty of the API-family and torrent/tracker contracts (DESIGN §5 standalone
majors): remove the `NotImplementedError` stubs from capability Protocols (a client
composes a Protocol only if it implements it — registry eligibility already handles
absence); delete the zero-implementation `IDCrossRef` machinery (YAGNI; the cross-ref flow
uses `external_ids`); collapse the dual legacy+capability method surfaces (pre-1.0, no
shims). Make the torrent/tracker layer symmetric: one provider-error mapping table per
family, title-quality parsing symmetric across trackers (torr9 included), Transmission
adder honesty (explicit `UnsupportedCapabilityError`, no silent label munging), and ingest
decoupled from `qbittorrentapi` exceptions via a neutral family-level error hierarchy.
Conformity fix **F4**: `grab --dry-run` runs the REAL chain (search→filter→dedup→**rank**)
with grab suppressed.

## Findings addressed

API-TRANSPORT-01/03/04 (NotImplementedError stubs; IDCrossRef zero-impl; dual method
surfaces), TORRENT-TRACKERS-01 (provider-error mapping per family), TORRENT-TRACKERS-03
(title-quality parsing asymmetry), TORRENT-TRACKERS-04 (Transmission adder honesty),
TORRENT-TRACKERS-05 + ACQUIRE-01 (`grab --dry-run` skips `rank()`), TORRENT-TRACKERS-08 +
PIPELINE-CORE-06 (ingest coupled to qbittorrentapi). Conformity fix F4.

## Code anchors (verified)

- NotImplementedError capability stubs: `personalscraper/api/metadata/_base.py` :323 (artwork URLs), :326 (keywords), :329 (videos), :332 (season details), :335 (notations), :338 (recommendations). Docstring reference in `personalscraper/api/torrent/_contracts.py:38`.
- IDCrossRef machinery: `IDCrossRef` imported in `personalscraper/api/metadata/registry/_semantics.py:15`, in `DIRECT_CAPABILITIES` :50 and the capability map :68; provider-facing helper `gather_cross_refs` referenced in `personalscraper/api/_contracts.py:80`. The live cross-ref flow uses `external_ids` (external-ids-flow feature).
- Torrent neutral error hierarchy: `personalscraper/api/torrent/_errors.py` — `UnsupportedCapabilityError` :40 (intentionally not an `ApiError`), re-exports `QBitAuthLockoutError` (from `qbittorrent.py`) + `ApiError`. Target: add `TorrentAuthError`/`TorrentUnreachableError`/`TorrentLockoutError` raised through the protocol.
- Torrent adders: `personalscraper/api/torrent/transmission.py`, `qbittorrent.py`, `_base.py`, `_factory.py`, `_contracts.py`.
- Tracker family: `personalscraper/api/tracker/` — `torr9.py`, `lacale.py`, `c411.py`, `_base.py`, `_fetch.py` (provider-error mapping today), `_factory.py`, `_registry.py`, `_contracts.py`. Title-quality parsing to make symmetric across all three (torr9 currently asymmetric).
- ingest coupling: `personalscraper/ingest/ingest.py:15` `import qbittorrentapi`; catches `qbittorrentapi.LoginFailed` :640, `qbittorrentapi.Forbidden403Error` :644, `qbittorrentapi.APIConnectionError` :653, and a BLE001 catch-all :657.
- F4 dry-run gap (verified): `personalscraper/commands/grab.py::_run_dry` :161 does search (:211) → `filter_to_episode` (:231) → `apply_hard_filters` (:244) → `dedup` (:245) → prints `deduped[0]` (:247-248) as "Top" — it never calls `rank()`. The real path `personalscraper/acquire/orchestrator.py` does `apply_hard_filters` :322 → `dedup` :329 → `rank(representatives, self._ranking)` :330. The grab docstrings/help (`grab.py:4`, `:42`, `:168`) already CLAIM "rank" — the code contradicts them.

Discrepancy note: the grab `--dry-run` help text and `_run_dry` docstring already say
"search + filter + dedup + rank", but the implementation prints `deduped[0]` **without**
`rank()`. F4 makes the code match its own contract (this is a genuine code-vs-doc lie, not
a stale audit). Pin it with the regression test before the fix.

## Tasks

1. **P8.1 — Hidden-consumer sweep (deletion safety, DESIGN §9).** Before deleting IDCrossRef / legacy method surfaces, run a repo-wide typed grep + memtrace caller check for each symbol; anything with a live caller is refactored, not deleted. Record the survivor set in IMPLEMENTATION.md. Verify: for every symbol slated for deletion, `rg -n "<symbol>" -g '*.py' personalscraper/ tests/` shows only definition + dead references.
2. **P8.2 — Remove NotImplementedError capability stubs (API-TRANSPORT-01).** Delete the six `NotImplementedError`-raising methods from `api/metadata/_base.py`; rely on registry eligibility (a client composes a capability Protocol only if it implements it). Verify: `pytest tests -k "metadata_capability or registry_eligibility" -q`; a provider lacking `keywords` is simply absent from that capability's chain (no runtime raise).
3. **P8.3 — Delete IDCrossRef machinery (API-TRANSPORT-03).** Remove `IDCrossRef` from `registry/_semantics.py` (`DIRECT_CAPABILITIES`, the map) and the `gather_cross_refs` helper from `api/_contracts.py`, plus any provider stub. Verify: `rg -n "IDCrossRef|gather_cross_refs" -g '*.py' personalscraper/ tests/` == 0; the external_ids cross-ref flow tests stay green.
4. **P8.4 — Collapse dual method surfaces (API-TRANSPORT-04).** Remove the legacy-method duplicates where a capability method exists (pre-1.0, no shims); keep the single typed surface. Verify: `pytest tests -k "metadata or transport" -q`; `make check` typed-api guardrail passes.
5. **P8.5 — Neutral torrent-error hierarchy + ingest decoupling (PIPELINE-CORE-06 / TORRENT-TRACKERS-08).** Add `TorrentAuthError`/`TorrentUnreachableError`/`TorrentLockoutError` to `api/torrent/_errors.py`; translate `qbittorrentapi` (and Transmission RPC) exceptions into them inside the client layer. Rewrite `ingest/ingest.py` to `import` no `qbittorrentapi` and catch only the neutral family errors; keep the systemic-abort (2-consecutive-failure) rule. Verify: `rg -n "qbittorrentapi\." -g '*.py' personalscraper/ingest/` == 0; `pytest tests -k "ingest and (auth or unreachable or lockout)" -q` green.
6. **P8.6 — Provider-error mapping + tracker title-quality symmetry (TORRENT-TRACKERS-01/03).** One provider-error mapping table per family (torrent + tracker in `_fetch.py`); make title-quality parsing symmetric across `torr9.py`/`lacale.py`/`c411.py` (torr9 included). Verify: `pytest tests -k "tracker_quality or torr9 or provider_error_map" -q`; torr9 parses the same quality tokens as the other trackers on shared fixtures.
7. **P8.7 — Transmission adder honesty (TORRENT-TRACKERS-04).** Make Transmission raise explicit `UnsupportedCapabilityError` for unsupported operations (e.g. label munging) instead of silently degrading. Verify: `pytest tests -k "transmission and (unsupported or label)" -q`; an unsupported label op raises rather than silently munging.
8. **P8.8 — F4 test-first: dry-run runs the real chain incl. rank().** Write a failing test asserting `grab --dry-run`'s printed top candidate equals the real chain's `rank(...)[0]` (search→filter→dedup→rank), grab suppressed. Prove it fails against `deduped[0]`. Then rewrite `_run_dry` to call the SAME chain the orchestrator uses (reuse `rank` + `self._ranking`), suppressing only the add. Verify: F4 test passes; `command python -m pytest tests -k "dry_run and rank" -q` green.
9. **P8.9 — Green.** Full gate. Verify: gate block above passes end to end.

## Non-goals

- Do not enable any qBittorrent "trust localhost"/auth-bypass toggle (security invariant).
- Do not change the tracker ranking WEIGHTS or the grab decision policy — F4 only makes the
  dry-run use the real ranked result (the operator's dry-run-first rule).
- Do not touch `TransportPolicy`/`HttpTransport` core semantics (bridge symbol; signature
  stable) beyond the error-translation seam.
- Do not re-open the resolve queue serialization (#287) or acquire store boundaries (P9).

## Commit

```
refactor(solidify): remove NotImplementedError capability stubs; delete IDCrossRef machinery
refactor(solidify): neutral torrent-error hierarchy; ingest decoupled from qbittorrentapi
refactor(solidify): symmetric tracker title-quality parsing; Transmission adder honesty
test(solidify): failing regression F4 — grab --dry-run shows the real ranked candidate
```

Phase-gate commit:

```
chore(solidify): phase 8 gate — API family honesty + tracker symmetry + ingest decoupling (F4)
```
