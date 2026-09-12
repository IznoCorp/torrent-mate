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
| B-345's settings half — the conflict and the restart reachable at rest | R128 `harness/seeds_at_rest.py` | +4 |
| B-398 — the ladder's rewind counts the stack (route C, the operator's D5 exception) | R165 | 3 of the 22 |

**B-397 filed, not repaired** (a panel re-produced after an edit pushes a second entry — L13's).
**B-299 and B-300 made confirmable by hand and NOT closed** — the confirmation is the operator's.

Eight mutations, each falling on its own holds and nothing else: the table is in `DESIGN.md`.

## What is LEFT, in order

1. **`page_host.py` replayed** — queued on the shared lock behind the gesture agent's oracle. Its
   one red was its own driven state (`maintTopic` left open while the walk promised « EVERY DIAL
   NAMED »); the dial is named and committed, so this is a confirmation, not a repair.
2. **`--a11y`** — THE OPEN QUESTION. CI run 34705845236 read `a11y[light]: 166 against a ceiling of
   162`: four new violations under `data-theme=light`, this wave's surfaces. **The ceiling is a
   RATCHET and does not move.** Name the four by selector and rule id from axe-core's own output,
   repair the ones that are this wave's, and put any that is an existing variant's debt to the
   steward with its selector.
   **The hypothesis, and it is not a reading**: `backAction` is `text-primary bg-transparent`,
   written for a SCREEN's bar, and this wave puts three of them on pages whose ground is
   `oklch(0.995 0 0)`. The computed pairs are in the steward thread. **A probe built to answer this
   without the shared lock was CAUGHT LYING** — it resolved `oklch()` through a canvas `fillStyle`,
   which keeps its previous value when it cannot parse one, so it read 1.00 for dark text on
   yellow. Discard it; use `--a11y`.
3. **The full suite once** on the final head (it has not run green end to end since the posed-entry
   repair).
4. **The oracle** — divergences ACCEPTED only on the states this wave draws (`settings-one`,
   `settings-field-*`, `settings-topic`, `settings-secrets`, `maintenance-topic`), zero elsewhere,
   or STOP B.
5. **Hold counts** — `failed` read FIRST.
6. **`make check`** — last run: 11 201 passed, and it stopped on the version bump, which is now
   0.98.85. Re-run it whole.
7. **Push, and the PR body** — the body is written and posted; add the run at
   `HEAVY_LOAD_CEILING=10` and why (the steward measured 12 of the load external to us).

## The envelope

Shared lock (`sh scripts/heavy.sh <wave> …`) for anything touching `/tmp/tm-refonte` or 8899 —
`run.sh` in any tier, the oracle, `harness-hold-counts.py`, a rule replay. Own lock
(`HEAVY_LOCK=/private/tmp/tm-heavy-settings/holder`) for everything else: `npm`, `make check`,
`pytest`, `git push`. `HEAVY_FREE_FLOOR_MB=2560`, `TM_HARNESS_JOBS=2`,
`PYTEST_XDIST_AUTO_NUM_WORKERS=3`, and `HEAVY_LOAD_CEILING=10` on the OWN lock only, by the
steward's measurement. Announce every shared-lock run to the steward, one line before and one
after. A replay helper is at `<scratchpad>/replay.sh` (acquires the served-copy lock, builds,
publishes, runs named rules).

## Two traps this wave paid for, so the next session does not

- **`git checkout --` restores to the last COMMIT.** Used to undo a mutation, it threw away an
  uncommitted repair with it. Commit first, mutate second.
- **« The surface is open » is not « the surface pushed an entry ».** A cold load and a driven state
  both open one without an entry; acting on the first reading pops something else's. The flag that
  settles it is in `lib/stacked-surface.ts` and clears itself.
