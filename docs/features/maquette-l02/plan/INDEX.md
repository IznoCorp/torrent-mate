# L02 — implementation plan

Design: `docs/features/maquette-l02/DESIGN.md`
Lot: `docs/reference/frontend-architecture.md` § Phase 0 → L02 · `depends on L01`, satisfied by #467

## Why the phases are in this order

The lot's whole argument is attribution: when a rule falls at L07, the failure must have **one**
possible cause. So the anchors move before the visual language, and inside the lot the same
discipline repeats one tier down — the instrument that judges the migration is built before
anything is migrated.

**Phase 1 builds the judge and nothing else.** The vocabulary, the guard arm, the independent
classifier, the baseline holding all 342 live violations, and the wiring that makes the dormant
`oracle.py --contracts` arm run automatically. It migrates zero calls on purpose: a guard written
after its wave has nothing left to fail on, and was therefore never seen fail. This one lands with
342 things it holds and a mutation proof that it names them.

Phase 1 also carries **ACC-06 before the arm that depends on it**. The `|| undefined` arm rests on
a belief about how React renders `data-open={false}`. The DESIGN refuses to let a belief be
load-bearing, so `harness/attrs.py` demonstrates the behaviour in the live document _first_; if the
demonstration contradicts the belief, the arm is written differently. An arm written first and
demonstrated second is an arm that encodes whatever its author assumed.

**Phases 2 to 6 are cut by DOM concept, never by file kind.** A `data-part` contract has three ends
— the markup that emits it, the harness selection that reads it, and the baseline entry that
tolerates its absence — and a concept's markup routinely sits on both sides of the engine boundary
(34 of the 114 tokens are emitted by `legacy.js` **and** by a component). Cutting by file would
split one contract across two commits and leave the half-moved state this lot exists to make
impossible.

**Phase 2 is second because it is the riskiest and the most instructive.** `.screen` heads 30 of
the 281 selections, `open` accounts for 54 of the 61 state assertions, and the migration carries a
semantic correction: `open` in `.screen.open` is static — five screens write it into a literal,
because a mounted screen _is_ open — while `sheet.tsx` alone makes it conditional. Dropping a
redundant state token from 30 selectors is exactly the edit that can leave a rule green while it
matches more than it did. That is why the unchanged-hold-count proof (ACC-08) is claimed here
rather than at the end, where a drift would already be indistinguishable from the sum of six waves.

Phases 3, 4 and 5 then descend the tail in decreasing cluster size — the card family, the list and
episode surfaces, the filter and setting rows — each self-contained, each removing its own entries
from the baseline in the same commit as the migration they correspond to. **Phase 6 takes the
remaining 128 selections and 3 assertions, empties the baseline, deletes it, and turns the arm's
floor into a hard zero in code.** The file is removed rather than left empty, because a file that
happens to be empty is a floor someone can raise again.

| #   | Phase                                                             | File                                    | Status |
| --- | ----------------------------------------------------------------- | --------------------------------------- | ------ |
| 1   | Vocabulary, the guard arm, the baseline, the dormant arm, the VALUE arm, hold counts | `phase-01-vocabulary-and-guard.md` | [ ]    |
| 2   | `.screen` / `.sheet` / `.scrim`, and the static-`open` correction | `phase-02-screen-sheet-scrim.md`        | [ ]    |
| 3   | `.card` and its parts                                             | `phase-03-card-and-parts.md`            | [ ]    |
| 4   | `.reslist`, `.sugwrap`, `.ep`, `.eppop`                           | `phase-04-lists-and-episodes.md`        | [ ]    |
| 5   | Filters and settings                                              | `phase-05-filters-and-settings.md`      | [ ]    |
| 6   | The tail, then the baseline is emptied and deleted                | `phase-06-tail-and-baseline-removal.md` | [ ]    |

### Phase 1 runs long on purpose

It is 204 lines against the plan convention's indicative 150, and it is not split. Two of its seven
sub-phases were added after the first draft, when reading the guards showed that ACC-12 and ACC-08
could not be run at all as the DESIGN first wrote them — 1.6 makes something read a `data-part`
VALUE, 1.7 captures the per-rule hold counts `run.sh` discards. **Phases 2 to 6 all gate on the whole
instrument existing**, so splitting it would create a seventh phase that no phase table in the
DESIGN declares, to satisfy a line count that exists to protect a context window 204 lines do not
threaten.

## The ACCEPTANCE map

Every criterion is claimed by exactly one phase — the phase where it is **decisive**, not merely
runnable. ACC-07 (the oracle) and ACC-08 (the 51-rule suite) are _executed at every phase gate_ as
standing proofs; the table says where each is formally claimed and recorded with its actual output.

