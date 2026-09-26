# L22a — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l22/BRIEF-L22a.md` (governs) and `RULINGS.md` (the lot's own, from 1).

## STATE

- Branch `feat/maquette-l22a`, worktree `/Users/izno/dev/worktrees/wave-l22a`, cut from `origin/main` `1c0dbea64`
  (the squash of #612: DESIGN and plan). Steward: the session named in your launch prompt (`Orch : TM frontend`, its
  reference changes with its process).
- Head: see `git log -1`; pushed state: `git ls-remote origin refs/heads/feat/maquette-l22a`.
- Phases (`plan/INDEX.md`): 1 the contract → 2 the candidates screen changes hands → 3 the two surviving states take
  their names → 4 the strip counts its cells → 5 one ladder, eight rungs → 6 arrivals join « En cours » → 7 the
  requester line → [MIDPOINT full suite, measure 20] → 8 the fourth tab exists and fits → 9 « À traiter » holds its
  cards (STOP D announced: seeds) → 10 the Plex match confirmed or corrected → 11 « Abandonner » quarantines → 12 the
  badge and the count → 13 the default tab (STOP D announced: unnamed walks) → 14 « Suivant » dies → the close of
  L22a (merge of `origin/main`, version bump, full gate, pull request READY). Phases 15–27 are L22b's.
- DONE: nothing yet. NEXT: the handshake, then phase 1.
- Rule labels R-L22-x → numbers: bound at phase 1 against `origin/main`, written here.
- LOGS: `~/Library/Logs/tm-l22a/`. Mutex `sh scripts/heavy.sh --held`; own npm lock
  `/private/tmp/tm-heavy-l22a/holder`.
- GATE FORM: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l22a frontend/maquette/harness/run.sh
  --contracts --oracle <full rule paths>` — the only form that reads rule names.
- MUTATIONS: `sh scripts/mutate.sh <full path> "<expr>" frontend/maquette/harness/<rule>.py`; commit before; read the
  NAMED FAIL line and keep the EXPRESSION; « RULE CRASHED » / « RULE NOT FOUND » prove nothing.
- PUSH: `sh scripts/heavy.sh --class test l22a git push -u origin feat/maquette-l22a`, its own command from the
  worktree root, no `cd … &&`, no `HEAVY_LOCK=`; a refusal = STOP with its exact text.
  `tests/scripts/test_check_maquette_comments.py` alone before any push.
- Traps inherited: the pre-push pytest fails 13 tests of `test_check_markup_contracts.py` on a tree without
  `node_modules` (« no TypeScript installation under frontend/ ») — both are installed here; `git grep plex` without
  `-w` catches « Duplex » in the seeds; `git grep data-pipe` also catches the levers' `data-pipeline-*`; `journey.py`
  reads `/arrivals` through a constant (`ARRIVALS`), not the literal.

## LEDGER (append-only)
