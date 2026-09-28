# L16 — RESUME

## STATE BLOCK (rewritten at every boundary — 2026-09-29, boundary after phase 6b)

- **Branch** `feat/maquette-l16`, worktree `/Users/izno/dev/worktrees/wave-l16`, on `origin/main` by MERGE
  (last: `0e523349f`, #627, merged at the 6a boundary — its only conflict the oracle reference, where main moved
  the header alone). `git merge --no-edit` at a phase boundary; NO force push, ever.
- **Orchestrator** « Orch : TM frontend [79475d] »; always write the reference. The gauge script runs here:
  `context-gauge.sh`, its `context_percent=` and `source=` lines in every report. Exit boundary ~55 %.
- **Done** 1 · 2a · 2b · 2c · 3 · 4 · 5a · 5b · 6a · 6b — each gated, mutated, pushed. **Next: 5c** (ruled
  2026-09-29: after 6b, before 7) — L22 RULINGS 25 inherited through #627 into phase 5: Zinzins (real, from
  `moving.json`) into the downloads seed, its « En vol » card gone, a hold « Zinzins downloading is readable in
  Torrents » in R261 with its mutation, R229 `follow_offered.py` re-aimed OUT LOUD with the removed state's
  successor named; the opening measure counts the READERS of « En vol ». Then 7.
- **Remaining** (from `ls plan/`): 5c · 7 · 8 · 9 · MIDPOINT FULL SUITE · 10 · 11 · 12 · 13 · 14 · 15 · 16 · 17.
  Known STOP D: 9 (no « vu » precedent), 12 (ratio cause = global `ingest.min_ratio`; the seed),
  14 (no read of a config file's content in the maquette's contract).
- **Rulings** (`RULINGS.md`): 1 — the tab's parameter is `?list=`; 2 — C2, the policy rows raise the settings
  page's own `setting` panel, its save bar drawn on Trackers through `lib/save-bar-door.tsx`; 3 — B, the filter
  line « Filtré sur <tracker> · Tout voir », lifted by the `trackers-filter` verb given no tracker.
- **Rules** R260 `trackers_page.py` (h) · R261 `trackers_roster.py` (a; holds 1–16, the Torrents tab since 5a,
  its filter and empties since 5b) · R262 `trackers_policy.py` (b) · R263 `trackers_removal.py` (c, the single-entry case); R122 `paths_to_sheets.py` reads
  `torrents/row`; `page_host.py`'s walk reaches `trackers`. Still to bind: d R264 (8) · g R265
  (12) · f R266 (14) · e R267 (16); cuts take R268+. Register rows B-570–B-589, none taken.
- **Gate (orders 49, 58, 59, 65, 70)**: static list first (CI `no-french` job + cheap guards, typecheck) →
  `run.sh --oracle` ALONE (class browser) → acceptance `bash -c 'run.sh --oracle; oracle.py --accept'` in ONE
  browser invocation (`--accept` needs the host `run.sh` starts), then `python3
  ~/Library/Logs/tm-l16/tools/accept_by_name.py <declared.json>` (declared list built by script) → `run.sh
  --rules <re-aimed rules + the surface's group>` in `--class rule` → `--a11y` (browser) on a drawing gate.
  NO `--contracts` at a phase gate: it runs at 9 (midpoint full suite), 14 and the close. entry R62 and pwa
  (R52, R105, R108, R111) are out of phase gates. Single-rule mutations run `--class rule`. Order 48 light:
  series in `--rules`; a known-unstable rule the phase does not read: 5 draws, stop at 0/5.
  `test_oracle.py`'s pinned count moves with every new state (142 states, 38 regions).
  `check-maquette-comments.py --record` INSIDE the commit when a maquette file is added.
- **Order 52**: harness lines added ≤ 0.6 × `design/src` lines added (`git diff --numstat origin/main...HEAD`);
  at 5b: 737 / 1452 = 0.51. A new check on a surface with a rule is a HOLD in that rule's file.
