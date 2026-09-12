# L20 — The global levers and the history · PLAN

Design: `docs/features/maquette-l20/DESIGN.md`. Contract:
`docs/reference/frontend-architecture.md` § 4, entry `#### L20 — The global levers and the history`.

---

## THE PHASES CHAIN. THEY DO NOT PAUSE.

**The operator arbitrates the SCOPE, never the cadence.** A phase that finishes goes straight into
the next one. Stopping to announce « phase N done » is the failure mode L12, L14, L19 and L21 each
wrote this paragraph to prevent, and the reason it is written HERE rather than in the chat is that
the chat gets compacted and this file does not.

**Self-check, at the end of every phase, before anything else:** « Am I about to report instead of
continuing? » If the answer is yes and the next phase exists, and none of the two STOPs below is the
reason, **continue**. The only permitted halts are:

- **STOP A** — the oracle diverging on a state this wave did not touch.
- **STOP B** — the pull request.

**There is no STOP for the levers' placement.** It was the lot's one open question and the operator
ruled it on 2026-09-12 (« Q1: B »), before this plan was written; DESIGN § 1 carries the ruling and
the reading that was refused. Anything else believed necessary outside the contract: STOP and ask
the steward first.

---

## The rule that governs every phase

**Rule first, seen RED against `main`, then the move, then the same rule green with its holds
counted.** Here the red is the strongest form this repository asks for and it needs no mutation:
**none of these surfaces exists on `main`**, so every hold fails there for the reason it was
written. Each phase says so explicitly, and the report records the red reading per rule.

Where a phase repairs something that DOES exist on `main` — phase 8's `data-pipe` — the rule is red
against the engine's own branch with no mutation either, and the mutation test comes after the move:
break it on purpose, confirm the rule falls and NAMES the right defect, restore.

**Commit BEFORE every mutation**, and mutate with `scripts/mutate.sh <file> <expression> <rule…>` —
by hand leaves the served copy of the PREVIOUS build in place (B-303). It cannot judge a GUARD
(B-273): a guard's exit code is read by hand.

**The numbers R-L20-a…j are LABELS, not rule numbers.** `R160` is the highest in the suite on this
branch (`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1`); R161–R164
are on #585's branch and the settings micro-wave takes R165+. **Phase 1 re-takes that command
against `origin/main` at the moment it runs and binds every label to a number then**, writing the
mapping into the report. A number chosen from this file without re-measuring is a collision.

**Every heavy run is wrapped.** The shared lock for anything touching the one served copy or the
8899 host:

    HEAVY_FREE_FLOOR_MB=2560 TM_HARNESS_JOBS=2 sh scripts/heavy.sh l20 <command>

The wave's OWN lock for everything else heavy (`npm ci`, `npm run build`, `make check`, `pytest`, a
`git push`):

    HEAVY_LOCK=/private/tmp/tm-heavy-l20/holder HEAVY_FREE_FLOOR_MB=2560 \
      PYTEST_XDIST_AUTO_NUM_WORKERS=3 sh scripts/heavy.sh l20 <command>

A run holding the SHARED lock is announced to the steward in one line before it starts and one after
(« done, exit N »). Never a build beside a parallel run of your own. Output to a FILE, exit code read
in the same tool call, **never `| tail -N` on a long gate**. Kill what you start, prove it with `ps`.

**The engine only SHRINKS.** No line is added to `legacy.js`. Phase 8 subtracts and re-records
`scripts/frontend_size_ledger.py` DOWNWARD in the same commit.

**Never `cd` into `frontend/maquette/design/src`** (B-384) — absolute paths from the worktree root.

**Documents are added BY FILE**: `git add -f docs/features/maquette-l20/<name>.md`, never the folder
(B-304 — `git add -f` on a path swept `node_modules` into a commit).

---

## Phases

