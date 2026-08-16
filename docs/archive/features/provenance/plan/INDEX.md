# Plan — provenance (F0: spine + #30)

Design: `docs/archive/features/provenance/DESIGN.md` · Epic: `docs/archive/features/provenance/EPIC-ROADMAP.md`

Advisory overlay throughout: FS + existing stores stay truth; every provenance write
is best-effort (never fails a pipeline step); every read is fail-soft (missing/stale
→ fall back to #29 → free match). Manual/direct grabs create no row and are unaffected.

| #   | Phase                                   | File                            | Status |
| --- | --------------------------------------- | ------------------------------- | ------ |
| 1   | Schema + ProvenanceStore                | phase-01-schema-store.md        | [ ]    |
| 2   | Grab + ingest write points              | phase-02-grab-ingest.md         | [ ]    |
| 3   | Sort/rename + dispatch write points     | phase-03-sort-dispatch.md       | [ ]    |
| 4   | #30 consumer — scrape identity resolver | phase-04-scrape-consumer.md     | [ ]    |
| 5   | Reconcile + advisory-overlay hardening  | phase-05-reconcile-hardening.md | [ ]    |

Each phase gate: `make lint` + `make test` green, new tests rouge-avant, no regression
on the manual/direct grab path.
