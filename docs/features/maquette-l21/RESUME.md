# L21 — where the wave stands, for whoever picks it up

Rewritten by the session that repaired B-365, answered the operator's four rulings of the day, and
took the wave gate twice. Read `BRIEF.md`, `DESIGN.md` and `plan/INDEX.md` first — this file says
only what is TRUE NOW and what those do not.

**Branch** `feat/maquette-l21`, pull request **#572** (draft). **Version** 0.98.79 — `main` reached
0.98.77 with the ci-draft merge and its post-merge gesture takes 0.98.78, so this branch sits above
both. Re-read `main` before touching it again.

⚠ **A DRAFT PULL REQUEST NOW DISPATCHES NO CI**, by the operator's decision of 2026-09-08: every job
in `.github/workflows/ci.yml` stands down on a draft. So « zero check-runs » has TWO causes now — a
run that never started (no pull request, a `paths-ignore`, or a `CONFLICTING` pull request) and a
pull request that is simply a draft. **This branch met BOTH within one hour.** Read the draft state
FIRST. CI is read after `ready_for_review`, or on a draft by adding the **`run-ci-on-draft`** label,
which dispatches the run without leaving draft.

⚠ **`scripts/check-implementation-state.py:271` infers « that wave has landed » from a VERSION
COMPARISON**, so a micro-wave overtaking a lot makes it declare this live « In flight » row stale
and ask for its deletion. The premise is false and the row is true. **It is not this lot's to
repair** — the ci-draft wave filed it and repairs it in its own gesture — but it runs in
`harness-contracts`, so it can fire on a run of yours for a reason that is not yours.

**HEAD is the sha the last commit of this file carries, and it IS pushed** — proven by
`git ls-remote --heads origin feat/maquette-l21` against the local sha, never by a push's own
output.

⚠ **`origin/main` at `7c0db3719` IS MERGED, and the proof is a COMMAND, not a merge commit.**
`git merge-base --is-ancestor origin/main HEAD` succeeds. **There are THREE merge commits on this
branch now**, so reading any one of their second parents says the branch is behind, which is false.
« Merged » is proven by `--is-ancestor` on HEAD, never by a merge commit's parent.

**The wave base is `7fecb0258`** — computed, not assumed: the parent of the branch's first commit,
and an ancestor of `origin/main`. Every « did this branch earn it » reading uses that base.

---

## 1. Done, with the reading that proves it

| Phase                               | State          | Proof                                         |
| ----------------------------------- | -------------- | --------------------------------------------- |
| 1 — the contract                    | **DONE**       | 3 operations + types + register               |
| 2 — the season grab (B-301)         | **DONE**       | R125, 16 holds · `fixed #572`                 |
| 3 — the journey's two verbs (B-302) | **DONE**       | R126, 16 holds · `fixed #572`                 |
| 4 — the five acts                   | **DONE**       | the act grep reads 0                          |
| 4b — B-315 (a), FIRST answer        | **SUPERSEDED** | reopened by the operator — § 2                |
| 5 — the release take                | **DONE**       | R137 + R123 + `exits.py`                      |
| 6 — the pastille                    | **DONE**       | R138 green + mutated; R124 16 holds           |
| 7 — B-313 + the close               | **DONE**       | R139 red on `main`'s producer then green      |
| **the operator's four rulings**     | **DONE**       | § 2 — three repaired, one filed               |
| **the wave gate**                   | **TAKEN**      | § 3 — every tier, with its figure             |

**Register**: B-301, B-302, B-313, B-315, B-322, B-323, **B-365**, **B-368** read `fixed #572`.
**Filed by this lot**: B-329, B-330, B-350, B-351, B-352, B-363, B-364, B-366, **B-367**, **B-369**,
**B-370**. Next free number is **B-371**. Rules R125–R139, **R155** and **R156** are spent; **R157+**
are free.

---

## 2. The operator's four rulings of the day, and what each cost

**B-365 — REPAIRED.** « no mutation was answered 409 » read Playwright response events; the mock
layer replaces `globalThis.fetch` and answers IN THE PAGE, so that list is empty whatever is
answered. It reads `window.__mocks.answered()` across EVERY operation now — not the three this wave
added, because the clause is about ANY legitimate action refused — with the network read kept beside
it and a guard hold that fails on an empty record. Mutation: BOTH refusal holds fall naming
`409 POST grabSeasonForFollow`, the third does not move, `16 rules EXECUTED`.
⚠ **The mutation also proved the OLD hold could never fall**: the fallen detail listed the layer's
record and nothing from the network, so `refused` was empty while a real 409 was answered.

