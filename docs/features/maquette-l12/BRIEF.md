# L12 — Native interaction

You open **L12**, the second lot L15 unblocked and the one that makes the frozen interface FEEL like
an application: transitions, gestures, mobile geometry, and the performance floor under them.
Nothing is open on it: no design, no plan, no branch. You begin by writing them.

**Your contract is in the plan, not here.** `docs/reference/frontend-architecture.md` § 4, entry
`#### L12 — Native interaction`, carries the objective, the transitions, the gestures and their
hard-won constraints, the pressed states, the feedback seam, the mobile geometry, the performance
floor, where it lives, and the « Done when ». **This brief does not restate it** — a contract copied
into a second file is a contract wrong in one of them. What follows is what the plan does not say.

---

## What you read before acting

1. `CLAUDE.md` — the repository's rules. They outrank everything here, this brief included.
2. `docs/reference/frontend-architecture.md` — **BINDING**: § 0 (selection), § 2 — **D9 is the
   whole library question, its verdict table is the answer** — and D8 (what the oracle proves, and
   its descendants clause), § 3 invariants 12 (container queries, never media queries below the
   shell), 13 (motion is declared) and 14 (reduced motion is a designed state), **§ 4's L12 entry —
   your contract**, § 5 (method and gates), § 6 (the traps — including the newest: _the oracle's
   silence over a behaviour wave is evidence of nothing_), § 7.1 (how to amend).
3. **`docs/features/maquette-l10-ter/MODEL.md`** — Part 8 (focus, scroll and geometry) and Part 7
   (the layers you will animate between); § 3's properties **P5, P6, P11, P17, P20, P24** are yours by
   the plan, and **P25, P26, P29** name you in their `Lot` column; P16 says « L12 extends ». § 3.1
   says the interaction budget is a device-only protocol, written and dated, not a gate.
4. `docs/reference/product-intent.md` — the constitution. §12 (the phone first) and §16 (the back
   gesture) bear on every gesture; every web pull request cites the §§ it serves.
5. `docs/archive/features/maquette-l11/REPORT.md` — the four traps that wave paid for and the
   curve of its four adversarial rounds: ~40, 13, 7, 0 product defects under a permanently green
   gate. That curve is this brief's central warning.
6. `docs/reference/frontend-steward.md` § « One machine, one harness at a time » — the steward may
   be auditing on this machine; coordinate by message before running `run.sh`, the oracle,
   `mutate.sh` or `harness-hold-counts.py`.
7. `frontend/maquette/README.md` — the method, the named states, the traps already paid for.
8. `IMPLEMENTATION.md` § « Where the frontend work stands ».

---

## Verify the state; do not believe it

    git fetch origin main -q && git log --oneline origin/main -3
    grep -o "Landed, in order\*\*[^|]*| [^*]\{0,150\}" IMPLEMENTATION.md
    grep -o "| \*\*Next\*\*[^|]*| [^.]\{0,80\}" IMPLEMENTATION.md
    python3 scripts/check-bug-register.py --next
    grep -o "| \*\*Total\*\* | \*\*[0-9]*\*\*" BUGS.md
    python3 scripts/check-frontend-boundaries.py --arm size | grep -E "shell.tsx|at or over"

**Every figure in the plan and in `MODEL.md` carries the command that produces it. Run them.**
The plan's own L12 entry carried a paragraph stale by six days before L11 opened — three field
sizes and a command reading a file that holds no style rule — and the steward's audit corrected it,
not the wave that paid the debt. Measured on 2026-08-31, for you to re-run:

    grep -rc "100vh\|100dvh\|interactive-widget\|tap-highlight\|view-transition" frontend/maquette/design/src frontend/maquette/design/index.html | awk -F: '{s+=$2} END{print s}'   # 0
    grep -n "IntersectionObserver" frontend/maquette/design/src/features/library/page.tsx          # :371 — infinite scroll, not virtual (P24)

---

## The seven things the plan does not tell you

