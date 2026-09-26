# Phase 25 — The close

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** The count of named states by the design's own command
  (`python3 -c "import re,glob;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"', open(f).read(), re.M)) for f in glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"`)
  → **114** today; the design's figure at the close is **128** (114 − 8 + 22). `grep -n 'Every state has a name' frontend/maquette/README.md`
  reads « count them there, never here ». Documents naming the page today:
  `git grep -c -i 'arrivals\|Arrivées' -- docs/reference frontend/maquette/README.md IMPLEMENTATION.md CLAUDE.md BUGS.md` →
  `BUGS.md` 37, `IMPLEMENTATION.md` 23, `frontend-architecture.md` 10, `product-intent-map.md` 9, `operator-method.md` 8,
  `product-intent.md` 4, `README.md` 4, `CLAUDE.md` 1, `backend-demands-architecture.md` 1, `frame-survey.md` 1.
  The README lines that name the page: `:597` (the card's readers), `:741`, `:780` (the cut table), `:949` (R66's row).
  The register rows this lot touches: B-515, B-531, B-371, B-514, B-037, B-038; B-538 and B-549 are NOT this lot's.
- **Points ≈ 9.** No code sites. The register re-read (8 rows) 3; the README's four lines and the cut table 2; the
  plan's own « Where it lives » and « Done when » lines checked against what landed 1; the report 2; the debt list 1.

A documentation phase, and the LAST: every claim below is a command re-run on the branch head with its output pasted in
the report; a sentence that cannot be re-run is removed, not softened.

## The proof FIRST

- **The register, row by row.** B-515 and B-531 die with the page (recorded as such; B-531 is already `fixed #603` and is
  annotated, not reopened); B-371 closed history with its walk re-aimed; B-514 closed or re-pointed at Système's levers;
  B-037 and B-038 die with `arrivals.py`; B-538 and B-549 named as NOT this lot's.
- **`frontend/maquette/README.md`**: the cut table (« A medium in trouble → **Arrivées** » becomes Acquisition › « À traiter »),
  the « A decision is a FOLDER » paragraph's « Arrivées list », R66's row, the card's readers row, and the state count —
  by command, never by copy.
- **`docs/reference/frame-model.md` / `frame-survey.md`**: any « Today → target » line that now reads false (the bar, the
  drawer's rows, the menu button); the survey's line 186 describes production's four tabs and is production's, not touched.
- **The operator's word, not this lot's**: `product-intent.md` § 20 point 3, § 16 point 3 and the new § 17 point 4 (dictated
  2026-09-26 — the design reads them from the annex until the operator commits them); the six clause-map rows
  (DESIGN § 6.3); demand D and the two by-hand stream rows. **The close hands these over; it edits none of them.**
- **The debt, by name**: the media sheet's trace of a film (« acquis le …, release, demandeur ») — DESIGN § 3.5 — for the
  steward to assign.
- **The open questions**: each of DESIGN § 7.2's eleven, with the operator's word if it came, or « still OPEN » with what
  the lot did meanwhile.
- **`IMPLEMENTATION.md`** is amended here and only here (the lot was not open before): the « In flight » row when the pull
  request opens — pull request number first, then the version — and `scripts/check-implementation-state.py` holds it.

## The gates the close runs

The full suite (`frontend/maquette/harness/run.sh`), `--a11y`, `--compare` with `failed` read FIRST,
`python3 scripts/check-intent-map.py` and `python3 scripts/check-bug-register.py` read by OUTPUT (B-346), `make lint`.

## Register

The six rows above, amended.

## Oracle: states that diverge, declared by name

**None.** The full oracle at zero divergence over every surviving state; the 22 new states recorded.

## Commit

`docs(maquette-l22): the lot's close — the register, the README and the debts`
