# maquette-mock-layer — resume note

Written at a ROTATION, not a stand-down: the operator ordered on 2026-09-12 that no agent runs in
tmux, and this session is replaced by one in an iTerm2 tab at its unit boundary (B-396). The wave
is NOT finished. Read `BRIEF.md` first, then this file, then `DESIGN.md` §§ 1–3.

Worktree `/Users/izno/dev/worktrees/wave-mock-layer`, branch `fix/maquette-mock-layer`, cut from
`origin/main` at `561ac7a39` (0.98.84). Orchestrator: `Orch : TM frontend [8e18d6]`. Register block
**B-470 to B-489** (B-470…B-474 used), rules **R170+** (R170…R172 used).

## The head

The commit that carries this file. Verify, never believe:

    git remote update origin >/dev/null && git log --oneline -6
    git status --short                     # must be empty
    git ls-remote --heads origin fix/maquette-mock-layer

## DONE — each with the rule that reads it

| Entry | Commit | Rule | Run | Mutation |
| --- | --- | --- | --- | --- |
| **B-379** the layer answers the declared success code | `9da6fd556` + `63fb37de1` (the outside-import allowance) | **R170** `harness/declared_codes.py` — in the `--contracts` tier | 15 holds, no violation | `const success = 200` → 4 violations naming the three codes and the latency dial |
| **B-383** (its two verbs) + **B-470** (the sheet's twin) + **B-473** (`__verbNames`) | `4613cd681` | **R171** `harness/said_and_done.py` — full suite | 17 holds, no violation | both `send(...)` removed → 7 violations: the three sheet holds, the panel's call, the real run's call and state, the blank run's call |
| **B-396** a second ambiguous folder | `cbd933f9f` | **R172** `harness/two_picks.py` — full suite | 16 holds, no violation | S.W.A.T.'s candidates emptied → 5 violations, the first naming it: « the second folder is picked INSIDE the first one's window » |

Filed and **open**, not this wave's to repair: **B-471** (`readMediaSeasons` declares one shape and
answers another; the conformance test reads only the first level), **B-472** (`heavy.sh`'s lock is
a polled `mkdir` with no queue — B-386's family), **B-474** (a folder panel's « Résoudre → » resolves
whichever resolution screen was last open; no finger reaches a named folder's arbitration).

**Two things R172's mutation says that its green run does not**: t6 stays green with the candidates
gone, because its pick goes through `__queueActions` and needs no card — it reads the put-back
mechanism, not the seed; and t4's « comes back at the index it held » is vacuously true when B was
never picked, which is why t2's « both are out » is written before it and falls first.

**B-383's other two verbs are not this wave's**: « Remplacer la valeur » is the settings wave's
(B-334, #588), « Lancer la veille maintenant » is L20's (DOIT-6, `POST /api/acquisition/detect`).
That split is NOT yet written into B-383's body — see LEFT, step 3.

## LEFT — in this order

1. **B-380 — one season family.** The operator's orchestrator's rulings of 2026-09-12, verbatim in
   substance, and binding:
   - **AIRED is DERIVED from the catalogue's own episode `airDate`s** (≤ the frozen TODAY,
     2026-08-10) — **no new field**. The measurement behind it, with its command in `DESIGN.md` to
     write: over every season both families know, **39 agree / 5 disagree / 0 without dates**; eight
     of the register's thirteen « disagreements » were the DENOMINATOR read in the wrong place
     (the catalogue's `episodes` total compared to `seasons.json`'s `aired`), not data. Record that
     table and sentence in B-380's body.
   - **`seasons.json` is corrected TOWARDS what really aired, on the five lines**, through the
     **ENGINE fixture** (`SEASONS` in `engine/legacy.js`) and then
     `python3 scripts/build-mock-seeds.py --write` — **never the seed by hand**: `SEASONS` is a
     NON-converted family and `check-mock-seeds.py --arm correspondence` refuses a seed that
     differs from its fixture. Five numbers in place, no line added — say the ledger figure.

     | show | season | `seasons.json` aired now | aired by the dates | catalogue total |
     | --- | --- | --- | --- | --- |
     | American Dad! | 16 | 24 (owned 24) | 20 | 20 |
     | Silo | 3 | 7 (owned 6) | 6 | 10 |
     | Les Animaniacs | 1 | 134 (owned 93) | 172 | 172 |
     | Les Animaniacs | 2 | 15 (owned 11) | 12 | 12 |
     | Les Animaniacs | 3 | 26 (owned 13) | 46 | 46 |

     ⚠ **American Dad! S16's owned (24) would exceed its aired (20)** — correct owned with it and say
     so; an « 24/20 » row is not a correction.
   - **R128's « a season with a hole at rest » is the operator's too.** Silo S3 becomes « 6/6 · À
     jour » under the correction, BUT six other holes remain (Tintin S1–S3, Animaniacs S1–S3,
     measured) — so R128 should still hold. **Re-measure it on the corrected seed before deciding.**
     Only if no hole remains: keep Silo S3's hole by the DATE of its seventh episode (make it aired
     before TODAY), not by a count, and write in DESIGN why (two operator rulings, one fixture).
   - **The client half is ONE line**: `features/media/queries.ts:125`,
     `const aired = typeof season.ep === "number" ? season.ep : null;` takes the catalogue TOTAL as
     aired. The layer should answer the aired count — `readMediaSeasons` gaining a top-level
     `aired: {"<season>": n}` parallel to its existing `owned` map avoids the `SHEETS_RAW`
     projection entirely (only `answered.seasons` goes through `toEngineShapeEntry`); both
     `seasonsHeld` and `season-list.tsx`'s catalogue branch (`aired: season.ep`) must read it — ONE
     derivation (§13), in the layer. Contract field `x-unseeded`; regenerate types; recompute
     demands.
   - **(c) the upcoming information**: an unaired season or episode drawn as « à venir » (the date
     if known), offering NO act — `seasonUpcoming` already gates the act; draw the information
     beside it, minimal, copy in `i18n/fr.json`.
   - **(d) the rule**: both surfaces (the sheet's row and the follow panel's) on three titles agree
     with the seed, plus one upcoming season drawn as information with no act. Mutation = the
     denominator back to the catalogue's total. The Animaniacs sheet's season 5 (aired 1997) keeps
     its act.
   - List the named states the seed edit moves (`grep -rn "<title>" frontend/maquette/regions.json
     frontend/maquette/design/src/mocks/seeds/`) and the oracle divergences accepted on exactly
     those (D8) — zero elsewhere, or STOP B.
