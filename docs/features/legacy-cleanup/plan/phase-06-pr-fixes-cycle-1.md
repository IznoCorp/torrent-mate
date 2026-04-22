# Phase 6 — PR fixes cycle 1

## Context

Fixes identified during PR #8 review cycle 1. Reviewer flagged three stale cross-references in `CLAUDE.md` that promise content removed or relocated by Phases 1-3. The DESIGN's Risk 4 grep missed these because `CLAUDE.md` used the literal placeholder `{N}` instead of digits.

All findings are coherent with DESIGN scope (Phase 2 was supposed to clean CLAUDE.md of legacy references).

## Sub-phase 6.1 — Fix CLAUDE.md stale cross-references

**Finding** (Major): `CLAUDE.md` contains three references that either promise non-existent content or point to relocated directories.

**Locations**:

- Line 10: `See \`docs/reference/architecture.md\` for version history and module map.` — architecture.md no longer contains a "version history" section.
- Line 106: table row `Directory layout, module map, version history, shared utilities, dependencies | docs/reference/architecture.md` — same issue, the reference's content description mentions "version history" which was removed.
- Line 113: `Also check version-specific planning docs under \`docs/v{N}-_/\` and archived versions under \`docs/archive/\`.`— the`docs/v{N}-_/`directories no longer exist (moved to`docs/archive/legacy-alpha/`).

**Severity**: Major — broken cross-references break the DESIGN's "no VX references in live docs" goal and make `CLAUDE.md` promise content that no longer exists.

**Scope**:

Edit ONLY `CLAUDE.md` at project root. NO other file changes.

**Acceptance criteria**:

1. Line 10: either remove the "version history" phrasing or restore a minimal pointer to archived history (preferred: simple rewrite without "version history").
2. Line 106: same principle — drop "version history" from the description column.
3. Line 113: rewrite to point at `docs/archive/legacy-alpha/` directly, drop the `docs/v{N}-*/` path reference.

**Suggested rewrites** (concrete):

- Line 10: `See \`docs/reference/architecture.md\` for the module map and package layout.`
- Line 106 (table row): `Directory layout, module map, shared utilities, dependencies | \`docs/reference/architecture.md\``
- Line 113: `Also check archived alpha versions under \`docs/archive/legacy-alpha/\` and archived features under \`docs/archive/features/\`.`

## Quality gates

- No Python code touched — skip ruff/mypy/pytest.
- After edit:
  ```
  grep -n "version history\|docs/v{N}" CLAUDE.md
  # expected: no output
  ```
- Global grep sanity:
  ```
  grep -n "docs/v\[0-9\]\|docs/v{N}" *.md docs/reference/*.md
  # expected: no output
  ```

## Commit

```
git add CLAUDE.md
git commit -m "fix(legacy-cleanup): remove stale CLAUDE.md cross-references to relocated/removed docs"
```

## Gate (exit)

- The three quoted lines no longer contain "version history" (line 10 / 106) or `docs/v{N}-*/` (line 113).
- `grep -n "docs/v{N}\|version history" CLAUDE.md` returns no output.
- No other file changes in this sub-phase.
