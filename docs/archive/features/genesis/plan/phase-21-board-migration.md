# Phase 21 — Live board migration to the transitions-only model (personal-scraper)

> After phase 20 lands the transitions-only engine, migrate the live `IznoCorp/personal-scraper` board
> (currently stale: 11 columns, no `transitions.yml` → was running the legacy column-class fallback).
> Each sub-phase = ONE commit. This phase touches the LIVE GitHub board (outward-facing) — narrate +
> verify each step; idempotent operations only; never delete the 50 Backlog cards.

---

## 21.1 — regenerate the personal-scraper per-repo tier (add `Prepare feature` + write `transitions.yml`)

**Files**: none in-repo (operational) — runs `kanban init` / `write_transitions_yml` against the live board;
records the outcome in IMPLEMENTATION.md.

- [ ] Re-run `kanban init` for `IznoCorp/personal-scraper` (idempotent): `ensure_columns` ADDS the missing
      `Prepare feature` Status option (12-column set), `ensure_labels` is a no-op, the config + registry are
      refreshed, and `write_transitions_yml` writes `<clone>/.claude/kanban/transitions.yml` (the PoC flow) +
      the bare `columns.yml`. Verify: no existing column removed, the 50 Backlog cards untouched.
- [ ] Restart the daemon (`pm2 restart kanban`) so it loads the new `transitions.yml` (transitions-only model
      active). Verify via `kanban doctor` (all PASS) + confirm the daemon now resolves moves against the
      whitelist (a log line / a dry probe), NOT the column-class fallback.
- [ ] Record in IMPLEMENTATION.md: the board is migrated; the PoC flow is live (Backlog→Spec launches
      `/implement:brainstorm`, etc.).

```bash
# operational — no source commit; record-only commit:
git commit --allow-empty -m "chore(genesis): phase 21 gate — migrate personal-scraper board to the transitions-only model (Prepare feature column + transitions.yml)"
```

---

### Phase 21 Gate

1. `kanban doctor` — all PASS against the migrated board.
2. The board has the 12 columns incl. `Prepare feature`; `<clone>/.claude/kanban/transitions.yml` exists +
   parses (the rendered PoC flow); `columns.yml` is the bare set.
3. A controlled live check (operator-gated): move ONE card `Backlog → Spec` → the daemon LAUNCHes
   `/implement:brainstorm` (the PoC's first stage), proving transitions-only triggering on the real board.
   Then `kanban cancel <issue>` (teardown) to clean up.
