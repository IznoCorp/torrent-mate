# Implementation Progress — conduit

> For Claude: read this file at session start. Current feature tracker.

**Feature**: MCP helpers — expose the board as an additive stdio MCP read+write surface (type: minor)
**Version bump**: 0.7.1 → 0.8.0
**Branch**: feat/conduit
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/conduit/DESIGN.md
**Master plan**: docs/features/conduit/plan/INDEX.md

## Phases

| # | Phase | Plan | Status |
|---|-------|------|--------|
| 1 | Layering guard + behaviour-preserving relocations | docs/features/conduit/plan/phase-01-layering-relocations.md | [x] |
| 2 | MCP pure shell — pin, resources, tools (SDK-free) + unit tests | docs/features/conduit/plan/phase-02-pure-shell.md | [x] |
| 3 | SDK server + `kanban mcp` command + roundtrip test | docs/features/conduit/plan/phase-03-server-cli.md | [x] |
| 4 | Lifecycle wiring — `.mcp.json` + `enabledMcpjsonServers` | docs/features/conduit/plan/phase-04-lifecycle-wiring.md | [x] |
| 5 | Version bump + final gate | docs/features/conduit/plan/phase-05-version-gate.md | [x] |

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

### Cycle 1

5 review agents ran against PR #39 (code-reviewer, pr-test-analyzer, silent-failure-hunter,
type-design-analyzer, comment-analyzer). Findings filtered against DESIGN §6/§7/§12. No design
contradiction. Retained + fixed:

- **F1 (critical)** — `adapters/workspace/base_sync.py:150` printed the happy-path "Fast-forwarding"
  message to **stdout**. Since `update_main` runs inside the stdio MCP server (stdout = JSON-RPC
  frames), a clean fast-forward would corrupt the protocol stream. Fix: route the line to `stderr`
  (behaviour-preserving — informational) + a regression test asserting `stdout == ""`.
- **F2 (major)** — `mcp/tools.py:update_main` was the only write tool skipping the PAUSE kill-switch
  floor that DESIGN §7 mandates for *every* write tool. Fix: thread `store` in, refuse (zero git I/O)
  under PAUSE; server dispatch passes `store`.
- **F3 (medium)** — `update_main` had no behavioural test and `progress`'s stage-sticky route was
  untested (DESIGN §12 requires per-write-tool routing tests). Fix: added routing + PAUSE tests.
- **F4 (medium)** — `move` leaked the bare `KeyError` repr (losing the "known columns: …" hint) on an
  unknown column, breaking the friendly-refusal contract. Fix: catch `KeyError`, return a refusal
  string; test added.
- **F5 (medium)** — `update_body`'s `set_field`/`append_section` array schemas were length-unbounded
  → a malformed (1/3-element) array `IndexError`'d out of the tuple-unpack. Fix: `minItems/maxItems: 2`
  so the SDK rejects it up front; both-/neither-mode XOR refusal tests added.
- Minor folded in: `resolve_target_column` docstring generalised (CLI → caller-supplied; now shared
  with the MCP `move` tool); a happy-path `move`-through-SDK roundtrip test (GAP-5 marshaling).

Ignored (out of scope / pre-existing / design-preference): `update_body` sum-type refactor (XOR is
runtime-enforced + tested), `queue` corrupt-marker observability (pre-existing intentional degrade),
comment line-number citation nits, the 36 env-only `tests/bin/*` failures (worktree pin + `KANBAN_*`
env leak; identical on pre-fix HEAD — 36 failed/2038 passed → 36 failed/2047 passed, CI-clean).

Gate after fixes: ruff ✓, ruff format ✓, mypy --strict (231 files) ✓, affected suites 312 passed
(+9 new). PR left **open** for human merge (merge = human-only).

## Next action

Cycle 1 fixes pushed. PR #39 open for human merge. Re-review (cycle 2) confirmed no remaining
critical/major/medium findings.
