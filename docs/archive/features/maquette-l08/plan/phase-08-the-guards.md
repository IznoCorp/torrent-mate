# Phase 8 — The guards, and R85

## Scope

- `scripts/check-mock-seeds.py` — five arms: `classification`, `correspondence`, `lossless`,
  `handlers`, `provenance`.
- A `mocks` arm in `scripts/check-frontend-boundaries.py`.
- `frontend/maquette/harness/mocks.py` — R85.
- Both wired: the guard into `make check` and into `run.sh`'s repository-guard tier; R85 into the
  full suite. **R85 is NOT in `--contracts`** — that tier is « a NAME moved without all of its
  ends », and determinism is not that question.

## What each arm reads, and what it does not

The design's § 3 is the specification. Each arm answers one line of it, and the answer to « what
does it not read? » is written in the guard's own docstring rather than left to a reader to
reconstruct.

**Every arm holds a NAMED INVENTORY, not a count.** `--list` prints what it holds; the register is
that list; both directions are checked. A floor placed at today's number is satisfied by
construction on the day it is written, which is B-075's shape and this wave will not repeat it.

## The mutations, and each names its expected message

Five arms, one boundary arm, one rule — seven mutations, each seen RED before the fix is restored,
and each checked for naming the right defect rather than merely failing:

| mutation | must name |
| --- | --- |
| add a fixture family to `legacy.js` | that family, as unclassified |
| remove a family from the register | that family, as missing from the register |
| change one value in a committed seed | the family, the path, and both values |
| remove a key from a declared mapping | the key and its family |
| put a data literal in a handler | the file and the line |
| add a seed with no source family | the seed file |
| import a seed from a feature | the forbidden edge, both ends |
| make a handler return a fresh object per call | the operation, in R85's determinism hold |

**Commit before mutating.** The restore is then a `git checkout` of a known-good tree rather than
a re-edit — the discipline this repository already records, and the reason it exists is that a
re-edit can restore something subtly different.

## The CI-collectability rule

Any test this phase adds must be collectable without a browser (B-077). No module-level Playwright
import; the browser import goes inside the function that needs it.

## Done when

- ACC-13 through ACC-19 all green, each with its mutation seen red and naming the right defect.
- `run.sh --contracts` carries the new guard; the full suite carries R85.
- `python3 scripts/harness-hold-counts.py` records R85's baseline.
