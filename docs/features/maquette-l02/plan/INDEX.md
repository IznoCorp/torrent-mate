# L02 — implementation plan

Design: `docs/features/maquette-l02/DESIGN.md`
Lot: `docs/reference/frontend-architecture.md` § Phase 0 → L02 · `depends on L01`, satisfied by #467

## Why the phases are in this order

The lot's whole argument is attribution: when a rule falls at L07, the failure must have **one**
possible cause. So the anchors move before the visual language, and inside the lot the same
discipline repeats one tier down — the instrument that judges the migration is built before
anything is migrated.

**Phase 1 builds the judge and nothing else.** The vocabulary, the guard arm, the independent
classifier, the baseline holding all 834 live violations, and the wiring that makes the dormant
`oracle.py --contracts` arm run automatically. It migrates zero calls on purpose: a guard written
after its wave has nothing left to fail on, and was therefore never seen fail. This one lands with
834 things it holds and a mutation proof that it names them.

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
the 432 class-carrying selections, `open` accounts for 54 of the 61 state assertions, and the migration carries a
semantic correction: `open` in `.screen.open` is static — five screens write it into a literal,
because a mounted screen _is_ open — while `sheet.tsx` alone makes it conditional. Dropping a
redundant state token from 30 selectors is exactly the edit that can leave a rule green while it
matches more than it did. That is why the unchanged-hold-count proof (ACC-08) is claimed here
rather than at the end, where a drift would already be indistinguishable from the sum of six waves.

Phases 3, 4 and 5 then descend the tail in decreasing cluster size — the card family, the list and
episode surfaces, the filter and setting rows — each self-contained, each removing its own entries
from the baseline in the same commit as the migration they correspond to. **Phase 6 takes the
remaining 365 token occurrences and 3 assertions, empties the baseline, deletes it, and turns the arm's
floor into a hard zero in code.** The file is removed rather than left empty, because a file that
happens to be empty is a floor someone can raise again.

| #   | Phase                                                             | File                                    | Status |
| --- | ----------------------------------------------------------------- | --------------------------------------- | ------ |
| 1   | Vocabulary, the guard arm, the baseline, the dormant arm, the VALUE arm, hold counts | `phase-01-vocabulary-and-guard.md` | [x]    |
| 2   | `.screen` / `.sheet` / `.scrim`, and `data-open` on five layers         | `phase-02-screen-sheet-scrim.md`        | [x]    |
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

## What phase 1 found, and what it cost the plan

Phase 1 built the instrument and migrated nothing, and the instrument found eight things before
a single anchor moved. Each is measured, each changed the plan, and three of them were this
lot's own defects.

1. **D4's method under-measures D4's objective by 54 %.** The classifier sorts each selector
   into one bucket — its strongest anchor — and so does D4: 280+276+92+32+4 = 684, one bucket
   per call. `#view .swipe` counts as id-anchored and the `.swipe` leaves the measurement. It
   still dies at L07. Measured over every token rather than the strongest: **432** selectors
   carry a class, not 281; **151** hide it behind a `data-*` or an id. The operator ruled the
   full scope in. The unit of work became the class TOKEN OCCURRENCE — a selector can owe work
   to two phases and only the occurrence has one owner — and the baseline became **694**.
2. **The total was 687, not 684, and two readers agreed on the wrong number.** D4 and the first
   pass of this lot both read only QUOTED selectors; three pass theirs as template literals.
   All three are `data-*`-anchored, so `class 281` never moved — but an exact agreement was two
   blind spots coinciding, and it is why the classifier is a file under review, not a regex.
3. **The wave's own rule added a class anchor.** `attrs.py`, written in 1.2 to demonstrate the
   React trap, selected `.segmini button`. The classifier read 282 against 281 and the dispatch
   refused to adjust the tool to agree. The rule now anchors on `[aria-pressed]` — what it
   measures — and that is the two-readers argument won on its first day.
