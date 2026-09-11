# L21 — The tunnel's verbs · PLAN

Design: `docs/features/maquette-l21/DESIGN.md`. Contract:
`docs/reference/frontend-architecture.md` § 4, entry `#### L21 — The tunnel's verbs`.

---

## THE PHASES CHAIN. THEY DO NOT PAUSE.

**The operator arbitrates the SCOPE, never the cadence.** A phase that finishes goes straight into
the next one. Stopping to announce « phase N done » is the failure mode L12, L14 and L19 each
wrote this paragraph to prevent, and the reason it is written HERE rather than in the chat is that
the chat gets compacted and this file does not.

**Self-check, at the end of every phase, before anything else:** « Am I about to report instead of
continuing? » If the answer is yes and the next phase exists, and none of the three STOPs below is
the reason, **continue**. The only permitted halts are:

- ~~**STOP A** — B-316's drawing decision.~~ **LIFTED 2026-09-06**: the operator chose
  reading (i) — a tap opens the media sheet, a long press opens the suggestion panel, reusing
  L14's gesture. B-315 (a), the button's size, was dictated in the same breath and is now this
  wave's. Both are written into phase 4; neither is a halt any more.
- **STOP B** — the oracle diverging on a state this wave did not touch.
- **STOP C** — the pull request.

Anything believed necessary outside the contract: STOP and ask the steward first.

---

## The rule that governs every phase

**Rule first, seen RED against the engine, then the move, then the same rule green with its count
unchanged.** L19 paid for the alternative on `data-take`: a repair held by nothing came back with
its sign turned round. Where the engine's branch still exists, the rule is red against it with no
mutation needed — the strongest form of « seen red first ». Where it does not, the rule is
mutation-tested at the moment it is written: break the behaviour on purpose, confirm it falls and
names the right defect, restore.

**Commit BEFORE every mutation**, and mutate with `scripts/mutate.sh <file> <expression> <rule…>`
— by hand leaves the served copy of the PREVIOUS build in place (B-303). It cannot judge a GUARD
(B-273): a guard's exit code is read by hand.

**Every heavy run is wrapped**: `TM_HARNESS_JOBS=2 sh scripts/heavy.sh l21 <command>`,
`PYTEST_XDIST_AUTO_NUM_WORKERS=3` for the test suite. Never a build beside a run. Kill what is
started, verify with `ps` — a sentence saying « stopped » is not a reading.

**The engine only SHRINKS.** No line is added to `legacy.js`. Every phase that subtracts
re-records `scripts/frontend_size_ledger.py` DOWNWARD in the same commit, from the base of 31 591.

**Documents are added BY FILE**: `git add -f docs/features/maquette-l21/<name>.md`, never the
folder (B-304 — `git add -f` on a path swept `node_modules` into a commit).

---

## Phases

| #   | Phase                                                                   | What it lands                                                      | Register     |
| --- | ----------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------ |
| 1   | [The contract](phase-01-contract.md)                                    | three operations declared, types generated, three demands recorded | —            |
| 2   | [« Récupérer cette saison »](phase-02-season-grab.md)                   | B-301's verb on the seasons panel                                  | B-301        |
| 3   | [The journey's two verbs](phase-03-journey-verbs.md)                    | « Remettre en file », « Re-scraper »                               | B-302        |
| 4   | [The five acts](phase-04-five-acts.md)                                  | follow · dropsug · sugmore · pause · remove leave the engine       | B-315, B-316 |
| 5   | [The release screen's take](phase-05-release-take.md)                   | `data-take`'s index half, one sentence, the 260 ms gone            | B-322, B-323 |
| 6   | [DOIT-4's pastille](phase-06-pastille.md)                               | the « En file » pastille of a MEDIUM, drawn                        | DOIT-4       |
| 7   | [The panel's doubled action, and the close](phase-07-b313-and-close.md) | B-313, B-247's list, the register, the report                      | B-313, B-247 |

**Ordering, and why it is this one.** The contract is first because every verb calls one of its
operations and `--check` refuses the three artefacts apart. The three verbs come before the five
acts because they are the lot's subject and the acts are what L19 carried here. The release take
is after the acts because it removes a `260` site and therefore touches `exits.py`'s inventory,
which is cheaper once. The pastille is late because its rule reads the acts under the busy
scenario, and those acts have to exist first. B-313 is last because it is one condition on a file
phase 4 has already opened, and because the close belongs with it.

---

## Gates

**Per phase**: `run.sh --contracts` (the contract rules AND the repository's cheap guards — the
script prints how many of each) and the oracle: divergences ONLY on the states this wave's verbs
and the pastille touch, each accepted with its reason (D8), every other state at zero.

**Before merging**: the full suite — `frontend/maquette/harness/run.sh`, not the `--contracts`
tier — **expected no failure** (the B-308 wave made that true; verified at the open); the `--a11y`
tier at 0; `scripts/harness-hold-counts.py --compare` with **`failed` read FIRST** (B-291) and
every movement written down; `make check` at zero failures and **zero errors** (an ERROR means
collection crashed and everything after it was skipped).

**The steward is told BEFORE a full-suite run.** The harness is one per machine
(`served_copy.py` is its lock and stamp); a rule that falls while another session held it is
re-run alone before it is read, and a re-run that removed the load the failure needed is said in
the same breath (B-277, B-307).

**The « In flight » row is written when the pull request opens** — pull request number first, then
the version; `scripts/check-implementation-state.py` holds the row by both.

---

## Departures from the brief, recorded as § 7.1 asks

**One, and it is a directive whose subject had gone.** The brief's § 4 ordered « `busy.py` is
yours to repair … R124 raises its panels THROUGH THE SEAM », on L19's report § 9. Measured on
`origin/main` `7fecb0258`: `grep -n "__panel.produce" frontend/maquette/harness/busy.py` answers
ONE hit and it is a COMMENT; both walks use `raise_by_finger`, defined at `:104` and called at
`:162` and `:210`; `git log -S raise_by_finger` names `9fa13da57` (L19's squash). **The repair
landed inside L19 itself.** L19's report § 6 row 16 records it; § 9 says it was left undone; § 9
is the stale half, written before that round.

**What replaces it** (steward's ruling, 2026-09-06 — depth, not scope: same rule, same class of
vacuity): phase 6 proves the existing repair still bites BY MUTATION before adding any hold, and
takes the residue the finger-driving did not cover — the action inside the raised panel is still
`act.click()` (`:172`, `:222`) and is not hit-tested, so a button covered on a busy page is
invisible to R124. No other scope is added.

**The brief's § 4 paragraph is corrected on this branch, in the same commit as this plan.** L19's
report is history and is NOT touched.
