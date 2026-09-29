# Phase 1 — The responsive rule (order 85, replaces order 60)

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `python3` over `harness/states/*.ts` (report § A.0's script) → **161** declared ids;
  `grep -n "PHONE = " frontend/maquette/harness/common.py` → line **429** (390 px, kept for every other rule — no
  global re-aim); `sed -n 242,258p frontend/maquette/design/src/styles/harness.css` → below 520 px the device IS the
  window, above it the frame draws a 390 px phone unless `#desktop-switch` is checked.
- **Points ≈ 14.** The rule, ≈ 110 lines new (11) with its mutation (3). Above 15 at the opening: cut into the
  measurement (1a) and the owed list (1b), the orchestrator told.
- **Readers.** `states.py` and `sweep.py` already refuse overflow at 390 px only; they stay as they are.

## The rule — `harness/responsive.py`, R-conformity-a

For every named state (`window.__states()`) at **320, 360, 369, 390, 412, 768, 1280** px: a context at that width
(touch and `is_mobile` up to 412; at 768 and 1280 `#desktop-switch` checked, so the device is the window and not the
390 px phone the frame draws), `__go`, `SETTLED`, then refuse, inside the measured target (the layer on top, else
`#view`, as `states.py` picks it):

1. **overflow** — `document.documentElement.scrollWidth > clientWidth`;
2. **outside** — an element whose border box leaves `[0, width]`, not inside an ancestor that SCROLLS on x;
3. **cut** — an element clipped by an `overflow: hidden | clip` ancestor on x (its box past the ancestor's), or
   text clipped in place (`scrollWidth > clientWidth` under `overflow: hidden`, the ellipsis);
4. **a border not painted as drawn** — a `border-*-style` of `outset | inset | groove | ridge` on any side: the
   design system draws none, so it is the UA button border (report B.5 R1).

Every fall prints `state · width · arm · data-part · rect`. The verdict counts states × widths.

## Red today

R1 first: `runs-list` — the runs list « cut on the right » (arm 4 at every width, and arm 3 if the list clips).
Every OTHER red the rule finds that this train does not repair goes into the rule's **owed list**, keyed by
`arm · data-part` (never by a whole state), each with its OWNER — § 12's card title (R2, the report's D.2),
L16-bis (R3), the tabs (R4, phase 9), the chip (R5), R6–R14 each to its named owner or to the orchestrator. The
owed list is data in the rule's file, read by name; nothing is silenced by a width or a class.

## Cost

Measured on the first full pass (≈ 161 × 7 = 1 127 readings), written in the RESUME. **Above 10 min**, the full
sweep runs only at the close and in CI, and a phase runs `responsive.py --states <ids>` on the states of the
surfaces it touches (the declared list built by script, office). CI: which job, under which trigger — decided here,
said in the commit body.

## Mutation

One per arm, each read on a state it reds: widen a `factList` child past its list (arm 3), a fixed 400 px block
(arms 1, 2), a bevelled border (arm 4) — each falls by name. After phase 4, restoring `runRow` fells `runs-list`
(phase 4's mutation).

## Oracle

Nothing drawn moves: `run.sh --oracle` green, no accept.

## Commit

`test(maquette-conformity): every named state at seven widths — no overflow, no cut, no bevelled border`
