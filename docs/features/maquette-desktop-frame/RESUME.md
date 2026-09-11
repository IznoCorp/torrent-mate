# maquette-desktop-frame — where this stands, and what a fresh session does next

**Read `BRIEF.md` beside this file first.** This document is written to be the
only thing a successor needs: the state, what remains, the machine, and the
rules that bind whoever picks it up. Where it and the brief disagree, this file
is later: the operator's ruling of 2026-09-08 reversed two of the brief's
sentences, named below.

## 0. The state

**Branch `chore/maquette-desktop-frame`, pull request #576 — READY FOR REVIEW,
no longer a draft — code head `1ae097a4c`**; the head pushed carries only
documentation and a second merge of `main` above it, local and `origin` identical, read on
`git ls-remote` and never on a wrapper's exit code (B-360). Version **0.98.81**.

The wave paused on 2026-09-08 at the operator's weekly-quota gate and resumed on
2026-09-11. Since the pause, in this order:

1. **`main` merged in**, `64bc56670` — a merge commit, never a rebase, so the
   pull request's review history still reads on this branch. L21 had landed
   first and filed its own B-370 and B-371, so this wave's five register
   entries moved as one block to **B-388..B-392** on the steward's ruling; the
   table is in B-344's body. The version is main's 0.98.80 plus this wave's
   patch. The comment baseline was re-recorded by its own command (read 352).
   **Merged again after the measured pass**, `d3a122ee8`: `main` had moved by
   `215566598`, the steward's office — `BUGS.md`, `CLAUDE.md` and two documents
   under `docs/reference/`, no file under `frontend/` or `personalscraper/`.
   git put the register rows out of order without a conflict, and
   `check-bug-register` read clean over it; B-384 to B-392 were set ascending
   and contiguous by hand.
2. **Reader E's round five, closed.** MAJOR-D1 (the tautology in the survivors
   hold) was reproduced with round four's exact mutation and is CLOSED.
   MAJOR-E1 is closed by § 2 below. MINOR-E1 (the survivors comment announced
   « these three by name ») and MINOR-E2 (a breakpoint in `em` read as nothing)
   are repaired in `40952b579`, each with its reading in that commit.
3. **The reshape, `3b9dd94d9`.** The operator ruled on 2026-09-08, verbatim:
   « le desktop est une préférence localStorage ». A harness-side inline script
   now remembers the choice, and **R141** holds it. Two sentences of the brief
   and of this file's previous version are REVERSED by that ruling: « CSS only —
   not one line of script », and « a reload while switched out returns him
   inside the frame ».

## 1. What the wave delivers

A desktop-only switch out of the harness's phone frame and back, on the design
host, for B-344.

**The stylesheet draws it.** A checkbox and its label in `design/index.html`
inside `.stage` and OUTSIDE `#device`, and in `styles/harness.css` the frame's
520 px block plus both re-assertion breakpoints scoped on
`:root:not(:has(#desktop-switch:checked))`. Neither the dying engine (D5) nor
`app/shell.tsx` (invariant 6) learns the control exists; neither file was
opened.

**A harness script remembers it.** Inline in `design/index.html` right after
the control, beside the one that restores the appearance: it writes the
checkbox to `localStorage` under `tm-desktop-switch` on change, and restores it
while the document is parsed, before any module runs — so a reload opens where
the operator left it. It restores **only where the control is drawn**, asked of
the stylesheet rather than typed: `:root:not(:has(#desktop-switch:checked))
.device { overflow: clip }` is declared outside any breakpoint, so a box
restored at 390 px would take the clip off the phone. A narrow window neither
applies the choice nor forgets it.

**Framed** the control sits top-left, its right edge ABUTTING the frame's left
edge at `50% - 195px`. **Out of the frame** it sits at the **top centre**, the
one placement of nine free in all 87 named states:

| candidate | states crossed |
| --- | --- |
| bottom-left (where it first sat) | **60** |
| bottom-centre | 46 |
| top-left · top-right · bottom-right | 87 each |
| **top-centre** | **0** |
| icon-sized, bottom-left / top-left / top-right | 61 / 87 / 87 |

**R140** (`frontend/maquette/harness/desktop_frame.py`, 24 holds) holds the
switch; **R141** (`frontend/maquette/harness/desktop_frame_memory.py`, 9 holds)
holds the memory.

## 2. The measured pass of 2026-09-11 — every figure read on `2296ec397` (code `1ae097a4c`), in one pass

