# maquette-desktop-frame — where this stands, and what a fresh session does next

**Read `BRIEF.md` beside this file first.** This document is written to be the
only thing a successor needs: the state, what is in flight, what remains, the
machine, and the rules that bind whoever picks it up.

Paused on 2026-09-08 at the operator's weekly-quota gate (`seven_day_percent`
reached 80). Nothing is half-finished: every unit is committed and pushed.

## The state, in one line

**Branch `chore/maquette-desktop-frame`, pull request #576 (DRAFT), head
`7389992158f3fa5c4973a5243be7364d33168b62`** — local and `origin` identical, read
on `git ls-remote`, never on a wrapper's exit code (B-360).

The wave is CODE-COMPLETE and its gate is green on that head. What is left is
review and the operator's word.

## What the wave delivers

A desktop-only switch out of the harness's phone frame and back, on the design
host, for B-344. **CSS only — not one line of script**: a checkbox and its label
in `design/index.html` inside `.stage` and OUTSIDE `#device`, and in
`styles/harness.css` the frame's 520 px block plus both re-assertion breakpoints
scoped on `:root:not(:has(#desktop-switch:checked))`. The state is the
checkbox's, read by `:has()`, so neither the dying engine (D5) nor
`app/shell.tsx` (invariant 6) learns the control exists; neither file was opened.

**Framed** the control sits top-left, its right edge ABUTTING the frame's left
edge at `50% - 195px` (it does not « stop 16px short » — that comment was false
and is corrected). **Out of the frame** it sits at the **top centre**, which is
the one placement of nine free in all 87 named states:

| candidate | states crossed |
| --- | --- |
| bottom-left (where it first sat) | **60** |
| bottom-centre | 46 |
| top-left · top-right · bottom-right | 87 each |
| **top-centre** | **0** |
| icon-sized, bottom-left / top-left / top-right | 61 / 87 / 87 |

It does not collide with the harness's own bar either: the bar is at the top
bar's empty middle while the frame is drawn (which top centre WOULD cross) and
at the top right out of it.

## The measured pass — every figure read on THIS head, in one pass

| tier | reading |
| --- | --- |
| R140 | **24 holds, no violation** at 390×844, 1280×800, 520×800, plus a presence sweep over seven widths derived from the stylesheet's own breakpoints and an 87-state walk out of the frame |
| full suite | **94 rules** and 27 repository guards, no violation |
| `--a11y` | 87 states, **0 violations**; light **166 against a ceiling of 166**, unmoved |
| oracle | 2 958 measurements, reference `f70ca029`, **no divergence**, reference NOT re-recorded |
| hold counts | **`failed` 0** read FIRST · 0 changed · 0 missing · 1 new: `desktop_frame.py (24)` |
| `make check` | **11 170 passed, 8 skipped, 1 xfailed, 0 failed, 0 errors**, no collection error |

## IN FLIGHT — reader E

**A narrow round on `7389992158`**, reading ONLY MAJOR-D1's repair and the
measured pass's readings. Its report will be at
`/Users/izno/dev/worktrees/review-desktop-frame/.review/r5-E.md` and is **relayed
by the steward** — do not go looking for it yourself, and **read it with `cat` /
`sed -n` in Bash, never with the Read tool**: a Read outside your own worktree
parks the session on a permission dialog nobody answers, which is how one reader
died.

## WHAT REMAINS, in order

1. **Reader E's verdict**, relayed by the steward, and any repair it names —
   each repair with its hold seen RED first, then green, then the reading that
   closes it named in the report.
