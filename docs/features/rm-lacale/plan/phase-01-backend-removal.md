# Phase 1 — Backend removal, test rewrites (D9), historic-data regression (D2)

## Gate (inputs from previous phase)

Branch `refactor/rm-lacale` exists at version 0.77.0 (create-branch commit
`b8a6297f`); `DESIGN.md` on branch; baseline `make test` green on branch tip.
No code touched yet.

## Verified reality (rg run 2026-08-03 — re-run before executing)

`rg -i "lacale" --type py -l personalscraper/` → 17 files (see 1.5 list).
`rg -i "lacale" --type py -l tests/` → 53 files (see groups below).
Web files `web/routes/acquisition_ranking.py` + `web/models/acquisition.py` are
**phase 2** — at the end of phase 1 they are the ONLY remaining py hits.

## Sub-phase 1.1 — D2 historic-data regression test — `test(rm-lacale): …`

Pre-verify D2 assumptions (both must hold, else STOP and report):

- No SQL CHECK on `source_tracker`: `rg -n "CHECK" --type py personalscraper/acquire/` → none on tracker columns.
- No runtime coercion of stored tracker strings: `rg -n "ProviderName\(" --type py personalscraper/` → no call fed from a DB row.

Extend `tests/acquire/test_removed_tracker_history.py` (existing torr9 pattern):

- Parametrize the read-path tests over `("torr9", "lacale")`: obligation
  round-trip, unmet-obligation veto, served-obligation allow, record_dispatch
  MISS, grab-writer skip, cross-seed readable+inert, ratio_state readable.
- Do NOT parametrize `test_enum_no_longer_carries_the_removed_tracker` yet
  (lacale is still in the enum — that pin flips in 1.5).
- Add ONE web read-model case: seed a `seed_obligation` row with
  `source_tracker="lacale"` and assert the obligations read path
  (`web/models/acquisition.py` — `source_tracker: str`, line 221) renders it as a
  plain string, no crash (mirror fixtures from `tests/unit/web/routes/test_acquisition_read.py`).
- Update the module docstring: file now pins BOTH decommissioned trackers.
  This file becomes the single grep exemption for D8 AND D10.
  Gate: `pytest tests/acquire/test_removed_tracker_history.py -q` green (pre-removal).

## Sub-phase 1.2 — dissolve `test_lacale_client.py` — `test(rm-lacale): …`

`tests/unit/test_lacale_client.py` (25 hits) pins: policy/rps/REQUIRED_CREDS,
search + categories against live captures, and — in `TestLaCaleParseTitle` — the
**shared** `parse_title_quality` (`_quality.py`) fed with live LaCale titles.

- Relocate the `TestLaCaleParseTitle` cases into `tests/unit/test_tracker_quality.py`
  with title strings inlined (they are plain release names — keep them verbatim
  minus any "lacale" token). Shared-parser coverage must not shrink (D9).
- Delete the client-class tests (policy/search/categories): they test the class
  removed in 1.5; equivalents exist (`test_c411_client.py`, `test_torznab_client.py`).
- Delete `docs/reference/_samples/lacale/` (5 JSON fixtures — dead sample data, §1).
  Gate: `pytest tests/unit/test_tracker_quality.py -q` green; file gone.
  Trap: relocating imports — PostToolUse ruff strips an import without same-edit usage.

## Sub-phase 1.3 — fixture-string sweep A (acquire/core/fixtures) — `test(rm-lacale): …`

"lacale" is an arbitrary provider string here; rename to `c411`/`tr4ker`, same
behavior (D9). Files (hit counts from the 2026-08-03 grep):
`tests/acquire/`: test_record_dispatch (42), test_dedup (36), test_orchestrator (18),
test_service (15), test_store (12), test_crash_window (10), test_domain (5),
test_delete_authority (3), test_factory (3), test_migrations (3), test_search_pass (3),
test_filters (2), test_search_error_taxa (2), test_filter_to_movie (1),
test_grab_auth_event (1), test_grab_transmission_add (1), test_orchestrator_bandwidth_caps (1).
`tests/core/test_delete_permit.py` (2).
`tests/fixtures/event_samples.py` (11) — event factories (GrabSucceeded,
RatioMeasured, TrackerAuthFailed, CrossSeedInjected) carrying `source_tracker`/
`tracker="lacale"` → `c411`.
Gate: `pytest tests/acquire tests/core tests/fixtures -q` green (still pre-removal).

## Sub-phase 1.4 — fixture-string sweep B (e2e/commands/integration/unit) — `test(rm-lacale): …`

