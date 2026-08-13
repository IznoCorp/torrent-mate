# Bug register

Every defect the operator reports lands here **the moment it is reported**, before any work
starts. A bug leaves this file only through the `Fixed` column, and only with a rule that fails
when the defect comes back.

## Rules of this file

1. **Reported = written down.** No triage, no judgement first. An unwritten bug is a bug that
   comes back a third time.
2. **One bug is closed at a time**, and the operator confirms the fix before the next one starts.
3. **A fix is not a fix without a rule that bites.** The rule is mutation-tested: break the
   behaviour on purpose, confirm the rule falls and names the right defect, restore. A closing
   entry names the script and the mutation.
4. **The rule must cover the path the operator actually walks.** Several bugs below survived a
   green harness because the rule drove a named state instead of the real journey — a cold load,
   a real finger, a real browser menu.
5. **Repeats are counted.** `Reported` records every time the operator has had to say it again.
   A count above one is a failure of this register, not of memory.

## Status vocabulary

| Status | Means |
| --- | --- |
| `open` | Reproduced and diagnosed, not yet fixed. |
| `fixing` | Being worked on right now. Exactly one bug may hold this. |
| `to confirm` | Fixed, rule green, mutation proven — waiting for the operator. |
| `closed` | Operator confirmed on a real device. |

---

## Open

| ID | Defect | Reported | Status |
| --- | --- | --- | --- |
| B-001 | The list poster is still too small | 2× | `open` |
| B-002 | The startup bar is never seen on a real load | 2× | `open` |
| B-003 | In Arrivées a poster does not lead where a poster leads | 2× | `open` |
| B-004 | Dragging the sheet handle down no longer closes the panel | 2× | `open` |
| B-005 | A long press on a poster raises the browser's own menu | 2× | `open` |
| B-006 | Two different sign-in screens: arrival and sign-out | 1× | `open` |
| B-007 | `--accent` is referenced 11 times and defined nowhere | 1× | `open` |

---

## B-001 — The list poster is still too small

**Reported** 2×. **Status** `open`.

**What happens.** Measured on the four pages at 390 px: every list poster is **49 × 74 px**. It
was 42 px, so it did change — by 17 %, which reads as "unchanged" on a phone where 49 px is 12.5 %
of the width.

**Why it is still wrong.** The size came from a derivation pinned to the median card's TEXT
height, so the poster can never grow past the text beside it. The operator had explicitly lifted
that constraint — « quitte à faire des cards plus hautes » — and the derivation kept it anyway.
The number is the honest output of the wrong question.

**Why no rule caught it.** R47 checks the poster matches the derivation. Whatever number the
derivation yields, the rule agrees with it. **A rule that checks arithmetic against itself cannot
report that the arithmetic answers the wrong question.**

**What closing it requires.** Re-derive with the card height free, then a rule that pins the
poster to a share of the CARD, not of the text column, so shrinking it back is a failure.

---

## B-002 — The startup bar is never seen on a real load

**Reported** 2×. **Status** `open`.

**What happens.** Measured on a cold load: at the first frame the splash is visible with the bar
at 0.4 px; by 300 ms it is **hidden** and the bar reset to 0 %. The five-second fill exists and
plays for about one frame.

**Why.** `masquerDemarrage()` is called **synchronously** on the line after the first `render()`.
In the prototype nothing is fetched, so the first render returns immediately and the screen it
was covering is already there.

**Why no rule caught it.** R53 measures the splash through `__go('demarrage')` and through the
login submit, which holds it on a 1100 ms timer. Both put the screen up artificially. **No rule
ever loaded the document and watched.**

**What closing it requires.** A floor on how long the screen stays — the bar reaching 100 % in
five seconds, leaving earlier only when loading finishes — and a rule that measures a COLD LOAD,
sampling the bar's width over time.

---

## B-003 — In Arrivées a poster does not lead where a poster leads

**Reported** 2×. **Status** `open`.

**What happens.** Arrivées cards do come from `cardHTML`, the same builder as everywhere else. But
their poster is `poster sansfiche`, carrying `data-panel`: it opens the **bottom panel**. Every
other poster in the interface opens the **media sheet**. Same object, same look, two destinations.

**Why.** A stuck folder has no medium yet, so it has no sheet to open. Rather than saying so, the
poster was pointed at the panel — which gave it a destination and broke the one invariant the
whole card system rests on: « the poster opens the media sheet ».

