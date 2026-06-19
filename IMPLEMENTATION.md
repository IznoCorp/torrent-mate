# Implementation Progress — torr9

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Additional Tracker — torr9 (authenticated JSON search + freeleech RSS) (minor)
**Version bump**: 0.36.2 → 0.37.0
**Branch**: feat/torr9
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/torr9/DESIGN.md
**Master plan**: _(to be defined after /implement:plan)_

## Phases

_(filled by /implement:plan)_

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

Run `/implement:plan` to generate the phase plan from the design doc.

> **Prep note (research 2026-06-19):** torr9 captured LIVE — it is a full search
> tracker via the **authenticated JSON API** (`POST /auth/login` → JWT;
> `GET /torrents?q=<query>` + Bearer → `{limit,page,torrents[]}`), NOT browse-only.
> Item carries `is_freeleech` (bool) + `magnet_link` (auth-free download); **no
> seeders**. Passkey RSS feeds (`freeleech`/`recent`) feed the radar R1. Dual auth:
> JWT (`TORR9_USERNAME`/`TORR9_PASSWORD`) + passkey (`TORR9_PASSKEY`), creds in
> `.env`. Reference: `docs/reference/torr9-api.md`. Golden fixtures:
> `docs/reference/_samples/torr9/`. The prepared plan was regenerated from the
> corrected (post-capture) design.
