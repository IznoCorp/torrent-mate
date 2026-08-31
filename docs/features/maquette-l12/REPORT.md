# L12 — Native interaction · REPORT

**Pull request #540 · version 0.98.58 · branch `feat/maquette-l12` · opened 2026-08-31.**

---

## 1. What this wave actually produced

**Not the transitions.** The transitions, the gestures and the window all work, and every one of
them landed with a rule. But the wave's output is **six instruments that could not fail, caught
because something forced them to**, and two blocked properties whose blockers are product decisions
rather than technical ones.

L11's warning was the brief's central one — ~40, 13, 7 and 0 product defects across four adversarial
rounds under a permanently green gate — and this wave met the same shape from a different direction:
**the oracle was green over 2 958 measurements at every single step, including over four defects it
had no way to see.**

---

## 2. The properties

| Property | Before | After | Held by |
| --- | --- | --- | --- |
| **P25** no tap flash | 0 declarations in the tree | declared once on the root | `check-compositor-css.py` |
| **P26** a long press selects nothing | partial, in the dying stylesheet | derived from `armPress`'s own selector | same |
| **P11** dynamic viewport | `height: 100%` | `100dvh`; `vh` refused tree-wide | `check-viewport-directives.py` |
| **P17 / B-234** keyboard resizes content | absent | on **all six** viewport metas | same |
| **P5** declared page transition | 0 | `startViewTransition` + `::view-transition-*` | **R115** |
| **P20** reduced motion | one place in the tree | a designed state for every transition added | **R113**, **R115** |
| **P24** no unvirtualised long list | infinite scroll | `@tanstack/react-virtual`, windowed | **R117** |
| **P29** no layout shift | undeclared instrument | a static guard **and** a CLS probe | `check-poster-box.py`, **R114** |
| **P16** gestures survive the compositor | true for what was measured | extended: the tolerance, the swallow, the pull threshold | **R112** |
| **B-252** two child nodes | open | **closed** | **R116** |

**The engine shrank by subtraction and grew by nothing**: `legacy.js` 32 604 → 32 420 non-blank,
**184 lines removed** (D5). The press arbitration and pull-to-refresh are `lib/` vocabulary now;
their engine-side callers stay for L19, by the brief's own boundary.

---

## 3. The six instruments that could not fail

**Every one was found by mutation or by another guard. None by reading.** That is the only reason
they were cheap.

1. **B-272 — the compositor manifest's floors carried slack its own note denied.** `taken_at` said
   « the figures below are the real sites, so a deletion has no slack to hide in ». Measured:
   `touch-action` at **8 against 11**, `user-drag` 3 against 4, `user-select` 4 against 5. **Three
   declarations were deletable under a green guard** — inside the instrument written to prevent
   exactly that deletion. Found because a two-declaration mutation produced ONE violation where two
   were owed. *The rule fell, and falling was not enough; the count was.*
