# Phase 8 — An obligation says where it came from

**Reads no OPEN question.** It files **demand D** (DESIGN § 6.2) as its first act: a demand is filed where its surface is drawn, and phase 1
could not carry it without crossing the ceiling.

**Opening measure (2026-09-27, on `46806a88d` — the obligations read is L16's and does not exist on this head):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(json.dumps(d['components']['schemas']['ObligationItem'])[:700])"`
  → `ObligationItem` carries `source_tracker`, `min_ratio`, `min_seed_time_s`, `observed_ratio`, `added_at`, `breached_at` / `satisfied_at` /
  `released_at`, `title` — **and no field that says the obligation is a cross-seed's** (`grep -c -i 'cross.seed' frontend/openapi.json` → 0, B-145's own command).
  `docs/features/maquette-l16/DESIGN.md` § 2.1 declares that read for the maquette in L16's phase 1 and § 4.2 draws the obligation's row in
  `features/trackers/tracker-screen.tsx` (L16 phase 5). The engine persists the obligation on injection (`sed -n 353,366p personalscraper/acquire/events.py`,
  « emit-after-persist »), so a cross-seed's obligation exists on the backend and only lacks its origin.
- **Points ≈ 13.** The obligations read edited (`crossSeedOf`) 1; the schema ≈ 12 lines new 1½ (rounded up 2 with the `x-unseeded` sentence);
  the obligations handler re-answered, deriving `crossSeedOf` from the SAME rows as the section 1; ≈ 8 lines of that handler edited 1½; the
  mark and its path in the obligation's row ≈ 15 lines new 1½ and ≈ 6 edited 1; `fr.json` ≈ 4 lines ½; the state `tracker-obligation-cross-seed`
  1; R-L17-d 3 → ≈ 12½, 13 by rounding.
- **Found.** The obligation row L16 draws carries « Libérer l'obligation » (its verb); this phase adds a mark and reads no verb. An obligation
  that is not a cross-seed's reads exactly as L16 drew it: no mark, no empty slot.

## Red today

**R-L17-d — an obligation says where it came from** (DESIGN § 5): a seeded obligation created by a cross-seed carries the mark « partage croisé
de <torrent d'origine> » and a path to the origin's sheet by provider ID; one that is not carries neither. Red against `main`: no field, no mark.

## Move

1. **The contract first**: extend the obligations read with `crossSeedOf{infoHash, title, media|null}` (demand D), `x-unseeded`, `compare-contracts.py
   --write` / `--check`, counters before and after in the report.
2. The handler derives `crossSeedOf` from the section's rows (an obligation that a cross-seed created is a row of S3 too, DESIGN § 2.3).
3. The mark in `tracker-screen.tsx`'s obligation row; `data-part="tracker/obligation-origin"`; the state in `harness/states/trackers.ts`.

## Mutation

Commit first: drop the mark → R-L17-d falls; mark every obligation → its absence hold falls; point the path at the obligation's own title → the
path hold falls.

## Register

Demand D filed by the regenerated register; nothing in `BUGS.md`.

## Oracle: states that diverge, declared by name

L16's `tracker-detail` where an obligation is a cross-seed's — accepted with « L17 § 3.4: the obligation's origin ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py`.

## Commit

`feat(maquette-l17): an obligation born of a cross-seed says whose copy it is`
