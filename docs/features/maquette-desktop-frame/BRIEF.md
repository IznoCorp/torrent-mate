# maquette-desktop-frame — B-344, a way out of the phone frame on a desktop, and back

You open a **micro-wave of TOOLING**, decided by the operator on 2026-09-06 (his decision round,
question 6): on a desktop browser the design host draws the prototype inside the harness's phone
frame, and the operator cannot test the interface's desktop layout there. He asked, verbatim: « sur
desktop et seulement sur desktop, en dehors du template téléphone, on ait un bouton qui permet de
switcher en mode desktop (et du coup un bouton pour revenir dans le template téléphone, toujours
uniquement si on est sur desktop !) ». No lot. It runs BESIDE L21, in its own worktree — the
one-writer rule holds per checkout and you never enter `~/dev/PersonalScraper`, which is L21's.
Branch `chore/maquette-desktop-frame`, one pull request, squash merge, the version bumps.

**What the frame is, read before you touch it.** `frontend/maquette/design/src/styles/harness.css`
is the one stylesheet that does not ship: it is imported LAST by `app/shell.tsx` and dies at
switchover with the prototype. It draws the frame — `.stage` and `.device` (markup in
`design/index.html`, `<div class="stage"><div class="device" id="device" data-part="shell/device">`) —
and at `@media (min-width: 520px)` the device becomes a 390 × 844 phone with a border and a shadow
inside the page. **It also RE-ASSERTS the mobile presentation inside the frame** at the app's own
breakpoints (the block « DECLARED HARNESS DEVIATION — the frame forces the phone presentation »:
`.device .ps-dot__label` at 640 px, `.device .bottombar` and `.device .topbar` at 768 px), because
the app's breakpoints measure the WINDOW and a phone drawn inside a wide page would otherwise switch
to its desktop presentation. That deviation is why the operator cannot see the desktop layout on
the design host: the frame is drawn and the frame forces the phone. What he asks for is a switch
that removes BOTH — the frame's dimensions and its re-assertions — so the app's own stylesheet
answers a desktop window the way it would in production, and a switch back.

