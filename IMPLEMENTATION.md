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
| 2   | Registry wiring + creds + config overlays + composition-root tests | phase-02-registry-wiring-creds-config.md       | [ ]    |
| 3   | Capabilities composition + schema-drift + ACC gate                 | phase-03-capabilities-schema-drift-acc-gate.md | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

Run `/implement:phase` to execute phase 2 (registry wiring + creds + config overlays + composition-root tests).

> **Phase 1 concern (carry to phase 3):** DESIGN.md is internally inconsistent on
> capabilities — Approach §1 says `Torr9Client(TorrentSearchable, FreeleechAware)`
> but the capabilities-test bullet + ACC-1 require `TorrentSearchable + CategoryListable`.
> Phase 1 implemented `(TorrentSearchable, CategoryListable)` and deliberately dropped
> `FreeleechAware` (freeleech is a structured `is_freeleech` bool in the search response —
> no separate re-check endpoint exists, so the protocol would be vacuous). The binding
> ACC-1 (search + get_categories) is satisfied. Phase 3's capabilities-composition test
> must assert `TorrentSearchable + CategoryListable` and NOT require `FreeleechAware`;
> reconcile DESIGN Approach §1 accordingly (awaiting user decision — do not silently drop).

> **Prep note (research 2026-06-19):** torr9 captured LIVE — it is a full search
> tracker via the **authenticated JSON API** (`POST /auth/login` → JWT;
> `GET /torrents?q=<query>` + Bearer → `{limit,page,torrents[]}`), NOT browse-only.
> Item carries `is_freeleech` (bool) + `magnet_link` (auth-free download); **no
> seeders**. Passkey RSS feeds (`freeleech`/`recent`) feed the radar R1. Dual auth:
> JWT (`TORR9_USERNAME`/`TORR9_PASSWORD`) + passkey (`TORR9_PASSKEY`), creds in
> `.env`. Reference: `docs/reference/torr9-api.md`. Golden fixtures:
> `docs/reference/_samples/torr9/`. The prepared plan was regenerated from the
> corrected (post-capture) design.
