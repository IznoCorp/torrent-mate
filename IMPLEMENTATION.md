# Implementation Progress — torrent-fetch

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP1a — Torrent fetch boundary (authenticated .torrent download + magnet exception, routable 401) (minor)
**Version bump**: 0.21.0 → 0.22.0
**Branch**: feat/torrent-fetch
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/torrent-fetch/DESIGN.md
**Master plan**: docs/features/torrent-fetch/plan/INDEX.md

## Phases

| #   | Phase                                                                   | File                            | Status |
| --- | ----------------------------------------------------------------------- | ------------------------------- | ------ |
| 1   | Errors module — `TrackerAuthError` + `TorrentFetchError`                | phase-01-errors.md              | [x]    |
| 2   | Transport binary GET — `get_bytes` + dedicated download circuit/limiter | phase-02-transport-get-bytes.md | [x]    |
| 3   | Fetcher module + public surface + docstring fix                         | phase-03-fetcher.md             | [ ]    |
| 4   | ACCEPTANCE.md + reference docs + `make check` gate                      | phase-04-acceptance.md          | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to start Phase 3.