**B-315 (a) — REOPENED, and it was a DEFECT, not a scale.** « le bouton est toujours beaucoup trop
gros [...] les boutons de l'interface doivent être des composants qui n'autorisent pas toutes les
tailles, l'icône et le bouton sont énormes ». Measured first: the button rendered **332 x 245** with
a **227 x 227** icon, on a screen whose other controls are 24 to 44 px. `svgIcon` emits an `<svg>`
with no size, and `base.css` already records the consequence at its `.installkey` rule. **R136's
four holds read steps and passed all of it.**
Both halves delivered: `actionButton` carries a bounded `size` (`screen` | `footer`, each branch a
string LITERAL so `residue.py` keeps reading it), so an arbitrary size is a compile error; the
`footer` branch carries the icon's size. All **19 call sites across 9 files** pass no argument and
their emitted class set is unchanged — held token for token, not asserted. **Height settled at 40 px
with a 16 px icon by the operator himself.** R136's fifth hold compares the RENDERED BOX to the
action-button system's own, measured on a screen that draws one: 40 against 44. Mutation (icon hook
emptied) brings back `245.328125` with a `227.328125` icon and fells only that hold.
⚠ **The type-level hold is a CONDITIONAL TYPE, not the compiler directive that expects an error**:
this tree counts every such directive as a typing escape against a floor of hard zero, and its guard
reads them INSIDE COMMENTS too. Proven to bite by widening the union — `error TS2322: Type 'true' is
not assignable to type 'never'` at the assertion itself.

**B-367 — FILED ONLY**, owner the settings micro-wave. The drawer's appearance control applies the
theme and does not move its selection. Measured rather than described, because the storage key made
a wrong mechanism plausible: pressing `light`, `dark`, `system`, `light`, the stored value follows
every press and `data-theme` follows every press, and `aria-pressed` moves NOT ONCE — it reads
`system=true light=false dark=false` at all four readings. A close and a reopen draws it correctly.
So it is a redraw that never happens, and `drawer.tsx`'s own comment beside `window.__store.touch()`
says « The bump is what redraws the pressed state », which the measurement contradicts.

**B-368 — REPRODUCED and REPAIRED.** It reproduces from a SPENT pile: the offer stood at y=286 and
the feed's container at y=626, under it. A stale node, not an ordering bug — the deck's body is
filled imperatively, React reuses that element when the mode leaves the deck and appends its own
children after what it never rendered. **The sweep written for exactly this knew `.body > .deck`,
and a SPENT pile is not a `.deck`**: it is the end mark carrying the offer. R155 walks both modes;
mutation puts the selector back and fells 4 holds, « action at 286, the feed at 421 ».

**B-366 — RE-RULED, and the repair is NOT done.** « il ne doit pas y avoir de suivi sans fiche [...]
le suivi sans fiche n'est pas un état possible ». The entry is rewritten around that. **R156 refuses
one in the prototype** by asking the DRAWING'S OWN resolver (`window.__referentiel.sheetFor`) for
every followed title — green at 14 follows, mutation on a seed title fells it.
⚠ **R156 IS A GATE, NOT THE REPAIR**, and the entry says so in its own sentence. Making the state
UNREPRESENTABLE leaves this lot on all three routes: the tile is the dying engine's drawing and the
ledger refuses it upward; seeding a sheet grows `SHEETS_RAW`, a 20 538-line literal inside
`legacy.js` whose derived copy the correspondence arm refuses drift on; and a contract that cannot
describe a sheetless follow is surgery on contract, types, handlers and engine. **Owner L13.**
⚠ **A follow with no EPISODE data is a DIFFERENT absence and stays legitimate.**
⚠ **The first version of R156's check compared titles in Python and reported « Dexter: Resurrection »
as sheetless. It is not** — `sheetFor` falls back to the base title, then a normalised key, then a
prefix match. A guard that re-implements the question it asks measures its own arithmetic.

---

## 3. The wave gate, taken — every tier with its figure