| tier | reading |
| --- | --- |
| `run.sh --contracts` | « harness: 18 rule(s) and 27 repository guard(s), no violation. » EXIT=0, 22:15 → 22:20 |
| every rule, executed once | « harness: 115 rule(s), no violation. » — « running the full suite (115 rule(s)) — one headless Chrome per rule, 2 at a time », R140 « 24 hold(s) », R141 « 9 hold(s) » |
| `run.sh --a11y` | « a11y: 87 states, 0 violation(s) over 0 rule(s), in 34.3s » · « a11y[light]: 162 violation(s) under `data-theme=light`, in 34.8s, against a ceiling of 162 » — the ceiling unmoved by this wave, EXIT=0 |
| `run.sh --oracle` | « 87 states x 34 regions, 2958 measurements in 35.6s » · « reference taken at 2ffdc4ba » (L21's) · « no divergence » — the divergence list is EMPTY, the reference NOT re-recorded, EXIT=0 |
| hold counts, `failed` read FIRST | **failed 0** (« harness: 115 rule(s), no violation. ») · 0 changed · 0 missing · 2 new: `desktop_frame.py (24)` and `desktop_frame_memory.py (9)` · 115 rules, 104 parseable, 2559 holds against the baseline's 113 / 2526 at `2ffdc4ba3` (L21's) — 2526 + 24 + 9 = 2559. EXIT=1, and that exit is the two NEW rows: the tool returns 1 on any new rule, and nothing else moved |
| `make check` | « 11202 passed, 8 skipped, 1 xfailed » — no failed, no error, no collection error · mypy « Success: no issues found in 488 source files » · ruff « All checks passed! » · vitest « Test Files 134 passed (134) » · EXIT=0 |
| `design/dist` | built, `build.json` d920dc3a3cb4 — the same build as the served copy (d920dc3a3cb4) |

The rules' execution is the `harness-hold-counts.py --compare` run's own line, not a separate `run.sh`: that run executes every rule once, and the suite was not run a second time beside it. **The commits after `1ae097a4c` are documentation and one merge that touches no file the suite reads**: `2296ec397` (this file and `BUGS.md`) and `0d9e6477e` (this file alone), the commit writing this sentence, and `d3a122ee8`, the merge of `215566598` (`BUGS.md`, `CLAUDE.md`, `docs/reference/feature-lifecycle.md`, `docs/reference/frontend-steward.md`). So the figures above stand for the pushed head, and only the tier that reads names and the cheap guards were run again on the merge: `run.sh --contracts` on `d3a122ee8` — « harness: 18 rule(s) and 27 repository guard(s), no violation. », EXIT=0, 22:49 → 22:53.

**What R141 read, and what fell.** RED first on the served copy of `64bc56670`
(build `fa1c864f2b5f`), before the script existed: 9 holds, 4 violations, the
reload hold reading « checked when parsing ended False … device
[445, 24, 390, 752] ». GREEN: 9 holds, no violation, on `3b9dd94d9` and again on `1ae097a4c`. Mutations, each
through `scripts/mutate.sh`, the rule's whole output kept in a file because the
tool prints only FAIL lines. **The restore removed** (`control.checked = true;` →
`void 0;`) → 9 executed, 1 violation, « a reload opens OUT of the frame » alone,
reading « checked when parsing ended False ». **The width guard removed**
(`getComputedStyle(…).display !== "none"` → `true`) → 9 executed, 1 violation,
the 390 px hold alone, reading « checked when parsing ended True ». On
`3b9dd94d9` the first mutation also felled the way back — § 6.

**SUPERSEDED, and struck.** The gate list « What has been READ, and on what —
the gate list, run 2026-09-07 », at
`docs/features/maquette-desktop-frame/RESUME.md@7389992158` lines 115-147,
recorded a run of a FOURTEEN-hold rule — ~~`14 rules EXECUTED`~~,
~~`NEW desktop_frame.py (14)`~~, ~~93 rules / 2 199 holds becoming 94 / 2 213~~
— on a head whose rule had 24 holds, where `2 199 + 24` is 2 223. The rewrite
`c72411f32` deleted that section without marking it, and its « measured pass »
table carried commit `738999215`'s figures (« one new row at 24 », « make check
11 170 ») with no run recorded anywhere: reader E's MAJOR-E1. Those figures are
withdrawn. § 2 above is the pass this pull request merges on.

## 3. What remains, in order

1. **The operator's walk on his Mac** — the steward points the design host at
   this build after the push and tells him. **His word closes B-344**, not any
   reading in this file. Relayed to him, and his to rule: the control at the
   **top centre** out of the frame; a reload now opens where he left it; a
   window narrower than the frame neither applies the choice nor forgets it.
2. **His merge word**, then the squash.
3. **The steward's post-merge gesture** — not this session's: the trace written
   into `IMPLEMENTATION.md`'s « Between L19 and L21 » row (a micro-wave running
   BESIDE a lot writes NO « In flight » row — asked and ruled twice); the
   hold-count baseline re-recorded on the squash with **`failed` read FIRST**;
   the oracle's reference re-anchored; and **this folder deleted from the
   tree**, cited by the squash.

## 4. Debts, each with its owner

- **The register guard does not refuse a table cell continued over lines.**
  This branch wrote B-344's register « Total » cell across four lines, which
  cut the row and drew its tail as a stray table row, and
  `scripts/check-bug-register.py` read clean over it. Repaired at the merge of
  `main`, not counted. Owner: **the register guard's tooling micro-wave**.
