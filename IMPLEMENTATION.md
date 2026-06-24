# Implementation Progress — ensign

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Indicateurs visuel issues close — visual indicator for CLOSED issues on the
KanbanMateUI Board + Monitoring views (minor)
**Version bump**: 0.18.0 → 0.19.0
**Branch**: feat/ensign
**Track**: lite (skiff)
**PR merge**: manual
**PR**: _(created after last phase)_
**Scope**: docs/features/ensign/SCOPE.md
**Master plan**: docs/features/ensign/SCOPE.md (lite lane — the scope note's `## Plan` checklist is the master plan; no separate plan dir)

## Phases

_(lite lane — phases follow the SCOPE.md `## Plan` checklist)_

| #   | Phase                                         | Status |
| --- | --------------------------------------------- | ------ |
| B1  | Plumb backend (is_closed, touchpoints 1-6)    | [x]    |
| B2  | Serving endpoints (touchpoints 7-9)           | [x]    |
| F1  | Board panel closed badge (touchpoint 10)      | [x]    |
| F2  | Monitoring panel closed badge (touchpoint 11) | [x]    |
| F3  | i18n closed/closed_hint (touchpoint 12)       | [x]    |
| T   | Tests (pagination / monitor / board_routes)   | [x]    |

## Review cycles

### Cycle 1 (lite lane — track=lite, max 2)

- **Code review** (norms subset: correctness / security / test-coverage; filtered vs
  `docs/features/ensign/SCOPE.md`): implementation matches touchpoints 1–12 exactly —
  `is_closed` threaded query → `_content_fields` → `RawItem` → `Ticket` → `_to_ticket`,
  surfaced on both serving endpoints with a fail-soft `False` default, rendered as a muted
  `Badge`+`CircleSlash` indicator in BoardPanel + MonitoringPanel, i18n keys present in
  `en.yaml`/`fr.yaml`. Tests assert real non-trivial values (closed=True/open=False/draft=False,
  issue numbers verified non-None). **No critical/major/medium code findings.**
- **Blocker fixed — merge conflict**: the PR was `CONFLICTING` (main advanced 0.19.0 → 0.19.3
  via skiff/buoy/moor, overlapping ensign's touchpoints). Merged `origin/main` into the branch;
  code files auto-merged cleanly, only the four version files conflicted → reconciled to **0.20.0**
  (minor feature on top of 0.19.3), incl. `plugin/.claude-plugin/plugin.json` for the
  version-sync manifest tests. PR is now `MERGEABLE`.
- **Gate**: ruff clean, mypy clean (156 files), full suite **2599 passed**; the 40 remaining
  failures are all `tests/bin/` + `tests/cli/test_doctor.py` — proven environmental (the helpers
  are pinned to #82 and `KANBAN_ROOT` is set in this PM2-spawned worktree; identical failures on a
  clean `origin/main` checkout in the same env — they are CI-clean).
- **Outcome**: no fix-phase needed (Case A — only the conflict blocker, now resolved + pushed).
  Loop exits at cycle 1. Merge left to human (merge = human-only).

## Next action

All phases complete; review cycle 1 clean. PR #107 conflict resolved and pushed (now MERGEABLE).
Awaiting human review + merge (merge = human-only).
