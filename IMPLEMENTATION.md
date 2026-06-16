# Implementation Progress — tracker-auth

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP7 — Tracker Auth Lifecycle (observability): TrackerAuthFailed event on 401 + Transmission add() fix (minor)
**Version bump**: 0.33.0 → 0.34.0
**Branch**: feat/tracker-auth
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/202
**Design**: docs/features/tracker-auth/DESIGN.md
**Master plan**: docs/features/tracker-auth/plan/INDEX.md

## Phases

| #   | Phase                                      | File                                   | Status |
| --- | ------------------------------------------ | -------------------------------------- | ------ |
| 1   | TrackerAuthFailed event + catalog plumbing | phase-01-event-catalog-plumbing.md     | [x]    |
| 2   | Grab emit + Transmission add() fix         | phase-02-grab-emit-transmission-fix.md | [x]    |
| 3   | PR #202 review fixes (cycle 1)             | phase-03-pr-fixes-cycle-1.md           | [x]    |

## Review cycles

### Cycle 1 — PR #202 (CI green)

Adversarial review (5 dimensions × refute-by-default): 6 findings, **4 confirmed**, 2 refuted.

- **major** (silent-failure) — orchestrator `except ApiError` swallow around `add_tags()` is defeated: real tagger clients raise raw `transmission_rpc.TransmissionError` / `qbittorrentapi.APIError` (not `ApiError`), so a tag failure escapes the swallow + outer ladder + service isolation → whole-batch abort. → Phase 3.1.
- **major** (silent-failure) — the tag-failure test injects `personalscraper.ApiError`, the type real clients never raise → vacuous. → Phase 3.1/3.2.
- **medium** (tests) — `TrackerAuthFailed` omitted from `_ALL_ACQUIRE_EVENT_CLASSES`; the formatter is never exercised (DESIGN §8.1 item 1 unmet). → Phase 3.3.
- **minor** (tests) — non-`TorrentTagger` skip branch not explicitly asserted. → Phase 3.4.
- _refuted_: dropped golden `tags` assertion (recovered + strengthened in the new test); tag_failed warning lacks a remediation field (DESIGN-sanctioned non-essential provenance).

Fix scope expands into merged seed-pure client code (`transmission.py`/`qbittorrent.py`) because the Phase 2 add-then-tag swallow depends on the `TorrentTagger` contract DESIGN §4.2 assumed but the clients never honored. Layering-correct fix: translate at the client boundary.

Cycle-1 fixes (Phase 3, commits `ea84f9eb` + `cfb8978f`): client-level `ApiError` translation (both clients, `add_tags`/`remove_tags`) + 5 regression tests (mutation-proof, re-reproduced independently for both clients) + `Raises: ApiError` on the `TorrentTagger` protocol + `TrackerAuthFailed` formatter exercised + skip-branch assertion.

### Cycle 2 — PR #202 (re-review of the cycle-1 fix)

Focused re-review (fix-resolution + regression-hunt × refute-by-default): the 2 major + 1 medium are **resolved**. 1 **minor** confirmed — the skip-branch assertion shipped in cycle 1 was vacuous (`not hasattr(...)` short-circuits on `MagicMock(spec=TorrentAdder)`). Fixed in `acd4b2c9` with a non-vacuous precondition assertion (`not isinstance(client, TorrentTagger)`), verified to fail when the client is a tagger. No new defects introduced by the fix. **Loop converged (Case A — no critical/major/medium).**

## Next action

Converged + CI re-run pending on `acd4b2c9`. Merge mode **manual** → hand off to operator for squash merge of PR #202.
