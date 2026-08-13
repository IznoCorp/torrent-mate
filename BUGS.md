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
| B-002 | ~~The startup bar is never seen on a real load~~ | 2× | `to confirm` |
| B-003 | ~~In Arrivées a poster does not lead where a poster leads~~ | 2× | `to confirm` |
| B-004 | ~~Dragging the sheet handle down no longer closes the panel~~ | 2× | `to confirm` |
| B-005 | ~~A long press on a poster raises the browser's own menu~~ | 2× | `to confirm` |
| B-006 | ~~Two different sign-in screens: arrival and sign-out~~ | 1× | `to confirm` |
| B-007 | ~~`--accent` referenced 11 times, defined nowhere~~ | 1× | `to confirm` |

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

**Reported** 2×. **Status** `to confirm`.

**Fixed.** The screen now comes off when the wait it covers RESOLVES, through a named seam
(`window.__chargementTermine()`) called by a timer the length of the bar here and by whatever
knows the interface is ready in the app. The early exit is not a second path: resolving sooner
ends it sooner. Measured on a cold load: visible at 0 ms, still up at 5.1 s, the bar monotonic
from 0 to 99 %, gone at 5.4 s; and resolving at 800 ms ends it at once. Rule R53 extended,
`harness/demarrage.py` — 27 checks, three mutations proven: the screen dropped on the first
render (the original defect), the bar filling in one second, the seam made inert.

**A rule was asserting the defect.** « retiré par le premier rendu, sans le harnais » certified
that the screen vanished immediately, and the suite called that conformity. What a rule asserts is
a decision — writing down the behaviour that exists is not the same as writing down the one that
is wanted. Twenty-eight harness scripts now close the startup wait through the same seam rather
than racing it.

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

**Reported** 2×. **Status** `to confirm`.

**Fixed.** A folder is not a medium, so it no longer wears a poster: it wears a FOLDER, in a
poster's footprint so the row still lines up, saying « DOSSIER » rather than miming an artwork
nobody has. Its card is marked `data-nonmedia="dossier"`, the way a release candidate's already
was, and it addresses its own panel — never a `media:` one, which would promise a subject that
does not exist. Rule R46 extended, `harness/cartes.py` — 137 checks over every named state, three
mutations proven: the folder back as a poster (the original defect), the folder addressing no
panel, the folder addressing a media panel.

**The two kinds of non-medium had been merged**, and that merge is what made the defect hard to
see: R46 said a non-medium promises neither sheet nor panel, which is right for a release
candidate and wrong for a stuck folder — a folder has its own actions. Splitting them is what let
the rule state the real invariant.

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

**Reported** 2×. **Status** `to confirm`.

**Fixed.** The handle claims its axis with `touch-action: none` and captures the pointer, and its
target is a 22px strip rather than the 4px bar it draws — a thumb aims at the bar and lands in the
strip, and the events used to stop the moment the finger left it. A cancel springs the sheet back
instead of closing it. Rule R55 extended, `harness/doigt.py` — 25 checks, four mutations proven:
the axis unclaimed (the original defect, under a real finger), the closing threshold dropped to
10px, the pointer capture removed (which only a MOUSE drag can catch — touch gets an implicit
capture), and a cancel treated as a lift.

**Two mutations passed at first and each named a hole in the rule.** Removing the capture changed
nothing under touch, so the rule had to grow a mouse drag. Treating a cancel as a lift changed
nothing because nothing cancelled any more, so the rule had to drive a real cancelled touch —
a hand-built PointerEvent carries an id no pointer owns, and the capture throws on it.

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

**Reported** 2×. **Status** `to confirm`.

**Fixed.** `contextmenu` is now refused across the whole frame, except inside a text field where
pasting has no other route. Measuring it turned up a second defect the report had named without
either of us knowing why: the press listeners lived on the SCROLLPORT, and every layer above it —
sheet, screen, drawer, dialog — sits outside, so four states drew a poster no press could reach.
Both listeners moved to the frame. Rule R55 extended, `harness/doigt.py` — 18 checks, four
mutations proven: the refusal removed, the refusal reaching into text fields, the refusal back on
the scrollport, and the press listeners back on the scrollport.

**Two rules were thrown away before one worked**, and both failures are the same failure: asserting
the panel is open AFTER the lift proves nothing, because on those surfaces a tap opens it too. The
oracle for a press is that the panel is open while the finger is STILL DOWN. A first attempt also
read the target's position before closing the sheet, and closing re-lays the screen out, so the
press landed on whatever had moved underneath.

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

**Reported** 1×. **Status** `to confirm`.

**Fixed.** Measured, the two renderings differed in more than the palette: the host restated the
typography too, so the wordmark had `line-height: normal` there against 1.35 here, and the whole
screen rendered at 16 px instead of 14. The reset is now extracted through `login:socle` markers
like the palette, and the host contributes only `.loginscreen { position: static }` and the
startup screen's positioning — what a page needs that a layer does not. Rule R62,
`harness/entree.py` — 10 checks comparing RENDERINGS, two mutations proven: the host taking back
a palette of its own (the original fault), and the host dropping the typographic extract. A third
mutation did not bite and earned its keep: removing the type scale I had first pinned on
`.loginscreen` changed nothing once the reset was extracted, so that declaration was removed
rather than left as something no rule defends.

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

**Reported** 1× (as "the sign-out screen has no TorrentMate style"). **Status** `to confirm`.

**Fixed.** The eleven references now name `--primary` / `--primary-foreground`. The host stopped
retyping the palette and EXTRACTS it, through new `login:palette` markers around `:root`. Rule
R61, `harness/palette.py` — 8 checks, three mutations proven: one reference back on the old name
(the static check names it), the wordmark recoloured while staying defined (the painted check
names it), the install button losing its background (the sweep over every state names it).

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