**Why no rule caught it.** `cartes.py` checks each card against its own shape. Nothing checks that
one visual element keeps ONE behaviour across pages. **The invariant was written in prose and
never made executable.**

**What closing it requires.** Decide what a poster with no medium does — most likely not be a
poster at all — and a rule that walks every page and fails when the same element leads two ways.

---

## B-004 — Dragging the sheet handle down no longer closes the panel

**Reported** 2×. **Status** `open`.

**What happens.** Reproduced under a real finger driven through CDP: a 150 px downward drag from
the handle delivers `pointerdown` ×1, `pointermove` **×2**, then `pointercancel`, and `pointerup`
**never**. The touch stream survives it — `touchmove` ×14, `touchend` ×1. `closeSheet()` hangs off
`pointerup`, so the sheet stays open.

**Why.** The handler reads the pointer stream, takes no `setPointerCapture`, and the handle
declares no `touch-action`. The compositor claims the vertical axis and cancels the pointer
stream — the exact mechanism that had already cost the pull-to-refresh and the view swipe.

**Why no rule caught it.** R55 was written for that mechanism and covers the pull-to-refresh and
the page swipe. **The sheet handle is a third gesture and no rule looked at it.** The lesson was
recorded, then not applied where it applied next.

**What closing it requires.** Read the finger from the touch stream, or capture the pointer and
claim the axis; then extend R55 to every draggable surface, sheet handle included.

---

## B-005 — A long press on a poster raises the browser's own menu

**Reported** 2×. **Status** `open`.

**What happens.** On a phone, a long press on a poster raises the browser's copy / open-image
menu instead of, or on top of, the bottom panel.

**Why.** `grep contextmenu` over the whole prototype returns **nothing**. `user-select: none` is
set and stops text selection; `-webkit-touch-callout: none` is set and only ever answers iOS
Safari. Android Chrome raises its menu from the `contextmenu` event, which nothing prevents.

**Why no rule caught it.** The long-press rule asserts the PANEL OPENS. It never asserts the
browser's own menu is refused — and a synthetic touch never raises a native menu, so **no script
written that way could have seen it.** The observable fact to assert is that `contextmenu` is
prevented, not that a native menu is absent.

**What closing it requires.** Refuse `contextmenu` on everything that answers a long press, and a
rule that dispatches `contextmenu` and fails when `defaultPrevented` is false.

---

## B-006 — Two different sign-in screens: arrival and sign-out

**Reported** 1×. **Status** `open`.

**What happens.** Arriving at the design host serves `serve.py`'s gate page. Signing out inside
the prototype shows `#login`. They are two documents and they do not look the same.

**Why.** `page_connexion()` extracts the prototype's login markup and styles — correctly — and
then adds a hand-written `socle` block defining a palette of its own. The prototype's screen never
gets that block.

**Why no rule caught it.** `deconnexion.py` checks that signing out LANDS on the entry screen.
Nothing compares the two renderings of the same screen. **A surface that exists in two places was
verified in one.**

**What closing it requires.** One screen, extracted once, with the host adding only what a page
needs that a phone frame does not; and a rule comparing the two renderings.

---

## B-007 — `--accent` is referenced 11 times and defined nowhere

**Reported** 1× (as "the sign-out screen has no TorrentMate style"). **Status** `open`.

**What happens.** On the prototype's sign-in screen the funnel is **white** instead of orange,
« Mate » is white, and « Se connecter » has **no background**. Measured: `var(--accent)` appears
**11 times** in `refonte.html` and `--accent:` is defined **0 times**. Every reference is invalid
at computed-value time, so the colour silently falls back and the background disappears.

**Why it was invisible.** `serve.py` retypes `--accent: #f5a524` into its `socle`, so the host page
— the only place the screen had been looked at — renders correctly. The prototype's own screen
was never looked at after the palette was renamed to `--primary`.

**This is the project's own rule broken.** « CSS is extracted, never retyped »: a retyped value
made the host look right and hid a defect in the reference.

**Why no rule caught it.** `export.py` checks class coverage. **Nothing checks that every custom
property referenced is defined**, so a whole palette can be dangling and every screen still
renders "something".

**What closing it requires.** Define the accent once, or point the eleven references at
`--primary`; then a rule collecting every `var(--…)` in the file and failing on any name never
defined. Seven other references live outside the login screen and must be checked with it.

---

## Closed

_None yet._
