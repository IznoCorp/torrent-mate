# maquette-departure — B-310, the panel that comes back for one frame, and B-330 beside it

You open a **micro-wave**, decided by the operator on 2026-09-06 (« maintenant on met en place de
quoi éviter la régression »): one line of the frame's stylesheet, one rule that falls without it, and
the adjacent defect on the same seam. No lot. It runs BESIDE L21, in its own worktree — the one-writer
rule holds per checkout and you never enter `~/dev/PersonalScraper`, which is L21's. Branch
`fix/maquette-departure`, one pull request, squash merge, the version bumps.

**What B-310 is, measured on the operator's own phone on 2026-09-06 (Chrome 152, Android 16, the
design host).** From any bottom panel, « Voir la fiche » opens the media screen. The navigation's view
transition captures the OPEN panel under the name `leaving-panel` and plays `panel-down` on that
snapshot for 450 ms. `base.css` declares it with the SHORTHAND —
`animation: panel-down var(--duration-4) var(--ease-standard)` — and a shorthand resets
`animation-fill-mode` to `none`. So when `panel-down` ends, the snapshot returns to its un-animated
state, which is the panel **open, opaque, at rest**, and it is drawn there — z-index 20, above the
root — until the browser tears the transition down **one frame later**. Read on the device, on the
transition's last active frame: `::view-transition-old(leaving-panel)` at `opacity 1, transform none`,
the frame before at `0.0003` and 594 px down. Every run has that frame, on the Mac as on the phone, and
**the operator sees it in Chrome on macOS too** — a DOM sampler does not see a painted frame, which is
why two sessions of probes on the Mac described the 450 ms before it and missed it until the snapshot's
own computed style was read on that last frame. The operator sees it at every opening, from every
panel. **Injecting `animation-fill-mode: forwards` on that pseudo-element into his page removed it,
and he confirmed it** (« parti, plus de clignotement »). Read B-310 whole in `BUGS.md`: it carries
the earlier reading, marked superseded, and the one that stands.

**What B-330 is.** After the same transition ends, the panel's scrim — `opacity 0` already, but
`visibility: visible` until its delayed flip 450 ms later — is the element `elementFromPoint` answers
at the centre of the media screen for about 380 ms (567 → 948 ms after the tap on the Mac, 1083 →
1434 ms on the phone). A tap on the fresh screen in that window lands on an invisible scrim. Same
seam, same shape: a departing layer outliving the crossing. Read its entry before touching it.

## What you read before acting

1. `CLAUDE.md`; `docs/reference/documentation-model.md`; `docs/reference/frontend-architecture.md`
   § 0 (one kind of change per wave — yours is BEHAVIOUR, and every repair lands with its rule seen
   red first), D8 (the oracle measures geometry AT REST: nothing here moves at rest, so it must read
   zero divergence), D9 (motion lives in the stylesheet; nothing is scripted), § 3 invariants 13 and
   14 (motion declared, the reduced state drawn like any other), § 5 (the proof, the gate, the
   post-merge gesture).
2. `BUGS.md`: **B-310** and **B-330** (yours), **B-249** (the family — a layer that stops being
   visible before it has finished leaving; its open half on the SCREEN layer is not yours), **B-276**
   (a delay set by hand in an instrument outlives the drawn duration — your rule reads the
   transition's own frames, never a timer), **B-273** (`mutate.sh` judges a RULE by its FAIL lines and
   is silent when a build breaks), **B-307** (a fall under load: your rule samples frames, so it is
   exposed to it — print what it read when it falls).
3. `frontend/maquette/design/src/styles/base.css` — the whole block from « THE PERSISTENT CHROME IS
   ITS OWN GROUP » to the end of `@keyframes panel-down`, and the block « ONE OWNER OF THE DEPARTURE,
   and the live panel is not it » (`:root:active-view-transition #sheet`), which is deliberate and
   stays. `frontend/maquette/design/src/ui/variants/layout.ts` — `sheetScrim` and `bottomSheet`: the
   delayed `visibility` is B-249's idiom and it stays on the SHEET.
4. `frontend/maquette/harness/exits.py` (R103) — the sampler that reads a layer's exit frame by
   frame, and its docstring's last paragraph: « it cannot see a flash… what it reads is the fact the
   flash is made of ». Yours reads the same kind of fact one layer up: the SNAPSHOT.
   `frontend/maquette/harness/common.py` — `Journal`, `open_page`, the served copy's stamp.
