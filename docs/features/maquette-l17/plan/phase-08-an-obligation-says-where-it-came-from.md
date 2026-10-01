# Phase 8 — An obligation says where it came from

**No OPEN question.** It files **demand D** (DESIGN § 6.2) as its first act: a demand is filed where its surface is
drawn, and phase 1 could not carry it without crossing the ceiling.

**Opening measure (2026-09-27, on `1d1282567` — the obligations read is L16's):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(json.dumps(d['components']['schemas']['ObligationItem'])[:700])"`
  → `ObligationItem` carries `source_tracker`, `min_ratio`, `min_seed_time_s`, `observed_ratio`, `added_at`,
  `breached_at` / `satisfied_at` / `released_at`, `title` — **and no field that says the obligation is a cross-seed's**
  (`grep -c -i 'cross.seed' frontend/openapi.json` → 0, B-145's own command). `docs/features/maquette-l16/DESIGN.md@f3d8fed01`
  § 2.1 declares that read for the maquette in L16's phase 1 and draws the obligation's mark on the Torrents tab's
  row (L16 phase 5). The engine persists the obligation on injection (`sed -n 353,366p
  personalscraper/acquire/events.py`, « emit-after-persist »), so a cross-seed's obligation exists on the backend
  and only lacks its origin.
- **Points ≈ 13.** The obligations read edited (`crossSeedOf`) 1; the schema with its `x-unseeded` sentence 2; the
  handler re-answered from the SAME rows as the mark 1, ≈ 8 lines edited 1½; the mark and its path ≈ 15 lines new
  1½, ≈ 6 edited 1; `fr.json` ½; the state `torrents-obligation-cross-seed` 1; R-L17-d 3 → ≈ 12½, 13 by rounding.
- **Found.** L16's obligation mark is a plain mark (round 10 Q3 = B retired the release verb). This phase adds a
  further mark and reads no verb of its own. An obligation that is not a cross-seed's reads exactly as L16 drew it: no mark, no
  empty slot.

## Red today

**R-L17-d — an obligation says where it came from** (DESIGN § 5): a seeded obligation created by a cross-seed
carries the mark « cross-seed de <torrent d'origine> » (round 9 Q10) and a path to the origin's sheet by provider ID; one
that is not carries neither. Red against `main`: no field, no mark.

## Move

1. **The contract first**: extend the obligations read with `crossSeedOf{infoHash, title, media|null}` (demand D),
   `x-unseeded`, `compare-contracts.py --write` / `--check`, counters before and after in the report.
2. The handler derives `crossSeedOf` from the mark's rows (an obligation that a cross-seed created is a row of S3
   too).
3. The mark in the Torrents tab's obligation mark; `data-part="torrents/obligation-origin"`; the state in
   `harness/states/trackers.ts`.

## ~~Mutation~~

Commit first: drop the mark → R-L17-d falls; mark every obligation → its absence hold falls; point the path at the
obligation's own title → the path hold falls.

**Register**: demand D filed by the regenerated register; nothing in `BUGS.md`.

## ~~Oracle: states that diverge, declared by name~~

L16's `torrents-list` where an obligation is a cross-seed's — accepted with « L17 § 3.4: the obligation's origin ».
~~Any other divergence is STOP A.~~

## Gate — done when

~~Per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py`.~~

## Commit

`feat(maquette-l17): an obligation born of a cross-seed says whose copy it is`