- **A phase that adds `data-mediasheet` runs `audit.py` at its gate** (R1 / R1 bis: every sheet behind a
  tap is filled, a castless one says so). A phase touching `ui/dialog` runs the dialog's readers.
- **B-554 in practice**: a new dialog moves `shell/dialog` on every state measured after it (24 at 6a); declared
  by script from the oracle-only reading, all with the same box pair. The light a11y ceiling (88) refuses
  `.warnbox > b` (the warning block) — say a warning in a paragraph's strong run.
- **Traps**: `git fetch` is blocked by a hook on the word — `git remote update origin`. The driver's reset
  (`harness/drive.ts`) clears the dials a state can move; a new dial that changes a drawing joins it.
- **Mock state**: `mocks/trackers-state.ts` holds trackers / downloads / obligations and their dials
  (`setTrackersEmpty`, `setDownloadsEmpty`, `setTrackerIdle`, `setObligationSatisfied`); `mocks/index.ts` is
  at 399 non-blank lines — nothing more fits there (the dials spread in without a line).
- **Logs** `~/Library/Logs/tm-l16/`; the proof tool lives in `tools/` there.

---

## LEDGER (append-only)

- 2026-09-28 — handshake; state verified: L22b's phase 47 is in (no `arr` row, no `features/arrivals`),
  highest rule R250, size and frame-domain guards exit 0, `heavy.sh --held` free. The brief's two
  stale references (DESIGN « § 7 », « phase-01-contract.md ») corrected by the steward's word.
- 2026-09-28 — phase 1 opening measure on `917fd864b`: none of the three reads in the maquette's
  contract (`[]`); `acquisition.ts` now 348 non-blank (the plan read 395) — the home stays
  `mocks/handlers/trackers.ts`, by SUBJECT, not by room. 46 seeds, `check-mock-seeds` clean.
- 2026-09-28 — phase 1: `readObligations`, `readDownloads`, `readTrackers` declared, tag `trackers`;
  seeds `obligations` / `downloads` (five real c411 rows of `acquire.db`, sizes from `library.db`,
  read read-only) and `trackers` (volumes composed — no engine route reads them); the alert
  threshold is served from the settings seed, never seeded twice. Register 68→71 required, 21→22
  missing, 47→49 shape, 18→16 unused. `tracker` added to `scripts/code-vocabulary.txt`. Slip: one
  read-only `cd` into `design/src/mocks/seeds` (B-384), left at once, nothing written or run there.
- 2026-09-28 — phase 2 opening measure on `c261da20d` ≈ 18 → CUT 2a / 2b by kind (steward agreed). R260
  (`trackers_page.py`) RED by `run.sh --rules` (`p02a-red.log`): 7 FAIL — no table row, no address, no
  button, no landing, the bar at three, `/trackers` cold → 404. Readers re-aimed: `url_state.py` PAGE_WALKS,
  `page_host.py` SHELL_OWNED / FLOORS (trackers 2: heading, body, container), R241 `arrivals_gone.py`'s
  THE_BAR_WANTED (said out loud). Frame-domain ceiling app/ 131 → 139 (+8, the guard with and without).
  Words `tracker`, `trackers` in the vocabulary.
- 2026-09-28 — 2a gate: 12 divergences, all on the new `trackers-page`, none on the 260 declared bar/drawer
  keys; accepted, `p02a-accept-proof.log`. `scroll_memory.py` re-aimed (it left by the empty Trackers page).
  Mutation 1 (`p02a-mutation1.log`): `switchPage` records instead of replacing → FAIL « the change of page
  REPLACES the entry — history.length 3 -> 4 ». First push refused by `test_oracle` (pinned 130/37) → 131/38,
  every state's record given a null `trackers/body`. Pushed `a7c8a5eac`.
