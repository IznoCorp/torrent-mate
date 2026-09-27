# Phase 11 — Acquisition's panel drops its hard-coded ratio facts

`features/acquisition/panel-more.ts`'s « ⋮ » sheet has drawn « Ratio global » and « Obligations en
cours » as HARD-CODED constants since before this lot existed — a fixture that names the operations
that would replace it (§ 18 point 1, DOIT-13, ruling 12). Now that phase 10 gives the ratio a real
surface with its own badge, the constants have no reason left to stand: this phase removes them (F17).

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `wc -l frontend/maquette/design/src/features/acquisition/panel-more.ts` → 84 lines.
  `sed -n '1,40p'` of the same file — the header itself says the four facts are a fixture, and names
  `GET /api/acquisition/obligations` / `/downloads` as their replacements, exactly the operations phase
  1 declares. `python3 -c "import json;d=json.load(open('frontend/maquette/design/src/i18n/fr.json'));print(d['panels']['standby'])"`
  → `{title, meta, lastPass, nextPass, globalRatio: 'Ratio global', obligations: 'Obligations en cours',
  runNow}` — the two keys this phase removes; `lastPass` / `nextPass` / `runNow` are L20's (the veille's
  own figures), untouched here.
- **Points ≈ 4.** `WATCH_FACTS.globalRatio` and `.obligations`, and their two `lignes` in the panel's
  `faits` block, removed (≈ 10 edited) 2; the two `fr.json` keys removed (≈ 2 edited) ½; a dated line
  in `docs/features/maquette-l22/DESIGN.md` § 1.7 (l.258), noting the panel's ratio facts leave at L16
  — a documentation row 1; a comment in `panel-more.ts` itself, naming L16 as the lot that closed this
  fixture rather than leaving the header's own promise unanswered ½.
- **Re-cut (2026-09-27, on `5e5ecd052`).** No row of the prior re-reads names this fix: F17 is an audit
  finding this redraw is the first to carry. It is placed here, its own small phase, rather than folded
  into phase 8 or 10 — removing a fixture is a DIFFERENT kind of change from drawing the surface that
  replaces it (INDEX's own « one kind of change per phase »), and it needs the real surface to exist
  first so the operator is never left with strictly less than before (INDEX, « Why seventeen phases »).

A CLEAN-UP change: a fixture is removed once its replacement exists; nothing new is drawn.

## No rule in this phase, and that is stated rather than skipped

Removing two hard-coded lines from an existing panel proves nothing new — the panel's own existing
tests (if any) or the oracle's own recorded reading of `panels.standby` carry the proof that the sheet
still renders. **A phase with no rule says so; it does not invent one to look complete.**

## The move

- **`features/acquisition/panel-more.ts`** — `WATCH_FACTS.globalRatio` and `.obligations` removed,
  along with their two `lignes` entries in `standbyPanel()`'s `faits` block; the header comment
  corrected to say the ratio facts left at L16 (§ 18, phase 10), never « replacement pending ».
  **`crossReference()` toward the Trackers page is NOT added** (DESIGN's own choice, § 4.9 of its
  reasoning): the panel is « second rank — consulté, pas surveillé », and a bare link to a page that no
  longer has a single « obligations en cours » figure to point at would read as a promise this design
  does not keep either.
- **`i18n/fr.json`** — `panels.standby.globalRatio` and `.obligations` removed.
- **`docs/features/maquette-l22/DESIGN.md`** § 1.7 (l.258) — a dated line: « the panel's ratio facts
  leave at L16 (§ 18, phase 10) », per F17.

## Register

None closes here (B-144's reading half already closed at phase 1). The dated line in L22's own design
is this phase's only cross-lot edit, and it is a NOTE, not an amendment of L22's own scope.

## Oracle: states that diverge, declared by name

**`panels.standby`'s own recorded reading changes**: two `lignes` are removed from its `faits` block —
accepted, named, with the reason « L16 phase 11: the ratio facts leave the standby panel for the
Trackers page ». Any OTHER change to the panel (the veille's own facts, the « Lancer la veille »
button) is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `panels.standby`'s own state
(re-recorded, not new).

## Commit

`chore(maquette-l16): drop the standby panel's hard-coded ratio facts`
