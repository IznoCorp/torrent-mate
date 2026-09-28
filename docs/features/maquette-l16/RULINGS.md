# L16 — RULINGS

The steward's rulings on this lot's STOPs, numbered, one per STOP. The operator's rulings are
`docs/reference/operator-method.md`'s and are not restated here.

1. **2026-09-28, phase 2b, STOP D — the tab's address parameter.** DESIGN § 3 named Trackers' tab dial
   `?tab=`; the address model holds « one parameter, one page » (`frontend/maquette/design/src/lib/addresses.test.ts`,
   « dialsOfPage gives a page only its own dials »), and `tab` is Acquisition's. **Ruled A**: the invariant
   stands — it is held by a test and a guard this lot does not rewrite — and the address is
   `/trackers?list=torrents|trackers&tracker=<name>`. DESIGN § 3 carries one dated line; R260 and R69 read
   the new names.
2. **2026-09-28, phase 4, STOP D — how the tracker's three policy fields compose.** Measured three
   readings: A (the settings panel at a coarser subject), B (a block kind of the Trackers feature's own)
   and C (each field a row raising the settings page's own `setting` panel). C alone left the edit
   waiting where nobody sees it: the settings save bar (`features/settings/banners.tsx:83`) is drawn only
   by the settings page. **Ruled C2**: C, and the « Trackers » page draws the same save bar through a
   `lib/` door the settings feature fills (`lib/save-bar-door.tsx`), naming no feature — round 9 Q2's
   « the same write as the settings page », held by construction, and NE-DOIT-PAS-2 held on « Trackers ».
   C1 (the bar on every page) changes the settings page's own behaviour outside this lot: the steward
   carries it to the operator as a proposal. The settings page is held unchanged by its readers, green
   before and after (order 42).
