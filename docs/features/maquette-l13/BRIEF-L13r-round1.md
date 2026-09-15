# maquette-l13r — round-one repairs (the reader's findings, DECIDED; a fresh session, the same branch, pull request #605)

You repair pull request #605 (`feat/maquette-l13r`, head `22166378e` = the sub-lot's r·18 close with `origin/main`
`c0a5062ac` merged in) on the reader's round-one findings. The findings are DECIDED: you apply them, you do not
re-assess them; what you find beyond them is a STOP, never a widening. Read
`docs/features/maquette-l13/BRIEF-L13r.md@08400a22a`
(governs: environment, locks, gate form, communication, envelope — all of it still binds),
`docs/features/maquette-l13/RESUME-L13r.md@08400a22a`'s state
block, `RULINGS.md` 98–114, and the reader's report `/Users/izno/dev/review-archive/l13r/round-1/r1-R.md` § FINDINGS
and § « For the next round » — its instruments (`r05_mutations.py`, `r07_state_texts.py`, the `.out` readings) are in
that same directory. Tier deep; the orchestrator's exact address is in your launch prompt; handshake first; every long
run waited for INSIDE the call (bounded polling, never `timeout N` around `run.sh`).

## Environment, unchanged — but the push form is new

Worktree `/Users/izno/dev/worktrees/wave-l13r`, branch `feat/maquette-l13r`, you are the only writer. Logs
`~/Library/Logs/tm-l13r/`. The mutex (`sh scripts/heavy.sh --held`), the gate form `TM_HARNESS_JOBS=3 sh scripts/heavy.sh
--class browser l13r frontend/maquette/harness/run.sh --contracts --oracle <full rule paths>`, mutations through
`scripts/mutate.sh` (commit before), one line to the orchestrator before and after every mutex run. **Every push runs
under the HARNESS mutex too** — `sh scripts/heavy.sh --class test l13r git push origin feat/maquette-l13r`, NO
`HEAVY_LOCK=` override (the steward's rule of 2026-09-15 20:5x: a pre-push suite never runs beside a harness pass;
another implementer, L13c, shares the machine). No force-push ever (main is merged IN, never rebased). Verify:
`git status --porcelain` empty, `git log --oneline -1` = the head this brief was pushed on = `git ls-remote`.

## The decided list — one commit per item, R1 with its hold red first then green and its mutation SEEN to fall

1. **R1 (blocker, r·10's miss) — « Retirer la clé » names the provider's label, not the raw key.**
   `features/settings/secret-verbs.ts:128–130` reads the secrets cache through a hand-written
   `getQueryData<{ k: string; l: string }[]>` and `one.k` / `one.l` — the engine's projection, invisible to tsc,
   while the cache holds the contract's shape since r·10 (`key` / `label`). Repair: the contract's type from
   `lib/contract-schemas.ts` (or the settings feature's types) and `one.key` / `one.label`; then sweep the tree once
   more for the same species — `git grep -n -E "getQueryData<\{|as \{ *[a-z]: " -- frontend/maquette/design/src` —
   and say in the body what it reads (a second hit is repaired in the same commit, said by name). Hold: `harness/secret_acts.py`
   gains « the removal dialog names the secret's label » read on the served page after the finger reaches « Retirer la
   clé » (the title reads « Retirer la clé Nom d'utilisateur qBittorrent ? », never the raw `QBIT_USERNAME`); RED on
   the head before the repair (log `r1-R1-red.log`), green after; mutation `one.label` → `one.key` through mutate.sh:
   the hold falls by name (log `r1-R1-mut.log`).
2. **R2 (minor, order 43's species) — engine mentions cited and in the past tense, or gone.** Harness: the 5
   `legacy.js` mentions (`transition.py:56`, `paused_tile.py:9` in the present tense, and the other three the report
   lists) → `engine/legacy.js@13a66a35b`, past tense. Src: `engine/seams.ts` in `shell-doors.ts:13`,
   `stacked-surface.ts:56` (« it dies with the engine » is false — say what is true), `sorting.ts:14`;
   `navigation-seam.ts:20` (« Nothing in the product reads this file » is false — say what reads it);
   `theme.css:73`, `types.d.ts:1292` (a generated file: if regenerated, fix its source), `acquisition/queries.ts:78`
   (a comment contrary to the code — make it true). One commit; `git grep -n -E "legacy\.js|engine/seams" --
   frontend/maquette/design/src frontend/maquette/harness` before/after counts in the body, 0 uncited after.
3. **R3 (minor) — the ledger's phantom log.** `docs/features/maquette-l13/RESUME-L13r.md@08400a22a`'s r·11 line cites `r11-mutation-follows-audit2.log`,
   pruned at a stand-down: replace the citation by the reader's replay (`review-archive/l13r/round-1/r05_M17-r11-actions.out`
   or the one that reproduced audit2's fall — read which) and one sentence saying the log was lost. Docs commit.

R4 (the unread-JavaScript arm counting untracked files, 372 vs 370) is FILED by the steward — not yours.

Then the gate on the final head: the contracts tier + oracle with `secret_acts.py` named (one invocation); the mutation of
item 1 SEEN to fall on the final head; `make lint`; `python3 scripts/check-no-french.py`; `scripts/check-docs-cited-paths.py`;
`tests/scripts/test_check_maquette_comments.py` alone (the comment baseline moves with item 2 — re-record it in the
same commit, diff read as counts only); push (harness mutex); PR body amended with a « Round one » section: per finding,
the commit, the hold, the red, the mutation's FAIL line, the reading. Report the head; the orchestrator verifies on the
files and merges — there is no second reader round (measure 2).

## Non-goals

- Any file outside `frontend/maquette/design/src`, `frontend/maquette/harness`, the comment baseline,
  `docs/features/maquette-l13/RESUME-L13r.md@08400a22a`
  and the phase files' dated lines; no `scripts/`, no `docs/reference/`, no `IMPLEMENTATION.md`, no `BUGS.md`, no
  version bump (0.98.96 is done), no rebase, no reference re-record (the oracle reads 0 today and must still).
- Widening a repair beyond its finding; a full suite (the reader ran it on this head: 141/141).

If you believe something outside this list is needed, STOP and ask the orchestrator first.
