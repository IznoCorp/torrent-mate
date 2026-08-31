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

## 6. What is blocked, and why it is the operator's

**Phase 10 builds nothing.** P6 asks for a shared element carrying a poster from a card into its
sheet. Measured:

- `/media/$provider/$id` renders `MediaScreen`, whose hero is a **wide background-image banner**, by
  a decision already taken and written down (« the banner prefers the wide visual; the vertical
  poster is only a fallback »);
- the surface that *does* carry a vertical poster is the long-press panel, reached by **no
  navigation**, so no view transition is involved.

The two further constraints — engine-drawn source, L14-owned destination — are **both soluble inside
this lot** and are not the blocker. **The blocker is product: there is no poster at the destination
to carry a poster to.** Three options are written out in the phase file; **deferral to L19 is
recommended**, because the alternatives either reinterpret the contract's word « poster » or redraw a
surface the operator has validated.

**And the decode half is blocked with it**, correcting what this plan said earlier in the same day:
nothing is carried, so no image's decode can tear anything — and the destination is a CSS
`background-image`, which `decode()` has no handle on.

---

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
| `harness-hold-counts.py --compare` | **0 changed, 6 new (37 holds), none lost** |
| `make check` | **10 961 passed, 4 skipped, 2 xfailed, 0 failed, 0 errors** |
| oracle | **2 958 measurements, no divergence** |

Every rule landed with its mutation seen red and restored.

**Register 147 → 151**: B-271, B-272, B-273, B-274 filed; **B-234 and B-252 closed**.
**B-085 recounted at six**, all six itemised in `BUGS.md`.

**Not claimed**: B-268, B-269 and B-270 stay open — no phase here opened `served_copy.py`, so the
brief's conditional did not fire.