| ACC    | What it proves                                              | Phase | Why that phase                                                                          |
| ------ | ----------------------------------------------------------- | ----- | --------------------------------------------------------------------------------------- |
| ACC-01 | zero class-anchored selection calls remain                  | 6     | only true once the tail has moved                                                       |
| ACC-02 | the independent classifier agrees, at total 687             | 6     | `class 0` is a final state                                                              |
| ACC-03 | the guard FALLS on a re-introduced class anchor             | 3     | its mutation needs `[data-part="card/title"]` in `cards.py`, created here               |
| ACC-04 | the guard FALLS on a half-moved contract                    | 4     | it needs a SINGLE-emitter target: `.reslist` → `data-part="result-list"`, created here  |
| ACC-05 | the guard FALLS on `data-open={x}` without `\|\| undefined` | 2     | `sheet.tsx` has no `data-open` today; phase 2 writes the first one                      |
| ACC-06 | the React trap is demonstrated in the browser               | 1     | the `\|\| undefined` arm rests on it, so it runs before that arm is written             |
| ACC-07 | the oracle is green: the wave moved no pixel                | 6     | claimed over the whole wave; re-run at every gate                                       |
| ACC-08 | the suite is green at UNCHANGED per-rule hold counts        | 2     | the static-`open` correction is where a hold count can silently drift; its tool is 1.7  |
| ACC-09 | the dormant `--contracts` arm now runs automatically        | 1     | the wiring lands here                                                                   |
| ACC-10 | the baseline is empty and gone                              | 6     | the closing act of the lot                                                              |
| ACC-11 | the five genre assertions survive, each with its reason     | 4     | `ep` moves as a selection while `classList.contains('ep')` stays — the split bites here |
| ACC-12 | no French entered the vocabulary, and something READS it    | 5     | the phase coining the most new names (`fr`, `fn`, `fk`, `fs`); its VALUE arm is 1.6     |
| ACC-13 | the whole gate                                              | 6     | final state                                                                             |

## Verified before planning, not assumed

Facts taken from the DESIGN are cited as such. Everything else was re-derived here by running the
command named beside it, on `f7e8073` (branch `refactor/maquette-l02`).

- **The 66 assertions and their 61/5 split reproduce exactly.** A counter over
  `classList.contains\(['"]([\w-]+)['"]\)` across `frontend/maquette/harness/*.py` returns 66 total:
  `open` 54, `noposter` 2, and one each of `show`, `in_library`, `fempty`, `fblocked`, `announced`
  (= 61 state), plus one each of `h2`, `flux`, `ep`, `radio`, `note` (= 5 genre). The DESIGN's
  disposition table is confirmed member by member, not just in total.
- **The total is 687, not 684, and `class 281` is untouched.** D4 and this lot's first pass both
  read only QUOTED selectors; three template-literal ones (`cards.py:82` and two more) were invisible
  to both, and all three are `data-*`-anchored. An exact agreement at 684 was two readers sharing one
  blind spot. A naive
  classifier — "any `.token` outside `[…]` makes the selector class-anchored" — returns 687 calls
  and 428 class anchors over the same corpus. The gap is the anchor-precedence rule, and it is the
  reason `scripts/classify-rule-anchors.py` is a phase-1 deliverable rather than a one-off script:
  the method has to be pinned in a file before any number derived from it means anything.
- **The three emission sites exist and hold the counts the DESIGN gives.** `wc -l` reports
  `frontend/maquette/design/index.html` at 374 lines, and `find … -not -path '*/engine/*'` returns
  **23** non-engine sources under `design/src`.
- **`scripts/check-markup-contracts.py` is 149 lines carrying one arm; `frontend/maquette/oracle.py`
  is 972** against the 1000-line hard ceiling (`wc -l`). The DESIGN's three reasons for putting the
  new arm in the smaller file hold as stated.
- **It is already in both gates.** `python3 scripts/check-markup-contracts.py` appears in the
  `Makefile` check target and in `.github/workflows/ci.yml`.
- **`oracle.py` runs nowhere but by hand.** `run.sh:140` invokes it as `--check` only; `--contracts`
  appears in no Makefile, workflow or script (`rg -n 'oracle\.py' -g '*.sh' -g '*.yml' Makefile`).
- **None of the three new artifacts exists yet**: `frontend/maquette/anchor-baseline.json`,
  `scripts/classify-rule-anchors.py`, `frontend/maquette/harness/attrs.py` — all `ls` → _No such
  file or directory_.
- **`sheet.tsx` carries no `data-open` today.** It writes `className={"sheet" + (open ? " open" :
"")}`. ACC-05's mutation target is therefore _created by phase 2_, which is why ACC-05 cannot be
  claimed by phase 1.
- **The five static-`open` sites are at the exact lines the DESIGN names**: `add.tsx:155`,
  `media.tsx:385`, `profile.tsx:85`, `releases.tsx:48`, `resolution.tsx:316`, each
  `className="screen open"`. The two conditional sites are `sheet.tsx:84` (the scrim) and
  `sheet.tsx:95` (the sheet).
- **The suite counts 50 rules by globbing, and `attrs.py` will make it 51.** `run.sh` collects
  `harness/*.py` minus `common.py` (51 files on disk today → 50 rules) and prints
  `harness: ${#scripts[@]} rule(s), no violation.` ACC-08's expected text says `50 rule(s)`; adding
  a browser rule to that directory raises it to 51. **Phase 1 records what the command actually
  printed**, per the DESIGN's own instruction that a criterion is filled in with its real output.
- **Adding a rule file does not disturb the two audit rules.** `EXPECTED_RULES = 13` in `audit.py`
  and `audit2.py` counts their own internal checks (`R11`, …), not the number of files in the
  directory (`rg -n 'EXPECTED_RULES'`).
