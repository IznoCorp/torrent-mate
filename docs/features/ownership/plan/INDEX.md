# ownership — Implementation Plan Index

> **Feature**: RP6 — "do I already own this?" predicate
> **Branch**: `feat/ownership`
> **Version bump**: 0.29.0 → 0.30.0
> **Design**: `docs/features/ownership/DESIGN.md`

| #   | Phase                                                            | File                                           | Status |
| --- | ---------------------------------------------------------------- | ---------------------------------------------- | ------ |
| 1   | Core port — `OwnershipChecker` Protocol + `NullOwnershipChecker` | [phase-01-port.md](phase-01-port.md)           | [ ]    |
| 2   | Indexer predicate — `is_owned` SELECT-only + golden tests        | [phase-02-predicate.md](phase-02-predicate.md) | [ ]    |
| 3   | Adapter + composition-root wiring + integration test             | [phase-03-wiring.md](phase-03-wiring.md)       | [ ]    |
| 4   | Docs + ACCEPTANCE + gate (`make check` green)                    | [phase-04-gate.md](phase-04-gate.md)           | [ ]    |
