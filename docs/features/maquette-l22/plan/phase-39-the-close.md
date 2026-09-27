# Phase 39 — The close

**Numbered 35, then 37, then 39, on 2026-09-27** (was 27; the triage's F51). **Carried at its opening, from the coherence triage (`review-archive/coherence-2026-09-27-triage.md` § B; texts in `coherence-2026-09-27.md`)**: F8 (the bar count in the
close's texts), F52 (the close edits only what the brief allows — `IMPLEMENTATION.md` and `docs/reference` are the
steward's — and counts the folder's deletion), F67 and C9 (their L22 parts).

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** The count of named states by the design's own command
  (`python3 -c "import re,glob;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"', open(f).read(), re.M)) for f in glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"`)
  → **114** today; the design's figure at the close is the states the phases declared, counted at the close by the design's command (amended 2026-09-27, triage F50: « 129 » was the first drawing's). `grep -n 'Every state has a name' frontend/maquette/README.md`
  reads « count them there, never here ». Documents naming the page today:
  `git grep -c -i 'arrivals\|Arrivées' -- docs/reference frontend/maquette/README.md IMPLEMENTATION.md CLAUDE.md BUGS.md` →
  `BUGS.md` 37, `IMPLEMENTATION.md` 23, `frontend-architecture.md` 10, `product-intent-map.md` 9, `operator-method.md` 8,
  `product-intent.md` 3 (4 before #611 rewrote § 20 point 3 and § 16 point 3), `README.md` 4, `CLAUDE.md` 1, `backend-demands-architecture.md` 1, `frame-survey.md` 1.
  The README lines that name the page: `:597` (the card's readers), `:741`, `:780` (the cut table), `:949` (R66's row).
  The register rows this lot touches: B-515, B-531, B-371, B-514, B-037, B-038; B-538 and B-549 are NOT this lot's.
- **Points ≈ 9.** No code sites. The register re-read (8 rows) 3; the README's four lines and the cut table 2; the
  plan's own « Where it lives » and « Done when » lines checked against what landed 1; the report 2; the debt list 1.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run: 114 named states, the
  README's four lines, the document counts — identical, except `product-intent.md` (3, was 4: #611 rewrote the two sentences that
  named the page). **Points 9 → 9; the rulings moved what the close checks, not what it costs**: the states are 129, not 128 (OPEN
  10 adds `acq-abandon-confirm`), and the eleven answers are proved landed rather than read as open.

A documentation phase, and the LAST: every claim below is a command re-run on the branch head with its output pasted in
the report; a sentence that cannot be re-run is removed, not softened.

## The proof FIRST

- **The register, row by row.** B-515 and B-531 die with the page (recorded as such; B-531 is already `fixed #603` and is
  annotated, not reopened — OPEN 6, ruled A, took away the lever on which an inactive action could look active); B-371 closed history with its walk re-aimed; B-514 closed or re-pointed at Système's levers;
  B-037 and B-038 die with `arrivals.py`; B-538 and B-549 named as NOT this lot's.
- **`frontend/maquette/README.md`**: the cut table (« A medium in trouble → **Arrivées** » becomes Acquisition › « À traiter »),
  the « A decision is a FOLDER » paragraph's « Arrivées list », R66's row, the card's readers row, and the state count —
  by command, never by copy.
- **`docs/reference/frame-model.md` / `frame-survey.md`**: any « Today → target » line that now reads false (the bar, the
  drawer's rows, the menu button); the survey's line 186 describes production's four tabs and is production's, not touched.
- **The operator's word, not this lot's**: the six clause-map rows (DESIGN § 6.3) — DOIT-3's wording (« lancer / stopper ») among
  them, since OPEN 6 was ruled A —; demand D and the two by-hand stream rows. **The close hands these over; it edits none of
  them.** The constitution's three sentences (§ 20 point 3, § 16 point 3, § 17 point 4, « dicté le 2026-09-26 ») are on `main`
  since #611 and need no hand-over.
- **The debt, by name**: the media sheet's trace of a film (« acquis le …, release, demandeur ») — DESIGN § 3.5 — for the
  steward to assign.
- **The eleven rulings** (DESIGN § 7.2, all ruled 2026-09-26): each is proved landed where the design says, by a command
  whose output goes in the report — OPEN 1 the tabs' DOM order (R-L22-e); OPEN 2 the bar's shares at three and at two
  (R-L22-s); OPEN 3 no arrival card in « Suivis » (R-L22-l); OPEN 4 « sur 8 » and eight cells (R-L22-f); OPEN 5 `/arrivals` drawn
  as not-found, not redirected (R-L22-o); OPEN 6 `data-pipe` gone from the source and the four rules re-aimed (the phase-31
  table); OPEN 7 no progression on the candidates screen (R-L22-d); OPEN 8 both families in the menu badge (R-L22-c); OPEN 9
  « Confirmer » and « Corriger » answered on the network (R-L22-t); OPEN 10 « Abandonner » sending nothing before its
  confirmation (R-L22-u); OPEN 11 no reassign gesture on the card.
- **`IMPLEMENTATION.md`** is amended here and only here (the lot was not open before): the « In flight » row when the pull
  request opens — pull request number first, then the version — and `scripts/check-implementation-state.py` holds it.

## The gates the close runs

The full suite (`frontend/maquette/harness/run.sh`), `--a11y`, `--compare` with `failed` read FIRST,
`python3 scripts/check-intent-map.py` and `python3 scripts/check-bug-register.py` read by OUTPUT (B-346), `make lint`.

## Register

The six rows above, amended.

## Oracle: states that diverge, declared by name

**None.** The full oracle at zero divergence over every surviving state; the new states recorded — the states the phases declared, counted at the close by the design's command (amended 2026-09-27, F50).

## Commit

`docs(maquette-l22): the lot's close — the register, the README and the debts`
