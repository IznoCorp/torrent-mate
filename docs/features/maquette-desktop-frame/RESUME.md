# maquette-desktop-frame — where this stands, and the exact next step

**Read `BRIEF.md` beside this file first.** This document says only what is
DONE, what is NOT, and what the next session picks up. It is written because the
operator ordered a clean pause on 2026-09-06 while the wave was mid-flight: no
harness run had yet touched the shared served copy, and none may be started
without the steward's word.

## What is committed and landed

Branch `chore/maquette-desktop-frame`, pull request **#576** (DRAFT, `MERGEABLE`). Its head is
on `origin`; the local sha and the remote sha are the same, read on
`git ls-remote`, never from a wrapper's exit code (B-360).

| commit | what |
| --- | --- |
| `cecfc905f` | the switch and R140 |
| `e272ac10e` | B-370 filed |
| `5b15d2cd6` | version |
| `0a0bf8044` | merge of `origin/main` at `163cbfcbb` |
| `1e929d250` | the version moved to 0.98.76 |
| `fc92c1aac` | this file — `1e929d250` claimed it and did not carry it, because `~/.gitignore` ignores `docs/` by default and its own comment says « use git add -f » |

**The switch.** `frontend/maquette/design/index.html` — a checkbox and its label
inside `.stage` and OUTSIDE `#device`, `data-part="harness/desktop-switch"` and
`harness/desktop-switch-label`, the input's id `desktop-switch`.
`frontend/maquette/design/src/styles/harness.css` — `.desktop-switch` added to
the `html.measuring` hide list; the 640 px and 768 px re-assertions AND the
520 px frame block each scoped on `:root:not(:has(#desktop-switch:checked))`; the
control's own block, `display: none` below 520 px and `position: fixed` above it.
No script anywhere: the state is the checkbox's, read by `:has()`, so neither the
engine (D5) nor `app/shell.tsx` (invariant 6) learns the control exists.

**Where it sits, and it is arithmetic rather than a measured number.** Framed:
top-left, `max-width: calc(50% - 211px)`, so its right edge cannot cross the
frame's left edge at `50% - 195px` at any width. Out of the frame the app fills
the window and there is no gutter, so it moves to bottom-left — the one corner
the app's fixed chrome never claims — lifted by `--tm-bottom-bar-h`, the height
the tab bar publishes, which reads 0 where the app hides the bar.

**R140** — `frontend/maquette/harness/desktop_frame.py`, 326 lines, eleven holds,
at 390 × 844 and 1280 × 800. Its expected values are MEASURED, not typed: the
frame's whole contribution is written `.device …`, so the same page with that
class removed from the device is the app's own cascade, at the same width, in
the same browser. One hold exists only to keep that honest — each of the three
forced properties must read DIFFERENTLY with the class off, or a property the
frame never moved could not show the frame leaving.

**B-370** filed: `chrome.py` (R51) opens « the prototype's own controls never sit
on top of the app's » and reads ONE piece of harness chrome by literal.

**Version 0.98.76**, and the number is deliberate. `main` carries 0.98.74; L21's
in-flight row and branch carry **0.98.75**, so 0.98.75 would have collided
whichever of the two merged second. 0.98.76 is past both.

## What has been PROVEN, and on what

Everything below was read on a PRIVATE copy served on port 8897 out of this
worktree — never on `/tmp/tm-refonte`, never on 8899, which belonged to L21 for
the whole session. **No rule was pointed at that private port** (B-325: a rule
run elsewhere is still certified by the stamp of the copy it did not read). What
ran there was a throwaway probe, kept at
`scratchpad/probe.py`, and the server and its copy are gone.

- **`:has()` survives the build.** The emitted stylesheet carries
  `:root:not(:has(#desktop-switch:checked)) .device{…width:390px…}` verbatim.
  Lightning CSS is in the path and no other reading would have shown this.
- **390 × 844**: 0 client rects, 0 area, nothing under `elementFromPoint(20, 20)`,
  and the input does not take focus.
- **1280 × 800 framed**: device 390 px at x 445–835, switch at [16, 16, 97, 26],
  covering nothing of R51's fixed-chrome list.
- **One press**: device 1280 px; tab bar `flex` → `none`, header `padding-left`
  14 px → 24 px, connection label `none` → `block` — exactly what the control
  document reads. Switch moves to [16, 758, 106, 26], still covering nothing.
- **Second press**: 390 px and all three back.
- **`__measure(true)`**: 0 client rects.
- **520 px, the worst width**: the label clips to 49 px and its right edge lands
  exactly on the frame's left edge at 65. The arithmetic holds where it is
  tightest, not only where the operator works.
- **Accessible name**: `- checkbox "Sortir du cadre"` framed,
  `- checkbox "Revenir au cadre" [checked]` out.
- Cheap repository guards: all 23 green, including `check-no-french` (15 arms),
  `check-markup-contracts`, `check-bug-register`, `check-implementation-state`.
- `npm run typecheck` clean; vitest 6 files / 104 tests passed. Both are weak
  here — this wave touches no TypeScript.
