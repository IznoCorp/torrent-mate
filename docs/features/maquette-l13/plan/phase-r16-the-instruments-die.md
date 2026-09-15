# r·16 — The file and its readers die

2026-09-15 (ruling 111): r·15 measured ≥ 30 and was cut — r·15 the engine's last code dies, r·16 the engine's instruments die, r·17 the full gate and the pull request.

**Kind**: DELETION. **Cost**: opened by its own measure, re-cut if > 15 (measure 11).

## Measured

On `ddb63b108` (ruling 111's STOP D): 18 scripts name `legacy.js`, `engine/legacy`, the extractor, the builder or the
registers — `markup_verbs.py`, `markup_dressing.py`, `markup_anchors.py`, `check-markup-contracts.py`,
`check-css-tokens.py`, `check-frontend-boundaries.py`, `boundaries_addressing.py`, `check-state-ownership.py`,
`nofrench_states.py`, `nofrench_lexicon.py`, `check-no-french.py` (the French debt section), `check-mock-seeds.py`,
`build-mock-seeds.py`, `extract-maquette-fixtures.mjs`, `refresh-maquette-fixture.py`, `classify-rule-anchors.py`,
`rename_readers.py`, `frontend_size_ledger.py`; 6 tests; `resync.py` and the harness rules naming the engine;
`fixture-register.json`, `fixture-projections.json` (the schema arm's `answers` needs a home), `regions.json`,
`ci.yml`; B-497's fate. Each is read for what it reads of the engine and killed or re-aimed — what loses its subject
is removed, not new apparatus.

2026-09-15 (ruling 111-precision): this phase's FIRST act is deleting `engine/legacy.js` (unimported and comment-only since r·15), with what reads the file — measured by a probe on eb0a7b848 with the file moved aside: check-frontend-boundaries (typing arm, `allowed = {engine/legacy.js}`), check-no-french (the French debt section), check-mock-seeds (the extractor), check-maquette-unit-tests, check-state-ownership (`ENGINE_SOURCES`) turn red; `harness/said_and_done.py` (`dataset.rescrape` in legacy.js) and `harness/page_host.py` l.952 (the engine's page table, 999/1000 lines) read it.

2026-09-15 (ruling 113): r·16 measured ≈ 20–24 and was cut — r·16 the file and its readers, r·17 the fixture apparatus dies (new), r·18 the full gate and the pull request. r·16 keeps: `engine/legacy.js` deleted, the five probe guards, the size-ledger entry, `markup_verbs.py`'s `ENGINE`, `said_and_done.py`, `page_host.py`, their tests; `docs/reference/frontend-architecture.md` l.269/271 re-cite `design/src/engine/legacy.js@13a66a35b` (narrow authorization, diff shown in this file); `CLAUDE.md` is not edited by the implementer. The extractor, builder, register, classification/correspondence arms, the `answers` home, refresh-maquette-fixture and ci.yml:103–104 are r·17's.

## Gate

Per INDEX « Gates »: contracts + oracle + the rules touched, logs postdating the commit; every guard touched exits 0
and its tests pass under the tests lock.
