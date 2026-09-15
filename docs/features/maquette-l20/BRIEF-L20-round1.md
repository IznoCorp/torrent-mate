# maquette-l20 — round-one repairs (the reader's findings, DECIDED; a fresh session, one pull request, the same branch)

You repair pull request #603 (`feat/maquette-l20`, head `05fa452b8` = `a026b4868` + main's docs merged in) on the
reader's round-one findings. The findings are DECIDED: you apply them, you do not re-assess them; what you find
beyond them is a STOP, never a widening. Read `docs/features/maquette-l20/BRIEF-L20.md` (governs: environment,
locks, gate form, communication, envelope — all of it still binds), `RESUME-L20.md`'s state block, `RULINGS-L20.md`
1–9, and the reader's report `/Users/izno/dev/review-archive/l20/round-1/r1-C.md` § FINDINGS and § « For the next
round » — its probe scripts (`c0*_*.py`, `c07_replay.py`, the `.out`/`.log` readings) are in that same directory and
are the instruments you replay. Tier deep; the orchestrator's exact address is in your launch prompt; handshake
first; every long run waited for INSIDE the call (bounded polling, never `timeout N` around `run.sh`).

## Environment, unchanged

Worktree `/Users/izno/dev/worktrees/wave-l20`, branch `feat/maquette-l20`, you are the only writer. Logs
`~/Library/Logs/tm-l20/`. The mutex (`sh scripts/heavy.sh --held`), the tests lock, the gate form
`TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l20 frontend/maquette/harness/run.sh --contracts --oracle <full
rule paths>`, mutations through `scripts/mutate.sh` (commit before), one line to the orchestrator before and after every
mutex run. Another implementer (L13r) shares the mutex: wait, never bypass. No force-push ever (the classifier refuses
it; main is merged IN). Verify: `git status --porcelain` empty, `git log --oneline -1` = 05fa452b8 = `git ls-remote`.

## The decided list — one commit per item, its hold red first then green, its mutation SEEN to fall

1. **C1 (blocker) — the locks block agrees with the layer after a hand start.** After « Lancer le pipeline » by finger,
   « Verrou du pipeline » must read HELD while `/api/maintenance/locks` answers `held:true`. Repair in
   `features/arrivals/verbs.ts` (the `pipe` verb refetches the LOCKS key beside the status) or the mock emitting the
   lifecycle event `live.ts` already maps — say which and why in the body. Hold: `harness/locks.py` gains an agreement
   hold read AFTER a finger press with NO `__go` between; mutation `const held = true;` in `readLocks` (the reader's
   C01) → the hold falls by name. The reader's C08 mutation (refresh only PIPELINE after a lever) falls too.
2. **C2 (blocker) — five holds green over nothing become holds that fall.** `harness/levers.py`: the watcher's STATE
   after the press (not « setWatcher was called »), the queued sentence read from the drawn text (emptying
   `screens.system.pipelineQueued` falls), `levers/bound-value` when ready (a figure a seed holds — read the seed, name
   it), `locks/pipeline` under loading (an injected « Libre » in the skeleton falls). `harness/locks.py`: the watcher
   sentinel's agreement (the inverted sentinel falls). `harness/raw_log.py`: the whole tail compared, not its last 60
   characters (dropping the first 4 000 characters falls). Replay the reader's C02/C03/C05/C06/C07/C11 mutations from
   `c07_replay.py` on your repaired head: SIX falls by name, logged.
3. **C3 (major) — the queue behind a maintenance lock is reachable by a hand.** `mocks/handlers/pipeline.ts`: a
   maintenance run that lasts while a person walks (ends on the scenario clock or an event, never on the second read),
   and `readLocks.held` true for it; `harness/queued_by_hand.py` hold 12 by finger (the press on Système's veille, then
   Arrivées « Lancer », then the queued mark), the `fetch` arrangement gone.
4. **C4 (major) — DOIT-6's « en cours » is drawn to a person.** Same mock change (`advanceDetection` ends on the
   clock/event); `harness/watch_run.py` holds the running state at rest (« lancé → en cours → chiffré », three states
   a person sees); mutation: the running state skipped → falls.
5. **C5 (major) — « Lancer la veille maintenant » from the ⋮ sheet answers on its surface.** `features/system/watch-run.ts`
   + `features/acquisition/panel-more.ts`: a visible answer where the finger pressed (the sheet's line changes state, or
   a toast — DOIT-4), one fr.json key; `harness/panel.py`/`watch_run.py` read it; mutation: the answer removed → falls.
6. **C6 (major, unadmitted difference from DESIGN § 4.2) — `watch-idle` shows the last veille from the history.**
   `features/system/watch.tsx` reads the history's last `follow-detect` run (« Dernière veille : <when> » + its figures)
   and « Jamais lancée » only when the history holds none; the client key `veille/launched` stops being the only source.
   Hold in `watch_run.py` red first on the served seed (43c48209 exists); mutation: the history read dropped → falls.
   Oracle: `watch-idle` diverges — DECLARE it before the run (one state, the watch region), accept by name.
7. **C8 (major, NE-DOIT-PAS-1) — the outcome word per outcome.** `features/system/run-list.tsx`: `running` / `killed` /
   `paused` never read « réussi »; `whatItDid` per kind (a detection that detected 6 never says « rien de nouveau »).
   `harness/run_history.py` (R182) holds the outcome word on a non-terminal row and the detection's sentence; mutation:
   the word map flattened → falls. Oracle: the rows' text changes on the history states — declare them.
8. **C7 (major) — RULING L20-10 (auditor, § 10, 2026-09-15 12:0x): reading (a).** `arr-queued`'s bar follows ruling 8 — no
   gauge, no step of a pass that does not run, copy « Votre passage est en file — il partira dès que la maintenance en
   cours sera finie » (fr.json `screens.arrivals.queued*`), `arrivals.py:190–192` re-aimed aloud, the divergence declared
   on `arr-queued` before the run and accepted by name; mutation: the old copy restored → falls.

Then the gate on the final head: `make lint`; the FULL suite (no flag, JOBS=2) + `--a11y` (dark 0, light ≤ 149);
`harness-hold-counts.py --compare` against a `.review`-style copy re-pointed to 5df76af33 (repo file untouched);
every mutation above SEEN to fall on the final head (one log per mutation, the FAIL line quoted); the reader's walk
scripts `c0*_walk*.py` from the archive replayed on the candidate (say what each reads now); push (plain, tests lock);
PR body amended with a « Round one » section: per finding, the commit, the hold, the mutation's FAIL line, the reading.
Report the head; the orchestrator verifies on the files and merges — there is no second reader round (measure 2).

## Non-goals

- C9–C13 (minors: the mock veille's instant, the duplicated guidance and the watcher label, the small hit areas, the
  whole-minute durations, the markup guard's spread reading) — FILED by the steward with owners; not yours.
- Any file outside `frontend/maquette/design/src`, `frontend/maquette/harness`, `frontend/maquette/design/src/mocks`,
  `fr.json`, the oracle reference (accept by name only), the phase files' dated lines and the RESUME/RULINGS; no
  `scripts/`, no `docs/reference/`, no `IMPLEMENTATION.md`, no version bump (the bump is done), no rebase.
- Widening a repair beyond its finding; repairing C7 before the word.

If you believe something outside this list is needed, STOP and ask the orchestrator first.