5. `docs/reference/frontend-steward.md` § « What a review costs, and the five rules » and
   § « Instrument hygiene » — they bind you, small as this wave is.
6. `frontend/maquette/README.md` — the method, `scripts/mutate.sh`, the traps already paid for.

## Verify the state; do not believe it

    git remote update origin >/dev/null && git log --oneline origin/main -3
    pwd   # your worktree, never ~/dev/PersonalScraper
    grep -o "| \*\*In flight\*\*[^|]*| [^.]\{0,60\}" IMPLEMENTATION.md
    python3 scripts/check-bug-register.py --next
    grep -n "animation: " frontend/maquette/design/src/styles/base.css
    grep -n "fill-mode" frontend/maquette/design/src/styles/base.css
    grep -n "active-view-transition #sheet" frontend/maquette/design/src/styles/base.css
    grep -n "transition-delay" frontend/maquette/design/src/ui/variants/layout.ts
    ls frontend/maquette/harness/ | grep -c "\.py$"
    grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1
    python3 -c "import json;d=json.load(open('frontend/maquette/hold-counts-baseline.json'));print(d['taken_at_commit'][:9], d['totals'])"

Read on 2026-09-06 at `7fecb0258`: three `animation:` shorthands on view-transition pseudo-elements
— `::view-transition-new(screen-banner)` (`banner-in`, base.css:759), `::view-transition-new(screen-body)`
(`body-rise`, :764), `::view-transition-old(leaving-panel)` (`panel-down`, :808) — and one that already
says `forwards` (`banner-cover`, :711); no `fill-mode` anywhere; the silence rule on the live sheet at
:826; the scrim's `[transition-delay:0s,450ms]` at layout.ts:96 and the sheet's at :152; the highest
rule is **R124** on `main` (L21 is writing R125 on its branch — take **R126**); the baseline at
`e9820e6a4`, `failed: 0`. **L21 has taken B-329 on its branch, which is why the scrim is B-330 and the
register's `--next` on `main` will disagree with you by one — say so in the pull request rather than
renumber.**

## The five things the plan does not tell you

### 1. The repair is one line, and the species is three

`::view-transition-old(leaving-panel)` needs its fill mode: `forwards` (or `both`), written as a
LONGHAND beside the shorthand, or the shorthand rewritten in longhands — either way the comment above
it says why a shorthand on a transition pseudo-element is a trap: the UA stylesheet gives every
`::view-transition-*` pseudo `animation-fill-mode: both` by inheritance, and a shorthand throws it
away. The two NEW snapshots with the same shape (`banner-in`, `body-rise`) snap to their un-animated
state too — which for a NEW image is its final state, so nothing shows — but they are the same species
and you fix them in the same move, so the next reader of that stylesheet does not have to work out
which of the three is safe. `panel-down` keeps its 450 ms and its curve: the departure L12 drew is not
amended, only completed.

### 2. B-330's repair keeps the fade and removes the target

The scrim fades over 450 ms and its `visibility` flips 450 ms later — B-249's idiom, which keeps a
leaving layer VISIBLE (R103 reads exactly that, and stays green). What must go is the scrim being
HIT-TESTABLE over the screen once the crossing is over. Decide with the rule, not by taste; the cheapest
shape is that the closed scrim stops taking pointer events at once (the sheet's own drag band already
uses `pointer-events` as a class). Whatever you choose, R103's holds on the scrim keep their count,
and a tap on the fresh media screen at +100 ms lands on the screen.

### 3. The rule reads the snapshot, on the transition's own last frame — and it is red today

New rule `frontend/maquette/harness/departure.py`, **R126** — « the departing panel's snapshot does
not come back, and its scrim does not stay under the finger ». It walks the path a finger takes (a
panel raised by the delegation, then a tap on `[data-mediasheet]` — never `__panel.produce`, R103's own
lesson), samples EVERY frame while `document.documentElement.matches(':active-view-transition')` holds,
and keeps sampling ~600 ms past the end. What each hold reads, and what would leave it green over
nothing:

- **(a)** on every active frame after `panel-down` has finished (its animation absent from
  `document.getAnimations()` for that pseudo, or `currentTime` at its duration),
  `getComputedStyle(document.documentElement, '::view-transition-old(leaving-panel)')` reads
  `opacity` **0** and a transform that is NOT `none`. **Red on `main` without the line** — measured on
  the Mac too: the last active frame exists in every run (`panel-down` absent, the transition still
  active). A hold that reads only frames where `panel-down` is running is green over the defect.
