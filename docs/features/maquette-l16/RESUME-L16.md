# L16 — RESUME

## STATE BLOCK (rewritten at every boundary)

- **Branch** `feat/maquette-l16`, worktree `/Users/izno/dev/worktrees/wave-l16`, cut from L22b's head
  `a227ad6cb` (PR #626). `origin/main` is NOT merged in — only on the steward's word that L22b is squashed.
- **Orchestrator** « Orch : TM frontend [84baa3] ». Handshake answered 2026-09-28.
- **Done** phases 1, 2 (2a · 2b · 2c, pushed `8051b49ca`); 3 committed, its gate next.
- **Next** phase 4 (the policy and the alert threshold; STOP D on how the three fields compose).
- **Remaining phase list**, rebuilt from `ls plan/`: 4 · 4 · 5 · 6 · 7 · 8 · 9 · (midpoint full suite) ·
  10 · 11 · 12 · 13 · 14 · 15 · 16 · 17. Phase 2 was cut 2a / 2b at its opening (≈ 18), 2b re-cut 2b / 2c at its own (≈ 17).
- **Known STOP D, one message each at its phase's opening**: 4 (how the three policy fields compose),
  9 (no « vu » precedent), 12 (the ratio cause is the global `ingest.min_ratio`; the seed), 14 (no read
  of a config file's content in the maquette's contract).
- **Numbers.** Rules R260–R299, register rows B-570–B-589. Highest rule on this head at opening: R250.
  Label → number, bound in the order the phases first need them:

  | label | rule | first written in |
  | --- | --- | --- |
  | R-L16-h | R260 | phase 2 |
  | R-L16-a | R261 | phase 3 |
  | R-L16-b | R262 | phase 4 |
  | R-L16-c | R263 | phase 6 |
  | R-L16-d | R264 | phase 8 |
  | R-L16-g | R265 | phase 12 |
  | R-L16-f | R266 | phase 14 |
  | R-L16-e | R267 | phase 16 |

  A cut that needs a further rule takes R268 onward. No register row taken yet.
- **Logs** `~/Library/Logs/tm-l16/`.

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
