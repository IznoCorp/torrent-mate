# L16 — RULINGS

The steward's rulings on this lot's STOPs, numbered, one per STOP. The operator's rulings are
`docs/reference/operator-method.md`'s and are not restated here.

1. **2026-09-28, phase 2b, STOP D — the tab's address parameter.** DESIGN § 3 named Trackers' tab dial
   `?tab=`; the address model holds « one parameter, one page » (`frontend/maquette/design/src/lib/addresses.test.ts`,
   « dialsOfPage gives a page only its own dials »), and `tab` is Acquisition's. **Ruled A**: the invariant
   stands — it is held by a test and a guard this lot does not rewrite — and the address is
   `/trackers?list=torrents|trackers&tracker=<name>`. DESIGN § 3 carries one dated line; R260 and R69 read
   the new names.
