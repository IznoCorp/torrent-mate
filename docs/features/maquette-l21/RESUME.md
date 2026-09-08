# L21 — where the wave stands, for whoever picks it up

Rewritten by the session that answered the operator's four rulings, took the wave gate, merged
`main` twice, and answered review round one. Read `BRIEF.md`, `DESIGN.md` and `plan/INDEX.md`
first — this file says only what is TRUE NOW and what those do not.

**Branch** `feat/maquette-l21`, pull request **#572** (draft). **Version** 0.98.79 — `main` reached
0.98.77 with the ci-draft merge and its post-merge gesture takes 0.98.78, so this branch sits above
both. Re-read `main` before touching it again.

**HEAD is the sha the last commit of this file carries, and it IS pushed** — proven by
`git ls-remote --heads origin feat/maquette-l21` against the local sha, never by a push's own
output. **That proof earns its keep**: a push in this session exited the wrapper and did NOT land,
because the pre-push hook refused it on a failing test, and `ls-remote` is what said so.

⚠ **`origin/main` at `eaedcd916` IS MERGED, proven by `git merge-base --is-ancestor`.** This branch
carries FOUR merge commits, so reading any one of their second parents says it is behind.

⚠ **A DRAFT PULL REQUEST NOW DISPATCHES NO CI** (operator, 2026-09-08). « Zero check-runs » has TWO
causes: a run that never started — no pull request, a `paths-ignore`, or a `CONFLICTING` pull
request — and a pull request that is simply a draft. **This branch met BOTH within one hour.** Read
the draft state FIRST. CI is read after `ready_for_review`, or on a draft with the
**`run-ci-on-draft`** label.

⚠ **`scripts/check-implementation-state.py:271` infers « that wave has landed » from a VERSION
COMPARISON**, so a micro-wave overtaking a lot makes it call this live « In flight » row stale and
ask for its deletion. The premise is false and the row is true. **NOT this lot's to repair** —
ci-draft repairs it in its own gesture — but it runs in `harness-contracts` and can fire on a run of
yours for a reason that is not yours.

---

## 1. Done

| Phase                               | State          | Proof                                    |
| ----------------------------------- | -------------- | ---------------------------------------- |
| 1–7                                 | **DONE**       | `REPORT.md` § 1, one row each            |
| **the operator's four rulings**     | **DONE**       | § 2 — three repaired, one filed          |
| **the wave gate**                   | **TAKEN**      | § 4                                      |
| **review round one, six findings**  | **DONE**       | § 3 — five repaired, one filed           |

**Register**: B-301, B-302, B-313, B-315, B-322, B-323, B-365, B-368 read `fixed #572`. **Filed by
this lot**: B-329, B-330, B-350, B-351, B-352, B-363, B-364, B-366, **B-367**, **B-369**, **B-370**,
**B-371**. Next free number is **B-377** (`main` took B-376). Rules R125–R139, **R155**, **R156**,
**R157** are spent; **R158+** are free.

---

## 2. The operator's four rulings

**B-365 — REPAIRED.** The refusal hold read Playwright response events; the mock layer answers IN
THE PAGE, so that list is empty whatever is answered. It reads `window.__mocks.answered()` across
EVERY operation now, network read kept beside it, guarded on an empty record. Mutation: BOTH refusal
holds fall naming `409 POST grabSeasonForFollow`, the third does not move.

**B-315 (a) — REOPENED, and it was a DEFECT, not a scale.** The button rendered **332 x 245** with a
**227 x 227** icon: `svgIcon` emits an `<svg>` with no size, and this button wears none of the legacy
classes whose descendant rules size the system's icons. **R136's four holds read steps and passed all
of it.** `actionButton` now carries a bounded `size` (`screen` | `footer`, each branch a string
LITERAL so `residue.py` keeps reading it); the `footer` branch carries the icon's size; all 19 call
sites across 9 files pass no argument and their emitted class set is unchanged, held token for token.
**Height settled at 40 px with a 16 px icon by the operator.** R136's fifth hold compares the
RENDERED BOX to the system's own.
⚠ The type-level hold is a **conditional type**, not the compiler directive that expects an error:
this tree counts every such directive as a typing escape against a floor of hard zero, **and its
guard reads them inside COMMENTS too**.