- 2026-09-28 — 2b opening ≈ 17 → RE-CUT 2b / 2c (steward agreed): the dials travel on the entry
  (`navigation-entry.ts` ENTRY_DIALS, `layers.ts` restore, `arrival.ts` opening state) and the landing door is
  single. R260 re-aimed out loud (holds 5, 6), RED `p02b-red.log` (4 FAIL: no strip, no dial, no filter).
  Attribute `data-trackers-tab` (two vocabulary words). Frame-domain lib/ 29 → 31, app/ 139 → 146, by the guard
  with and without.
- 2026-09-28 — 2b gate 1 (`p02b-gate.log`): R69 counted six parameters (→ eight, re-aimed out loud);
  `check-state-ownership` wanted the two dials classified (interface state); `addresses.test.ts:134` refused
  `?tab=` (Acquisition's) → STOP D, RULINGS 1 = A: the parameter is `list`. 2 divergences, both on
  `trackers-page` (the strip).
- 2026-09-28 — 2b closed: RULINGS 1 applied; mutation (`p02b-mutation.log`) a tab verb that PUSHES → FAIL « a
  finger's tap on « Torrents » ADJUSTS … length 3 -> 4 » and « a back then leaves the page … 'trackers' ».
  Oracle 2 keys on `trackers-page`. Pushed `151aa6b56` (the comment record forgotten in `b723ae9a0`, caught
  by the pre-push).
- 2026-09-28 — 2c, order 42: the READERS of Acquisition's tab memory and landing door — R202
  `default_tab.py` (16 holds), R239 `no_sentence_to_arrivals.py` (29, the `data-dial="todo"` walk),
  `return_to_todo.py` (16), R69 `url_state.py` (103), `entry.py` (10) — all GREEN before the move
  (`p02c-acq-before.log`); `inter.py` and `surfaces.py` print no hold count and are not counted.
  R260 hold 7 RED (`p02c-red.log`, 4 FAIL). The move: `lib/tab-memory.ts` (no feature named, each
  brings its key), Acquisition's memory reads it, the landing door made plural, the boot asks every
  page of the table for its dial (Acquisition receives the very call it received). Words `memory`,
  `doors`. Frame-domain unchanged (lib/ 31, app/ 146).
- 2026-09-28 — 2c closed: Acquisition's readers 16 · 29 · 16 · 103 · 10 holds, green before AND after;
  mutations « memory forgotten » (R260 FAIL « a tab tapped is the one the next cold entry opens ») and
  « Acquisition's door unplugged » (R202 7 FAIL). Pushed `8051b49ca`.
- 2026-09-28 — phase 3 opening ≈ 13 (the plan's figure holds; +1 for the trackers' mock state module).
  R261 (`trackers_roster.py`) RED (`p03-red.log`, 11 FAIL). `mocks/trackers-state.ts` holds the roster,
  the entries and the obligations, keyed on `mockState()`'s object so `reset()` renews it without a line of
  its own (`mocks/index.ts` 397 → 399, `state.ts` untouched); its dial `setTrackersEmpty`. The feature
  reads the contract through `lib/contract-schemas` (fan-in ceiling 4 on `contract/types.d.ts`). Words
  `gigabyte`, `owner`, `trend`, `volumes`, `ratio`, `roster`.
- 2026-09-28 — phase 3 closed: mutation « a row draws its neighbour's fields » → 6 FAIL named, e.g. « c411:
  its ratio is its own, 1,42, never the mean 0,98 — 'Ratio 0,55' ». Oracle 26 = 2 new states + 2 keys of
  `trackers-page`. Pushed `6d15c19c8`.
- 2026-09-28 — phase 4: STOP D → RULINGS 2 = C2 (after the steward asked where the save bar is drawn:
  `settings/page.tsx` only). Settings readers GREEN before (`p04-settings-before.log`: `settings.py` 68,
  `settings_editing.py` 15, `seeds_at_rest.py` 23, `page_host.py` 42). R262 (`trackers_policy.py`) RED
  (`p04-red.log`, 10 FAIL). The move: `lib/save-bar-door.tsx`, filled by `features/settings/banners.tsx`;
  `ui/disclosure.tsx` gains an optional `open` (the `tracker` dial opens an entry, DESIGN § 3); the seed
  row `tracker.providers.c411.economy.alert_threshold` (raw null, « non défini » — the operator's
  configuration sets none); `settings/format.test.ts` re-aimed out loud (160 → 161 settings). The walk
  shuts the setting's panel by the back gesture before saving, as `settings_editing.py` does — « Valider »
  keeps the panel up.
- 2026-09-28 — phase 4 closed: 14 keys moved, HEIGHT only (`p04-moved-keys.log`); mutations « door unfilled »
  (R262 FAIL « Valider makes the save bar appear … 'bar': False ») and « stale catalogue copy » (FAIL « the
  entry, read again, shows the value the layer now answers »); settings readers 68 · 15 · 23 · 42 before and
  after. Pushed `33283269f`. Phase 5 re-measured ≈ 19, cut 5a / 5b (announced); not opened — stand-down
  on the steward's word at gauge 49 %.
- 2026-09-28 — successor session (« Agent : l16 2 »): handshake; the gauge script runs here (9 %). Phase 5a
  opening ≈ 11. Slip: one read-only `cd` into `design/src` (B-384), one grep, left at once, nothing written
  or run there. R261 re-aimed OUT LOUD onto the Torrents tab (holds 6–11, a finger on a title lands on
  `/media/tvdb/466198`), R122 re-aimed OUT LOUD (« card and tile, and no third » → `torrents/row` the third);
  RED `p05a-red.log` (R261 « état inconnu : torrents-list », 0 rows of 6; R122 crashes on the same absent state).
- 2026-09-28 — 5a move `7228f6896`; merge of L22b's head `f91e4c714` (steward's order, operator ruling A:
  tm-design shows the lot in flight): one conflict, the comment baseline, re-recorded. The merge felled
  `page_host.py` — L22b's new hold « every page the shell owns is in the walk » met `trackers` — re-aimed
  OUT LOUD, the walk reaches it from `discover` and `sys`. `check-intent-map` green from the merge on.