| #   | Phase | What it lands | Register |
| --- | --- | --- | --- |
| 1 | [The contract](phase-01-contract.md) | four operations declared, three re-shaped, the mocks that MOVE, the demands regenerated, the rule labels bound to numbers | — |
| 2 | [The named states leave the engine's ledger](phase-02-named-states.md) | `states/system.ts`; the engine's table SHRINKS and its record follows | B-306's arm |
| 3 | [The host, and the locks](phase-03-host-and-locks.md) | the « Pipeline » section of Système exists; the lock, the two sentinels and the sweep drawn | B-297 |
| 4 | [The levers](phase-04-levers.md) | pause · resume · the automatic trigger · the bound's path; DOIT-4 on a lever; §13's loading | DOIT-3, DOIT-4 |
| 5 | [« Relancer la veille »](phase-05-watch-now.md) | the veille's five states and DOIT-6's figures, from both emitters | DOIT-6, B-383 |
| 6 | [The history list](phase-06-history.md) | the rows become paths; empty, degraded, loading, error | DOIT-6 |
| 7 | [A run's detail, and its raw log folded](phase-07-run-detail.md) | the `/run/$runUid` screen, `ui/disclosure.tsx`, the log CLOSED by default | B-296 |
| 8 | [B-371 — the path a hand takes](phase-08-hand-path.md) | `data-pipe` onto the verb registry, the engine's branch subtracted, the pastille reachable | B-371 |
| 9 | [The close](phase-09-close.md) | the map, the register, the states counted, the report | all |

### The ordering, and its reason

**The contract is FIRST** because every surface below calls one of its operations and
`scripts/compare-contracts.py --check` refuses the three artefacts apart. It is also the phase that
produces the demands, which is what makes the divergences of DESIGN § 3.2 decisions rather than
discoveries.

**The named states leave the engine SECOND, and it is not housekeeping.** `engine/states.js` is
grandfathered at 786 non-blank lines and `scripts/check-frontend-boundaries.py` refuses the count
going UP (B-306). This lot declares 26 states; **even two would be refused there.** Every phase
after this one adds its ids to a file with no ceiling, so the block is met once instead of seven
times. Phase 2 carries the measurement and the alternative it refused.

**The host is a phase of its own** because it was the ruling's only subject (DESIGN § 1): cut by
surface, the ruling would have touched four phases.

**The locks come BEFORE the levers** because the locks are a READ-ONLY surface and the levers' own
drawing reads them. Drawing the read first means the levers phase adds only ACTS, which is « one kind
of change per phase » held rather than recited — and it means R-L20-g's agreement half has something
to disagree with.

**The veille comes after the levers** because it lands in the levers' own section and registers its
verb through the machinery phase 4 puts there.

**The list comes before the detail** because a row's path needs a list to leave from.

**The detail carries the disclosure primitive** because it is its only consumer in this lot; a
primitive with no consumer is a primitive no rule can hold.

**B-371 is LATE, and that is deliberate.** It is the lot's one engine subtraction and the one phase
that moves an existing named state's precondition (`arr-queued`). Landing it early would put that
oracle divergence before the surfaces that explain it, and would make every later phase's oracle
reading harder to attribute.

**The close is last** and re-reads the map and the register rather than trusting what the phases
claimed.

---

## Gates

**Per phase**: the shared-lock `run.sh --contracts` — the contract rules AND the repository's cheap
guards, the script prints how many of each — and the oracle, with divergences ONLY on the states
DESIGN § 7 names for that phase, each accepted with its written reason (D8). Every other state at
zero, or it is **STOP A**.

**Before merging**: the full suite (`frontend/maquette/harness/run.sh`, not the `--contracts` tier),
expected no failure; the `--a11y` tier at 0 over the 26 new states;
`scripts/harness-hold-counts.py --compare` with **`failed` read FIRST** (B-291 — the baseline is
NOT re-recorded while a rule is failing) and every movement written down; `make check` at zero
failures **and zero errors** (an ERROR means collection crashed and everything after it was
skipped); `python3 scripts/check-intent-map.py` and `python3 scripts/check-bug-register.py` read by
OUTPUT, not by exit code (B-346).

**The steward is told BEFORE a full-suite run.** The harness is one per machine — `served_copy.py`
is its lock and its stamp (B-256) — and a rule that falls while another session held it is re-run
alone before it is read, with the re-run's loss of load said in the same breath (B-277, B-307).

**The « In flight » row is written when the pull request opens** — pull request number first, then
the version; `scripts/check-implementation-state.py` holds the row by both.

---

## What this plan believes the CONTRACT gets wrong

Recorded here as § 7.1 asks, and written in full in DESIGN § 8. **No file outside
`docs/features/maquette-l20/` is edited for it** — the steward amends the plan.

1. **§ 8.1** — « relancer la veille (`POST /api/pipeline/watcher`) » names the directory watcher's
   on/off, which answers no figure. DOIT-6's veille is `POST /api/acquisition/detect`. Ruled by the
   steward on 2026-09-12: BOTH are L20's, and B-383's « Lancer la veille maintenant » half moves
   here.
2. **§ 8.2** — DOIT-6 is served by TWO operations; the clause map's row names one.
3. **§ 8.3** — the parallelism bound exists in NO configuration file. It is a demand, and phase 1
   files it.
4. **§ 8.4** — the named-state table cannot hold this lot's states, so phase 2 moves the Système
   surface's slice of it out of the engine. No lot owed that; this one takes it because it is the
   first that cannot proceed without it.

And one operation the contract's own clause map sends here that this lot DECLINES with its reason:
`GET /api/pipeline/stages`, the Flow Board's eight stations of current stock — a board showing THE
run is the surface §20 removed (DESIGN § 9). The steward decides whether the map's row moves or the
operation is written off as `config/validate` was.