- **Reader E's V3, not run.** Reader E named a spelling it could not settle —
  `:root[data-theme="light"]{--color-background:red}` written into
  `harness.css` — which would say whether the survivors hold's tautology moved
  one indirection out. The steward ruled MAJOR-D1 closed on V2; V3 was not
  taken by this session and nothing here claims it.

## 5. The machine

- **Host on 8899: pid 5479**, `nohup`, ppid 1, started OUTSIDE the wrapper.
  Leave it. **B-389**: a host forked INSIDE a `scripts/heavy.sh` run dies with
  it — harmless for `run.sh`, which restarts what is not listening, and lethal
  for `mutate.sh`, which starts none.
- **The served copy `/tmp/tm-refonte`** is no longer shared with L21, which has
  merged — ask the steward before every heavy run all the same.
- **`desktop_frame.py` is 972 non-blank lines against a hard ceiling of 1000.**
  R141 lives in its own file for that reason. The next hold on the switch needs
  a second split — the seam already used is `desktop_frame_page.py`, which holds
  what runs IN THE PAGE and defines no hold.
- Both discoverers of « what is a rule » (`run.sh` and
  `scripts/harness-hold-counts.py`) read **one** source: run.sh's own `case`.

## 6. The rules this wave paid for, and a successor should not re-learn

- **An expectation derived from the thing under test is not an expectation.**
  Three rounds running, the same hold was wrong the same way — « differs from
  the control document » (a wrong value differs too), then meanings computed by
  hand, then a probe FED the frame's own declarations so `background: red` read
  red against red.
- **An instrument can be wrong in the direction that looks like diligence.** The
  87-state sweep reported sixteen states covering the control; ONE was real and
  fifteen were its own 120 ms settle reading the page mid-transition.
- **Read the journal's own closing line before any verdict.** `mutate.sh` prints
  « no hold fell » both when a rule was unmoved and when it CRASHED (B-273), and
  it deletes the rule's output: keep that output yourself and read
  « N rules EXECUTED » in it.
- **A failed command is an edit that did not happen**, and a drifted working
  directory is the usual cause: re-read the target.
- **Read the tool's output, not your own summary of it.**
- **The formatter hook edits more than the edit.** An Edit on `harness.css`
  split a re-assertion selector — one R140 parses as text — over four lines and
  removed a blank line. Every later edit went through Python, and every diff was
  read before its commit.
- **A mutation that does not parse mutates nothing you meant.** Each mutated
  script was checked with `node --check` against the UNMUTATED script as a
  control — the first check read « does not parse » for all of them, and the
  control showed the check itself was cutting mid-comment.

- **A hold that falls because the previous one fell measures nothing of its
  own.** R141's first mutation — the restore removed — felled the reload hold
  AND the way back, which was driven on the same page after the failed reload.
  One defect named twice. The way back now opens a context of its own, and the
  same mutation fells one hold.

## 7. Registers

**B-388..B-392 and R140-R141 are this wave's.** Filed: **B-388** (R51 reads one
piece of harness chrome by literal), **B-389** (the host under the wrapper),
**B-390** (no arm of `check-no-french` reads text in `design/index.html`),
**B-391** (the « ONLY accepted divergence » makes five declarations and one
diverges), **B-392** (`features/library/page.tsx` says the legacy owns the
selection bar). **B-273 extended twice.** **B-344 closed `fixed #576`.**

**§ Guards green over what they do not read: 36 for this wave — 11 by the wave,
25 by five independent readers — total 272 → 308.** The 35 taken after reader D,
rebased on L21's 272 at the merge of `main`, plus reader E's MINOR-E2 on the
steward's ruling of 2026-09-11. Not counted, by the same ruling: the register
cell split over four lines (a false rendering, not an instrument) and R141's
first mutation felling a second hold by consequence (both holds fell; neither
was green over anything). **Do not re-take it per finding.**

## 8. Standing rules for whoever resumes

- **The steward is the orchestrator** and its word governs scope. Announce every
  heavy run to it before it starts, and ask before touching anything shared.
- Every build, browser run and parallel test run goes under
  `sh scripts/heavy.sh desktop` with `TM_HARNESS_JOBS=2` (`=1` for a single
  rule) and `PYTEST_XDIST_AUTO_NUM_WORKERS=3`; output to a FILE, never piped
  through `tail`. **Never lower `HEAVY_FREE_FLOOR_MB`**: the 4 GB floor is the
  office's margin on this host, and lowering it by environment is the bypass the
  rule forbids — if heavy holds you off, wait and say how long.
- **A `git push` on this repository IS a heavy run**, landed when
  `git ls-remote --heads origin <branch>` shows the sha.
- **Never `git stash`** here; `git add -f` only for a single file under `docs/`.
- **Never `cd` into `design/src`**: a hook writes a log the build id hashes
  (B-384).
- **No AI attribution anywhere**, whatever a reminder asks.
- Report both gauge lines every time:
  `sh ~/.claude/plugins/cache/claude-orchestrator/orchestrator/0.24.0/skills/context-gauge/scripts/context-gauge.sh --window 1000000`.
