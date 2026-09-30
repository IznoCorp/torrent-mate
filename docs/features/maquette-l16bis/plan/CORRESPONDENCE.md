# L16-bis — CORRESPONDENCE: every item of the 18-phase plan, every ruling, every owed row → its new phase

Read BEFORE any code (the auditor's condition). The old plan is `docs/features/maquette-l16bis/plan/INDEX.md@9234341fc`
and its pages `docs/features/maquette-l16bis/plan/phase-NN-….md@9234341fc` (`git show 9234341fc:<path>`). New phases:
**1** the torrent card · **2** the « Torrents » tab · **3** the « Trackers » tab · **4** Découvrir · **5** the close
(`INDEX.md`). « Train N » = the conformity train's phase N (`feat/maquette-conformity`, its `plan/INDEX.md`).

## 1. The old phases, item by item

| Old phase | Item | → |
| --- | --- | --- |
| 1 the contract | `Download`'s seven fields, their descriptions, the stream demand of the rates (DECIDED 1) | 1 |
| 1 | `Tracker`'s `enabled` / `disabled`, `identifierRefusedSince` folded; the `422` refusal | 3 |
| 1 | the register regenerated, counters before and after | 1, 3 (each regenerates); 5 (the last reading) |
| 2 the seeds | the seven entries' figures, read once from qBittorrent, dated | 1 |
| 2 | `lacale` real, three composed trackers, their `settings.json` rows, the fixture register | 3 |
| 3 the mocks | `poseLongName`, `poseUnlinked`, `poseEntryState`, `poseOneEntry` | 1 |
| 3 | `readTrackers`' `enabled` from the settings seed; the `422`; `poseRecovered`; `poseIdentifierRefused` onto `disabled` | 3 |
| 4 « Torrents » first | the two values; R-L16bis-a; `trackers_page.py` re-aimed | 2 |
| 5 (removed on 2026-09-29, DECIDED 7) | the one tab component | train 3 (built), train 11 (Trackers' bar converted) |
| 6 the legend moves to ui | the move | **REMOVED — subject lost**: done by train 4 (`2caa2d183`), keyed by tone (`7c0d9c2dc`) |
| 6 | what is left: this page's codes mapped to tones; the legend's `danger` and `neutral` tones | 2 (the adaptation, and « Torrents »), 3 (« Trackers ») |
| 7 the legend on Trackers | R-L16bis-c; the tone map; `torrents-legend`, `torrents-legend-partial` | 2 |
| 7 | `trackers-legend` | 3 |
| 8 the torrent card | the card, the whole name, the `wrap` value, the marks; R-L16bis-d's whole-name half; re-aims | 1 |
| 9 the card's facts | the state chip, size, sources, date, DECIDED 1's three states, the progress fill; R-L16bis-d's facts | 1 |
| 10 the poster and the panel | the poster, the folder side (DECIDED 2), the panel; R-L16bis-e; re-aims | 1 |
| 10 | the midpoint « after phase 10 » | after 2 |
| 11 the swipe | the right drawer, the confirmation; R-L16bis-f; no left drawer (DECIDED 9) | 1 |
| 12 the tracker selector | the pill, the panel of choices, RULINGS 3's line deleted; R-L16bis-b | 2 |
| 13 the switch | the switch, one write two doors; R-L16bis-g; `trackers_roster.py` re-aimed | 3 |
| 14 a failing tracker says why | the reason, the refusal, the badge term (DECIDED 6); R-L16bis-h; R-L16-d re-aimed | 3 |
| 15 the tracker row and the chevron | the row → its panel (DECIDED 3); re-aims | 3 |
| 15 | `ui/Disclosure`'s chevron (DECIDED 4) | train 3 (built) |
| 16 the design system swept | the orphaned factories of `features/trackers/variants.ts` | deleted where orphaned: 1, 2, 3; the file's end at 3 |
| 16 | R-L16bis-i | 3 |
| 17 Découvrir's header | the move, the count (DECIDED 8); R-L16bis-k | 4 |
| 18 the records | the four register rows of DESIGN § 6 | 2 (legend), 3 (a component redrawn), 4 (literals as figures); train (three tab bars) |
| 18 | the states confronted with DESIGN § 3; demands T1–T3; the fixture register; L17's ledger line | 5 |
| 19 the close | the map's proposal, the demands' counters, the report, the lot's mutations | 5 (the gate); the reader round (ten random mutations, order 99) |

## 2. The rulings

| Ruling | → |
| --- | --- |
| DECIDED 1 (Q1) — volumes by default, a bar and the rate while downloading, the rate while uploading | 1 |
| DECIDED 2 (Q2) — the folder side for an unlinked torrent | 1 |
| DECIDED 3 (Q3) — the tracker row opens a panel, the switch on the row | 3 |
| DECIDED 4 (Q4) — the one chevron | train 3 (done) |
| DECIDED 5 (Q5) — the legend reused, inline, only the codes present | 2, 3 |
| DECIDED 6 (Q6) — a tracker off by failure counts one in the badge | 3 |
| DECIDED 7 (Q7 and its precision) — the train builds the tabs; Trackers conforms | train 3, train 11; the code opens after the train |
| DECIDED 8 (Q8) — « n séries et m films à découvrir » | 4 |
| DECIDED 9 (Q9) — no cross-seed swipe before L17 | 1 (nothing drawn) |
| DECIDED 10 (conformity round Q7) — Découvrir's swipe, left = pass, right = reject, list and deck | 4 |
| OPEN 10 — what « passer » does on the data side | 4 (written for A; STOP C) |
| L16's RULINGS 2 (the second door), kept and extended to `enabled` | 3 |
| L16's RULINGS 3 (the filter line), reversed in form | 2 |
| L16's RULINGS 7 (poses for the unlinked, the long name, the states) | 1 |
| The operator's feedback points 1–10 (DESIGN § 0) | 1: 4, 5 · 2: 1, 2, 3 · 3: 3, 7, 9 · 4: 8 · train: 10 · every phase: 6 |
| DESIGN § 1.9's guard arms | train 12 |
| R-L16bis-j (withdrawn, DECIDED 7) | train (R-conformity-b) |

## 3. The register — what the lot owns, and its neighbours

**Owned rows: none.** `grep -n -i -E "l16-?bis" BUGS.md | wc -l` → **0** on `9234341fc`: no `B-` row names L16-bis
its owner. The lot FILES four (DESIGN § 6, order 57) — § 1 above says where. The demands T1–T3 (DESIGN § 6) → 3
(T1, T2's `disabled`), 1 (T3), all regenerated at 5; T4 withdrawn (DECIDED 8).

**Neighbours read, not owned** (their owner unchanged):

| Row | Why it is near | What this lot does |
| --- | --- | --- |
| B-337 — a follow card swiped open ignores the first tap on its revealed action (`open`; owner L21 / L13, both shipped) | phase 1 wraps the torrent card in the SAME swipe row (`ui/rows.ts`) | phase 1's finger walk taps « Retirer » ONCE after a swipe, on the device; a reproduction is reported to the orchestrator, never repaired here |
| B-532 — three raw `<details>` after `ui/disclosure.tsx` exists (`open`, owner none) | the chevron of DECIDED 4 | train 7 and 9 convert the three sites |
| B-552 — the library's tab floor at 34 px (`open`, owner the operator's walk) | the one tab component | train 3 landed the floor (its gate note, 2026-09-30) |
| B-316 — the suggestion card's two attributes on one node (closed on a reading, 2026-09-06) | phase 4 touches the list row's wrap | the tap / long press held by `discover_gestures.py` stays green; nothing re-opened |
