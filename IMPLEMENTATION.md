# Implementation Progress — torrent-write

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP1 — Torrent Write Capability (add + categorize + tags + limits) (minor)
**Version bump**: 0.20.0 → 0.21.0
**Branch**: feat/torrent-write
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/torrent-write/DESIGN.md
**Master plan**: docs/features/torrent-write/plan/INDEX.md

## Phases

| #   | Phase                                                                      | File                              | Status |
| --- | -------------------------------------------------------------------------- | --------------------------------- | ------ |
| 1   | `TorrentSource` + `TorrentLimits` value objects                            | phase-01-value-objects.md         | [x]    |
| 2   | `TorrentAdder` + `TorrentLimiter` Protocols + `UnsupportedCapabilityError` | phase-02-protocols.md             | [x]    |
| 3   | `TorrentItem.tags` field + mapper updates (qBit CSV + Transmission D5)     | phase-03-torrentitem-tags.md      | [x]    |
| 4   | `QBitClient.add()` + `_limit_kwargs()`                                     | phase-04-qbit-add.md              | [x]    |
| 5   | `QBitClient.apply_limits()` + composition assertions                       | phase-05-qbit-apply-limits.md     | [x]    |
| 6   | `TransmissionClient.add()` + `_labels()` + composition assertions          | phase-06-transmission-add.md      | [x]    |
| 7   | `AppContext.torrent_client` field                                          | phase-07-appcontext-field.md      | [x]    |
| 8   | Fail-fast in `_build_app_context()` (D3/D9)                                | phase-08-boot-failfast.md         | [x]    |
| 9   | Remove lazy inline `QBitClient` fallbacks                                  | phase-09-remove-lazy-fallbacks.md | [x]    |
| 10  | Reference docs updates                                                     | phase-10-docs.md                  | [x]    |
| 11  | Executable `ACCEPTANCE.md` + ROADMAP flip                                  | phase-11-acceptance-roadmap.md    | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Phases 1–10 complete. Next: Phase 11 (final) — executable `ACCEPTANCE.md` + ROADMAP RP1 flip.

> **Phase 9 re-scope (documented):** the plan estimated 3 files; reality was 23 — `run_ingest`'s
> signature change rippled through `pipeline_steps.py` (IngestStep/LegacyCallableStep — missed by
> the plan, would have broken the live pipeline) + ~20 test call sites. Phase 9 also fixed a
> Phase-8 boot-fail-fast regression (56 trailers/indexer CLI tests with bare-MagicMock configs
> tripping the fail-fast) — verified pre-existing at baseline SHA 9a9eac1d via a worktree run.
> Net: zero new failures, full suite green.
