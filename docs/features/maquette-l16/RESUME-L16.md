# L16 — RESUME

## STATE BLOCK (rewritten at every boundary)

- **Branch** `feat/maquette-l16`, worktree `/Users/izno/dev/worktrees/wave-l16`, cut from L22b's head
  `a227ad6cb` (PR #626). `origin/main` is NOT merged in — only on the steward's word that L22b is squashed.
- **Orchestrator** « Orch : TM frontend [84baa3] ». Handshake answered 2026-09-28.
- **Done** phase 1; 2a (pushed `a7c8a5eac`); 2b committed, its gate next.
- **Next** 2c (the tab memory; the landing door made plural — Acquisition's readers green before AND after).
- **Remaining phase list**, rebuilt from `ls plan/`: 2c · 3 · 4 · 5 · 6 · 7 · 8 · 9 · (midpoint full suite) ·
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