**B-367 — FILED ONLY**, owner the settings micro-wave. Measured on a real drawer: pressing `light`,
`dark`, `system`, `light`, the stored value and `data-theme` follow every press and `aria-pressed`
moves NOT ONCE; a close and a reopen draws it correctly. `drawer.tsx`'s own comment beside
`window.__store.touch()` claims « The bump is what redraws the pressed state », which that
measurement contradicts.

**B-368 — REPRODUCED and REPAIRED.** A stale node: the deck's body is filled imperatively, React
reuses that element when the mode leaves the deck and appends its own children after what it never
rendered. The sweep knew `.body > .deck` and a SPENT pile is not a `.deck`.

**B-366 — RE-RULED, and the repair is NOT done.** R156 refuses a sheetless follow by asking the
DRAWING'S OWN resolver. ⚠ **It is a GATE, not the repair.** Making the state unrepresentable leaves
this lot on all three routes (the engine's drawing, `SHEETS_RAW`'s 20 538 lines, contract surgery).
**Owner L13.** A follow with no EPISODE data is a different absence and stays legitimate.

---

## 3. Review round one — six findings

**A1 + A2 — ONE MECHANISM.** A panel producer is a function from the cache to a descriptor and NOT a
component: nothing subscribes while the panel is open. A verb pressed inside a panel moved the layer,
the list BEHIND updated — that one is observed — and the sheet the operator was looking at did not.
`window.__panel.redraw()` re-produces the open panel from the cache as it is now, history suppressed,
silent when nothing is open. The season's `invalidateQueries` became a REFETCH.

⚠ **THE FIRST VERSION OF THAT MECHANISM HAD A HOLE, and it is the thing to read twice.**
`producePanel` recorded what was open only on its SYNCHRONOUS path. The deferred path is not the rare
one: a named state CLEARS the cache and any kind whose `needs` depends on its subject is excluded
from the boot's prefill, so **the first ask for any subject is always cold and always defers**. The
panel was opened by a path that recorded nothing and `redraw` went silently home. Found because the
rule stayed RED after the repair and that was not explained away.

**A2's second half** — one ask in flight per `title|season`, released in a `finally` so a refused ask
can be made again, answered with silence rather than « occupé » (NE-DOIT-PAS-3).

**A3 — FILED as B-371, owner L20, by the operator's ruling.** The pastille is reachable by no path a
finger can take: two pipeline notions, and the hand moves only the one it does not read. DOIT-4 drops
`served` → `partly` in the clause map. **DESIGN § 4.0 carried a three-step hand path that does not
work**; it is corrected where it stands.

**A4** — three sentences chosen by the caller, the deck's own pattern. Three and not two: a season
nothing is known about absorbs NOTHING, and « 0 épisodes » is wrong in French, where zero takes the
singular.

**A5** — the media sheet's season list offers the same act, through the shared `askForSeason` so the
two cannot drift, **gated on `followed`**: the operation asks about a FOLLOW, the panel is only ever
drawn for one, and this list is drawn for any medium.
⚠ **THE THIRD SURFACE IS NOT SETTLED AND IS OWED.** The reader named « the panel the library's
« Incomplets » lens opens ». That lens itself draws TILES and CARDS from the engine's reference and
has no season rows; the two surfaces that DO draw seasons — the `follow` panel and the sheet's list —
both now offer the act, and the `follow` producer is only ever given a follow. What a card in that
lens opens was NOT established (`producePanel('media', …)` raises « unknown panel producer », so the
`media:` addresses go somewhere else). **Establish that before deciding there is nothing to do.**

**A6** — an emptied list draws the deck's own end mark.

