# L03 — implementation plan

Design: `docs/features/maquette-l03/DESIGN.md`
Lot: `docs/reference/frontend-architecture.md` § Phase 1 → L03 · `IN PROGRESS` · *depends on L01*
<sub>« Phase 1 » there groups LOTS. The phases numbered below are this plan's own — same word, two scales.</sub>
Branch: `feat/maquette-l03` · version 0.98.18 · squash merge, pressed manually

## Why the phases are in this order

**Phase 1 exists because an instrument comes before the change it measures.** That is L01's lesson
applied to its own successor: a violation count taken before the work is a fact, the same count
taken after is an opinion. Phase 1 also repairs the two instruments this wave's proofs depend on
before it leans on them.

**Phases 2 → 3 → 4 → 5 follow the DOM.** Landmarks fix the tree; names are read off that tree;
focus order and trapping walk it; live regions announce changes inside it. Each inversion of that
order costs rework: naming a region before it exists, or trapping focus in a subtree whose
boundary has not been decided.

**Phase 6 is not a formality.** The floor only bites once it is hard, and a rule nobody has seen red
proves only that it agrees with the code.

## Phases

| # | Phase | File | Status |
| --- | --- | --- | --- |
| 1 | The instrument, and the debt recorded | phase-01-instrument-and-debt.md | [x] |
| 2 | Landmarks and structure | phase-02-landmarks-and-structure.md | [x] |
| 3 | Accessible names | phase-03-accessible-names.md | [x] |
| 4 | Focus manager and keyboard paths | phase-04-focus-and-keyboard.md | [x] |
| 5 | Live regions and states | phase-05-live-regions.md | [x] |
| 6 | The floor bites | phase-06-the-floor-bites.md | [x] |

## ACCEPTANCE criteria

Every criterion is an executable command with a documented expected output — prose criteria are
invalid (`docs/reference/feature-lifecycle.md`). They are re-exercised in full before the squash
merge.

| ID | Phase | Criterion |
| --- | --- | --- |
| ACC-01 | 1 | `frontend/maquette/harness/run.sh --a11y` exits 0 and prints one line per state |
| ACC-02 | 1 | `python3 frontend/maquette/a11y.py --record` writes `a11y-debt.json`, and the file names a violation count per state and per axe rule |
| ACC-03 | 1 | `git merge-base --is-ancestor "$(python3 -c 'import json;print(json.load(open("frontend/maquette/hold-counts-baseline.json"))["taken_at_commit"])')" HEAD` exits 0 |
| ACC-04 | 1 | `python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json --only logout` refuses a baseline whose commit is not an ancestor of HEAD, naming it |
| ACC-05 | 1 | `grep -c '83 states' Makefile` returns 1 and `grep -c '82 states' Makefile` returns 0 |
| ACC-19 | 1 | `python3 scripts/refresh-maquette-fixture.py --check` exits 0 |
| ACC-06 | 2 | `grep -rEc '<main([ >/]\|$)' frontend/maquette/design/index.html` returns 1 |
| ACC-07 | 2 | `python3 frontend/maquette/oracle.py --check` reports 0 divergence |
| ACC-08 | 3 | `python3 frontend/maquette/a11y.py --check --rules button-name,link-name,image-alt,label` reports 0 violations over 83 states |
| ACC-09 | 3 | `python3 scripts/check-no-french.py` exits 0 |
| ACC-10 | 4 | The focus rule reports, for every layer that opens: focus moved inside, background inert, focus restored to the trigger on close — 0 failures |
| ACC-11 | 4 | `Escape` closes the top layer in every layered state; the rule reports 0 failures |
| ACC-12 | 5 | `python3 frontend/maquette/a11y.py --check --rules aria-valid-attr-value,aria-required-attr,region` reports 0 violations |
| ACC-13 | 6 | `frontend/maquette/harness/run.sh --a11y` reports **0 violations** over 83 states, `color-contrast` excepted |
| ACC-14 | 6 | `python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json` reports no changed count |
| ACC-15 | 6 | `python3 frontend/maquette/oracle.py --check` reports 0 divergence |
| ACC-16 | 6 | The mutation record shows the a11y rule and the focus rule each seen RED on a deliberate break, each naming the right defect, then restored |
| ACC-17 | 6 | `make check` exits 0 |
| ACC-18 | 6 | `a11y-contrast.json` records the contrast findings and `docs/reference/frontend-architecture.md` § L06 cites it |

## What this plan does NOT do

Named so that « not done » is on the record rather than an oversight (DESIGN § 6): touch-target
sizing and colour-contrast remediation both go to L06; B-036 waits for a wave of its own;
engine-drawn surfaces are not converted to components — L03 places attributes in the engine, it
does not migrate it.
