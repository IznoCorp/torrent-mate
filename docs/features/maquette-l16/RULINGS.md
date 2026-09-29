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
5. **2026-09-29, phase 5c, STOP D — R229's « arrived unfollowed series » loses its only subject.** With Zinzins
   out of `moving.json`, « En vol » holds two followed series and two films; the settled series stand past
   « rangé » and are never drawn there. Readings: A (holds 2 and 4 re-aimed on the one-off season), B (A's
   Zinzins before arrival, plus a POSED arrival of the same real subject), C (a composed `moving` row).
   **Ruled B**: `poseArrived` follows `poseTunnelError` / `poseUnknownIdentity`, a derivation declared as one in
   its state and in R229's docstring, never a new seed; Zinzins end to end — before arrival in « Torrents »,
   without « Suivre », absent from « En vol »; after, an « En vol » card with its « Suivre » foot, a tap +1 once;
   holds 2 and 4 re-aimed out loud with their successor named; hold 6 unchanged. C refused: a row the real data
   does not hold. Cut 5c / 5d, each ≤ 15.
6. **2026-09-29, phase 7, STOP D — the clean external removal has no real row.** `acquire.db`'s
   `seed_obligation` holds 60 rows, none released, breached or satisfied; the plan asked for a new seed
   row. Readings: A (a composed released obligation, as the plan says) and B (a POSED removal by hand).
   **Ruled B**, in line with RULINGS 4 and 5: `poseExternalRemoval(infoHash)`, a dial declared as a
   derivation in its state and in R263's docstring, no seed; subject Ted Lasso on c411; the hold reads the
   row absent, `releasedAt` set and no `removeDownload` call, and a mutation leaving the row falls by name.
   R263 hold 4's re-aim cites its source (round 9 Q7; the plan's « BOTH entries gone … in the SAME
   render »). The `shell/dialog` moves (B-554) and the new states declared by script, accepted by name.
7. **2026-09-29, phase 8, STOP D — two composed seed rows the real data does not hold.** No real tracker
   carries an alert threshold or a refused identifier, and no real obligation is breached. **Ruled** as
   proposed: the threshold is the operator's own setting, posed where the settings write puts it
   (`poseAlertThreshold`); `poseIdentifierRefused` and `setObligationBreached` are dials declared as
   derivations; no seed. **Standing rule for the rest of L16** (steward): when the plan asks for a composed
   seed row for a case the real data does not hold, a dial POSED on a real subject in `trackers-state.ts`,
   declared as a derivation, replaces it — ANNOUNCED in the phase report and the ledger, no STOP. A STOP
   remains only when no real subject can carry the derivation, or when it changes a product behaviour.
8. **2026-09-29, phase 9, STOP D — the « vu » control has no precedent.** The prototype's only per-row
   dismissals (`dismissDecision`, a suggestion swept away) make the row LEAVE; the contract says of a
   broken obligation « seen is not gone ». Readings: A (a text control « Vu » per row, the row staying and
   saying « Vue »), B (the sweep reused — refused: the row would leave), C (unfolding marks all — refused:
   « marked seen individually »). **Ruled A**: « Vu » / « Vue » in `fr.json`; the hold reads the row
   staying, the unseen count down by one, and the write asked once; the mutation « success without the
   write » falls by name. `poseBrokenObligation` announced under RULINGS 7.
9. **2026-09-29, phase 11, STOP A / STOP D.** (1) The « ⋮ » sheet's title « Veille et obligations » would
   promise what the sheet no longer shows once its two ratio facts leave. **Ruled A**: the title reads
   « Veille », `meta` unchanged (NE-DOIT-PAS-1); the oracle divergence is the panel's own state, declared
   by name. (2) The plan's dated line in L22's DESIGN cannot land: `docs/features/maquette-l22/` died at
   #627. **Ruled**: a ledger line and a dated line in phase 11's plan; phase 17 carries it, the steward
   brings it to L16's closing docs pull request if needed.
10. **2026-09-29, phase 12, STOP D (known) — the engine defers on the GLOBAL threshold.**
    `personalscraper/ingest/deferral.py:73` reads `config.ingest.min_ratio`; the plan's opening measure said
    the obligation's own. **Ruled A**: the maquette draws the next version — the card names the tracker and
    THAT tracker's own threshold (DESIGN § 4.6); the engine's limit is RECORDED as a demand in the
    contract's descriptions (the contract carries no `x-demand` key; its demands live in descriptions, the
    `Download` precedent), never drawn around; the threshold mutation is kept. Cut 12a / 12b approved; the
    path is `?list=` (RULINGS 1). No real card is deferred: `poseDeferral` announced under RULINGS 7.
11. **2026-09-29, phase 14, STOP D (known) — no read of a config file's content.** The maquette's contract
    declared `/api/config/files/{name}` as a `put` alone; the plan read `readConfigurationFiles` (names only)
    as answering a file's content. **Ruled A**: `readConfigurationFile` is declared — a hole in the contract,
    not a demand (the backend answers it, `FileContent`); its seed is the operator's REAL `ranking.json5`,
    read read-only (no key, token or secret in it — the steward checked), its path and date of reading in
    the fixture register. Cut 14a (the read, the screen, R266's read half) / 14b (B-298's two sites, the
    screen walk, loading/error states, B-298's closure).