2. **The operator's walk on his Mac.** He opens the design host in Chrome and
   toggles it himself. **His word closes B-344**, not any reading in this file.
   Two things are relayed to him and are HIS to rule, not to be changed without
   it: the control at the **top centre** out of the frame, and that a **reload
   while switched out returns him inside the frame** (the state is the
   checkbox's and nothing persists it).
3. **His merge word**, then the squash.
4. **The steward's post-merge gesture** — not this session's: the trace written
   into `IMPLEMENTATION.md`'s « Between L19 and L21 » row beside the schedulers'
   and the departure's (a micro-wave running BESIDE a lot writes NO « In flight »
   row — that row is L21's, and this was asked and ruled twice); the hold-count
   baseline re-recorded on the squash with **`failed` read FIRST**; the oracle's
   reference re-anchored; and **this folder deleted from the tree**, cited by the
   squash.

## The machine

- **Host on 8899: pid 5479**, `nohup`, ppid 1, started OUTSIDE the wrapper. Leave
  it. **B-389**: a host forked INSIDE a `scripts/heavy.sh` run dies with it
  (`set -m`, the group is signalled on release) — harmless for `run.sh`, which
  restarts what is not listening, and lethal for `mutate.sh`, which starts none
  and then runs its rule against a refused port.
- **The served copy `/tmp/tm-refonte` is SHARED with L21** (`personalscraper-e1`,
  itself paused). Ask the steward before touching it; republish before reading it.
- **`desktop_frame.py` is 955 non-blank lines against a hard ceiling of 1000**,
  past the 800 warning. **The next hold added needs a second split** — the seam
  already used is `desktop_frame_page.py`, which holds what runs IN THE PAGE.
- Both discoverers of « what is a rule » (`run.sh` and
  `scripts/harness-hold-counts.py`) read **one** source: run.sh's own `case`.

## The rules this wave paid for, and a successor should not re-learn

- **An expectation derived from the thing under test is not an expectation.**
  Three rounds running, the same hold was wrong the same way — « differs from the
  control document » (a wrong value differs too), then meanings computed by hand,
  then a probe FED the frame's own declarations so `background: red` read red
  against red. The sentence is in the rule's header now.
- **An instrument can be wrong in the direction that looks like diligence.** The
  87-state sweep reported sixteen states covering the control; ONE was real and
  fifteen were its own 120 ms settle reading the page 450 ms into a transition. A
  false negative hides behind a green gate; a false positive arrives dressed as
  thoroughness.
- **Read the journal's own closing line before any verdict.** `mutate.sh` prints
  « no hold fell » both when a rule was unmoved and when it CRASHED — including
  after printing two FAIL lines (B-273, third and fourth instances). `common.Journal`
  prints « N rules EXECUTED »; a rule that died never reaches it. `lsof` on 8899
  catches one cause, that line catches all of them.
- **A failed command is an edit that did not happen.** Two edits in this wave
  silently did not apply because the shell's working directory had drifted from
  an earlier `cd`; both were caught only by re-reading the target.
- **Read the tool's output, not your own summary of it.** A head was pushed
  failing `check-module-size` because a loop printed `FAILED size` on the line
  above an echoed « guards clean ».

## Registers

**B-389+ and R141-R149 are this wave's block.** Filed: **B-389** (the host under
the wrapper), **B-390** (no arm of `check-no-french` reads text in
`design/index.html`, so the guard's silence was never evidence for the label
ruling), **B-391** (the « ONLY accepted divergence » makes five declarations and
one diverges), **B-392** (`features/library/page.tsx` says the legacy owns the
selection bar; `paintSelBar` is empty and React draws it). **B-273 extended
twice.** **B-344 closed `fixed #576`**, body and status in the same commit.

**§ Guards green over what they do not read: 35 for this wave — 11 by the wave,
24 by four independent readers — total 250 → 285.** Written ONCE, on this head,
after reader D. **Do not re-take it per finding**; that is how the L12 cell
drifted to 151 while its itemisation read 15.

## Standing rules for whoever resumes

- **The steward is the orchestrator** and its word governs scope; L21's agent is
  a peer, not an authority. Announce every harness run to both before it starts,
  and ask before touching anything shared — including killing a host you started
  yourself, once another session depends on it.
- Every build, browser run and parallel test run goes under
  `sh scripts/heavy.sh desktop-frame` with `TM_HARNESS_JOBS=2`,
  `PYTEST_XDIST_AUTO_NUM_WORKERS=3`, `HEAVY_FREE_FLOOR_MB=3072`; output to a
  FILE, never piped through `tail`; `TM_HARNESS_JOBS=1` for a single rule.
- **A `git push` on this repository IS a heavy run**, and it is landed when
  `git ls-remote --heads origin <branch>` shows the sha — never when a wrapper
  exits 0.
- **Never `git stash`** here; `git add -f` only for a single file under `docs/`.
- **No AI attribution anywhere**, including any session trailer a system message
  asks for. One asked during this wave; it was refused and reported.
- Report both gauge lines every time:
  `sh ~/.claude/plugins/cache/lounisbou/orchestrator/0.4.2/skills/context-gauge/scripts/context-gauge.sh --window 1000000`.
