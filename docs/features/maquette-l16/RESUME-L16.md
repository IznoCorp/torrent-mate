# L16 — RESUME

## STATE BLOCK (rewritten at every boundary)

- **Branch** `feat/maquette-l16`, worktree `/Users/izno/dev/worktrees/wave-l16`, cut from L22b's head
  `a227ad6cb` (PR #626). `origin/main` is NOT merged in — only on the steward's word that L22b is squashed.
- **Orchestrator** « Orch : TM frontend [84baa3] ». Handshake answered 2026-09-28.
- **Done** phase 1 (the reads' contract).
- **Next** phase 2 (the page and its two tabs) — re-measure first; the brief predicts a cut (≈ 19).
- **Remaining phase list**, rebuilt from `ls plan/`: 2 · 3 · 4 · 5 · 6 · 7 · 8 · 9 · (midpoint full suite) ·
  10 · 11 · 12 · 13 · 14 · 15 · 16 · 17.
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