- `tests/e2e/test_golden.py` (6) + `tests/e2e/golden.py` (2): `[LaCale]-…` names
  test tracker-tag stripping in `_normalize_torrent_name` — swap to another
  bracket tag, keep behavior AND keep golden fixture data consistent (update any
  golden entry keyed on those names). `tests/e2e/test_assertions.py` (1),
  `tests/e2e/test_cross_seed_roundtrip.py` (3).
- `tests/commands/`: test_grab (4), test_grab_dry_run_rank (4), test_library_clean_e2e (1).
- `tests/integration/acquire/test_cross_seed_service.py` (108): `_TRACKER_LACALE`
  origin-tracker constant → rename onto a live pair (origin `c411`, target `tr4ker`);
  same scenarios. `test_acquisition_chain_e2e.py` (3); `tests/integration/test_provider_ids_e2e.py` (4).
- `tests/unit/`: test_tracker_parser_schema_drift (23), test_tracker_fetch (14),
  test_torznab_client (8), test_tracker_quality (7 pre-existing hits),
  test_http_transport_get_bytes (4), test_ranking_language_provider (4),
  test_tracker_errors (3), test_c411_client (2 — reword "reused from LaCale"
  comments to point at shared `_quality`; ALSO reword its torr9 comment generically).
- `tests/unit/web/routes/test_acquisition_read.py` (14) + `tests/unit/web/test_no_tracker_call_on_read.py` (1):
  fixture strings → `c411`. (`test_acquisition_ranking_preview.py` waits for phase 2.)
  Gate: `pytest tests/e2e tests/commands tests/integration tests/unit -q` green.

## Sub-phase 1.5 — backend source removal + membership tests — `refactor(rm-lacale): …`

Delete/purge (REAL file list, verified 2026-08-03):

- DELETE `personalscraper/api/tracker/lacale.py`.
- `api/tracker/_factory.py` — registry entry L30, docstring L40, comment L119.
- `api/_activation.py` — PROVIDER_CREDS L34, PROVIDER_OPTIONAL_SECRETS L100, docstring L123.
- `api/_contracts.py` — `ProviderName.LACALE` L49 (then `rg -n "LACALE" --type py personalscraper/ tests/` → only the exempted regression file).
- Docstring/comment purges: `api/tracker/_contracts.py` L9,34; `_quality.py` L9,11;
  `_fetch.py` L130,238; `_errors.py` L99; `_base.py` L63 (+ reword its torr9
  comment generically); `_registry.py` L162; `torznab.py` L364;
  `api/metadata/registry/_types.py` L38; `acquire/events.py` L161,223,243,260,274;
  `acquire/domain.py` L241; `acquire/_cross_seed_store.py` L57 → use `c411` as the example name.
  Rewrite membership tests in the SAME commit (they pin lacale existence):
  `tests/unit/test_tracker_factory.py` (51 — lacale as canonical factory key; add
  ABSENCE pin: unknown-tracker error for "lacale"), `test_activation.py` (4 — roster

* passkey-absent test onto c411), `test_api_config_models.py` (2),
  `test_tracker_config_errors.py` (7), `test_tracker_registry_priority_by_media_type.py` (21),
  `test_tracker_registry_close.py` (16), `test_tracker_capabilities_composition.py` (10),
  `test_tracker_registry_except_scope.py` (7 — raising-tracker fixture + module
  docstring recounting the lacale incident: reword as history),
  `test_tracker_registry_transports.py` (5), `tests/conf/test_tracker_config_priority_by_media_type.py` (6),
  `tests/integration/api/tracker/test_composition_root.py` (2).
  Also NOW parametrize the enum-absence test in `test_removed_tracker_history.py`
  over `("torr9", "lacale")` (D2 pin: `ProviderName("lacale")` raises).

## Phase gate (all green before phase 2)

1. `make lint` — zero errors.
2. `make test` — `NNNN passed`, 0 failed, **0 ERROR** (collection errors mean a
   stale import of `personalscraper.api.tracker.lacale` — grep it, fix, rerun).
3. Residual grep: `rg -i "lacale" -g '*.py' -g '!tests/acquire/test_removed_tracker_history.py' personalscraper/ tests/`
   → EXACTLY 2 files remain: `personalscraper/web/routes/acquisition_ranking.py`,
   `personalscraper/web/models/acquisition.py` (phase 2 scope). Anything else = missed.
4. `python -c "import personalscraper"` smoke.