- The pre-push gate ran all five checks green on `5b15d2cd6`.

## What is NOT done — the whole remaining gate list

None of these has been run, because every one of them reads the shared served
copy on 8899 and the machine holds ONE harness:

1. **R140 on 8899**, through `run.sh`, `TM_HARNESS_JOBS=1`. It has never been
   executed against the served copy. What it read on the private port is not a
   certification.
2. **The mutation pair**, `scripts/mutate.sh`, committed first (B-303):
   - remove the small-breakpoint guard →
     `'t.replace(".desktop-switch {\n  display: none;\n}", ".desktop-switch {\n  display: flex;\n}")'`
     — hold (a) must fall naming the box it found;
   - unscope one re-assertion →
     `'t.replace(":root:not(:has(#desktop-switch:checked)) .device .bottombar", ".device .bottombar")'`
     — the « the app's own stylesheet answers » hold must fall naming the
     property that still reads the frame's value.
3. **The full suite**, `frontend/maquette/harness/run.sh`, expected no failure.
4. **`run.sh --a11y`** — expected 0 with the light ceiling unmoved. Note, and it
   is this wave's own « guard green over what it does not read »: the
   accessibility tier audits at 390 px, where the control is deliberately absent,
   so it reads NOTHING of this change. R140 holds the naming and the labelling
   instead.
5. **The oracle** — expected **zero divergence**, and the reference is NOT
   re-recorded. It measures at 390 px where the control is `display: none`.
6. **`scripts/harness-hold-counts.py --compare`**, `failed` read FIRST —
   expected one new row (R140) and no other movement. The baseline this branch
   carries is `f70ca0295`, 93 rules / 2 199 holds / failed 0.
7. **`make check`** — 0 failed, 0 errors.

## The two arbitrations, and how they were ruled

**1 — the brief's `fr.json` instruction could not be followed, and the tree says
why.** `index.html` is static markup served raw (`serve.py` hands over
`dist/index.html`, no templating) and there is no markup i18n anywhere: no
`data-i18n`, nothing in `legacy.js`. Every string in that document is written in
place and none is in `fr.json` — checked: « Aller au contenu », « Se connecter »,
« Identifiants invalides », « Notes de conception », « Harnais », zero hits.
Adding a namespace nothing reads would be a dead resource AND a retyped string.
**Ruled by the steward: write the two labels in `index.html`**, beside the
harness's other strings, and say so in the pull request. `check-no-french` does
not refuse them, which is the tree confirming the ruling rather than an argument.

**2 — the machine.** A build is a heavy run and goes under
`sh scripts/heavy.sh`; a static server on a private port is not and runs
unwrapped; anything driving a browser is a browser group and goes under the lock.
No rule is ever pointed at a private port.

## The memory floor override, and its scope

`scripts/heavy.sh`'s default floor is 4 096 MB free, and on this host that floor
is not reachable while three sessions are up: about 4.4 GB is kernel-wired and
reclaimed only by a reboot. A wrapped push sat 33 minutes in the readiness loop
holding the lock and never started. **The steward's ruling**: kill the wrapper
and re-run with the script's own documented override,
`HEAVY_FREE_FLOOR_MB=3072`, for runs driving at most two browser groups
(`TM_HARNESS_JOBS=2`), never for a larger fan-out. The push then landed with all
five pre-push checks green. The override is the steward's and is filed as a
register entry against `heavy.sh`; it is not this wave's to write about.

## Two findings this wave paid for, and they are worth carrying forward

**A probe caught a defect in R140 before R140 ever ran.** The accessible-name
hold read `label.textContent`, and `textContent` returns BOTH words — the one on
screen and the one `display: none` is holding back. That hold was green over a
name that never changes and over a control announcing two contradictory verbs at
once: B-085's shape written into a brand-new rule on its first day. It reads the
accessibility tree now, and a hold was ADDED that the name must DIFFER between
the two states.

**`check-markup-contracts` refused four class-anchored selectors in the rule**
(D4, and it was right). Three of them now anchor on `data-part`; the fourth, the
connection label, has no naming attribute of its own — its owner is in `app/`,
which this wave may not touch — so it is reached structurally,
`[data-part="shell/connection-mark"] > span:last-child`.

## The exact next step

1. Ask the steward for the served copy and 8899. Nothing on that copy without it.
2. Rebuild it from this branch, then run items 1 to 7 above in that order.
3. **The « In flight » row is NOT written, deliberately.** The single row in
   `IMPLEMENTATION.md` names L21 (PR #572, draft), and this micro-wave runs
   BESIDE L21 rather than in its place. Overwriting another wave's row is not a
   call this session was willing to make alone, and `check-implementation-state`
   reads clean as it stands. **Ask the steward where a beside-a-lot micro-wave's
   row goes**, then write it.
4. Close **B-344** with `fixed #576` — the closure arm requires the entry's BODY
   to change in the same commit, not only its status.
5. Recount « guards green over what they do not read » for this wave on the final
   head, zero included, and write the figures ONCE, there.
6. Then the steward launches its independent reader; the operator judges on his
   Mac and his word closes B-344.