4. **The ratchet could be defeated in three commands.** A new violation was refused, then
   absorbed by `--write-baseline`, and the guard's own failure message handed over the bypass.
   Phases 2 to 6 shift line numbers in every commit and would have regenerated each time, so the
   ratchet would have been inert for the whole wave. Regeneration now refuses additions;
   identity dropped the line number, then the selector string (a prefix rewrite made an unmoved
   leaf look new); `--allow-additions` exists, is loud, and is banned from phases 2 to 6.
5. **React behaves as believed — measured, not quoted.** A boolean `false` renders the STRING
   `"false"`, present, and `[aria-pressed]` matches it; `undefined` is omitted. The
   `|| undefined` arm rests on a measurement now. The subject had to be found: React is not on
   `window` and no `data-*` boolean existed yet, so the proof ran on `aria-pressed` and a `title`,
   and 2.2 owes the same four holds against the real `data-open`.
6. **Two criteria could not run, and one read nothing.** ACC-08 named `run.sh`, which prints a
   passing rule's output nowhere — `harness-hold-counts.py` captures it now, and says plainly
   that **39 of 51** rules report a count (985 holds) while 12 print a prose verdict and are
   compared on exit status alone. ACC-12 exited 0 over values nothing read — `check_data_attributes` now reads the
   VALUES of the naming attributes (20 today), and left `data-go="profil"` alone.
   `oracle.py --contracts`, which already held half of D4, ran nowhere; it runs in `make check`
   and CI in 0.158 s.
7. **Two breaks were reported pre-existing and were the wave's.** An argv-reading `main()` broke
   an in-process test; a test left unformatted broke `make lint`. Both passed at `226e71fb` and
   failed at the report — the comparison point had been the dispatch's own previous commit.
   « Pre-existing » is a claim about a date, and the date is the branch point.
   And five reports claimed `check-module-size.py → exit 0` on the guard while it stood at
   1275 non-blank lines: they ran the tool without `--root scripts`, so its default root never
   read the file. `make check` runs it with the flag and stopped the gate on it. A gate proves
   what it READS — and the gate list a dispatch is handed must name the exact command the
   Makefile runs, flags included.
8. **A second blind spot, found by dry-running phase 2 on a scratch copy.** Both readers extract a
   selector only as the literal argument of a selection call; the harness also HOLDS selectors in
   variables and in tables a helper walks (`screen_port = ".screen.open .port"`, the state tables
   of `audit2.py`). Measured: 113 selector-shaped strings outside any call, 146 class token
   occurrences before a RULE filtered the false positives (`.json5`, `.torrentmate`): emitted by a
   design site, or carrying selector structure. **140 entered the instrument** before any
   migration, tagged `held` apart from `call`, through the one sanctioned use of
   `--allow-additions` — a re-classification of what the instrument reads, once. The baseline is
   **834**, and the burn-down was recalibrated a third time: 201 / 143 / 46 / 76 / 368.

Carried, not hidden: `host.tsx:142` renders `data-region={region}` from a table — six region
names reach the DOM through a value no arm reads; `content.py` is a SECOND live-data rule
`run.sh`'s header does not name; six `#screen.classList.contains('open')` assertions are
vestiges of an engine path nothing calls, and move in 2.3 still reading false.

## What phase 2 found, and what it cost the plan

Phase 2 moved the first contract — 138 entries, 834 → 696, every tripwire on its number, three oracles
green — and the first contract rewrote the phase three times before a line of it landed. Each rewrite is measured, and the sequence is kept because the sequence is the
lesson.

1. **`.screen.open` was read three ways, and only the third was checked against what runs.** The
   first draft called `open` static and redundant; a correction made the mount node a mere
   `screen-host`; a second correction made `open` the token telling the engine's `#screen` apart
   from React's sections. Then `openScreen()` turned out to have no caller — republished on
   `window`, named by two past-tense comments, invoked by no rule and no state. The engine-screen
   path is dead, `#screen` never opens, and the six `#screen.classList.contains('open')`
   assertions read false for good. The target stayed `[data-part="screen"][data-open]` for a plainer
   reason: the attribute mirrors the class, on the sections because `open` is there and on `#screen`
   through the same helper that would set it — so the day the path wakes, the contract already holds.
