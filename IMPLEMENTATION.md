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
| 2   | `TorrentAdder` + `TorrentLimiter` Protocols + `UnsupportedCapabilityError` | phase-02-protocols.md             | [ ]    |
| 3   | `TorrentItem.tags` field + mapper updates (qBit CSV + Transmission D5)     | phase-03-torrentitem-tags.md      | [ ]    |
| 4   | `QBitClient.add()` + `_limit_kwargs()`                                     | phase-04-qbit-add.md              | [ ]    |
| 5   | `QBitClient.apply_limits()` + composition assertions                       | phase-05-qbit-apply-limits.md     | [ ]    |
| 6   | `TransmissionClient.add()` + `_labels()` + composition assertions          | phase-06-transmission-add.md      | [ ]    |
| 7   | `AppContext.torrent_client` field                                          | phase-07-appcontext-field.md      | [ ]    |
| 8   | Fail-fast in `_build_app_context()` (D3/D9)                                | phase-08-boot-failfast.md         | [ ]    |
| 9   | Remove lazy inline `QBitClient` fallbacks                                  | phase-09-remove-lazy-fallbacks.md | [ ]    |
| 10  | Reference docs updates                                                     | phase-10-docs.md                  | [ ]    |
| 11  | Executable `ACCEPTANCE.md` + ROADMAP flip                                  | phase-11-acceptance-roadmap.md    | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Phase 1 complete (commit 9be4c0ac). Next: Phase 2 — Protocols + `UnsupportedCapabilityError`.
