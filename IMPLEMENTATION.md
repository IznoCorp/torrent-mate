# Implementation Progress — rudder

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Directional arrow buttons for the agent terminal (mobile) — on-screen ↑/↓/←/→ quick-keys so a phone keyboard (no arrow keys) can move agent-menu selections (minor)
**Version bump**: 0.21.0 → 0.22.0
**Branch**: feat/rudder
**PR merge**: manual
**PR**: https://github.com/IznoCorp/kanban-mate/pull/118
**Track**: lite (skiff fast-track — no full DESIGN.md/plan dir)
**Design**: docs/features/rudder/SCOPE.md
**Master plan**: docs/features/rudder/SCOPE.md § "Checklist plan" (lite-lane — checklist serves as the plan)

## Phases

_(lite-lane — the SCOPE.md "Checklist plan" (4 steps) is the implementation plan; no separate /implement:plan phase dir)_

| # | Step | Status |
| --- | --- | --- |
| 1 | Extend `KEY_BYTES` with Up/Down/Right/Left (`AgentTerminal.jsx:26`) | [x] |
| 2 | Add four armed quick-key `Button`s ↑↓←→ in `ControlBar` (`AgentTerminal.jsx:391-421`) | [x] |
| 3 | i18n `tip.term_up/down/left/right` in en.yaml + fr.yaml | [x] |
| 4 | Optional: `Arrow keys` row in `TerminalHelp` cheatsheet (non-blocking) | [x] |

## Review cycles

### Cycle 1 (lite — max 2)

- **Reviewed**: PR #118 against `docs/features/rudder/SCOPE.md` (lite filter artifact). Lite dimensions:
  correctness, security, test-coverage. Inline Opus review + one adversarial Opus reviewer (no Sonnet
  dispatch per operator rule); review scoped to the 63-line additive UI diff.
- **Grounded facts**: `sendKey` (`AgentTerminal.jsx:265-272`) forwards `KEY_BYTES[name]` over the
  existing `{type:"input"}` frame while `armed` — no logic change needed; buttons sit in the
  `armed && (…)` block (`:402`) wired `onSendKey → sendKey`; ANSI bytes correct
  (`\x1b[A/B/C/D` = Up/Down/Right/Left, no transposition); `npm run build` exits 0; version synced
  across all 4 files (0.22.0); i18n symmetric en/fr.
- **Findings**: no critical/major. One **medium→retained** (DECCKM normal-mode-only): buttons send
  DECCKM-off cursor bytes while the native keyboard path (xterm.js `onData`) is DECCKM-aware, so they
  can diverge for an application-cursor-keys-mode TUI. Coherent with SCOPE's deliberate normal-mode
  choice; not a design contradiction. **Fix (in-scope, doc-only)**: added a "Known limitation"
  note to SCOPE.md acknowledging the divergence + the future-enhancement path (reading
  `term.modes.applicationCursorKeysMode`). A code change was rejected as scope creep on the lite lane
  (SCOPE guarantees "no logic change"); the feature works for its stated target (Ink/readline menus).
- **Security / test-coverage**: clean — no new input surface (reuses the gated raw-byte path), no new
  dependency; web/ has no JS test framework (project convention — verification is build + manual).
- **Outcome**: loop exits (no remaining critical/major/medium code findings). PR left **OPEN** for a
  human to merge (merge = human-only). Note for the merger: PR is currently CONFLICTING/DIRTY vs main
  and has no CI checks reported — resolve conflicts before merge.

## Next action

Human review + merge of PR #118 (merge is human-only; this skill does not merge).