- **Full suite: 109 rules, ZERO rule failures.**
- **`--contracts`: exit 0** (18 rules + the repository's cheap guards).
- **a11y: 87 states, 0 violations.** Light **162**, and the ceiling was LOWERED to 162 from 166.
- **Oracle: 43 divergences, the set IDENTICAL LINE FOR LINE** to the commit before this session's
  first change — verified by diffing captured sets, never by comparing totals. **The reference is
  NOT re-recorded by this wave.**
- **Hold counts, `failed` READ FIRST**: the baseline's own `totals.failed` is **0**, so it was
  recorded over a clean suite. Then: 109 rules, no violation; 4 changed and every one UPWARD —
  `busy.py` 10 → 16, `cards.py` 65 → 70, `drawer.py` 28 → 30, `persistence.py` 47 → 57 — and 16 new
  since the baseline. **Exit 1 is drift against a baseline this wave does not re-record, not a
  failure.**
- **`make check`: exit 0 — 11 201 passed, 0 failed, 4 skipped, 2 xfailed**; the maquette's own
  unit tests 110/110 across 7 files, against floors of 7 files and 107 tests.
- **`legacy.js` 31 467** non-blank against a record of 31 467 · **six-verb grep 0** · ledger exit 0.
- **109 rule files** (103 at the wave base).

### ⚠ What the a11y ceiling cost, because the number lies about its own itemisation

The tool prints « 162 is BELOW the ceiling of 166 — lower it ». **The debt file cannot name the four
that left.** Recorded and diffed: **no state's entry count moved at all** — 34 selectors before, 34
after — while `counts.total` went 166 → 162. **Eleven states had their selectors RESPELLED with
their counts unchanged** (`.chip[data-part="chip"]` → `.waiting.chip`, `.mt-3` →
`button[data-pipe="stop"]`), which is markup this branch moved; `data-take` → `data-pick-release` is
the species, since that file is keyed by SELECTOR. **The totals and the selector map are not the
same quantity.**
**So it was attributed by measurement instead**: the wave base `7fecb0258` built in a throwaway
worktree reads **166**, this head reads **162**. The branch earned four. That is a WAVE-level debt
figure and it is lowered on a wave-level reading — not on a per-phase one, which the file cannot
support.

---

## 4. Two corrections this session owes its own record

**« eslint 0 » in `55c375c14`'s message is FALSE, twice over.** The maquette is outside eslint's
scope BY NAME — `frontend/eslint.config.js` ignores `maquette/**`, because it is a separate npm
project whose conformance is held by its own harness and its own typecheck. And the figure was never
eslint's anyway: **the command was piped through `tail`, so the exit code captured was TAIL's.** The
commit is not rewritten — the correction is worth more stated than erased, and a squash composes its
message fresh. **A gate piped into anything yields the LAST command's status**; `set -o pipefail` or
`${PIPESTATUS[0]}` is the answer.

**One gate pass compared NOTHING while looking like it ran.** `harness-hold-counts.py --compare`
takes a FILE; invoked without one it exits **2** on an argparse usage error, which a gate reading
exit codes cannot tell from a comparison that found drift. Filed as **B-370**, not repaired.

---

## 5. What is OWED

1. **The pull request out of draft** — the orchestrator's word, and only his.
2. **The review rounds** — his. This wave has had none.
3. **B-366's real repair**, owner L13. **B-367**, owner the settings micro-wave.
4. **B-370**, for whoever next opens `harness-hold-counts.py`.

### How to push, because it is not what it looks like

A push runs the parallel suite through its pre-push hook, so **it IS a heavy run and is wrapped like
one, every time**:

    PYTEST_XDIST_AUTO_NUM_WORKERS=3 HEAVY_FREE_FLOOR_MB=3072 sh scripts/heavy.sh l21 \
      git push origin feat/maquette-l21 > <a file> 2>&1

then prove it with `git ls-remote --heads origin feat/maquette-l21` against the local sha (B-360).

---

## 6. The machine, and the traps that live in it

**One served copy machine-wide**, on 8899 from `/tmp/tm-refonte`. The host is a **nohup process
started OUTSIDE the wrapper** — read `lsof -nP -iTCP:8899 -sTCP:LISTEN` rather than trusting a number
written here, and never restart it under the wrapper.

⚠ **The heavy lock is SHARED with sibling agents and it works.** `sh scripts/heavy.sh --held` names
the holder; waiting is correct and is never bypassed.

⚠ **READ THE `EXECUTED` LINE BEFORE THE `FAIL` LINES.** `mutate.sh` greps only `^  FAIL` and
`violation(s)`, so a crashed rule and an unmoved rule print identically. **A mutation that produces
no verdict line is not a mutation that found nothing.** All of this is B-273.

⚠ **A `str.replace` mutation matches EVERY occurrence.** Print the mutated region BEFORE running it.

⚠ **`mutate.sh` REFUSES a dirty tree**: fix → gates → commit → mutate → restore.

⚠ **A worktree at another commit is the honest way to attribute a figure**, and it was used three
times here (the oracle set, the a11y base). Symlink `node_modules` from the main checkout, build,
publish, read, then REMOVE the worktree and republish the main copy — the served copy is one
machine-wide resource.

⚠ **`docs/` is globally gitignored**: a file under it needs `git add -f`, one file at a time.

---

## 7. The one thing not to repeat

**A fixture edit is not a contained edit.** B-366's workaround renamed two paused follows precisely
BECAUSE it touched no code — and one of the new titles, « The Venture Bros », is the subject of the
named state « Fiche — suggestion NON possédée (série) ». The state's own premise became false, the
sheet drew its disabled button, and `follow_verb.py` fell on an emitter with no data. **One rename,
two instruments: it silenced the one it was made for and falsified another two files away.** Only
the FULL suite could see it — eighteen contract rules ran in between and none of them reads that
state. Repaired (B-369) by moving the follow to a title chosen against four filters: it has a sheet,
it is not followed, it is the subject of no named state, and it is named in no harness rule.
