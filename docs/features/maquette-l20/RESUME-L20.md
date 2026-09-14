# maquette-l20 — RESUME

## STATE BLOCK (rewritten at every boundary — at most 40 lines)

- **Updated**: 2026-09-14, phase 1 opening (Agent : l20 1).
- **Branch / worktree**: `feat/maquette-l20`, `/Users/izno/dev/worktrees/wave-l20`, cut from `main`
  at `4f242ecb3`; plan re-target `b7e600cc5`.
- **Phases done**: none.
- **Next**: phase 1 — the contract (`plan/phase-01-contract.md`).
- **Waiting on**: nothing. Phase 8 waits for L13b's merge AND the steward's word.
- **Rule numbers**: RULINGS-L20.md ruling 1 (a…h → R178–R185, j → R187, R186 unused).
- **Tooling**: `main`'s — tiers as separate invocations (`run.sh --contracts`, then
  `python3 frontend/maquette/oracle.py --check`), `TM_HARNESS_JOBS=2`.
- **Locks**: shared mutex `scripts/heavy.sh --class browser l20 …` (announce before/after to the
  steward; shared with `Agent : l13b 2`); tests lock `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder`;
  own lock `HEAVY_LOCK=/private/tmp/tm-heavy-l20/holder` for `npm ci` and builds.
- **Logs**: `~/Library/Logs/tm-l20/<phase>-<step>.log`.
- **Owed**: midpoint full suite after phase 5's commit; at phase 9 the full suite, `--a11y`,
  `--compare`, `make lint`, pre-push pytest, then ONE pull request opened READY.

---

## LEDGER (append-only)

- 2026-09-14 — handshake readings: origin/main `4f242ecb3`; highest rule R177 (the plan's « R160 »
  is stale); `__version__` 0.98.92; `engine/` holds no `states.js`; the shared mutex was held by l13b.
- 2026-09-14 — the demands register read « required and missing » **15** before phase 1 (the plan
  says 14 — a stale figure, not a defect; the before/after comparison uses 15).
- 2026-09-14 — DESIGN.md's three present-tense measurements of the dead `engine/states.js` re-pointed
  at the `60530dbd8` blob (steward's note); both commands re-run on that blob read 786 and 87.
