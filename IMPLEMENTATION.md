# Implementation Progress — seed-caps

> For Claude: read this file at session start. Current feature tracker.

**Feature**: [O4] Seed Safety — download events + bandwidth caps (ticket #177)
**Type**: feat
**Version bump**: 0.75.2 → 0.76.0 (minor)
**Branch**: feat/seed-caps
**Ticket**: #177 — claimed (heartbeat live)
**PR merge**: auto — standing operator contract: adversarial review(s) + tests before merge.
**PR**: _(created after last phase)_
**Design**: docs/features/seed-caps/DESIGN.md
**Master plan**: _(to be defined after /implement:plan)_

## Non-negotiable invariants (DESIGN D1-D10, frozen)

- Scope = bandwidth caps + download events ONLY. `ratio`/`seed_time_minutes` share
  limits stay None — they belong to #173/#174.
- `None` config field = touch nothing (never reset an operator-set qBittorrent limit).
- A cap must never block a grab: clients without `TorrentLimiter` → warn once, add uncapped.
- Global caps re-asserted at run start, fail-soft on ApiError (run continues).
- Download events exactly-once via `download_marks` (migration 014), persist-before-emit
  (a crash loses the emit rather than duplicating it — advisory events).
- `DownloadProgressed` on 25/50/75 crossings only; Telegram subscribes DownloadCompleted
  ONLY; the web event feed shows all three (French labels, X7 no-raw-enum).
- `reconcile_wanted` gains REQUIRED `event_bus` + `client_items` dict — ALL callers updated
  (event_bus project contract).

## Phases

_(filled by /implement:plan)_

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:plan` to generate the phase plan from the design doc.