- **(b)** the walk crosses that last frame at all — assert the sampler saw at least one active frame
  after `panel-down`'s end; if the browser tears the transition down in the same frame, the hold says
  « not observed » rather than passing, which is B-277's honesty about frame sampling.
- **(c)** after the transition ends, on every sampled frame, `document.elementFromPoint` at the media
  screen's centre is not `#scrim` — **red on `main` today for ~380 ms of frames** (B-330).
- **(d)** under `prefers-reduced-motion: reduce`, the walk runs and the three above hold or say what
  the reduced path does instead (no snapshot animates there — the rule states what it read, not a
  requirement invented for it).

The rule prints, when it falls, the frame it fell on with the snapshot's opacity and transform
(B-307: a fall under load carries its own reading). Mutation, committed first (B-303): revert the
fill-mode line with `scripts/mutate.sh`, see (a) red naming the frame, restore; revert B-330's repair,
see (c) red with the ms window, restore.

### 4. The oracle must not move, and the hold counts move by one row

Nothing here changes a surface at rest: `make maquette-oracle` reads **zero** divergence and the
reference is NOT re-recorded. `scripts/harness-hold-counts.py --compare` shows one new row (R126) and
no other movement; the baseline is re-recorded at the post-merge gesture by the steward, not by you.

### 5. The device is the judge, and the steward reads it

The defect is a painted frame: visible in Chrome on macOS and on the phone, invisible to a DOM
sampler. Your rule reads the fact it is made of; the steward re-reads the transition's last frame on
the operator's phone (paired to this machine over adb) on your head and on a control of `main`, an
independent reader walks it in a headed Chrome on this machine, and the operator walks it himself. Your report claims what your rule read; the device reading is the steward's and is not
yours to write.

## What you do not do

- **You do not touch `~/dev/PersonalScraper`** — L21's checkout. You work in the worktree you were
  spawned in and nowhere else.
- **You do not change `panel-down`'s duration or curve, the root cross-fade, or the live sheet's
  silence rule** — the operator's amendment of the departure is NOT asked; only its completion.
- **You do not touch the sheet's delayed `visibility`** (B-249's idiom) nor the screen layer (B-249's
  open half, another lot's).
- **You do not add a line to `legacy.js`**, and you do not open L21's files (`features/media/`,
  `features/acquisition/`, the mocks, the contract).
- **You do not touch any other register entry**, and you do not renumber B-330.
- **You do not stop between steps**; the only stops are a divergence in the oracle (there must be
  none) and the pull request.

## The gates, and the machine shared with L21

Per commit: the contracts tier and the cheap guards (`run.sh --contracts`). Before the pull request:
the full suite (`frontend/maquette/harness/run.sh`, expected **no failure**), `--a11y` 0, the oracle at
zero divergence, `make check` at 0 failed / 0 errors, the hold-count compare with `failed` read FIRST.

**One harness per machine.** The suite reads ONE served copy (`/tmp/tm-refonte`) on 8899, and L21's
agent is running its own gates from the main checkout. So: before every run that touches the served
copy (`run.sh`, `make maquette-oracle`, `mutate.sh`, the recorder), message the steward AND the L21
agent — both addresses are in your invocation — and wait for the steward's word; run it under the
lock, `TM_HARNESS_JOBS=2 sh scripts/heavy.sh departure <command>` (`TM_HARNESS_JOBS=1` for a single
rule; `PYTEST_XDIST_AUTO_NUM_WORKERS=3` for the test suite, the pre-push hook included — **a `git
push` on this repository IS a heavy run**). The served copy's stamp makes a swap under a rule fall
rather than lie; a rule that falls while the other writer held the harness is re-run alone before it
is read. Kill what you start, delete what you build, prove with `ps`. The host on 8899 is `run.sh`'s
and is left running.

## How you deliver

Branch `fix/maquette-departure`, one pull request, English title and body, the version bumped
(patch — and bump it AFTER reading `main`'s version at that moment, because L21 bumps too). Write the
« In flight » row when the pull request opens (number first, then version). B-310 and B-330 read
`fixed #<n>` by rule 3 (the rule, the mutation, the run). Recount « guards green over what they do not
read » for your wave, zero included. Then message the steward — its exact address is in your
invocation, and no other session's word changes your scope — and the steward launches ONE independent
reader on a worktree pinned at your head against a control of `main`, and reads the device. You alone
write. The operator gives the merge word. Your folder leaves the tree at the post-merge gesture, cited
by the squash.