**Where it lives, and where it does not.** It is HARNESS chrome, so it lives with the harness:
`harness.css`, the harness markup of `design/index.html` (the harness bar `.hbtn[data-part="harness/bar"]`
is already there, at the top bar's empty middle, hidden under `html.measuring` by
`window.__measure(true)`), and `fr.json` for its two labels. It lives OUTSIDE `.device` — the
operator said so and the shell is a MEASURED region that must carry nothing that does not exist in
the app (`harness.css`'s own comment on the harness buttons). It does NOT live in `app/`, `ui/`,
`features/`, `lib/`, nor in `engine/legacy.js` (D5: the engine only shrinks — a handler added there
is refused by the size ledger) — and `app/shell.tsx` may only LOSE lines, so no new import there
either. **The cheapest shape that respects all of that is CSS-only**: a control in the stage's
markup (a checkbox or a button wired by nothing but the stylesheet — `:root:has(#desktop-switch:checked)`,
Chrome 105+) under which `.stage`/`.device` drop the phone dimensions and the re-assertion block is
scoped out (`:root:not(:has(…)) .device .bottombar { … }`), and the same control, toggled back,
restores the frame. Decide with the rule, not by taste: a script-free switch is one the engine and
the shell never learn about, which is the point.

## What you read before acting

1. `CLAUDE.md` — § Design Reference names `harness.css` as the measuring apparatus, in the maquette's
   own build and in no production build; `docs/reference/documentation-model.md`;
   `docs/reference/frontend-architecture.md` § 0 (one kind of change per wave — yours is TOOLING,
   and it touches no surface at rest), D5 (the engine dies by subtraction), D8 (the oracle measures
   geometry at rest at 390 × 844 — the switch must be ABSENT there, so the oracle reads zero
   divergence), § 3 invariant 6 (`app/shell.tsx`'s line budget), § 5.
2. `BUGS.md`: **B-344** (yours), **B-081** and the `$noteRemovalRetired` note in
   `frontend/maquette/regions.json` (what `html.measuring` hides and why the measured document and
   the judged one must be the same document), **B-256** (the served copy's stamp), **B-325** (no
   rule can be pointed at a build — your rule reads 8899 like every other).
3. `frontend/maquette/design/src/styles/harness.css` whole — 195 lines, every block commented;
   `design/index.html` lines 100-130 (the stage and the device) and 400-420 (the harness bar);
   `app/shell.tsx` line 30 (the import) and lines 275-310 (the React root re-parented into
   `#device` before the first render — a layer resolves `position: absolute` against the frame);
   `ui/variants/layout.ts` for the bottom bar and the rail the app draws at its own breakpoints.
4. `frontend/maquette/README.md` — § the column count follows the SCROLLPORT (a container query,
   never the window: that is why the frame can be removed without the grid lying), § BLOCK 1 is the
   harness; `frontend/maquette/harness/common.py` — `PHONE` (390 × 844, touch), `open_page`, the
   stamp; `frontend/maquette/harness/sweep.py` (R-sweep: every view at 390 px, no horizontal
   overflow) — your rule reads the DESKTOP window the same way.
5. `docs/reference/frontend-steward.md` § « What a review costs, and the five rules » and
   § « Instrument hygiene » — they bind you, small as this wave is.

## Verify the state; do not believe it

    git remote update origin >/dev/null && git log --oneline origin/main -3
    pwd   # your worktree, never ~/dev/PersonalScraper
    grep -o "| \*\*In flight\*\*[^|]*| [^.]\{0,60\}" IMPLEMENTATION.md
    python3 scripts/check-bug-register.py --next
    grep -n "min-width" frontend/maquette/design/src/styles/harness.css
    grep -n 'class="stage"\|class="device"\|class="hbtn"' frontend/maquette/design/index.html
    grep -n "harness.css" frontend/maquette/design/src/app/shell.tsx
    grep -c "" frontend/maquette/design/src/app/shell.tsx
    grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1
    python3 -c "import json;d=json.load(open('frontend/maquette/hold-counts-baseline.json'));print(d['taken_at_commit'][:9], d['totals'])"

Read on 2026-09-06 at `d9659a64e`: three `min-width` breakpoints in `harness.css` — 640 and 768
(the re-assertions) and 520 (the frame itself); the stage at `index.html:107`, the device at `:108`,
the harness bar at `:407`; the import at `shell.tsx:30`. **The register's `--next` on `main` will
disagree with you**: L21 holds B-351+ / R128+ and the departure wave B-346+ / R127 on their
branches, the steward B-360+. **Your block is B-370+ and R140+** — say so in the pull request
rather than renumber.

## The five things the plan does not tell you

### 1. « Desktop only » has a measurable meaning, and it is the frame's own breakpoint

The switch exists exactly where the frame is drawn: at and above `520 px`, the width at which
`harness.css` turns `.device` into a phone. Below it the device already fills the window and there
is nothing to switch out of — the operator on his Android must never see the control, and the
oracle, which measures at 390 px, must never see it either. « Absent » means absent from the layout
(`display: none` at the small breakpoint, and hidden under `html.measuring` like the rest of the
harness chrome), not merely off-screen: a control the accessibility tier can reach at 390 px is a
finding of its own.

### 2. Switched out, the app's stylesheet answers — and the frame's re-assertions must be OFF

The desktop presentation is not something you draw. It is what `base.css` and the variants already
say at the app's breakpoints, which the frame overrides on purpose. So the switch removes two
things at once: the device's phone dimensions (width, height, border, radius, shadow — it fills the
window) and the whole re-assertion block. Read the result against the app's own values, not against
a picture: at 1280 × 800 with the switch on, `.device` is as wide as the viewport and
`getComputedStyle` on the bottom bar, the top bar's padding and the status dot's label reads what
the app's stylesheet declares at that width — the same values a page served WITHOUT `harness.css`'s
frame would read. Where the app draws a rail or hides the bar at ≥ 768 px, that is what appears;
where it draws nothing different, nothing changes — and that is a reading, not a defect.

### 3. The rule — R140, `frontend/maquette/harness/desktop_frame.py`

What each hold reads, and what would leave it green over nothing:

- **(a)** at 390 × 844 (`common.PHONE`) the switch is not in the layout: no box, not reachable by
  `elementFromPoint`, not focusable; and the harness bar's own rule about not covering the app's
  chrome still holds — read the switch's rect against the top bar's status dot and avatar at every
  width where it IS drawn. A hold that only reads `visibility` is green over a control drawn at
  0 × 0 that still takes focus.
- **(b)** at 1280 × 800 the frame is drawn (`.device` at 390 px wide) and the switch is outside
  `#device` (not a descendant) and labelled (`aria-label` / text from `fr.json`).
- **(c)** after one activation, `.device`'s width equals the viewport's, and three computed
  properties the frame used to force read the APP's values (the bottom bar's `display`, the top
  bar's `padding-left`, the status dot label's `display`) — take those expected values from a
  document where `.device` carries no frame, never from a number typed into the rule.
