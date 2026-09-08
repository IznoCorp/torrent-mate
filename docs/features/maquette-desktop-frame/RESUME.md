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

**Where it sits. Framed it is arithmetic; out of the frame it is a table.**
Framed: top-left, `max-width: calc(50% - 211px)`, so its right edge ABUTS the
frame's left edge at `50% - 195px` at any width and never crosses it.

Out of the frame it goes to the **top centre**, and the sentence this paragraph
used to carry — « bottom-left, the one corner the app's fixed chrome never
claims » — was false. Out of the frame the app fills the window, so there is no
corner it does not claim: all 87 named states were walked and every candidate
counted against every button, link, input and ARIA control the app draws.

| candidate | states crossed |
| --- | --- |
| bottom-left (where it was) | **60** |
| bottom-centre | 46 |
| top-left · top-right · bottom-right | 87 each |
| **top-centre** | **0** |
| icon-sized, bottom-left / top-left / top-right | 61 / 87 / 87 |

Top centre is the only one free in all 87, and an icon-sized box rescues none of
the others. It does not collide with the harness's own bar either: the bar is at
the top bar's empty middle while the frame is drawn — which top centre WOULD
cross — and at the top right out of it. The control is only ever at top centre
out of the frame, so the two are never in the same place at once, and the sweep
reads other harness chrome beside the app's controls rather than leaving that to
a comment.

**R140** — `frontend/maquette/harness/desktop_frame.py` and its page scripts in
`desktop_frame_page.py`, **twenty-four holds**,
at 390 × 844, 1280 × 800 and 520 × 800, plus a presence sweep over seven widths
derived from the stylesheet's own breakpoints and an 87-state walk out of the
frame. Its expected values are MEASURED, not typed — and, since round four, they
are measured against something the frame does not itself declare: the
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
- Cheap repository guards: all green, including `check-no-french` (15 arms),
  `check-markup-contracts`, `check-bug-register`, `check-implementation-state`.
  (This line read « all 23 green ». `run.sh` prints its own count and the full
  suite reported **27** on 2026-09-07 — a number written into prose goes stale,
  which is the trap `CLAUDE.md` names twice about this very script. The count is
  the script's to print, not this file's to record.)
- `npm run typecheck` clean; vitest 6 files / 104 tests passed. Both are weak
  here — this wave touches no TypeScript.
- The pre-push gate ran all five checks green on `5b15d2cd6`.

## What has been READ, and on what — the gate list, run 2026-09-07

The steward gave this session the served copy and 8899 for the whole list, in order.
The machine had rebooted: `/tmp/tm-refonte` was gone and nothing listened on 8899, so
the first run rebuilt both from this branch. Every run wrapped —
`HEAVY_FREE_FLOOR_MB=3072 sh scripts/heavy.sh desktop-frame …` — output to a file.

1. **R140 on 8899**, against the shared served copy: `14 rules EXECUTED — no violation`.
   The stamp read `41862-1788805584169005000` before AND after, so the reading spans
   one build. `run.sh` has no single-rule mode — its argument parsing accepts only
   `--oracle`, `--a11y`, `--contracts` — so this was its own preamble invoked for one
   rule: the same lock, the same single assembly point, the same stamp check.
2. **The mutation pair**, `scripts/mutate.sh`, tree clean. The small-breakpoint guard
   opened → the phone hold falls ALONE, naming the box it found: `client rects 1,
   area 2516.3125, takes focus True`. One re-assertion unscoped → the « the app's own
   stylesheet answers » hold falls ALONE, naming the property still reading the frame's
   value: `tab-bar: flex` against an unframed `none`. One violation each.
3. **The full suite**: `harness: 94 rule(s) and 27 repository guard(s), no violation.`
4. **`--a11y`**: `87 states, 0 violation(s)`; light tier `166 against a ceiling of 166`,
   exactly unmoved. It audits at 390 px where this control is deliberately absent, so it
   reads NOTHING of this change — reported as a gate that passed, never as evidence.
5. **The oracle**: `87 states x 34 regions, 2958 measurements`, `reference taken at
   f70ca029`, **`no divergence`**. The reference is NOT re-recorded.