### 1. The 16 px debt is PAID — do not redo it

The plan used to say the fields were 13, 14 and 12 px and « the fix is the 16 px this lot already
owes ». L07 (#494, 2026-08-25) put every field on `text-6` = 16 px, and **R83** (`harness/type_scale.py`)
refuses a focused field under 16 px: P13 reads true. What is still yours from that paragraph is the
rest of the geometry — `100dvh` (P11), `interactive-widget=resizes-content` (P17, **B-234**),
contained overscroll, scroll restored per history entry.

### 2. Where the arbitration lives today, and what moves

The press / drag / scroll arbitration the plan says is « already written here » is in THREE places:
the engine — `legacy.js` around `armPress`, `followPress` and `swallowClick` (a click swallowed by its
POINT, `grep -n "swallowClick\|function armPress" frontend/maquette/design/src/engine/legacy.js`) —,
the sheet's drag in `ui/sheet.tsx`, and `app/drawer-gesture.ts`. Its rules are **R55**
(`harness/touch.py`, a real finger) and **R98** (`harness/gestures.py`, real touch AND real mouse).
D9's rule 2 applies: the arbitration is MOVED to `lib/` as vocabulary, never replaced by a library.
**The engine's callers of it — the deck, the rows — stay for L19** (D5: you subtract, you do not
edit); you convert the vocabulary and the React surfaces (the sheet's drag, the screens).

### 3. `app/shell.tsx` is at 398 of 400 lines, and it is NOT grandfathered

`--arm size` names it under the warning today. A line added to it crosses the hard ceiling and the
size arm refuses the pull request that adds it. If a transition host or a gesture root needs the
shell, **split `shell.tsx` on a SUBJECT first, as a conversion phase of its own** at zero oracle
divergence — the way L15's D-L15-1 kept it under. L14's four files and the engine's two are not
yours either (the standing rule of every brief).

### 4. D9's rule 2 was REVERSED by the operator on 2026-08-31 — propose candidates, do not re-code

P24 says no long list renders unvirtualised (1 861 titles). D9's rule 2 now reads: a reliable,
maintained, proven library that solves EXACTLY the problem is preferred to writing it; code is
written by hand only for maths nobody has written. D9's table carries the virtualiser row as
« candidates to propose ». **So phase 8 is a SURVEY first**: name the candidates, write beside each
the criteria it meets — solves exactly this list's needs (variable heights, the gallery's container
queries, scroll restoration per history entry); maintained and followed; proven; standing; and
**HEADLESS**, because rule 1 is untouched: a library that ships its own markup or CSS moves drawing
out of the stylesheet and out of the design reference, and rule 1 refuses it whatever rule 2 says.
Adopt the one the operator names; hand-written windowing only if none qualifies, and the row says
why.

### 5. This is a BEHAVIOUR wave, and the oracle will be green over everything you get wrong