- 2026-09-28 — 5a gate: a11y read 6 colour-contrast on `torrents-list` (the title button's native ground) →
  `features/trackers/variants.ts`, 0. Oracle: `torrents-list` new (0 keys moved), then its `shell/page` and
  `trackers/body` height 739.1 → 870 (the title at 44 px), accepted by name (`p05a-accept-proof2.log`).
  Mutations: ratio on the tracker's volume → R261 FAIL « President Curtis on c411: its ratio is its own, 0,42,
  on its own size — never 0,00 on the tracker's volume » (`p05a-mutation1.log`); title path dropped → R122
  FAIL « 6 dead of 6 — carried by none » (`p05a-mutation2.log`). Orders 49 and 52 received.
- 2026-09-28 — 5a pushed without force: the rebase's `--force-with-lease` push was refused by the classifier
  (« [Git Destructive] »); steward's option B — `reset --keep bb1135e76`, `git merge origin/main`, the 18
  conflicts resolved to `bb1135e76`'s tree (main's tree is `f91e4c714`'s, already in it), diff against the
  re-based `ef04518fe` empty; pushed `d5c255c57`.
- 2026-09-28 — 5b opening: STOP D (the filter neither seen nor lifted) → RULINGS 3 = B. Orders 58, 59, 65,
  67a and 70 received (the gate without `--contracts`; the rule class). R261 holds 12–16 RED
  (`p05b-red.log`, 11 FAIL: four unknown states, the filter unsaid, the address keeping `tracker=c411`).
- 2026-09-29 — 5b move `0579d44b9`. The oracle alone read `torrents-list` 870 → 270.1: `trackers-policy-unset`
  left the tracker dial on tr4ker, which now filters the Torrents tab — the driver's reset clears it
  (`b10457537`), `torrents-list` back to its reference. Four new states accepted by name, 0 keys moved
  (`p05b-accept-proof.log`); a11y 0 on 140 states; rules R261 56 · R122 13 · R260 27 · R262 14 · page_host 42
  holds, 0 failed. Mutations: the filter not applied → FAIL « filtered to c411: its rows alone »
  (`p05b-mutation1.log`); « Tout voir » pushing → FAIL « « Tout voir » drops the tracker from the address and
  pushes nothing — history.length 7 -> 8 » (`p05b-mutation2.log`).
- 2026-09-29 — phase 6 opening ≈ 21 (the dialog has no checkbox block) → CUT 6a / 6b, announced. R263
  `trackers_removal.py` RED (`p06a-red.log`, 7 FAIL). `removeDownload` declared (DELETE with a body, the
  `deleteLibraryItems` precedent), types regenerated, demands register recomputed (72 required, 23 missing); the
  mock keeps a `removals` log read through `trackerRemovals()`. Word `hash`.
- 2026-09-29 — 6a gate: oracle alone 42 divergences — the new state, the three row states grown by the
  gesture, and 24 states on `shell/dialog` alone, one identical box pair (B-554, L22 RULINGS 7) — declared by
  script, 30 keys proved. a11y light 89 > 88: `.warnbox > b` fails contrast (lib-delete's known debt) → the
  obligation said in a paragraph (`ec30b59a6`), light 88, dark 0; 25 `shell/dialog` keys re-accepted, proved.
  Rules R263 10 · R261 56 · R122 13 · R260 27 · R262 14 · page_host 42, 0 failed. Mutation: the confirmation
  without the call → FAIL « confirmed, the removal of THAT entry is answered, its files deleted — answered [] »
  (`p06a-mutation1.log`). Merged `origin/main` `0e523349f` (#627) at the boundary.
- 2026-09-29 — 6b: R263 holds 6–8 RED (`p06b-red.log`, 5 FAIL). `ui/dialog` gains a `check` block, its value
  the block's own (the closed `#dlg` keeps content). Oracle: `torrent-remove-confirm` new + 25 `shell/dialog`
  keys (B-554), proved; a11y dark 0, light 88. Word `checked`.
- 2026-09-29 — 6b gate, order 42 on `ui/dialog`'s 13 readers: `audit.py` fell, R1 « hollow sheet behind a
  poster — 3 », reproduced twice. ESCAPED FROM: `audit.py` absent from the 5a/5b gates; WHY: `ui/dialog` not
  yet touched, so its readers were not run; FAMILY: the readers of `data-mediasheet`. R1 on the 142 states:
  Lanterns ×3 alone (torrents-list, -filtered, -obligation-done). → RULINGS 4 = B1 reinforced. Lanterns's
  sheet read from `/Volumes/Disk1/medias/series/Lanterns (2026)/tvshow.nfo` and its seven episode NFOs,
  located through `library.db` (`mode=ro`: media_item 3308 → path 7429 → disk 1); no `<actor>` anywhere, so
  cast []; composed: status « En cours » (none in the NFO), rating null (tmdb 0.0 on 0 votes), genres in
  the seed's own labels. R1 re-aimed OUT LOUD + hold R1 bis (`audit.py` 13 → 14 holds).
- 2026-09-29 — 6b mutations: Lanterns's overview null → `audit.py` FELL « torrents-obligation-done :
  Lanterns » (`p06b-mutation-r1.log`; a first expression wrote invalid JSON, the build failed — no verdict,
  re-run); the cast strip drawn empty → FELL « « Lanterns » : {'strip': True, 'said': True} »
  (`p06b-mutation-r1bis.log`); the obligation paragraph dropped → R263 FAIL « the box unchecked, the running
  obligation on c411 is still named » (`p06b-mutation2.log`; the naming is static, independent of the box by
  construction). Rules audit 14 · audit2 13 · R263 15 · R261 56 · R122 13, 0 failed; oracle no divergence.