6. **`harness-hold-counts.py --compare`**, `failed` read FIRST: **0**. Then
   `0 changed · 0 missing · 1 new` — `NEW desktop_frame.py (14)`. 93 rules / 2 199 holds
   at `f70ca0295` become 94 / 2 213. The baseline is NOT re-recorded here: the steward
   does it at the post-merge gesture.
7. **`make check`** — see the pull request.

**The « eleven holds » this file carried until now was WRONG**, and a second instrument
caught it: the compare parses the count from the rule's own journal, independently of
anyone reading the rule's output. The figure predates the three holds the probe's finding
added. It is fourteen.

## Two defects in the instruments, found by running them

**`scripts/mutate.sh` said « NO RULE FELL. That is the finding. » over a rule that had
CRASHED.** The first mutation ran with nothing serving 8899: the rule died on
`net::ERR_CONNECTION_REFUSED` with exit 1, and the tool — which discards the exit status
(`|| true`) and greps only for journal `FAIL` lines — reported it in the exact words of a
rule that read the page and was unmoved. The reading was false and was believed for one
command. Filed as **B-273's third case**, on the steward's ruling that `main` already
holds the species; the repair is B-273's owner's, not this wave's.

**The 8899 host does not survive the invocation that starts it under the wrapper.**
`run.sh` forks the host inside its own run; `scripts/heavy.sh` runs that command under
`set -m`, in a process group it signals on release. Harmless for `run.sh`, which restarts
what is not listening — harmful for `mutate.sh`, which starts no host. Filed as **B-371**.
The host is now started with `nohup` OUTSIDE the wrapper and stays up.

## The two arbitrations, and how they were ruled

**1 — the brief's `fr.json` instruction could not be followed, and the tree says
why.** `index.html` is static markup served raw (`serve.py` hands over
`dist/index.html`, no templating) and there is no markup i18n anywhere: no
`data-i18n`, nothing in `legacy.js`. Every string in that document is written in
place and none is in `fr.json` — checked: « Aller au contenu », « Se connecter »,
« Identifiants invalides », « Notes de conception », « Harnais », zero hits.
Adding a namespace nothing reads would be a dead resource AND a retyped string.
**Ruled by the steward: write the two labels in `index.html`**, beside the
harness's other strings, and say so in the pull request.

This paragraph ended « `check-no-french` does not refuse them, which is the tree
confirming the ruling rather than an argument », and that sentence has been
STRUCK. It was not evidence. The guard's text arms are rooted on `design/src`
and `index.html` sits above it, so no arm reads text in that file at all — the
silence means « not looked at », not « looked at and allowed ». The ruling stands
on the argument above it, which is about the tree; **B-372** carries the guard's
blind spot.

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

**And round one's reader showed that repair was HALF of one.** Moving from
`textContent` to the accessibility tree closes « the name never changes ». It does
not close « both verbs at once », because an accessible name is computed from the
label's RENDERED subtree: with the CSS that hides one span defeated, the name
becomes « Sortir du cadre Revenir au cadre » and BOTH holds stay green — one word
and two words are never equal. The name is held against the single VISIBLE span
now, in both states. A repair that closes one of a defect's two halves and is
written up as closing the defect is the shape this wave paid for twice.

**`check-markup-contracts` refused four class-anchored selectors in the rule**
(D4, and it was right). Three of them now anchor on `data-part`; the fourth, the
connection label, has no naming attribute of its own — its owner is in `app/`,
which this wave may not touch — so it is reached structurally,
`[data-part="shell/connection-mark"] > span:last-child`.

## What remains

1. The steward's independent reader, on a worktree pinned at this head against a control
   of `main`, and its own reading of the switch in a browser.
2. The operator opens the design host in Chrome on his Mac, toggles it himself, and his
   word closes B-344 in fact. This file records what the rules read; the walk is his.
3. The post-merge gesture: the hold-count baseline re-recorded on the squash with `failed`
   read FIRST, the oracle's reference re-anchored, this folder leaving the tree cited by
   the squash, and the trace written into `IMPLEMENTATION.md`'s « Between L19 and L21 »
   row beside the schedulers' and the departure's — a micro-wave running BESIDE a lot
   writes no « In flight » row, which is L21's.
