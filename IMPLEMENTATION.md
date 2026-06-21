# Implementation Progress — anchor

> For Claude: read this file at session start. Current feature tracker.

**Feature**: [helm-pr3] Board repatriation — columns + card positions off Projects v2 (minor)
**Version bump**: 0.10.0 → 0.11.0
**Branch**: feat/anchor
**PR merge**: manual (human-only)
**PR**: https://github.com/IznoCorp/kanban-mate/pull/52
**Design**: docs/features/anchor/DESIGN.md
**Master plan**: docs/features/anchor/plan/INDEX.md

## Phases

| # | Phase | Plan | Status |
|---|-------|------|--------|
| 1 | Native board store | docs/features/anchor/plan/phase-01-native-store.md | [x] |
| 2 | NativeBoardBackend decorator | docs/features/anchor/plan/phase-02-native-backend.md | [x] |
| 3 | Wiring + registry + daemon switch | docs/features/anchor/plan/phase-03-wiring-registry.md | [x] |
| 4 | Import migration + CLI | docs/features/anchor/plan/phase-04-import-cli.md | [x] |
| 5 | helm HTTP API board routes | docs/features/anchor/plan/phase-05-http-routes.md | [x] |
| 6 | Version bump + final gate | docs/features/anchor/plan/phase-06-version-gate.md | [x] |

## Review cycles

### Cycle 1

PR-review (`/implement:pr-review`, merge SKIPPED — human-only). Five Sonnet review agents
(code-reviewer, silent-failure-hunter, pr-test-analyzer, type-design-analyzer, comment-analyzer)
filtered against `docs/features/anchor/DESIGN.md`. Retained + fixed:

- **MAJOR** — `/api/board/*` store-root divergence (`http/board_routes.py:_get_store` used
  `len(registry)>1`; daemon/CLI use `len(enabled)>1`) → daemon + HTTP wrote *different* `board.json`
  when a 2nd project is registered-but-disabled (defeats the dual-writer flock guarantee, DESIGN §6.3).
- **MAJOR** — `GET /api/board/state` omitted `issue_number`+`title` (DESIGN §10:499 pins
  `cards:[{item_id,issue_number,title,column_key,index}]`) → now JOINs the forge issue set (fail-soft).
- **MEDIUM** — `place_card` accepted negative/out-of-range `index` (silent `list.insert` clamp) →
  now validated, fail-loud `400` (DESIGN §10 input contract).
- **MEDIUM** — HTTP `/move`,`/place` accepted empty `item_id` (phantom `""` card) → `400`.
- **MEDIUM** — brittle `"concurrency" in msg` 409/400 split → typed `VersionConflict(ValueError)`.
- **MEDIUM** — corrupt `board.json` raised opaque `JSONDecodeError` from the daemon tick → clear
  `ValueError("board.json at … is corrupt")`.
- **MEDIUM** — `snapshot()` empty-columns silent fallback to GitHub Status (non-authoritative) → logged loud.
- **MEDIUM** — docstring fixes (`import_board` "updatedAt"→POSITION page order; `cheap_probe` token wording).
- **MINOR** — `_nudge()` bare `except: pass` → `logger.debug(exc_info=True)`.
- **TESTS** — added cli/board.py coverage; combined-probe forge dimension; import `moved_in` branch;
  snapshot first-sight idempotency; index/empty-id validation; reorder/place 409; state JOIN + fail-soft.

Ignored (out of scope / precedent-consistent, not defects): `dict[str,Any]` board doc lacks a TypedDict
(quality, matches `fs_store` precedent); `_write` no dir-fsync (matches `FsStateStore.save`);
`forge:Any`/`mirror:Any` typing; `seed_board` private-member reach. Merge stays human-only; PR left OPEN.

Local gate after fixes: ruff + format + mypy + size green on the anchor diff; full suite 2094 passed,
9 skipped (the local `mcp/server.py` mypy noise + `tests/bin/*` failures are pre-existing, env-only,
in untouched files, and CI-clean on the 3.12 `[dev,ui,mcp]` install).

### Cycle 2

Adversarial verification of the cycle-1 fix commit (`9de426f`) by an independent code-reviewer:
all six fixes CONFIRMED correct against source (store-root matches `wiring_for_entry`; `/state` card
shape matches DESIGN §10:499; `place_card` range correct for the remove-then-insert order; internal
`index=None` callers unaffected; `VersionConflict` subclass caught before bare `ValueError` — no dead
handler; `_parse_board` routes both `load`/`_read` and preserves the empty-skeleton path; layering
guard green). **No new critical/major/medium finding.** Loop converges → Case A (no remaining
findings). Final squash-merge SKIPPED — merge is human-only. PR #52 left OPEN.

## Next action

All phases complete — run `/implement:feature-pr` (create the PR; CI owns the gate).