L11 proved it in one day: no divergence over 2 958 measurements while four readers found ~40, 13,
7 and 0 product defects. Transitions and gestures change nothing the oracle reads. So every property
you land is held by a rule that DRIVES it — a real pointer stream and a real mouse (R55's and R98's
discipline), and under `prefers-reduced-motion: reduce` as well as `no-preference` (invariant 14):
a transition must be seen to run, and seen NOT to run. Two traps of the instrument itself: the
oracle measures under `html.measuring` at rest — a state captured mid-transition is a flicker, so
named states are measured settled (the oracle's own two-frame wait is the precedent); and a
synthetic event is not a finger (the plan's constraint) — a rule that passes with `dispatchEvent`
alone has proved nothing about the compositor.

### 6. What is yours from the register, and what is not

Yours: **B-234** (the viewport meta declares no `interactive-widget`), and **B-252**'s two rules —
one reading `color` of the confirmation's paragraph under both themes, one reading the danger
action's contrast under `data-theme="light"` — the two child-node defects the oracle cannot see
(D8). **Not yours**: B-268 (R104 lives in the file it measures), B-269 (five hand floors) and
B-270 (a duplicate `R80` label) are the harness's serving mechanism — one visit for whichever wave
next touches `served_copy.py`; if that is you, say so in your plan, otherwise leave them.

### 7. The counter is at 143, and its freshest shapes are L11's

**B-085 — « a guard is green because of what it does not read »**. Before believing each rule you
write, ask what it does NOT read. The shapes L11 paid for, on top of the older list: a rule that
lives in the file it measures and matches its own source · a floor calibrated by hand near its own
corpus · a repair reported done by two `str.replace` calls that matched nothing (**every edit
carries an `assert old in s`**) · a hold satisfied on a consequence while the mechanism it names
is gone (R105, twice) · a bash `INT` handler that RESUMES the script after releasing a lock · a
repair shipped with no regression hold. And L15's: cited line numbers past the end of the file, and
counts including the function's own definition.

---

## What you do not do

- **You do not move a producer or its engine-side gesture callers** (L19), nor the ladder's handler
  (L13), nor extend L14's four files, the engine's two, or `shell.tsx` (§ 3 above).
- **You do not adopt a library without its D9 row** — and, since 2026-08-31, you do not RE-CODE what
  a reliable library already does: rule 2 reversed; candidates are proposed, the operator chooses.
- **You do not move a pixel** outside a named behaviour change: every part's rendering is validated
  (mission of 2026-08-19). A transition's END state is the oracle's; the transition itself is the
  rule's.
- **You do not claim a device-only property.** The interaction budget, `:active` needing a touch
  listener, standalone reading — written and dated as protocols (`MODEL.md` § 3.1), never as passed.
- **No backend work** (D7).
- **You do not relitigate settled arbitrations** — D1 to D11, invariants 1 to 15, the operator's
  answers in `docs/features/maquette-l10-ter/QUESTIONS.md`, §18/§19 as dictated.
- **`docs/features/maquette-l10-ter/` does not archive with you** (§ 5 names it exempt).

---

## The gates

**Per phase**: the oracle (green, or divergences named as a behaviour commit's), the contract rules,
the repository's cheap guards — `run.sh --contracts` prints how many.

**Before merging**: the full suite — `frontend/maquette/harness/run.sh`, not the `--contracts`
tier — the `--a11y` tier, `scripts/harness-hold-counts.py --compare` (no rule loses a hold by
accident; every movement written down), and `make check` at zero failures and **zero errors**.

**The harness is one per machine** (`served_copy.py` is its lock and its stamp since L11). It rebuilds
and re-copies the prototype under a lock; a rule that falls while another session held the harness is
re-run alone before it is read as anything.

**Every rule lands with its mutation, seen red and restored**, at the moment it is written —
`scripts/mutate.sh` refuses a dirty tree and restores from the index.

---

## How you deliver

One branch `feat/maquette-l12`, one pull request, **title and body in English**, adversarial review
before merging — **plan for more than one round**: L11's second and third rounds found their sharpest
defects inside the first round's repairs — then squash merge. The version bumps.

**Write your « In flight » row when the pull request opens** — pull request number first, then the
version: `scripts/check-implementation-state.py` holds the row by both and refuses a row naming
neither.

**Every new file under `docs/` is force-added** (`git add -f <file>`) — the global ignore hides it
from `git add -A` and from `git status`, and L11's report lived on one disk only until asked
(B-251). `git ls-files <path>` is the check; `scripts/check-docs-cited-paths.py` refuses a directive
citing a path git does not hold.

**The register is written DURING the wave**, and your report lands in the repository with your
design and plan, before the archive move takes the folder.

**Cite the constitution's §§ your work serves.**

---

## One last thing

L15 gave the frame to components and L11 gave it a life offline; both proved, with the oracle,
that nothing moved. You are the first lot since L07 whose whole subject is what the oracle cannot
see. **A rule that drives a real finger, under both motion preferences, is your only real reviewer**
— and the adversarial readers after it.