2. **ONE shared-lock `run.sh --contracts`** after B-380 — it covers every commit of the wave. Then
   the **FULL suite** once, `--a11y` 0, the oracle (divergences only on the states DESIGN lists), the
   hold-counts compare with `failed` read FIRST, `make check` (own lock). Announce each shared run
   to the orchestrator before and after.
3. **The register at delivery**: B-379, B-396, B-470, B-473 → `fixed #<PR>`. **B-383's body** gains
   the split — its two verbs fixed here, « Remplacer la valeur » owned by settings (B-334, #588),
   « Lancer la veille maintenant » owned by L20 — and its row goes `fixed #<PR>` only when both of
   this wave's halves are in (they are). B-380 → `fixed #<PR>` after step 1.
4. **Merge `origin/main`** before the push (settings #588 and tooling #589 may land first; the
   register's conflict has a shape — rows with rows in ascending order, bodies after, guard clean),
   version patch bump, wrapped push, `ls-remote`, PR READY with the brief's title, report.

## The envelope (unchanged, and loosened only where the orchestrator said)

- **Test suites serialize ACROSS WAVES** — the orchestrator's machine rule of 2026-09-12, 21:10:
  the pre-push suite (i.e. every `git push`), `make check` and ANY `pytest` run go under ONE lock
  shared by all waves, `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder`, because three concurrent
  suites are what the kernel was killing (this session's first push died at 96 %, `Terminated: 15`).
  Harness runs keep the shared harness mutex below. Never `--no-verify`.
- **Own lock** for `npm ci`, builds, `typecheck`, the unit tests, a private-bench replay:
  `HEAVY_LOCK=/private/tmp/tm-heavy-mock-layer/holder HEAVY_FREE_FLOOR_MB=2560 HEAVY_LOAD_CEILING=10 PYTEST_XDIST_AUTO_NUM_WORKERS=3 sh scripts/heavy.sh mock-layer <command>`
  — **`HEAVY_LOAD_CEILING=10` is the operator's word for tonight, for OWN-lock runs only; say it in
  the PR.**
- **Shared lock** (anything touching `/tmp/tm-refonte` or 8899):
  `HEAVY_FREE_FLOOR_MB=2560 HEAVY_LOAD_CEILING=12 TM_HARNESS_JOBS=2 sh scripts/heavy.sh mock-layer <command>`
  — only the THREE runs in LEFT step 2, each announced.
- **Per-commit proof without the shared lock** — the orchestrator's sequencing of 2026-09-12: own-lock
  `typecheck` + the maquette's unit tests + `make lint` + **all 27 cheap guards by EXIT CODE**, plus
  each touched rule replayed on a PRIVATE build:
  - the bench is `replay.py` in the previous session's scratchpad — re-create it: it re-points
    `served_copy.SERVED` / `STAMP` / `LOCK` to a private directory **before importing `common`**
    (so B-256's guard runs LIVE over the copy the rule reads — never stub it), publishes there,
    serves `harness/server.py --serve 8901 <private dir>`, rebinds `common.PROTOTYPE` to 8901, runs
    the rule, kills its host. Keep the copy OUT of the worktree. When #589 merges, switch to
    `TM_PROTOTYPE_URL` + `TM_SERVED_COPY` and say so.
- Gauge as the last call before every report; past 60 %, finish the unit, update this file, stop.

## The traps this wave paid for — read them, they cost real runs

1. **Read the EXIT CODE, never the last line of prose.** `check-frontend-boundaries.py` was run
   twice and read as clean: its last lines say « 4 module(s) reach outside the tree, 3 named » and
   « 1 file(s) outside them » — no word « violation » — over an exit 1. It was caught by the
   orchestrator, on a commit already pushed. Every guard is now run through a script that prints
   `ok` / `FAIL` from the exit code.
2. **The cheap guards read what a maquette phase edits, and a local `typecheck` + `make lint` does
   not.** They caught six English words missing from `scripts/code-vocabulary.txt` and a `data-*`
   attribute classed a boolean STATE because no rule ever read its VALUE
   (`scripts/markup_states.py`). The repair for the second was to make the rule read the value —
   which added a real hold.
3. **`pkill` by wrapper name is forbidden**: a pattern matching `heavy.sh` or `run.sh` kills other
   waves' runs (it cost settings two runs). Kill only by the task id or the pid you started, and
   prove it with `ps -eo pid,ppid,etime,command | grep -E "heavy.sh|run.sh"`.
4. **A waiting shared-lock run HOLDS the lock while holding off on load** — relaunch with the shared
   ceiling rather than leaving it to block other waves.
5. **`shell.tsx` is at the 400-line ceiling** (398 now) and `app/` at its domain-word ceiling (130).
   A new install line goes through `app/feature-verbs.ts`; a new domain word in `app/` is a measured
   raise with its reason, or it does not land.
6. **`data-resolve` is the chosen CANDIDATE everywhere** (B-474): no finger reaches a named folder's
   arbitration; navigate with `window.__screens.resolution(folder)` and say so.
7. **The follow panel's re-scrape is drawn only for a follow the library holds under the SAME
   title**, and of fourteen follows only « Dark Matter » does.
8. **`runMaintenanceAction` has no GET that reads its state back**; the pipeline state is read by a
   BLANK run's answer, which changes nothing by contract.
9. **A new file under `frontend/maquette/` moves `comment-references-baseline.json`'s `read`**, and
   `tests/scripts/test_check_maquette_comments.py` asserts it equals the live corpus — the GUARD
   exits 0 over the drift and only the pre-push suite sees it. Re-record with
   `python3 scripts/check-maquette-comments.py --record` IN the commit that adds the file, and read
   the diff: only `read` may move, never a per-file reference count upward.