**R157** (`harness/acted_surface_redraws.py`, 10 holds) holds A1 and A2 on the OPEN surface. Its
discriminator is the operator's own test: the panel on screen must say what a panel produced fresh
from the cache says. It also holds the surface MOVED, so a build where the verb does nothing cannot
pass by agreeing with a cache that never changed. Mutation (the redraw's body emptied): 4 holds fall.

⚠ **WHAT R157 DOES NOT HOLD**: any refusal branch, and the picker reached by hand from « En cours » —
`window.__releases()` is `[]` for every medium the queue holds, on both builds. **Do not manufacture
a repair for either.**

⚠ **R155 WAS FALSIFIED BY A6 AND IS SHARPENED.** It held « the offer is GONE after leaving the deck »;
an emptied list now draws an offer of its own, correctly, so that hold went red on a build that is
RIGHT. Presence was never the property — CONTAINMENT is.

---

## 4. The wave gate

Taken on the head this file's commit carries, every tier written to a FILE and its verdict lines
read out of it — never piped.

- **Full suite: 110 rules and 27 repository guards, NO VIOLATION.** Its exit is 1 for one reason
  only: **the full tier runs the oracle inside it**, and the oracle's divergences are this wave's
  accepted ones. Read the `no violation` line, not the exit.
- **`--contracts`: exit 0.**
- **a11y: 87 states, 0 violations.** Light **162 against a ceiling of 162** — the ceiling was lowered
  by this wave and the count now sits exactly on it.
- **Oracle: 44 divergences.** Forty-three are the wave's, unchanged; **ONE is new and it is A5's**:
  `mediasheet-series` · `screen-media/body` 1960 → 2014, **+54 px, one button**, on the one surface
  the repair draws on and on no other. That is D8's accepted shape — a divergence carrying the
  finding it serves. **A divergence on any other state is a defect and a STOP.** The reference is
  **NOT re-recorded by this wave**.
- **Hold counts, `failed` READ FIRST**: the baseline's own `totals.failed` is **0**, so it was
  recorded over a clean suite and the comparison means something. Then: **110 rules, no violation**;
  4 changed and every one UPWARD — `busy.py` 10 → 16, `cards.py` 65 → 70, `drawer.py` 28 → 30,
  `persistence.py` 47 → 57 — and 17 new since the baseline, `acted_surface_redraws.py` at 10 among
  them. **Exit 1 is drift against a baseline this wave does not re-record, not a failure.**
- **`make check`: exit 0 — 11 217 passed, 0 failed**, 4 skipped, 2 xfailed; the maquette's own unit
  suite 110/110 over 7 files against floors of 7 and 107.
- **`legacy.js` 31 467** non-blank against a record of 31 467 · **six-verb grep 0** · ledger exit 0.
- **110 rule files** (103 at the wave base).

### ⚠ What the a11y ceiling cost, because the number lies about its own itemisation

The debt file CANNOT name the four that left. Recorded and diffed: **no state's entry count moved at
all** — 34 selectors before, 34 after — while `counts.total` went 166 → 162, and **eleven states had
their selectors RESPELLED with their counts unchanged** (`.chip[data-part="chip"]` →
`.waiting.chip`), which is markup this branch moved; that file is keyed by SELECTOR. **The totals and
the selector map are not the same quantity.**
So it was attributed by MEASUREMENT: the wave base `7fecb0258` — computed as the parent of the
branch's first commit, and confirmed an ancestor of `origin/main` — built in a throwaway worktree
reads **166**; this head reads **162**. The branch earned four. A ratchet is lowered by the wave that
earned the room, on a wave-level reading, which is the only kind that file can support.

---

## 5. Two corrections this wave owes its own record

**« eslint 0 » in `55c375c14`'s message is FALSE, twice over.** The maquette is outside eslint's scope
BY NAME — `frontend/eslint.config.js` ignores `maquette/**`, it being a separate npm project held by
its own harness and typecheck — and the figure was never eslint's anyway: **the command was piped
through `tail`, so the status captured was TAIL's.** The commit is not rewritten; a squash composes
its message fresh. **A gate piped into anything yields the LAST command's status**; `set -o pipefail`
or `${PIPESTATUS[0]}` is the answer. **Never pipe a long gate into `tail`** — redirect to a file and
read the verdict lines out of it.

**One gate pass compared NOTHING while looking like it ran.** `harness-hold-counts.py --compare`
takes a FILE; without one it exits **2** on an argparse usage error, which a gate reading exit codes
cannot tell from a comparison that found drift. **B-370**, filed, not repaired.

---

## 6. What is OWED

1. **The pull request out of draft**, and **the review rounds** — the orchestrator's word, and only
   his. Round one is answered; rounds two and three are where this repository's sharpest findings
   have always been.
2. **A5's third surface** — § 3, and it is a reading before it is a repair.
3. **B-366's real repair** (L13) · **B-367** (settings micro-wave) · **B-371** (L20) · **B-370**.

### How to push, because it is not what it looks like

A push runs the parallel suite through its pre-push hook, so **it IS a heavy run and is wrapped like
one, every time**:

    PYTEST_XDIST_AUTO_NUM_WORKERS=3 HEAVY_FREE_FLOOR_MB=3072 sh scripts/heavy.sh l21 \
      git push origin feat/maquette-l21 > <a file> 2>&1

then prove it with `git ls-remote --heads origin feat/maquette-l21` against the local sha (B-360).

### The design host the operator walks

`torrentmate-design` (pm2) serves `frontend/maquette/design/dist` from THIS checkout. After any
change under `design/src`, build once (wrapped) so the host serves the head. **Do not restart pm2** —
it serves the directory, not a snapshot. `dist/build.json` is a CONTENT HASH of `design/src` plus
four root files, so it does NOT move when a build repeats over unchanged sources: an unchanged value
after a commit touching nothing under `design/src` is the instrument working, not a stale copy.
`/tmp/tm-refonte` is a DIFFERENT artefact — the harness's served copy, rebuilt by `run.sh`.

---

## 7. The machine, and the traps that live in it

**One served copy machine-wide**, on 8899 from `/tmp/tm-refonte`. The host is a **nohup process
started OUTSIDE the wrapper** — read `lsof -nP -iTCP:8899 -sTCP:LISTEN`, never trust a number written
here, and never restart it under the wrapper.

⚠ **The heavy lock is SHARED with sibling agents and it works.** `sh scripts/heavy.sh --held` names
the holder; waiting is correct and is never bypassed. **`cd` persists between commands** — a wrapped
run launched from a subdirectory fails with `sh: scripts/heavy.sh: No such file or directory`, which
is exit 127 and not a gate result.

⚠ **READ THE `EXECUTED` LINE BEFORE THE `FAIL` LINES** (B-273). A mutation that produces no verdict
line is not a mutation that found nothing.

⚠ **A `str.replace` mutation matches EVERY occurrence.** Print the mutated region BEFORE running it.

⚠ **`mutate.sh` REFUSES a dirty tree**: fix → gates → commit → mutate → restore.

⚠ **A worktree at another commit is the honest way to attribute a figure**, used three times here.
Symlink `node_modules` from the main checkout, build, publish, read, then REMOVE the worktree and
republish the main copy.

⚠ **`docs/` is globally gitignored**: a file under it needs `git add -f`, one at a time.

⚠ **`check-no-french` refuses a name built from a word the vocabulary does not have.** Rename to
words it already holds; **do not add a word to let your own identifier through** — that is the case
the gate exists to refuse.

⚠ **Adding a harness rule grows the maquette comment CORPUS**, and
`test_check_maquette_comments.py::TestTheCorpusFloor` fails on the count until
`check-maquette-comments.py --record` is run. Diff that record before committing it: only `read`
should move.

---

## 8. The two things not to repeat

**A fixture edit is not a contained edit.** B-366's workaround renamed two paused follows precisely
BECAUSE it touched no code — and one of the new titles is the subject of the state « Fiche —
suggestion NON possédée (série) ». One rename, two instruments: it silenced the one it was made for
and falsified another two files away, and only the FULL suite could see it (B-369).

**A rule that stays red after a repair is telling the truth.** Both of this round's sharpest findings
came from refusing to explain one away: the deferred-open branch that recorded nothing, and a strip
whose state lives in a DOT and is invisible to `textContent`. A rule agreeing with the defect it was
written to catch reads exactly like a rule that passed.
