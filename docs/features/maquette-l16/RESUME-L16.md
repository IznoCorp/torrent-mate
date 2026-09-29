# L16 — RESUME

## STATE BLOCK (rewritten at every boundary — 2026-09-29, after phase 15)

- **Branch** `feat/maquette-l16`, worktree `/Users/izno/dev/worktrees/wave-l16`, on `origin/main` by MERGE
  (last: `77e7b8436`, #631, at 15's opening). `git merge --no-edit` at a phase boundary; NO force push, ever.
- **Orchestrator** « Orch : TM frontend [79475d] »; always write the reference. Gauge: `context-gauge.sh` as the
  LAST tool call before any message carrying a figure. Context gate 80 %, exit ~75 % (brief's dated line).
- **Done** 1 · 2a–c · 3 · 4 · 5a–d · 6a · 6b · 7 · 8 · 9 · MIDPOINT · 10 · 11 · 12a · 12b · 13 · 14a · 14b · 15 —
  each gated, mutated, pushed. **Next: 16** (`plan/phase-16-live-preview.md`), not opened — re-measure it.
- **Remaining** (from `ls plan/`): 16 · 17 (then the close's full suite + `--compare`, PR). No known STOP D.
- **Rulings** (`RULINGS.md`) 1 `?list=` · 2 C2 save bar door · 3 B filter line · 4 B1 Lanterns · 5 B `poseArrived` ·
  6 B `poseExternalRemoval` · 7 posed dials replace composed seeds (STANDING: announce, no STOP) · 8 A « Vu » ·
  9 « Veille », L22's note to phase 17 · 10 A tracker's own threshold (demand) · 11 A `readConfigurationFile` +
  the real ranking.json5 · 12 B the rubric keeps /quality/global, the weights button leads to the editor.
- **Rules** R260 trackers_page · R261 trackers_roster (17 holds) · R262 trackers_policy · R263 trackers_removal (10) ·
  R264 trackers_alert (11) · R265 deferred_reason (6) · R266 ranking_editor (11 holds, 32 checks; save half at 15) · R229
  re-aimed at 5d; R91 fanout reads trackers/live.ts. Next label: e R267 (16); cuts R268+. Register: B-570 taken
  (live-relay guard's constant-key blind spot, `open`); B-298 `to confirm`; next B-571.
- **Gate** (office § The gate): the scratchpad `static.sh` = CI's no-french job + run.sh's 26 cheap guards (read
  from `REPOSITORY_GUARDS`) — a successor rebuilds it the same way; → `run.sh --oracle` alone → accept with
  `bash -c 'run.sh --oracle; oracle.py --accept'` + `tools/accept_by_name.py <declared.json>` (declared BY SCRIPT
  from `states/*.ts`) → `run.sh --rules` (`--class rule`) → `--a11y`. `test_oracle.py` pinned 159 / 38. Maquette
  vitest: `vitest run --root frontend/maquette/design`. The RULE is read RED BEFORE the move (14a slipped).
- **Order 52** at the midpoint 0.56; **Order 73**: a rule red 3× for a non-product reason → a register row naming
  its mechanism before READY (entry/pwa excluded: the router hairpin, a train's).
- **Phase 17 carries**: L22's DESIGN § 1.7 note (RULINGS 9); B-298 `to confirm`; the closing full suite + `--a11y` +
  `--compare`; the 390 px screenshots of both Trackers tabs.
- **Traps** `git fetch` blocked (use `git remote update origin`); the git index lock is held by a concurrent reader
  — `git add` then `git commit -F <file>` with bounded retries, never delete the lock; BSD `sed` has no `\b`;
  zsh does not split `$VAR` (use `xargs`); a `[data-follow]` selector is refused (read the value); a maquette
  comment naming a lot/phase/date is refused; Playwright `has_text` is case-free (another row may quote it).
- **Size watch** `mocks/handlers/staging.ts` 399, `mocks/index.ts` 399 (ceiling 400). Frame-domain app/ 153.
- **Mock** `mocks/trackers-state.ts` (roster, downloads, obligations, removals + dials), `mocks/configuration-files.ts`
  (the files' content, per layer state; `writeFileContent` — a whole file under its digest), `mocks/handlers/ranking.ts` (the preview), `posed-deferral.ts`.
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
- 2026-09-29 — 6b push refused by the pre-push: `test_check_markup_contracts` (3 FAILED) — `scripts/markup_anchors.py`
  keys `audit.py`'s declared class sites BY LINE, and R1's re-aim moved them 114 → 125, 180 → 191. My slip:
  the static list ran BEFORE `audit.py` was edited and was not re-run after. Re-keyed, fixture followed; the
  three test files 150 passed. Rule kept: the static list runs again after ANY harness edit, before a push.
- 2026-09-29 — 5c opening measure ≈ 14 (above); stand-down on the steward's word at gauge 43 %, every phase
  pushed, tree clean. The successor opens 5c on this measure.
- 2026-09-29 — successor session (« Agent : l16 3 »): handshake; the brief's « § Amendment 23:27 » is its « orders
  58, 59, 65, 67a, 70 » paragraph (steward's word), context gate 80 %, exit ~75 %. Merged `origin/main` `e65130ab1`
  (#628 office, #629 heavy), no conflict, pushed `041830709`. Slip B-384: one read-only `cd` into
  `design/src/mocks/seeds` chained in a command, nothing written or run there — the rule: no `cd` into design/src,
  even read-only, even chained.
- 2026-09-29 — 5c opening: the predecessor's R229 successor (« Pan Am 103 », « Smiling Friends ») is FALSE — a
  settled folder stands at « verified » pending (`staging.ts` SETTLED_AT), « rangé » done, so `slotArrivals` keeps it
  out of « En vol », and the offer is drawn on « En vol » alone (`now-tab.tsx`). STOP D → RULINGS 5 = B
  (`poseArrived`). Cut 5c (Torrents side) / 5d (« En vol » side), announced. « En vol » readers GREEN before
  (`p05c-readers-before.log`): requester_line 14 · abandon_quarantines 15 · scroll_keeps_place 40 · audit2 13 ·
  content 27 · now_holds_in_flight 8 · one_card_per_medium 6 · one_ladder 44 · release_take_sentence 5 ·
  follow_offered 13 · release_candidates 4; `actions.py`, `ident.py` print no hold count, not counted.
- 2026-09-29 — 5c: R261 hold 17 RED (`p05c-red.log`: « the seeds hold an entry the client is still downloading —
  ['seeding'] »). Zinzins COMPOSED into `downloads.json` (real: title, ids, S03E14, 0.34; composed: infoHash = sha1
  of the name, release name, 1.2 GB, c411, origin, ratio 0, no deadline, no eta). Oracle alone: 10 keys, 5 states ×
  (`shell/page`, `trackers/body`), one row taller; declared by script (7 states, `trackersTab: "torrents"`),
  proved (`p05c-accept-proof.log`). Hold 17 first read the title by equality — the row draws « title · S03E14 »;
  re-read as its opening. Rules R261 64 · R263 15 · R122 13 · audit 14 · audit2 13 · R260 27 · R262 14 · page_host
  42, 0 failed; a11y dark 0, light 88. Mutation Zinzins's row dropped → FAIL « « Les Zinzins de l'Espace »,
  downloading, is a row of « Torrents » under its own title — None » (`p05c-mutation.log`). Pushed `3b822cf55`.
- 2026-09-29 — 5d: R229 re-aimed OUT LOUD (holds 2 and 4: successor = the same real series, read off
  `downloads.json`, absent from « En vol » before arrival, offered after), RED (`p05d-red.log`, 6 FAIL: Zinzins a
  card of « En vol », `acq-now-direct-arrived` unknown). The move: the staging lists are SERVED through
  `arrivedOnly` (`mocks/handlers/staged-folders.ts`; `staging.ts` stays at 399 — no new line), a direct add the
  client still downloads is no card, a follow's card kept; dial `poseArrived` (`mocks/trackers-state.ts`: the
  download completes, the progress chip goes); state `acq-now-direct-arrived` (`states/tunnel.ts`, beside its
  precedents). `moving.json` keeps the row (the served answer goes 5 → 4); its line « S03E14 · suivi » for a series
  nobody follows → « qBittorrent (manuel) ». Slips: my `[data-follow]` selector refused by `check-markup-contracts`
  (re-read by value); one `rg` over the tree hung, stopped at once — every `rg` names a type or a PATH.
- 2026-09-29 — 5d gate: static list 10/10, typecheck 0, vitest 141 passed. Oracle alone: 8 keys, 4 states ×
  (`shell/page`, `acquisition/body`) lose the card + the new state; declared by script (scen loaded, Now tab),
  proved (`p05d-accept-proof.log`); `test_oracle.py` 142 → 143. Readers AFTER (`p05d-readers-after.log`):
  requester_line 14 · abandon_quarantines 15 · scroll_keeps_place 40 · audit2 13 · content 27 · now_holds_in_flight
  8 · one_card_per_medium 6 · one_ladder 40 · release_take_sentence 5 · follow_offered 16 · release_candidates 4 ·
  R261 64 · R122 13 · audit 14, 0 failed. `one_ladder` 44 → 40: its four per-card holds on Zinzins's card go with
  the card; SUCCESSOR: the direct add's ladder still read on Alabama Solution and Conclave, Zinzins arrived read by
  R229. a11y dark 0, light 88. Mutations: filter off → FAIL « before it arrives, « Les Zinzins de l'Espace » is no
  card of « En vol » »; `poseArrived` inert → FAIL « once arrived, … carries the offer » (+ panel, tap); a
  `data-follow` on the Torrents title → FAIL « … offered no « Suivre » there — {'follow': 1} » (`p05d-mutation1–3`;
  a first M1 expression broke the build, no verdict, re-run).
- 2026-09-29 — phase 7 opening ≈ 12: `acquire.db` `seed_obligation` 60 rows, 0 released/breached/satisfied →
  STOP D → RULINGS 6 = B. The shared subject is already seeded (President Curtis c411 / tr4ker, same `name`), so
  `torrent-remove-confirm-obligation` itself gains the consequence. R263 hold 4 re-aimed OUT LOUD (round 9 Q7),
  holds 9, 10 new; RED (`p07-red.log`, 6 FAIL). The move: the mock's removal takes every entry of the same
  `name`, releasing each running obligation; the confirmation says the share ends on the other trackers and names
  each running obligation there; dial `poseExternalRemoval`; states `torrent-remove-confirm-shared`,
  `torrents-external-removal`; words `external`, `removal`. Slips: names `owesRunning`, `sharing`, `owing`
  refused by the vocabulary arm — renamed.
- 2026-09-29 — phase 7 gate: static 10/10, typecheck 0. Oracle alone: 2 new states + 25 `shell/dialog` keys
  (6b's B-554 list, identical), proved (`p07-accept-proof.log`); `test_oracle.py` 143 → 145. Rules R263 21 · R261
  64 · R260 27 · R262 14 · R122 13 · audit 14 · page_host 42, 0 failed; a11y dark 0, light 88. Mutations: the
  removal not grouped → FAIL « the same files on tr4ker left with it, in the same render »; the posed removal
  leaving the row → FAIL « « Ted Lasso », removed by hand, is simply gone … — 7 row(s) »; the consequence dropped
  → FAIL « removing it from tr4ker says the share on c411 ends too » (`p07-mutation1–3.log`).
- 2026-09-29 — phase 8 opening ≈ 13.5: no real threshold, refused identifier or breach → STOP D → RULINGS 7
  (and the standing rule). R264 `trackers_alert.py` RED (`p08-red.log`, 13 FAIL; a first run crashed on the absent
  dial — the calls made optional so the red reads every hold). The move: `alertOf` in `queries.ts` (one derivation:
  under its own threshold, refused identifier once per tracker, breach on an active entry), the entry's two chips,
  the row's breach chip; dials `poseAlertThreshold` (the settings row the write sets; its key `alertThresholdKey`
  now shared with the summary handler), `poseIdentifierRefused` (the layer's frozen now), `setObligationBreached`
  (its own deadline); states `tracker-alert-active` (c411 at 1,5), `tracker-identifier-refused` (tr4ker),
  `torrent-obligation-breached` (Star Trek); word `breached`; `--record` for the new rule file.
- 2026-09-29 — phase 8 gate: static 10/10, typecheck 0. Oracle alone: the 3 new states only, 0 key moved, proved;
  `test_oracle.py` 145 → 148. Rules R264 14 · R261 64 · R263 21 · R262 14, 0 failed; a11y dark 0, light 88.
  Mutations: the entry reading a stale threshold (null) → FAIL « tracker-alert-active: every entry's alert agrees
  with the summary served »; the refusal joined to every torrent of its tracker → FAIL « no « Torrents » row of
  tr4ker carries the refusal — one unit for its tracker » (`p08-mutation1–2.log`).
- 2026-09-29 — phase 9 opening ≈ 13.5: STOP D (the « vu » precedent absent) → RULINGS 8 = A; broken obligations
  POSED (`poseBrokenObligation`, Lanterns + Ted Lasso on c411), announced under RULINGS 7. R264 re-aimed OUT LOUD
  (holds 7–9), RED (`p09-red.log`, 7 FAIL). The move: `markBrokenObligationSeen` declared (`x-unseeded`), types and
  demands register regenerated (`compare-contracts.py --write`, `--check` 0); the mock flips `seen`; `alertOf`
  gains `unseen` per tracker; the entry's count chip, the nested fold (`BrokenObligations`), « Vu » / « Vue »; verb
  `obligation-seen` in `verbs.ts`; states `tracker-broken-obligations`, `…-open` (the fold opened by a finger,
  `OPEN_AFTER`); word `broken`. Slip: a guessed hash for Lanterns, caught by reading the seed before the run.
- 2026-09-29 — phase 9 gate: static 10/10, typecheck 0. Oracle alone: the 2 new states only, 0 key moved, proved;
  `test_oracle.py` 148 → 150. Rules R264 21 · R261 64 · R263 21 · R262 14 · R260 27, 0 failed; a11y dark 0, light
  88. Mutations: « Vu » without the write → FAIL « « Vu » asks the write once for that obligation — [] » (+ stays,
  count); the write removing the row → FAIL « the row seen STAYS, and says it » (`p09-mutation1–2.log`).
- 2026-09-29 — MIDPOINT FULL SUITE (`midpoint-suite.log`, `run.sh` no flag: 181 rules + 26 guards; the oracle is its
  own tier, not in it): 179/181 rules, 25/26 guards. `entry.py`, `pwa.py`: `Page.goto` 30 s on the DEPLOYED
  `tm-design` (an HTTP probe answers 401 in 0.04 s, pm2 online, 0 restarts), 5/5 draws each
  (`midpoint-o48-1…5.log`) — charged to the ENVIRONMENT by the steward, no 10-against-10 (they read the deployed
  host, not the branch); the `load` diagnosis is the steward's. `check-live-relay` [map-completeness]:
  `/api/trackers` read, refreshed by no event, exempted nowhere — a REAL fall dating from phases 1–3, invisible to
  the guard (it reads literal keys only; the Trackers reads key on constants) until phase 9's « Vu » spelled the
  key → steward: A, phase 10 repairs it by its substance and opens on it as its RED; the guard must read green at
  10's gate AND name /api/trackers, /api/acquisition/downloads, /api/acquisition/obligations. The blind spot: B-570
  `open` (not repaired, measure 1). Order 52 at the midpoint: harness 1286 / product 2301 = 0.56. My slip: a report
  claimed the oracle green in this suite — corrected at once, it is not in it.
- 2026-09-29 — phase 10 opening ≈ 13.5 (+ `useBadgeReads`). R264 re-aimed OUT LOUD (holds 10–11, the bar), RED
  (`p10-red.log`, 6 FAIL) with the live-relay fall (`p10-red-relay.log`). The move: `trackersBadge` and
  `useTrackersBadgeReads` in `queries.ts`, the row's `badge` + `useBadgeReads` in `app/navigation.ts`;
  `features/trackers/live.ts` (RatioMeasured → summary; SeedObligationRecorded/Satisfied → obligations;
  SeedObligationBreached → both; Download* → downloads), registered in `app/live-updates.ts`; the four ratio names
  leave `acquisitionLiveExemptions`, its `because` rewritten; the reads key on exported literal keys `trackersKey`,
  `downloadsKey`, `obligationsKey` (the guard reads `\w*[Kk]ey` only — an upper-case `TRACKERS_KEY` was still
  invisible, caught by asking the guard's own `read_addresses()`); dial `poseTrackerRatio`; state
  `bar-trackers-alert` (frame.ts, beside drawer-navigation); frame-domain app/ 146 → 152 (baseline `_why`); word
  `unseen`. Slips: a BSD `sed` with `\b` that changed nothing (caught by a grep, redone in Python).
- 2026-09-29 — phase 10 gate: static 10/10, relay 0 with the three addresses READ (32 read, 24 refreshed), typecheck
  0. Oracle alone: `bar-trackers-alert` only, 0 key moved, proved; `test_oracle.py` 150 → 151. Rules R264 27 · R91
  170 · R261 64 · R263 21 · R260 27 · page_host 42 · badges_observed 9 · bar_places 13 · bar_shares 14, 0 failed;
  a11y dark 0, light 88. Mutations: the badge dropping the unseen → FAIL « tracker-broken-obligations: the bar's
  Trackers tab counts the sum of the components, 2 »; the rules unregistered → R91 FAIL « trackers: RatioMeasured
  refreshes something — 0 of 56 »; RatioMeasured unclaimed → FAIL « a RatioMeasured event above the threshold moves
  the badge » (`p10-mutation1–3.log`). Order 73 received.
- 2026-09-29 — phase 11 (≈ 4, no rule, as planned): STOP A (the title would lie) + STOP D (L22's DESIGN is gone)
  → RULINGS 9. « Ratio global » / « Obligations en cours » removed from `panel-more.ts` and `fr.json`, the title
  « Veille », the header rewritten (why the facts left). Static 10/10, typecheck 0. Oracle alone: `sheet-more` on
  `shell/sheet-content` only, declared by script, proved. Rules producers 48 · panel 60; a11y dark 0, light 88.
  NOTE FOR PHASE 17: L22's DESIGN § 1.7 (`docs/features/maquette-l22/DESIGN.md@232a908ca`, l. 258) should read
  « the panel's ratio facts leave at L16 (§ 18, phase 10) » — its folder died at #627. Slip: a gauge figure
  written into a STOP message before it was measured (the measure then read the same 46).
- 2026-09-29 — phase 12 opening ≈ 16 → STOP D (the engine's global threshold) → RULINGS 10 = A; cut 12a/12b.
  Card readers GREEN before (`p12-readers-before.log`): follow_offered 16 · set_aside_is_later 13 · plex_match 15 ·
  one_ladder 40 · cards 78 · content 27 · requester_line 14 · card_without_identity 13 · todo_holds 11.
- 2026-09-29 — 12a: R265 `deferred_reason.py` RED (`p12a-red.log`, 10 FAIL). A deferral is BEFORE « arrivé »: the
  first subjects (Curtis, Furious) were already in staging — re-aimed before the move onto « This City Is Ours »,
  the one card of « En vol » not arrived, all three causes posed on it. The move: `JourneyStage.tracker` /
  `.minimumRatio` (demands in their descriptions), types and register regenerated (`--check` 0); the reason's
  sentence takes the tracker and its own threshold (`Intl.NumberFormat(i18next.language)`); `poseDeferral` in
  `mocks/handlers/posed-deferral.ts` (the threshold read from the tracker's economy block, c411 = 1, the global
  `ingest.min_ratio` = 0); three states in `tunnel.ts`; words `cause`, `deferral`, `deferred`.
- 2026-09-29 — 12a gate: static 10/10, typecheck 0. Oracle alone: the 3 new states only, 0 key moved, proved;
  `test_oracle.py` 151 → 154. Rules R265 12 and the nine card readers AFTER, the same counts, 0 failed; a11y dark 0,
  light 88. Mutation: every cause drawn as « space » → FAIL « « This City Is Ours » says it is deferred, « Différé :
  le ratio sur … » » (`p12a-mutation1.log`).
- 2026-09-29 — 12b: R265 holds 5–6 RED (`p12b-red.log`, 2 FAIL). The move: « Voir le tracker » at the foot of a card
  whose rung stands on a ratio deferral — `data-go="trackers"`, `data-dial="trackers:<tracker>"` — read by the
  Trackers page's own landing door (tab, then the tracker whose entry opens); no import across features. Hold 6
  RE-AIMED OUT LOUD before the gate: it read `list=trackers` on the address, but the « Trackers » tab is the default
  and never written (`lib/addresses.ts:141`) — it reads the tab selected, no `list=torrents`, `tracker=c411`. Name
  `feet` refused by the vocabulary arm → `footOptions`.
- 2026-09-29 — 12b gate: static 10/10, typecheck 0. Oracle alone: `acq-card-deferred-ratio` on (acquisition/body,
  shell/page), the foot's line, declared by script, proved. Rules R265 16 · cards 78 · follow_offered 16 · R260 27 ·
  R262 14 · url_state 103 · default_tab 16, 0 failed; a11y dark 0, light 88. Mutations: the path dropped, the words
  kept → FAIL « a finger on « Voir le tracker » lands on the Trackers tab … — {'path': '/' …} »; the global
  `ingest.min_ratio` read instead → FAIL « it names c411 and its own threshold 1, never the global 0 — '… seuil de
  0.' » (`p12b-mutation1–2.log`).
- 2026-09-29 — phase 13 (≈ 9, no rule, as planned): `previewRanking` declared with its schemas (maquette names);
  `trackerRatioState` on the scored release a DEMAND; seed `ranking-samples.json` = the backend's own twelve
  `_ranking_preview_samples`, family RANKING_SAMPLES `served` (fixture-register + projections); the mock
  (`mocks/handlers/ranking.ts`) ranks with `rank()`'s semantics, nothing dropped. Types + register regenerated,
  `compare-contracts --check` 0, `check-mock-seeds` clean. Words criterion, economy, lower, met, points, preview,
  scored. The contracts tier FELL on `check-state-ownership`: 12b's conditional spread inside `store.write` —
  ESCAPED FROM 12b's gate; WHY: the guard sits in run.sh's cheap guards, not in the CI static list my gate ran;
  FAMILY: every cheap guard of the tier — the static list now runs all 26 (`p13-contracts.log` red,
  `p13-contracts2.log` green). Fixed by two writes (`03e148b51`); R265 16 · R260 27 · default_tab 16 green.
  Oracle alone: no divergence (154 × 38).
- 2026-09-29 — phase 14 opening ≈ 19 → STOP D (the content read absent) → RULINGS 11 = A; cut 14a/14b.
- 2026-09-29 — 14a: `readConfigurationFile` + `ConfigurationFileContent` declared; seed `configuration-files.json` =
  the operator's `ranking.json5` (9 criteria), provenance in fixture-register; `mocks/configuration-files.ts` (held
  per layer state) + the route; `/settings/ranking` (`routes/ranking.tsx`, router tree, SCREEN_PARENTS → cfg,
  `__screens.ranking`); `features/settings/ranking-screen.tsx` lists field, scoring, weight from the file; state
  `ranking-editor`; the settings exemption names the file's key; conformance test's known `name` → `ranking.json5`
  (said out loud); frame-domain app/ 152 → 153; words criteria, editor, ranking, scoring. METHOD SLIP: the move
  was written BEFORE R266 — its red was then read on HEAD with the route unplugged (`p14a-red.log`: « one row per
  criterion … — [] against [9] »), a first try restoring the parent's files broke the build (no verdict) and a
  zsh unsplit variable made an earlier try run on HEAD (R266 crashed there on a string threshold « 1GB », fixed).
- 2026-09-29 — 14a gate: 28 static checks green, typecheck 0, vitest green. Oracle alone: `ranking-editor` only, 0
  key moved, proved; `test_oracle.py` 154 → 155. Rules R266 22 · settings 68 · settings_editing 15 · page_host 42 ·
  url_state 106 (it reads the new screen address) · screen_addresses 61, 0 failed; a11y dark 0, light 88. Mutation:
  a constant list (one criterion, weight 1) → FAIL « one row per criterion of the file … — ['resolution'] against
  [9] » (`p14a-mutation1.log`).
- 2026-09-29 — 14b: R266 holds 4–6 RED first (`p14b-red.log`: the rubric stays on /settings, the quality foot
  toasts its promise, the two states unknown). The move (`cee542f68`): the verb `ranking-editor`, the editor's
  skeletons and surface error, states `ranking-editor-loading` / `-error` (the read held back / answered 500),
  `rankingToast` removed. page_host FELL — the rubric opened /quality/global → STOP A → RULINGS 12 = B: the
  rubric keeps `data-profile="global"`, the weights button alone leads to the editor; hold 4 re-aimed OUT LOUD
  onto rubric → global profile → weights → editor. The « settings row intercepting the tap » I reported was MY
  locator: `has_text` is case-free and the tracker topic's subtitle quotes « le classement des releases » —
  the rule now finds the rubric by `[data-profile]`.
- 2026-09-29 — 14b gate: 28 static checks, typecheck 0. Oracle alone: the 2 new states only, 0 key moved, proved;
  `test_oracle.py` 155 → 157. Rules R266 27 · page_host 42 · settings 68 · settings_editing 15 · screen_addresses
  61, 0 failed; a11y dark 0, light 88. Mutation: the weights button toasting again → FAIL « and there « Poids du
  classement (global) → » lands on the editor … {'path': '/quality/global'} » (`p14b-mutation1.log`). B-298 →
  `to confirm`, its text corrected. Stand-down at gauge 65 % (measured), the steward's word (successor takes 15).
- 2026-09-29 — successor session (« Agent : l16 4 »): handshake (gauge 11 %); merged `origin/main` `77e7b8436` (#630,
  #631): one conflict, BUGS.md's index — B-564 (main) and B-570 (ours) both kept; `check-bug-register` clean; pushed
  `d24c6a6c0`. The scratchpad `static.sh` rebuilt from `REPOSITORY_GUARDS` + the CI's two (28 checks; macOS bash 3.2
  has no `mapfile`).
- 2026-09-29 — phase 15 opening ≈ 10, no cut. The write's body for a WHOLE file is `{values, digest}` — the digest the
  read answered is the precondition; the maquette's contract answers a conflict as `200 {conflict: true}`
  (`queries.ts:102`), not 412. The settings' identity-keyed write unchanged. R266 hold 2 RE-AIMED OUT LOUD (the weight
  read as the field's value), holds 7–10 new; RED (`p15-red.log`: 31 holds, hold 2 ×9, 7, 8 named).
- 2026-09-29 — 15 move `62a135990`: a weight field per criterion (`weightInput`), « Enregistrer » (closed while
  nothing valid is typed, « Enregistrement… » while in flight), the conflict banner in `screens.settings.conflictLead /
  Rest` with « Relire le classement » (the edits kept until then); `writeFileContent` in the mock (refuses a stale
  digest, gives the written file a new one); states `ranking-editor-saving` (the write held back), `-save-conflict`
  (`setConfigurationConflict`), a finger typing +2 and tapping save; words `conflict`, `digest`, `saving`. Slip: a
  `rename-identifiers.py` run on `whole` renamed that local across 15 harness files — every file outside the phase
  restored from HEAD before the commit, the rename re-done on a unique name.
- 2026-09-29 — 15 gate: static 28/28, typecheck 0, vitest 142. Oracle alone: the 2 new states only (24 divergences,
  all theirs), declared by script (every state entering the ranking screen), 0 key moved, proved
  (`p15-accept-proof.log`); `test_oracle.py` 157 → 159. Rules R266 32 · settings 68 · settings_editing 15 ·
  seeds_at_rest 23 · page_host 42 · screen_addresses 61 · trackers_policy 14, 0 failed; a11y dark 0, light 88. Hold 11
  added after the gate's rules (the digest precondition was held by nothing): a stale-digest write is refused.
  Mutations: the save answered without the call → FAIL « « Enregistrer » writes ranking.json5 through
  updateConfigurationFile, once, and says so — … [] · toast 'Enregistré — ranking.json5.' »; the mock keeping no
  content → FAIL « the NEXT read answers the saved weight 6 … — {'resolution': '4' …} »; the digest not compared →
  FAIL « a second editor holding the digest read before the save is refused … — conflict False · read 4 »
  (`p15-mutation1–3.log`).
