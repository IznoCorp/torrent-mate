# L22 — the lot's rulings (the steward's, on the implementers' STOPs), one numbered file, non-reopenable

The operator's rulings are not here: organisation rulings 1–15 are in `docs/reference/operator-method.md`, the eleven
on the design's open questions in DESIGN § 7.2. This file holds the steward's rulings on the lot's STOPs, from 1.

## 1 — a state id inside a `page.evaluate` string (auditor, 2026-09-26 16:3x; phase 3)

**The STOP.** `scripts/rename-identifiers.py --values` moves a Python string only when its whole body is an id token, and
its non-values path skips hyphen-adjacent words by design; so `arr-resolution` / `arr-decision` inside
`pg.evaluate("()=>window.__go('…')")` (and one JS array inside a Python string) stayed in five rule files: `actions.py`,
`attrs.py`, `bugs.py`, `decision.py`, `hiding.py` — seven occurrences.

**Ruled A.** Those seven move by an exact substitution of the QUOTED form only (single and double quotes), said out loud
in the commit, and the proof lives outside the tool: (1) the count before on `main` (`frontend/maquette`: 15
`arr-resolution`, 11 `arr-decision`, no other id sharing those prefixes) and ZERO after on the whole repository, every
occurrence kept as history listed by `file:line` with its reason; (2) both quote forms searched; (3) a mutation putting
one old id back into one of the five rules, which must make that rule FALL by name. **B** — a tool arm reaching a state
id inside an evaluate string — goes to the documentation pull request's register as a candidate, not built here.

## 2 — `acq-card-rungs` holds the rungs real rows reach (steward, 2026-09-26; phase 5, STOP D)

**The STOP.** « Eight cards, one on each rung » (DESIGN § 4 row 3) cannot be built from real rows: the queue's families
reach six rungs — notFound « cherché », takeable « attrapé », in-flight « téléchargement » / « arrivé » / « identifié »,
blocked « identifié », doneToday « vérifié dans Plex » — and no row stands at « demandé » or « rangé ».

**Ruled (proposal A).** `acq-card-rungs` is the loaded « En cours » with every family on its ladder: six rungs reached by
real rows, said in the state's label and in R207's docstring. The eight rungs are held whole on `sheet-journey` (« rangé »
opened into its three steps), where R207's order, agreement and one-source holds read them. No derived row: a row nobody
lived is not seeded to fill a picture (§ 13).

## 3 — Acquisition's tabs at a finger's size (steward, 2026-09-26; phase 8, STOP D)

**The STOP.** R206's « every target meets the touch minimum » hold fell on `main` for a reason the design did not
measure: the existing tabs are 99×34 px and the « ⋮ » 40×40 px, and `segmentTab` is shared with the library's lens
segment. No written directive names a touch floor; the harness holds 44 px locally (`add_footer.py`).

**Ruled (proposal A).** Acquisition's bar alone is lifted — its four tabs and its « ⋮ » at 44 px — inside the states
phase 8 already declares on `acquisition/tabs`; the library's segment does not move. B (hold at 34 px) would prove
nothing; C (the shared primitive) crosses the phase's declaration. One register row files the library segment at
34 px (B-552, owner none). Carried out as two floors in Acquisition's own catalogue (`fingerTab`, `fingerMore`,
worn beside the primitives) because `ui/variants/controls.ts` stands at 397 of its 400 lines.

## 4 — the light theme's contrast ratchet does not rise (auditor, 2026-09-26 20:0x; phase 8 gate)

**The STOP.** Phase 8's `--a11y` read the light-theme ratchet at 234 against its ceiling of 147: phases 5 to 7 had
drawn more cards and not run the tier (a cadence fault, said in the RESUME), adding 93 findings — 61 `waiting`-tone
rung chips, 32 plain card feet — every one an instance of a pair already in the ledger.

**Ruled.** A: a `waiting` rung's chip takes `neutral`. B (raising the ceiling) REFUSED: this ratchet may fall and may not
rise. The feet are repaired at the card-foot variant with an existing token that passes on light (`text-primary-text`),
which lowers the feet already counted too; the ledger is re-taken at the value read (98). A repair only a
`theme.css` token could make would have been a STOP to the steward. From here to the pull request, `--a11y` runs on
every phase gate that draws.

## 5 — the tunnel-error card is a derivation from Top Chef's real row (steward, 2026-09-26; phase 9, STOP D)

**The STOP.** The « tunnel error » section of « À traiter » has no real row: the ten real runs hold no errored step
(`pipeline-runs.json`, `errorCount` summed → 0).

**Ruled (proposal a).** « Top Chef Le Concours Parallèle (2026) » is the tunnel-error card — a DERIVATION from its real
stuck row, shown as one: its reason is a step that cannot finish (no episode data, the files cannot be named), and no
pending decision names it. The seed carries the step it stopped at; the layer files a stuck row that carries one and that
no pending decision names under the tunnel error; its reason is drawn in full as the seed words it; its feet are
« Relancer » and, from phase 11, « Abandonner ». Guard: it never reads as resolvable by an identity pick — no « Résoudre »
foot. (b), a section drawn on nothing, refused (§ 13).