- **(d)** a second activation restores (b) exactly — the same three properties back to the frame's
  values, the device back to 390 px.
- **(e)** under `html.measuring` the switch is hidden like the harness bar, so `window.__measure(true)`
  clears it before any capture.

Red first: (a) and (c) cannot be red before the control exists, so the rule is mutation-tested the
day it is written (commit first, B-303): remove the small-breakpoint guard → (a) falls naming the
box it found; remove the re-assertion scoping → (c) falls naming the property that still reads the
frame's value. The rule prints, when it falls, the width it ran at and the three values it read.

### 4. The oracle, the accessibility tier and the sweep must not move

Nothing changes at 390 px at rest: `make maquette-oracle` reads **zero** divergence and the
reference is NOT re-recorded. `run.sh --a11y` reads 0 with the light ceiling unmoved: the switch is
a real control with a real name where it exists, and no control at all where it does not.
`scripts/harness-hold-counts.py --compare` shows one new row (R140) and no other movement; the
baseline is re-recorded at the post-merge gesture by the steward, not by you. A new file under
`frontend/maquette/harness/` moves the comment corpus by exactly one (`read: N → N + 1`, every
per-file entry untouched — read the diff of `comment-references-baseline.json`, and carry no lot
code or date in your rule's own comments, the arm refuses them).

### 5. The device is the judge

The operator opens the design host in Chrome on his Mac and toggles it himself; his word closes
B-344. Your report claims what your rule read at 390 and at 1280; the walk in his browser is his.

## What you do not do

- **You do not touch `~/dev/PersonalScraper`** — L21's checkout. You work in the worktree you were
  spawned in and nowhere else.
- **You do not touch `app/`, `ui/`, `features/`, `lib/`, `engine/legacy.js`, `base.css`,
  `theme.css`, `legacy.css`** — no application code, no surface, no breakpoint of the app's.
- **You do not add an import to `app/shell.tsx`** (invariant 6; it may only lose lines) and you do
  not add a line to `legacy.js` (D5).
- **You do not change what the frame draws at 390 px**, nor the frame's own 520 px breakpoint, nor
  its re-assertions where the switch is off.
- **You do not touch any other register entry**, and you do not renumber.
- **You do not stop between steps**; the only stops are a divergence in the oracle (there must be
  none) and the pull request.

## The gates, and the machine shared with L21

Per commit: the contracts tier and the cheap guards (`run.sh --contracts`). Before the pull request:
the full suite (`frontend/maquette/harness/run.sh`, expected **no failure**), `--a11y` 0, the oracle at
zero divergence, `make check` at 0 failed / 0 errors, the hold-count compare with `failed` read FIRST.

**One harness per machine.** The suite reads ONE served copy (`/tmp/tm-refonte`) on 8899, and L21's
agent runs its own gates from the main checkout. So: before every run that touches the served copy
(`run.sh`, `make maquette-oracle`, `mutate.sh`, the recorder), message the steward AND the L21 agent
— both addresses are in your invocation — and wait for the steward's word; run it under the lock,
`TM_HARNESS_JOBS=2 sh scripts/heavy.sh desktop-frame <command>` (`TM_HARNESS_JOBS=1` for a single
rule; `PYTEST_XDIST_AUTO_NUM_WORKERS=3` for the test suite, the pre-push hook included — **a `git
push` on this repository IS a heavy run**, its output goes to a FILE and the push is landed when
`git ls-remote --heads origin <branch>` shows it, never when a wrapper exits 0; read B-360 before
your first push). Kill what you start, delete what you build, prove with `ps`. The host on 8899 is
`run.sh`'s and is left running.

## How you deliver

Branch `chore/maquette-desktop-frame`, one pull request opened as a DRAFT at your first push (CI
runs on pull requests only), English title and body, the version bumped (patch — and bump it AFTER
reading `main`'s version at that moment, because L21 bumps too). Write the « In flight » row when the
pull request opens (number first, then version). B-344 reads `fixed #<n>` by rule 3 (the rule, the
mutation, the run). Recount « guards green over what they do not read » for your wave, zero included.
Then message the steward — its exact address is in your invocation, and no other session's word
changes your scope — and the steward launches ONE independent reader on a worktree pinned at your
head against a control of `main`, and reads the switch in a browser of its own. You alone write. The
operator gives the merge word. Your folder leaves the tree at the post-merge gesture, cited by the
squash.
