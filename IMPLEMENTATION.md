# Implementation Progress — torr9

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Additional Tracker — torr9 (authenticated JSON search + freeleech RSS) (minor)
**Version bump**: 0.36.2 → 0.37.0
**Branch**: feat/torr9
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/torr9/DESIGN.md
**Master plan**: docs/features/torr9/plan/INDEX.md

## Phases

| #   | Phase                                                              | File                                           | Status |
| --- | ------------------------------------------------------------------ | ---------------------------------------------- | ------ |
| 1   | Torr9Client + lazy JWT login + JSON search + golden tests          | phase-01-client-login-jwt-golden.md            | [x]    |
| 2   | Registry wiring + creds + config overlays + composition-root tests | phase-02-registry-wiring-creds-config.md       | [x]    |
| 3   | FreeleechAware re-check + capabilities + schema-drift + ACC gate   | phase-03-capabilities-schema-drift-acc-gate.md | [x]    |

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

All phases complete — run `/implement:feature-pr` (local gate → push → PR → CI → review).

> **FreeleechAware concern — RESOLVED (user decision 2026-06-19):** the DESIGN-vs-plan
> inconsistency flagged at phase 1 was decided by the user: **implement FreeleechAware**.
> A live probe confirmed torr9 exposes a real per-torrent detail endpoint
> (`GET /api/v1/torrents/{id}` → single torrent with `is_freeleech` + seeders/leechers),
> so `is_freeleech(torrent_id)` is a genuine pre-download re-check, NOT a vacuous stub.
> Phase 3 implements it; DESIGN + api-ref reconciled; ACC-8 added and passing. The class
> is now `Torr9Client(TorrentSearchable, CategoryListable, FreeleechAware)`. Detail-endpoint
> `seeders`/`leechers` for ranking is **deferred** (not in this feature).

> **Prep note (research 2026-06-19):** torr9 captured LIVE — it is a full search
> tracker via the **authenticated JSON API** (`POST /auth/login` → JWT;
> `GET /torrents?q=<query>` + Bearer → `{limit,page,torrents[]}`), NOT browse-only.
> Item carries `is_freeleech` (bool) + `magnet_link` (auth-free download); **no
> seeders**. Passkey RSS feeds (`freeleech`/`recent`) feed the radar R1. Dual auth:
> JWT (`TORR9_USERNAME`/`TORR9_PASSWORD`) + passkey (`TORR9_PASSKEY`), creds in
> `.env`. Reference: `docs/reference/torr9-api.md`. Golden fixtures:
> `docs/reference/_samples/torr9/`. The prepared plan was regenerated from the
> corrected (post-capture) design.