2. **B-274 — `page_host.py` read docstrings as code.** Its state-alias arm strips quote characters
   deliberately (a driver is a string, split at the author's convenience), which turns prose into
   something that parses: a docstring ending « … the pressed state. » before `errors = []` flattens
   to `state. errors =`. It accused a rule that mutates nothing. **B-085 with its sign reversed** —
   red over what it should not read. Fixed narrowly with `ast`, and verified BOTH ways, because a
   fix that blinds the arm looks identical from here.
3. **The viewport guard's floors ran after its own summary.** A run that fired a floor printed
   « 0 violation(s) » on the line a human and a log read, while exiting 1. Found by a mutation that
   *looked like* a rule which had not bitten.
4. **R112's tolerance hold could not fail, twice over.** Its driver ramped the drift across the whole
   hold, so the 480 ms press timer fired before the drift ever passed 12 px — the tolerance was never
   consulted. And, once that was fixed: **under a real touch stream the tolerance is unobservable at
   all.** Chrome's compositor cancels the press at every drift ≥ 14 px whether the tolerance exists
   or not — measured both ways at seven distances, identical. **Only a real mouse isolates it**,
   because the compositor never claims a mouse gesture, and the hold now asserts
   `pointercancel == 0` so that it proves something about the arbitration rather than about the
   browser. *This inverts the repository's standing lesson: here the mouse is the truth.*
5. **R112's swallow hold could not fail either.** Every `pointerdown` clears the mark, so a
   deliberate tap is never swallowed *whatever* the point check does. The check's real subject is a
   click arriving with **no pointerdown** — a programmatic or keyboard-fired click — and it must be
   probed with the finger still **down**, because the lift's own click consumes the mark 1 ms later.
6. **R113's reduced-motion hold was satisfied by a stylesheet saying nothing.** « Nothing animates »
   is true of an absent rule. Reduced motion is a **designed** state (invariant 14), so the hold had
   to read that the marked node *looks different*, not merely that it does not move.

**Three holds now carry explicit controls** — a 5 px press that must open, a mark that must be set,
a long pull that must refresh — because a negative hold with no control passes just as well over a
mechanism that never worked.

---

## 4. Defects the rules found in this wave's own work

- **R113 found phase 4's acknowledgement was invisible.** The seam marked the pressed node and
  `onPress` re-renders it: measured, `isConnected` false while the mark still read `commit`. **Not
  repaired by moving the mark** — the panel appearing under the finger *is* that gesture's
  acknowledgement, and a pulse on top would be a second answer to one gesture. The call stays for the
  haptic half; the rule observes the call.
- **R115 found phase 9's reduced-motion CSS incomplete.** One animation still ran under `reduce`: a
  view transition is drawn as a *group* containing an image *pair*, and the browser animates the
  group too. Silencing `-old` and `-new` leaves one running.
- **`boot_order` found that the transition had made `go()` asynchronous.** Phase 9's commit message
  claimed it was safe and cited the ladder rules — **and was wrong**: the ladder rules pass because
  they *wait*. Measured, the address had not moved after a microtask nor after a
  `requestAnimationFrame`, only ~120 ms later, which breaks the « one call, one entry » the engine's
  unwinding counts. The fix asks for the snapshot first and commits *now*; both properties verified,
  not one.
- **`navigation` found unhandled rejections.** A superseded transition rejects `ready` and `finished`
  — what a fast thumb causes all day — and they reached the console as errors.
- **`cards.py` R50 fell on a pixel-perfect layout.** The window's `display: contents` wrapper left a
  tile's `parentElement` as the wrapper rather than `.gallery`. **The oracle was green**, correctly.
  The wrapper is gone: spacers are part of the same markup string.
- **The windowing was not pixel-identical at first** — 33 divergences, all exactly +16 px, because a
  spacer is itself a grid child and brings its own gap. The un-windowed list has N rows and N−1 gaps;
  three children make it N+1.

---

## 5. The library question, reversed mid-wave

The operator **reversed D9's rule 2** on 2026-08-31. This wave's design had argued a **refusal** —
« windowing a uniform list is arithmetic » — and that argument is **void**. It is kept above its
replacement rather than deleted (§ 7.1), so the next wave sees it was tried and overruled.

Three candidates were surveyed with registry facts. All MIT, all maintained, all released within six
weeks: **those criteria separate nothing.** **Rule 1 does**, and it is untouched — `react-virtuoso`
and `react-window` each render their own scroller and write inline styles onto every child.
`@tanstack/react-virtual` is headless. **The operator named it.**

**The geometry measurement corrected the design in both directions.** The grid *looked* variable —
two heights, 171 and 203.34 — and those were **skeletons**: `[data-part="tile"]` selects `.sk.tile`
too. Real tiles are 24 of 24 at 203.34. And the card list, assumed variable because §12 requires a
long title to wrap, is exactly 126 px throughout. **Both modes are fixed-height.** A virtualiser
configured from the first reading would have paid measurement cost per row for a spread no rendered
list contains.

**The ≤ 613 ceiling held, and it took three attempts** — 636, then 621, then 616, then 613 exactly.
The stop-and-report was armed at each one and would have fired.

---

## 6. The operator's four decisions, and the defect they uncovered

**Phase 10 was declared blocked on a premise that was FALSE, and the operator corrected it.**

This wave reasoned that P6's shared element had no destination: the media screen leads with a wide
fanart, and the surface carrying a vertical poster — the long-press panel — is reached by no
navigation. Two errors:

1. **The media page keeps its fanart definitively.** « Defer to L19, when the surface is redrawn »
   rested on a redraw that will never come, so it abandoned P6 in silence.
2. **`startViewTransition` animates any DOM change, not only a navigation.** Ruling the panel out
   « because it does not go through `go()` » confused the mechanism with the possible. The panel
   already pushes a history entry and is already addressable.

**P6 is built and true.** The poster travels from the tile into the panel. `app/shared-poster.ts`
marks exactly one poster at the moment the gesture picks it — `view-transition-name` must be unique,
so no class rule can place it — and the name lives in the stylesheet (rule 1). The proof is
`::view-transition-old(carried-poster)` **and nothing else**: a `group` and a `new` exist for any
newly named element, so every weaker reading is green over a poster that does not travel.

**Transitions A and A-extended** land with it: the fanart fades up while the content block rises, no
shared element (there is nothing honest to share between a 2:3 poster and a banner); and the panel
carries its own name so its old snapshot slides down while A plays underneath, Back playing the
mirror — which §16 requires anyway. All three names are keyed on attributes the surfaces already
emit, so **not one line is added to `media-screen.tsx`**, one of L14's four.

**D9's virtualiser row is written as DECIDED**, citing the operator's naming. There is nothing left
to ask.

### And building them exposed the wave's sharpest defect

**The page transition was DEGENERATE, and every gate was green over it.**

Phase 9 kept `go()` synchronous by asking for the capture and committing immediately after. It kept
the synchrony and animated **nothing**: the browser captures the old state after the current task, so
the commit had already run and the « old » snapshot *was the new page*.

**What proved it is a name that exists on one side only.** Transition A names the media screen's
hero, and `::view-transition-old(screen-banner)` was present — while the library page it leaves
carries **zero** `[data-part="hero"]`. An old snapshot for a name the old state does not contain can
only mean the new screen was already mounted when the snapshot was taken.

**R115 was green throughout, and correctly by its own words**: animations ran, and it counted them.
*« A view transition is running »* and *« a view transition is showing the previous state »* are
different claims, and only the first was ever held. The oracle could not see it either — it measures
settled states, and both ends were right.

The commit runs inside the callback now. **`go()` is asynchronous again**, said plainly: the flush
still keeps « one call, one entry » (that was always about the router batching two writes in ONE
task), and the ladder was re-read rather than assumed. `boot_order` read the address in the same
evaluate as the screen call — its hold is about the seams being filled, not about synchrony, so the
call and the read are two steps now.

**A probe that truncated its own evidence nearly cost a re-architecture.** While building P6, a
reading sliced the pseudo-element list to eight rows while ten were running, cutting off the two
`old(carried-poster)` rows — and the conclusion drawn was that the shared element did not work.
It did. *A rule that truncates its evidence reports a defect that is not there, which is the mirror
of the guard that reports none that is.*

## 6b. P6 was built, then WITHDRAWN — and what replaced it

**The operator watched the real slow-motion and withdrew the gesture**: « la transition poster entre
liste et panneau n'est vraiment pas fluide du tout, elle est même très dérangeante, je préfère qu'on
la retire et qu'on trouve autre chose. »

Withdrawn entirely, **including its rule** — a rule measuring a withdrawn gesture is a rule with no
subject, which is the disease § 7.1 exists to fight. `app/shared-poster.ts` deleted, both
`carried-poster` ends and the group rule gone, R115's eight holds removed. **The view transition
around the panel's opening went with it**, and that was a judgement rather than rote: the sheet
already slides in its own stylesheet, so wrapping it without the carry would have been the same
two-systems-one-element defect the hero was about to pay for.

**What replaced it — « l'accusé de presse me plaît »**: the panel rises over `--duration-4` on
`--ease-emphasized` with the scrim darkening on the same step, and the tile **sinks and darkens while
the press ARMS**, releasing as the panel arrives. It plays what the carry was for — binding the panel
to the card that summoned it — in place, moving nothing across the screen.

**Three moments, held apart because they are easy to conflate**: `:active` is the finger being down
at all, `[data-feedback]` is the acknowledgement *after* a gesture commits, `[data-pressing]` is the
span between. A hold reading only « something changed while the finger was down » is satisfied by
`:active` alone.

**The durations and curves are DRAWINGS and are not treated as validated.** The steward re-films at
0.25 playback; the operator has the last word.

## 6c. The hero's flash — a CLASS of defect, and my own « fix » could not work

The steward's bench sampled at 25 ms: the transition drew the hero full for 315 ms, the element went
to **opacity 0 in one frame** when the transition ended, and `heroin` replayed its 450 ms entry.
Appear, flash, reappear — the operator read it as a bug and was right.

**The mechanism is general.** A CSS animation on a tree mounted under `startViewTransition` does not
START until the transition ENDS — rendering is frozen for the capture — so **any element-side entry
animation on a surface reached by a transition replays afterwards**, over a snapshot that already
showed the final state.

**And `:active-view-transition` cannot guard it**, which is the correction of what I had shipped one
commit earlier: by the moment the animation starts, the transition is over and the selector no longer
matches. My guard silenced nothing.

**The fix is ownership**: an entry has ONE owner, and on a surface reached by a transition that owner
is the transition. **Removing only the Tailwind utility left it running** — `heroin` was declared
twice, as a utility and as a residue rule — so the repair was re-measured rather than assumed. *A
duplicated declaration is a defect that survives half a repair.*

The audit found no other instance. **The trap has its line in § 6**, named against L12, and the rule
holds the **symptom** rather than the cause: the arriving background's opacity is sampled through the
whole arrival and a dip is refused. A static grep for `animate-*` would have to know every spelling
of an entry, and would have missed this one twice over.

## 6d. §16's mirror — verified, and PRE-EXISTING

Back from a media screen opened via « Voir la fiche » lands on `/` with the panel not reopened.
**Identical on `origin/main` (5322c2fa)**, same flow, same 1.3 s. Filed as **B-275**. The cause is the
ladder — `switchPageFromLayer` REPLACES the layer's entry rather than pushing over it — and that
handler is **L13's**, which this lot may not touch. The mirror rule is written, correct, and has no
subject today; it is kept.

**The first attempt at that comparison was worthless and the entry says so**: `git checkout
origin/main` was REFUSED because a source file was still modified, so the « comparison » ran on the
branch under test. *A checkout that aborts is not a checkout*, and it nearly produced a false
attribution.

## 7. Device-only protocols — written and dated, never claimed as passed

Neither was exercised, and `MODEL.md` § 3.1 is explicit that they are protocols rather than gates.

- **The interaction budget on a real device.** Not measured. A headless browser's frame timing says
  nothing about a phone's.
- **Whether `:active` still needs a touch listener to fire.** Not measured. If it does, the remedy is
  **one empty listener**, never a per-component JavaScript state.

---

## 8. The gates

| Gate | Result |
| --- | --- |
| `run.sh` full suite | **85 rules + 25 guards, no violation** |
| `run.sh --a11y` | 87 states, 0 violations; light-theme debt **at its ceiling**, unmoved |
| `harness-hold-counts.py --compare` | **6 new rules; 3 later ROSE (press +1, transition +12, virtual +1). Nothing ever lost a hold** |
| `make check` | **10 961 passed, 4 skipped, 2 xfailed, 0 failed, 0 errors** |
| oracle | **2 958 measurements, no divergence** |

Every rule landed with its mutation seen red and restored.

**Register 147 → 151**: B-271, B-272, B-273, B-274 filed; **B-234 and B-252 closed**.
**B-085 recounted at six**, all six itemised in `BUGS.md`.

**Not claimed**: B-268, B-269 and B-270 stay open — no phase here opened `served_copy.py`, so the
brief's conditional did not fire.
