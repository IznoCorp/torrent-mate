# Phase 10 — The shared element

**Kind: BEHAVIOUR.** **Owned P6.**

---

## ⚑ CLOSED — BUILT, THEN WITHDRAWN BY THE OPERATOR (2026-08-31)

**This phase shipped nothing, and that is its outcome rather than its failure.**

The blockage below was answered, the carry was built (`5f24d829`), the operator watched it on his
own phone and **withdrew it** (`a6be3a6e`). `grep -rn "carried-poster" frontend/maquette` reads 0
at HEAD; the rule that would have held it went with the drawing, and the transition baseline moved
18 → 10 when it did — in `fd744005`, the baseline commit, not in `a6be3a6e` which removed the
drawing. A baseline moves in the commit that RECORDS it.

**What ships in its place** is transition A, phase 11's: the arriving fanart fades while the body
rises, sharing nothing. The reasoning is the one `MODEL.md`'s P6 row already carried before the
build — there is nothing honest to share between a 2:3 poster and a wide banner, and morphing one
into the other is an animation pretending two pictures are one.

**P6 is therefore not « to build ».** It is a property the operator looked at and declined, and
`MODEL.md` says so in those words, dated. A later wave that reads this file must not re-propose it
as unfinished work.

**Why the whole record below is kept rather than deleted.** § 7.1: an argument that lost is kept
above its replacement, because the next reader's first question is « was this considered? ». What
follows is the state of this phase on the morning of 2026-08-31, before the answer arrived.

---

## ⚠ BLOCKED — an anomaly, measured 2026-08-31, awaiting the operator

**P6 as the contract words it cannot be built in this lot, and the reason is a design decision
somebody already took deliberately — not an oversight this phase can repair.**

The contract asks for « the shared element that carries a poster from a card into its sheet ». Four
measurements, each with its command:

1. **The tap destination is not a sheet and shows no poster.** `/media/$provider/$id` renders
   `MediaScreen` (`routes/media-sheet.tsx`), whose hero is a **wide** background-image banner —
   `data-part="hero/background"`, a `div` with `backgroundImage`, not an `<img>`. Its own comment
   says why: « The banner prefers the wide visual; the vertical poster is only a fallback »
   (`media-screen.tsx:347`). A 2:3 poster carried into a wide banner is not a shared element; it is
   a morph between two different pictures.
2. **The surface that DOES carry a vertical poster is not reached by a navigation.**
   `ui/panel/index.tsx:217` emits `.sheetposter` — the long-press panel — and a long press opens it
   without going through `go()`, so no view transition is involved at all.
3. **The source cannot be marked in its markup.** The tile is drawn by the engine
   (`legacy.js:7996`, `tileHTML`), and `view-transition-name` must be unique per element, so it
   cannot be applied to `.tile` by a class rule — every tile would carry the same name and the
   browser would ignore all of them.
4. **The destination cannot be extended.** `features/media/media-screen.tsx` is one of L14's four
   grandfathered files, which this lot may not extend.

**What is NOT the blocker**: (3) and (4) are both soluble inside this lot — a single tile can be
marked from `app/` at navigation time, exactly as the feedback seam marks a node, with the NAME
itself declared in the stylesheet so rule 1 holds. **(1) is the blocker**, and it is a product
question rather than a technical one: there is no poster at the destination to carry a poster to.

### The options, for the operator

- **A — defer P6 to L19**, when the tile stops being engine markup and the media surface is redrawn.
  Nothing is built here and P6's row says « L19 » rather than « L12 ». Cheapest, and it changes no
  design decision.
- **B — carry the WIDE visual instead**, tile → hero banner, accepting that the shared element is
  the artwork rather than the poster. Buildable now within every boundary. It reinterprets the
  contract's word « poster ».
- **C — redraw the media surface to lead with a vertical poster**, which makes P6's literal reading
  true. That is a design change to a validated surface and is not this lot's to take (the mission
  forbids relitigating what the maquette already holds).

**Recommended: A.** B changes what the contract asked for on a technicality, and C changes a surface
the operator has validated. Deferring names the lot that can do it properly and costs nothing now.

**Until this is answered, phase 10 builds nothing** and the wave continues past it.

**AND THE OTHER HALF IS BLOCKED WITH IT, correcting what this file said an hour ago.** « Images that
a transition carries are decoded before they are needed » was written here as « not blocked, lands
below ». It has no subject once the carry is deferred: **nothing is carried**, so there is no image
whose decode could tear a shared-element transition. Worse, the destination's artwork is a CSS
`background-image` rather than an `<img>`, and `decode()` is a method on `HTMLImageElement` — there
is no handle to decode even if there were something to carry. Implementing a decode here would be
machinery with no reader, which is the exact disease § 7.1 exists to fight. It goes to L19 with the
carry.

## What it does

The poster that a tap carries from a card into its sheet is one element across the transition. The
name is declared on both ends — a `view-transition-name` present on only one end produces no shared
transition and no error, which is the landmine shape this repository already knows from `var()`.

## The performance floor, and it is this phase's real subject

**Images a transition carries are decoded BEFORE they are needed.** The contract states the reason
and it is measured, not theoretical: *the same asynchronous decode that makes the oracle flicker
makes a shared-element transition tear.* A poster still decoding when the transition starts is the
defect; `decode()` before the switch is the remedy.

## The rule

One driven rule: the name is present on **both** ends (a static read that names which end is
missing — not a count, which would be green on two names at one end), **and** the carried image is
decoded before the transition starts.

## Mutation

Strip the name from the sheet's end → the rule falls **naming the sheet**, not merely reporting a
count. Remove the decode → the decode half falls. Restore.

## Done when

P6 reads true; the carried image is decoded before it is carried; both mutations bit; the phase's
oracle divergences are named in its commit.
