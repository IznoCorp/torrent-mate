# L16-bis — the Trackers page's correction, and Découvrir · PLAN

Design: `docs/features/maquette-l16bis/DESIGN.md`. The implementer is held to `docs/reference/implementer-office.md`,
AMENDED by the auditor's orders 98 and 99 (§ « The gates » below); this plan carries only what is the lot's own.

**Re-cut 2026-09-30, on `main` at `9234341fc`** (orders 97, 98, 99): L16-bis is the CORRECTION of L16 — « bis veut
dire correction » (the operator, 2026-09-14) — so it is cut BY SURFACE, one page each, not drawn as a lot. The plan
of 18 phases (1–4, 6–19; 180 points) is `docs/features/maquette-l16bis/plan/INDEX.md@9234341fc`; every item of it,
every ruling and every owed row has its new phase in `CORRESPONDENCE.md`. **The code opens after the conformity train
has merged** (DECIDED 7's queue; DESIGN § 0.4 for what the train already built).

## The operator's principles, and the phase that proves each (order 97 — the design's table is DESIGN § 0.5)

| Principle, his words | Phase |
| --- | --- |
| « Il faut uniformiser les comportements. Sauf exception volontaire de ma part. » — the torrent card's taps and swipe are the media card's and the follow row's; the tracker row opens a panel; Découvrir's two views swipe alike | 1 · 3 · 4 |
| « on crée pas de nouveau composant on adapte » — every element from `ui/` (DESIGN § 1.8); the adaptations written there | 1 · 2 · 3 · 4; R-L16bis-i at 3 |
| « seule une maquette montrant tout les cas possibles est utile » — 73 named states (DESIGN § 3), each in the catalogue | every phase; counted at 5 |
| « tout doit être responsive … sur tous ! » — R-conformity-a on the touched surfaces' states at each gate; the full sweep at the midpoint and the close | every phase; 2 · 5 |
| « une différence entre film et série » — `torrent-card-film`, `torrent-panel-episode`; Découvrir's « séries » and « films » | 1 · 4 |
| Constitution § 16 (bar pages replace; a link inside a page stacks) — walked by finger | 1 · 2 · 3 |
| « Mes retours sont des corrections sur ce qui est attendu » — a defect he reports on these surfaces while the lot runs joins the phase of its surface (order 98) | any |

## The phases — one surface each, sized by the context (gauge + the last phase's cost ≤ 80), no point cap

| # | Surface | DESIGN | Rules | Page |
| ---: | --- | --- | --- | --- |
| 1 | The torrent card — its facts, its poster and panel, its swipe, and the data they read | S4, S5, S6; § 2.1 | d, e, f | [phase-01](phase-01-the-torrent-card.md) |
| 2 | The « Torrents » tab around it — the landing, the selector, the legend — then the MIDPOINT | S1, S2, S3 | a, b, c | [phase-02](phase-02-the-torrents-tab.md) |
| 3 | The « Trackers » tab — the roster, its switch, its failure, its panel, its legend | S7, S3; § 2.2 | g, h, c, i | [phase-03](phase-03-the-trackers-tab.md) |
| 4 | Découvrir — the header, and the swipe of Q7 | S8, S9 | k, l | [phase-04](phase-04-discover.md) |
| 5 | The close — the lot's gate, the records, the pull request | — | all, by name | [phase-05](phase-05-the-close.md) |

**Measured**: 18 phases → **5** (4 surfaces + the close). The old scale's points are not re-added: order 99 sizes a
phase by the agent's context, and each page's « Opening measure » says what it re-takes.

**The legend phase is removed, its subject lost**: the old phase 6 moved the season legend into `ui/`; the conformity
train did it (phase 4, `2caa2d183`), keyed by tone (`7c0d9c2dc`). What is left — mapping this page's codes to tones,
and the two tones the legend lacks — joins the surfaces that draw a legend (2 and 3). Also gone from this lot, done by
the train: the chevron (old phase 15's `ui/Disclosure` half), the tab bar (train phase 11).

## The gates (order 99, amending the office's « The gate »)

- **A phase gate — light**: the static guards on the files touched; the ORACLE ALONE, accepting only the states the
  page names (the declared list built BY SCRIPT); `run.sh --rules` on the rules of the surfaces touched — each new
  hold read RED on the old code first, then green (its proof: no per-phase mutation, no per-phase `--a11y`);
  R-conformity-a on the touched surfaces' states (`TM_RESPONSIVE_STATES`, built by script). Every browser run names
  `TM_HARNESS_JOBS=2` (order 88); every pytest `-n 2`.
- **The midpoint, after phase 2**: `--contracts` and the full responsive sweep (Chromium + WebKit), once.
- **Once per lot, at phase 5**: the full suite (CI is its authority), `--a11y`, the full sweep, the hold counts, each
  rule of this lot re-run BY NAME (order 98). The reader round follows the pull request: ten claimed mutations drawn
  at random, the finger walk at the seven widths, the principles (`docs/reference/reader-office.md`).

## The stops

**STOP A** — the oracle diverging on a state the page did not name. **STOP B** — the pull request. **STOP C** — OPEN
10 (DESIGN § 5): phase 4 is written for its recommended reading A; the operator's answer is read before phase 4
opens. **STOP D** — a ceiling (`grep -cv '^\s*$'`, 400): `features/acquisition/discover-feed.ts` **382**,
`ui/variants/controls.ts` and `frame.ts` near it on the train's head — a phase landing there moves lines out.
Anything outside these pages: STOP, ask the orchestrator.

## The gate of THIS docs pull request

`python3 scripts/check-docs-cited-paths.py`, `check-no-french.py`, `check-implementation-state.py`,
`check-intent-map.py`, `make lint` — the implementer's gates above do not apply to it.