2. **Every `.screen.open` carries two tokens, and the burn-down counted one.** Rewriting the prefix
   removes `.screen` AND `.open`; the per-phase model had put 72 `.open` in the tail. Phase 2 grew
   from 117 to 189, then to 201 when the held selectors were counted.
3. **A dry run on a scratch copy found the second blind spot.** Rewriting the 63 baselined lines left
   24 `.screen.open` behind — 17 comments, and 5 live selectors held in variables and tables that no
   reader had counted. That became phase 1's last instrument change (140 held occurrences, 834
   entries) before this phase's first commit.
4. **The engine IS touched, at 14 sites.** The draft said it was not; it toggles `open` on four
   layers, and the 54 assertions read five. A `setOpen(element, on)` helper routes all 14 so the
   attribute cannot drift from the class it mirrors; `#scrim` keeps its two writers, React and the
   engine, exactly as the class already did.
5. **`rename-identifiers.py` is struck for selectors**, by its own header — a selector is a STRING
   it « NEVER » renames, and `--values` is the mode whose read-back proof is skipped. A literal prefix
   rewrite on baseline-listed lines, asserting its counts and judged by three oracles outside itself,
   replaced it.
6. **The DeepSeek provider ran out of credit** between phases; the operator authorised an Opus
   escalation, same prompts, same guarantor. Every dispatch of this phase ran on Opus.
7. **The third arm read raw text, and an escaped quote hid a selection from it.** Ten of 2.1's 63
   `data-part` selections sat in single-line double-quoted Python strings as `[data-part=\"screen\"]`,
   and the selection ⇒ emission arm counted 55 — one end of eight contracts unwatched, with nothing
   refusing the shape. The arm now REFUSES the line, with the one-sentence fix, proved by a mutation
   the unfixed guard let through at 62 of 63 with exit 0 — a decoder was not the answer, because
   nothing in the instrument decodes a literal and a first decoder would still skip a call whose own
   quotes are escaped. The same fix named the hole it left: the third arm read a `data-part`
   selection only as a call argument. It gained the anchor arm's held pass and went from 65 to
   **74 checked, 9 of them held** — the brief had said 63 and 5, both read from a commit message
   rather than from a run, and the dispatch reported the tripwires instead of bending to them. Among
   the nine are three hold MESSAGES in `attrs.py` that quote a selector; they count, by ruling: a
   message that names what was selected lies the day the value moves, and excluding it would need a
   prose-or-selector heuristic, which is the half-reading this guard refuses everywhere else.
8. **The fourth arm became load-bearing in 2.2, measured.** `attrs.py` gained four holds on the
   real `data-open` — absent on the closed sheet, present on the open one, `[data-part="sheet"]
   [data-open]` selecting 0 then 1 — closing the gap phase 1 had written into its docstring. The
   guard's state arm went from `0 state attribute(s) checked` to 2, and ACC-05 fell naming
   `sheet.tsx:85`. The hold-count baseline moved once, deliberately: `attrs.py` 4 → 8, nothing else.
9. **2.3 moved 54 assertions and 9 id-head selectors in one line-targeted pass** — 59 lines removed,
   59 added, each added line its removed line with only the shape substituted, checked pairwise by
   an oracle outside the tool (`mismatches 0`). Every variable the assertions read through (`s`,
   `sh`, `sc`, `g`, `sheet`, `sel`) was resolved to a layer that emits `data-open` before it moved.
   The mutation chose a POSITIVE assertion (`selection.py:42`, « the sheet IS open ») over
   `logout.py`'s negative one, which would have stayed green under the mutation and proved nothing.

Carried: three assertions in `audit2.py:160-167` and `audit.py:208` became tautological when 2.1 put
`[data-open]` in the very selector they then test for `data-open` — introduced by the rewrite, not
by 2.3, harmless on the close path (`?.` yields `undefined`), and a line for a later tidy-up; `#scrim`'s double writer (React and engine) is the strangler state, mirrored and not
resolved; the six vestigial `#screen` assertions are a later tidy-up.

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
