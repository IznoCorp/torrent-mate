# seed-caps — Implementation Plan Index

> **Feature**: [O4] Seed Safety — download events + bandwidth caps (ticket #177)
> **Codename**: seed-caps · **Type**: feat · **Bump**: minor (0.75.2 → 0.76.0)
> **Branch**: feat/seed-caps · **DESIGN**: docs/features/seed-caps/DESIGN.md

## Phases

| # | Phase | File | Status |
|---|-------|------|--------|
| 1 | Config foundations + migration 014 + download_marks store | [phase-01-config-migration-marks.md](phase-01-config-migration-marks.md) | [ ] |
| 2 | Per-torrent caps + global caps (protocol, qBit impl, wiring) | [phase-02-caps-orchestrator-global.md](phase-02-caps-orchestrator-global.md) | [ ] |
| 3 | Events catalogue + reconcile signature change + emission + callers | [phase-03-events-reconcile-emission.md](phase-03-events-reconcile-emission.md) | [ ] |
| 4 | Subscribers + frontend labels + ACCEPTANCE + full gate | [phase-04-subscribers-frontend-acceptance.md](phase-04-subscribers-frontend-acceptance.md) | [ ] |

## Global Constraints

- `event_bus` is a REQUIRED parameter at every new emission site; ALL callers updated in the same phase.
- Emit-after-persist ordering for download events (marks persisted first, then events emitted).
- `ratio` / `seed_time_minutes` fields of `TorrentLimits` stay `None` (out of scope, #173/#174).
- ACCEPTANCE.md criteria must be executable shell commands with documented expected output (SH-16 rule).
- New tests choose unit / integration per `docs/reference/testing.md`; every phase ends with `make lint` + targeted pytest green.
- Each sub-phase = 1 commit; commit scope = `(seed-caps)`; format: `{type}(seed-caps): description`.
- Config drift rule: `config.example/acquire.json5` gains commented block for every new config key.
- DO NOT commit plan files; DO NOT modify IMPLEMENTATION.md (main session responsibility).
- Honor DESIGN.md decisions D1–D10 and §7 out-of-scope list verbatim.

## Design Decisions Reference (quick lookup)

| # | Decision |
|---|----------|
| D1 | Config at `acquire.bandwidth` (new `BandwidthConfig` on `AcquireConfig`) |
| D2 | `None` = touch nothing (per-field); never reset operator-set qBit limits |
| D3 | Per-torrent caps applied AT ADD TIME via `add(limits=)` — atomic |
| D4 | Clients without `TorrentLimiter` → log `grab.limits.unsupported` once, add without limits |
| D5 | Global caps re-asserted at start of every acquire run, fail-soft on `ApiError` |
| D6 | Download events emitted from `reconcile_wanted` — single truthful observation point |
| D7 | Exactly-once via `download_marks` table (migration 014); prune when row leaves open set |
| D8 | `DownloadProgressed` on 25/50/75% thresholds; Telegram only `DownloadCompleted` |
| D9 | `reconcile_wanted` gains REQUIRED `event_bus` + `client_items: dict[str, TorrentItem] \| None` |
| D10 | Humanized byte sizes in config (`"5MB"`), reusing `ByteSize` coercion pattern of `_ranking.py` |

## Out of Scope (§7)

- Ratio/seed-time share limits (→ #173/#174)
- Web write-path UI for bandwidth config
- Transmission implementations of either capability
- Scheduling/throttling windows (time-of-day caps)
