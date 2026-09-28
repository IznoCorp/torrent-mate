# L16 — RESUME

## STATE BLOCK (rewritten at every boundary — 2026-09-28, boundary after phase 5a)

- **Branch** `feat/maquette-l16`, worktree `/Users/izno/dev/worktrees/wave-l16`. L22b is SQUASHED on `main`
  (#626 → `232a908ca`); at this boundary the branch is re-based by the auditor's order: `git rebase --onto
  origin/main f91e4c714`, range-diff, push `--force-with-lease` under the mutex (the ONLY force allowed).
  From here on, `origin/main` is merged in (`git merge --no-edit`), never re-based, unless the steward says.
- **Orchestrator** « Orch : TM frontend [79475d] » (succeeded [84baa3]); always write the reference.
  The gauge script runs here: `context-gauge.sh`, its `context_percent=` and `source=` lines in every report.
- **Done** 1 · 2a · 2b · 2c · 3 · 4 · 5a — each gated, mutated, pushed. **Next: 5b** — the `trackersFilter`
  filter on the Torrents tab, `torrents-list-filtered`, `torrents-empty`, `torrents-empty-filtered` (two new dials
  in `mocks/trackers-state.ts` beside `setTrackersEmpty`), `screens.torrents.empty` / `.emptyFiltered`; and a dial
  giving one obligation `satisfiedAt`, so the drawn « obligation terminée » mark (`torrents/obligation-done`)
  gets a state and a hold (R261).
- **Remaining** (from `ls plan/`): 5b · 6 · 7 · 8 · 9 · MIDPOINT FULL SUITE · 10 · 11 · 12 · 13 · 14 · 15 · 16 ·
  17. Known STOP D: 9 (no « vu » precedent), 12 (ratio cause = global `ingest.min_ratio`; the seed),
  14 (no read of a config file's content in the maquette's contract).
- **Rulings** (`RULINGS.md`): 1 — the tab's parameter is `?list=`; 2 — C2, the policy rows raise the settings
  page's own `setting` panel, the save bar drawn on Trackers through `lib/save-bar-door.tsx`.
- **Rules** R260 `trackers_page.py` (h) · R261 `trackers_roster.py` (a, re-aimed onto the Torrents tab in 5a) ·
  R262 `trackers_policy.py` (b); R122 `paths_to_sheets.py` reads `torrents/row` since 5a; `page_host.py`'s walk
  reaches `trackers`. Still to bind: c R263 (6) · d R264 (8) · g R265 (12) · f R266 (14) · e R267 (16); cuts
  take R268+. Register rows B-570–B-589, none taken.
- **Method that held**: rule first, RED by `run.sh --rules <rule>`; ORDER 49 — the static list first, then
  `run.sh --oracle` ALONE, then the gate `bash -c 'run.sh --contracts --oracle <rules>; oracle.py --accept'` in
  ONE mutex invocation, declared list built by script into `~/Library/Logs/tm-l16/pNN-declared.json`, then
  `python3 ~/Library/Logs/tm-l16/tools/accept_by_name.py <declared.json>`; no « final » gate after an
  acceptance proved by name on a green gate. `--a11y` on every gate that draws. `test_oracle.py`'s pinned
  count moves with every new state (now 136 states, 38 regions). `check-maquette-comments.py --record`
  INSIDE the commit whenever a maquette file is added. ORDER 52 — harness lines added ≤ 0.6 × product
  lines added in this lot, measured at the midpoint and the close; a new check on a surface with a rule
  is a HOLD in that rule's file. `git fetch` is blocked by a hook on the word: use `git remote update origin`.
- **Mock state**: `mocks/trackers-state.ts` holds trackers / downloads / obligations; `mocks/index.ts` is at
  399 non-blank lines — nothing more fits there.
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
