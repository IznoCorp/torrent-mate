# Implementation Progress — torrent-write

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP1 — Torrent Write Capability (add + categorize + tags + limits) (minor)
**Version bump**: 0.20.0 → 0.21.0
**Branch**: feat/torrent-write
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/36
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
| 11  | Executable `ACCEPTANCE.md` + ROADMAP flip                                  | phase-11-acceptance-roadmap.md    | [x]    |
| 12  | PR review fixes — cycle 1 (bencode, qBit add, seed-time, +mediums)         | phase-12-pr-fixes-cycle-1.md      | [x]    |

## Review cycles

### Cycle 1 — 2026-06-02

pr-review-toolkit (5 agents) + Opus filter vs DESIGN. Findings **independently
reproduced** before classification (evidence-before-severity). All are
implementation bugs within DESIGN scope — **no design contradiction**.

**Retained — blocking (must fix before merge):**

- **C1 (critical)** `_base.py` `_bencode_info_hash`: flat `data.find(b"4:info")`
  matches inside a sibling string value (`comment`/`announce`/`created by` sort
  before `info`) → crash or **silent wrong info_hash** (attacker-influenceable).
  Reproduced (crash). Fix: structural top-level dict walk.
- **C2 (critical)** `qbittorrent.py` `add()`: ignores `torrents_add` return +
  miscatches duplicate. Lib raises `Conflict409Error` on duplicate (uncaught →
  D7 broken) and returns `"Fails."` on failure (→ silent fake-success, D8
  violated). Verified vs qbittorrentapi v5.1.4. Fix: catch Conflict409 →
  idempotent; inspect return, raise on `"Fails."`; catch file/media errors.
- **M1 (major)** `qbittorrent.py` `_limit_kwargs`/`apply_limits`: `seed_time_minutes
  - 60`— qBit expects **minutes** (verified). 60× error. Test asserts the bug.
Fix: drop`\* 60`; fix test.

**Retained — medium:**

- Md1 `apply_limits` sends `-2` (reset-to-global) for the unspecified field →
  contradicts "None = no-op". Fix: only send provided fields.
- Md2 bencode not hardened (length bound / recursion depth) — folds into C1.
- Md3 base32 (32-char) magnets rejected → crash add path. Fix: accept + decode.
- Md4 `TorrentSource("")`/`from_file(b"")` pass exactly-one. Fix: reject empties.
- Md5 Transmission dup match `"duplicate" in str(exc)` fragile. Fix: `"torrent-duplicate"`.
- Md6 boot tests miss `enabled=False` + factory-raise propagation. Fix: add tests.
- Md7 doc rot: `_contracts.py` docstring + `architecture.md` say "5 protocols"
  (now 7) — DESIGN §5.2 asked to update. Fix: correct counts/tables.

**Minor (bundle opportunistically):** Transmission D6 hashString cross-check
unwired (log.warning on mismatch); `info_hash` vs `hash` param naming;
`UnsupportedCapabilityError` extends Exception (add intent comment); misleading
`patch.object(info_hash)` stub; `_errors.py` module docstring.

**Verdict:** Case B → fix phase 12 generated; run `/implement:phase`, then
re-push (CI) + re-review. PR #36 **blocked** until C1/C2/M1 fixed.

## Next action

**All phases (1–12) complete.** Cycle-1 review fixes landed (C1 bencode, C2 qBit add, M1 seed-time + 7 mediums) — each independently re-verified, `make check` exit 0, design-gaps audit `--strict` = 0 findings. Run `/implement:feature-pr` to re-push PR #36 + re-poll CI, then `/implement:pr-review` cycle 2.

> **Phase 9 re-scope (documented):** the plan estimated 3 files; reality was 23 — `run_ingest`'s
> signature change rippled through `pipeline_steps.py` (IngestStep/LegacyCallableStep — missed by
> the plan, would have broken the live pipeline) + ~20 test call sites. Phase 9 also fixed a
> Phase-8 boot-fail-fast regression (56 trailers/indexer CLI tests with bare-MagicMock configs
> tripping the fail-fast) — verified pre-existing at baseline SHA 9a9eac1d via a worktree run.
> Net: zero new failures, full suite green.
