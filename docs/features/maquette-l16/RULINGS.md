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
3. **2026-09-28, phase 5b, STOP D — how the tracker filter is seen and lifted.** DESIGN § 4.3 filters the
   « Torrents » rows by the `tracker` dial and draws no sign of it and no way out: the tab verb keeps the
   dial, and the filter verb REPLACES the entry, so a back leaves the page. Readings: A (the tab lifts
   it, the filter left invisible), B (a line « Filtré sur <tracker> · Tout voir » above the rows) and C
   (the address alone). **Ruled B**: DESIGN § 4.3's own « a filter that reads like a bug is a defect on
   its own »; « Tout voir » is the same `trackers-filter` verb given no tracker, an adjustment that pushes
   nothing, proved by a finger (R261); the line serves `torrents-empty-filtered` too; the met-obligation
   state `torrents-obligation-done` is declared in 5b.
4. **2026-09-29, phase 6b, STOP D — a torrent's title leads to a hollow sheet.** `audit.py` R1 fell on
   « Lanterns » ×3: its sheet was in no seed. A (swap the torrent) was refused — it hides a real state;
   B2 (the cast from TMDB) refused — the interface reads the NFO, not the provider live. **Ruled B1,
   reinforced**: Lanterns's sheet enters `media-sheets.json` from its real NFO, cast empty; R1 is re-aimed
   OUT LOUD, not weakened — a sheet is filled with an overview and genres — and a new hold R1 bis reads
   that a castless sheet draws no cast strip and says « Distribution inconnue. » (condition 2 corrected by
   the steward: saying the absence is an answer, § 8). No product change, no new state.
