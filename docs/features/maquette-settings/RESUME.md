# maquette-settings — where this stands, and what is left

Written at 58 % context so a fresh session finishes from it rather than from a transcript.
**Everything described as done is committed**; nothing below rests on an uncommitted edit.

## The head

Branch `fix/maquette-settings`, pull request **#588** (opened READY), version **0.98.85** — `main`
took 0.98.84 with #585 on 2026-09-12, so this was re-read and moved; re-read it again before the
final push.

    fb29ccdec  chore: bump to 0.98.85
    4227389ac  test: re-record the comment-reference baseline over lib/stacked-surface.ts
    6c8fea468  style: page_host under its ceiling, at 999
    253b907d7  fix: a surface says when it has POSED an entry, not merely when it is open
    809c1d40f  docs: the figures, the mutations and the register's closures
    a7dc2a3d0  fix: the ladder's rewind counts the stack instead of assuming it
    ef6a04c8f  test: re-record the comment-reference baseline (first)
    fe8f98221  fix: the settings the operator could not use by hand

## What is DONE, with the rule that reads it

| Entry | Rule | Holds |
| --- | --- | --- |
| B-332, B-361 — a rubric is an arrival, and draws a back that POPS | R165 `harness/topics.py` | 22, over both pages |
| B-341 — « Valider », and the two labels say what they are | R166 `harness/settings_editing.py` | 15 |
| B-342 — the mock keeps the value; a file changed on disk takes nothing | R166 | ″ |
| B-343 — the restart flag is the layer's, the banner reads a query | R166 | ″ |
| B-334, B-335 — both secret acts write the layer; the removal asks first | R167 `harness/secret_acts.py` | 14 |
| B-345's settings half — the conflict and the restart reachable at rest | R128 `harness/seeds_at_rest.py` | +5 (10 → 15, measured) |
| B-398 — the ladder's rewind counts the stack (route C, the operator's D5 exception) | R165 | 3 of the 22 |

**B-397 filed, not repaired** (a panel re-produced after an edit pushes a second entry — L13's).
**B-299 and B-300 made confirmable by hand and NOT closed** — the confirmation is the operator's.

Eight mutations, each falling on its own holds and nothing else: the table is in `DESIGN.md`.

## What is LEFT, in order

**State at `d7f01f8fa` (2026-09-12, 23:45).** `origin/main` merged once more at `a2721935f`
(#589), version **0.98.87**; `page_host.py` joined back to 999 after #589's `__main__` guard.
Done since the previous note, each with its reading:

- `--a11y` — `backAction` → `text-primary-text` (`f0d91157d`), light ceiling 162 → 149 recorded
  once; mutation 166 against 149. The steward verified the arm stable (six readings, three builds).
- R74 `bridge.py` repaired (`dd401c957`): `lib/stacked-surface.ts` steps back via
  `window.__bridge.back()`. 10 holds.
- R82 `journey.py` RE-AIMED (`1850ddeb4`, ruled): the maintenance topic left `SETTING_WALKS`,
  74 → 70 holds; mutation 74 holds, exit 1, the two named holds.
- R128 gained FIVE holds, not four (`3d99639a4`).
- Full run on `9ecce44d4`: 122 rules and 27 guards, no violation; a11y 149/149; oracle 36
  divergences, all heights on Réglages/Maintenance, ACCEPTED by the steward and recorded in
  DESIGN.md (`d7f01f8fa`). **The oracle reference is NOT re-recorded here** — the post-merge
  gesture is the steward's.
- Hold-counts on `9ecce44d4`: the two declared movements only (journey 74→70, seeds_at_rest
  10→15), but `failed = 1` on journey.py, green in the full run and the replay.

Left:

1. **The single hold-counts re-run, CAPTURED** — `<scratchpad>/holdcounts_capture.py` imports
   the tool unchanged and keeps the full output, duration, load and free memory of any rule that
   falls. If journey.py falls: name the mechanism (which hold, its reading, the wait, the load) and
   record it in B-307's body if it is that class, or as its own row. `failed` first; the two declared
   movements only. **No re-running until green.**
2. **`make check`** under `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder`, two workers, NEVER beside a
   harness run.
3. **Push** (under the tests lock), the PR body (draft at `<scratchpad>/pr-addendum.md`: the a11y
   repair, R74, R82 74 → 70, R128 five holds, the page_host line, the sequenced gates), then report
   with the CI run id. No reader round (operator, 23:30): a green, verified head is merged by the
   steward.

## The envelope

Shared lock (`sh scripts/heavy.sh <wave> …`) for anything touching `/tmp/tm-refonte` or 8899 —
`run.sh` in any tier, the oracle, `harness-hold-counts.py`, a rule replay. **Every pytest run,
`make check` and `git push`** (its hook runs the suite) goes under ONE lock shared by all waves,
`HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder` — the steward's rule of 2026-09-12, after the
system killed two waves' pushes running side by side. Own lock
(`HEAVY_LOCK=/private/tmp/tm-heavy-settings/holder`) for the rest: `npm`, the cheap guards. The
default 4 GB free floor stands (the 2560 override is revoked), `TM_HARNESS_JOBS=2`,
`PYTEST_XDIST_AUTO_NUM_WORKERS=3` (2 beside a harness run), `HEAVY_LOAD_CEILING=12` on the shared
mutex and 10 on the others, by the steward's measurement. Announce every shared-lock run to the steward, one line before and one
after. A replay helper is at `<scratchpad>/replay.sh` (acquires the served-copy lock, builds,
publishes, runs named rules).

## Two traps this wave paid for, so the next session does not

- **`git checkout --` restores to the last COMMIT.** Used to undo a mutation, it threw away an
  uncommitted repair with it. Commit first, mutate second.
- **A kill pattern that names the WRAPPER kills every run of the wave.** `pkill -f "heavy.sh
  <wave>"`, used to withdraw one harness run, also killed a `git push` that was in its pytest step
  under the wave's OWN lock — both locks go through the same wrapper, so the wrapper's name is not
  a selector for one of them. Kill by pid, or by the pattern of the command being WRAPPED.
- **« The surface is open » is not « the surface pushed an entry ».** A cold load and a driven state
  both open one without an entry; acting on the first reading pops something else's. The flag that
  settles it is in `lib/stacked-surface.ts` and clears itself.
