# L15 — the plan

**Nineteen phases.** Each names what it converts, what it subtracts from the engine, the rule it
lands with, and the gate it passes. The design is `../DESIGN.md`; the contract is
`docs/reference/frontend-architecture.md` § 4, `#### L15 — The frame`.

**Two kinds of phase, and the difference is the whole method.** A **conversion** phase moves
drawing from the engine to a component and the oracle must read **zero divergence**. A
**behaviour** phase changes what the interface does, lands alone, and every divergence the oracle
reports is named before it is accepted. They are never mixed in one commit.

**Every phase ends the same way**: its rule written and mutation-tested (broken on purpose, seen to
fall naming the right defect, restored), then `run.sh --oracle` and `run.sh --contracts`.

---

## The order, and why it is this one

The table (P1) comes first because four surfaces read it. The chrome (P2–P5) before the layers
(P6–P11) because the bottom slot's geometry is what the layers clear. The entry (P12–P14) last of
the conversions because the sign-in gate covers everything and is the easiest to prove once
everything under it is a component. The four behaviour changes sit beside the surface they touch,
each alone. B-142's arm (P17) is independent and could run anywhere; it runs late so the CI filter
it needs is settled by the phase that found the hole in it.

| # | Phase | Kind | File |
| --- | --- | --- | --- |
| 1 | The one navigation table | conversion | `phase-01-the-table.md` |
| 2 | The tab bar | conversion | `phase-02-the-tab-bar.md` |
| 3 | The action button | conversion | `phase-03-the-action-button.md` |
| 4 | The bottom slot | conversion | `phase-04-the-bottom-slot.md` |
| 5 | The selection bar becomes the library's | conversion | `phase-05-the-selection-bar.md` |
| 6 | The toast | conversion | `phase-06-the-toast.md` |
| 7 | The drawer | conversion | `phase-07-the-drawer.md` |
| 8 | The dialog | conversion | `phase-08-the-dialog.md` |
| 9 | **B-229** — the dialog's rung on the ladder | **behaviour** | `phase-09-b229-the-rung.md` |
| 10 | **B-237** — the dialog's z-order | **behaviour** | `phase-10-b237-the-z-order.md` |
| 11 | The popover layer | conversion | `phase-11-the-popover.md` |
| 12 | The scrim gets one owner | conversion | `phase-12-the-scrim.md` |
| 13 | The splash | conversion | `phase-13-the-splash.md` |
| 14 | The sign-in gate | conversion | `phase-14-the-sign-in-gate.md` |
| 15 | The install proposal, and the appearance | conversion | `phase-15-install-and-appearance.md` |
| 16 | **B-233** — `theme-color` follows the theme | **behaviour** | `phase-16-b233-theme-color.md` |
| 17 | **B-230** — the viewport fallback is removed | **behaviour** | `phase-17-b230-the-viewport.md` |
| 18 | **B-142** — the clause map's instrument | instrument | `phase-18-b142-the-instrument.md` |
| 19 | The close — the inventory, the counts, the register | gate | `phase-19-the-close.md` |

---

## What no phase does

- **L11, L12, L19.** The offline shell, the transitions, the ten panel producers.
- **Move the ladder's handler.** `onEngineBack`, `unwindLayer`, `hideLayers`, `__closeLayers` stay
  in the engine. The layers REGISTER; L13 moves the walk.
- **Extend a file at the ceiling.** `features/acquisition/page.tsx`, `features/library/page.tsx`,
  `features/media/media-screen.tsx`, `features/arrivals/resolution-screen.tsx` are L14's;
  `engine/legacy.js` and `engine/states.js` are L13's and are touched by subtraction only.
  `app/shell.tsx` is at 380 of 400 and is not grandfathered — D-L15-1 is how it stays under.
- **Draw a desktop rail.** Q1, answered: the drawer alone, at every width.
- **Backend work.** A missing capability is a demand (D7).
- **Move a pixel.** Every part's rendering is validated (mission of 2026-08-19); the oracle is the
  reviewer of every conversion commit.
