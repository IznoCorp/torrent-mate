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

**State on 2026-09-13, after the last merge of `main`.** `c5e0b1c58` passed the whole gate and was
pushed (CI run 34722645096); then #592 merged as `5eafd3cfc` (0.98.87) and #588 went CONFLICTING.
`origin/main` was merged a last time: seven conflicts — BUGS.md rows (B-396 from main, then
B-397/B-398), `i18n/fr.json` (both the `secret` and the `maintenance` notice blocks kept),
`comment-references-baseline.json` (re-recorded), the size ledger (`legacy.js` MEASURED at 31 444),
the version (**0.98.88**, main at 0.98.87), and the two a11y records (taken from this side, then
RE-RECORDED on the merged tree under the shared mutex — never hand-resolved). `check-bug-register`
and the 27 guards + typecheck: 28/28 exit 0.

Everything the gate read before that merge still stands, and each reading is in DESIGN.md: the
`.fback` repair (ceiling 162 → 149), R74 repaired, R82 re-aimed 74 → 70, R128 +5, the 36 oracle
divergences accepted (reference NOT re-recorded here — the steward's post-merge gesture), hold-counts
`failed` 0 with the declared movements only, B-307's sixth instance, the three new rules guarded
under `__main__` for #589's test, `make check` 11 263 passed.

Left:

1. **Push** under `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder` — the pre-push suite is the gate
   for this merge — re-reading main's version first.
2. **Read the CI run on the pushed head** (`gh run list --branch fix/maquette-settings`), report its
   id and each red job with its log to the steward. No reader round (operator, 2026-09-12 23:30):
   the steward verifies the files and merges a green head.
3. After the merge: delete the local branch and remove this worktree.

**The steward's address.** `Orch : TM frontend [7d99b6]` — the successor of `[8e18d6]`, which
answers nothing new since 2026-09-13. Every report, request and handshake goes to that exact name and
reference. Silence rule: 15 minutes without an answer → a fresh `ListAgents`, re-send to the session
whose NAME matches, else tell the operator.

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
