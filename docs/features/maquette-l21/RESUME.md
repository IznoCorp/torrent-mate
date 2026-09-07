# L21 — where the wave stands, for whoever picks it up

Rewritten at 47 % context by the session that landed item 4 and phases 5 and 6-part-one.
Read `BRIEF.md`, `DESIGN.md` and `plan/INDEX.md` first — this file says only what is TRUE NOW and
what the plan does not.

**Branch** `feat/maquette-l21`, pull request **#572** (draft). **Version** 0.98.75 — re-read `main`
and bump again at the close if it has moved. `origin/main` at `163cbfcbb` IS MERGED into this
branch.

**HEAD is `131b7b51d`. The remote is at `a58c1e6e7`** — the last three commits (`e1b2a1838`,
`b0cb73555`, `131b7b51d`) are LOCAL ONLY and must be pushed. See § 6.1.

---

## 1. Done, with the reading that proves it

| Phase                               | State           | Proof                                                         |
| ----------------------------------- | --------------- | ------------------------------------------------------------- |
| 1 — the contract                    | **DONE**        | 3 operations + types + register                               |
| 2 — the season grab (B-301)         | **DONE**        | R125, 16 holds                                                |
| 3 — the journey's two verbs (B-302) | **DONE**        | R126, 16 holds                                                |
| 4 — the five acts                   | **DONE**        | the act grep reads 0                                          |
| **4b — B-315 (a)**                  | **DONE, READ**  | R136 red-then-green, § 2                                      |
| **5 — the release take**            | **DONE, READ**  | R137 + R123 + `exits.py`, § 3                                 |
| **6 — the pastille**                | **HALF DONE**   | R138 green + mutated; R124's three new holds NOT written, § 5 |
| 7 — B-313 + close                   | **not started** | —                                                             |

**Register**: B-315, B-322, B-323 read `fixed #572`. **B-363 filed** (`residue.py` cannot read a
factory built from a shared constant). Free in this block: **B-364…B-369**, **R139**.

**Readings on the current head**, all on the served copy after `run.sh --contracts` republished it:
`--contracts` 18 rules + 27 repository guards no violation · R136 6 holds · R137 5 holds · R138
7 holds · R123 9 holds (count unmoved) · `exits.py` 18 holds · R124 11 holds · `tsc` 0 · maquette
unit suite 107/107 (floors raised to 7 files / 107 tests) · the 27 cheap guards clean.

**The numbers that gate the wave**: `legacy.js` **31 467** non-blank, ledger recorded at 31 467
(from 31 484); `grep -cE "closest\.dataset\.(follow|pause|remove|dropsug|sugmore|take)\b"` reads
**0**; 106 rule files (103 at the wave base — R136, R137, R138 are the three added).

---

## 2. B-315 (a) — the button's size, and how the red was got for free

`.btnprimary` — the action-button system — gave « charger 30 de plus » the screen's own scale at
the foot of a spent pile. It is `loadFooterAction` now, beside the load footer's retry.

**R136 (`harness/load_more_scale.py`) writes NO pixel count.** A probe element wearing
`font-size: var(--text-N)` is laid out by the same engine that lays out the button, so it compares
the STEP. **Red first with no mutation**, on the served copy as it stood — wave-desktop-frame's
build of `28ed279db`, which predates both commits — with three violations naming this exact
subject: type 13 where the step resolves to 12, type equal to the SCREEN's step, padding 10 where
the footer's step resolves to 8.

⚠ **The 44 px trade goes to the operator at his Mac walk** and is written in DESIGN § 3.3d: the
footer scale carries no touch-target floor, so the box is about a third shorter. It clears the
24 px minimum and is what the catalogue's other footer action already ships at.

**`residue.py` refused the shared constant** the two footer actions were first given — it reads a
factory's base through its string LITERALS and a template literal reads empty. **The repair that
suggests itself is worse than the defect**: concatenating a literal with the constant silences the
report and leaves the reader comparing one token on a pair it has stopped reading. The scale is
spelled out twice and held equal by `ui/variants.test.ts`. **That is B-363.**

---

## 3. Phase 5 — the collision was REMOVED, not guarded

**The plan's mechanism and its own gate could not both hold**, and the orchestrator ruled road C.
Two doors telling themselves apart by what a shared `data-take` value NAMES keeps the engine
calling both, so it goes on naming the attribute — and `lib/verbs.ts` holds ONE handler per name,
so a name two features claim can never move onto the registry at all.

So: the picker emits **`data-pick-release`** (`features/releases/verbs.ts`), the panel keeps
**`data-take`** and MOVED ONTO THE SAME REGISTRY (`features/arrivals/verbs.ts`). That second move
is what makes the grep read 0 while arrivals keeps its name — the engine was `__arrivalsVerbs`'s
only reader. B-309's root cause is closed rather than guarded.

**Six ends moved in one commit**, and the one a source grep misses:
`frontend/maquette/a11y-light-debt.json` records accessibility debt **keyed by selector** and
carried three spelled `button[data-take="1|2|3"]`.

**`function releases()` went too** — this phase removed its last caller, so the phase took the
function. Ledger 31 484 → 31 470 → 31 467.

---

## 4. THE THREE INSTRUMENT DEFECTS THIS SESSION PAID FOR — read before writing a rule

1. **A DOM observer CANNOT see two writes in one task.** R137's « exactly one sentence » hold was
   VACUOUS and only a mutation said so: with a second sentence written into the verb on purpose,
   only the « both halves » hold fell. The message host is a component, so both writes are batched
   into one render and the DOM never holds the first value. **This is why B-322's own first reading
   says « sampled every 180 ms, only the second is ever observed » — that sentence describes the
   limit of the instrument it was taken with, and the rule reproduced it while quoting it.** The
   count is at the seam now (`window.__toast.show` wrapped, forwarding unchanged).
2. **A hold green over an unreadable value is not a hold.** R138's first « the pipeline is running »
   read `window.__mocks.mockState()`, which is NOT published — it answered `unknown`, and
   `unknown != "idle"` passed. It reads the layer AND the interface now, and disagreement fails.
3. **`window.__go` RE-SEEDS the mock layer.** A pipeline started before the state is driven is idle
   again by the time the act lands, so the walk measures a clause it has itself switched off. R125
   documents it; R138's first version re-discovered it the hard way.

Plus two smaller ones, both in R137: it counted the prototype's own **welcome hint** as a sentence
of the gesture (the engine toasts it on a timer after boot; it is spent now through the engine's own
« disappears on first interaction » contract rather than by copying its delay), and it read the
screen **bar whole**, so the subject came out « Retour Silo » and appeared in no message.

**And `check-markup-contracts` caught a third**: selecting `[data-pick-release]` by CSS attribute
PRESENCE enrols a VALUE attribute in the derived list of boolean states, where the refusal is that
it must vanish when false — which an index does not do. Anchor on `data-part`, read the verb from
the dataset. `take.py` already said so in a comment.

---

## 5. Phase 6 — what landed, and what is OWED

**LANDED**: the pastille. `data-part="season/queued"`, drawn on BOTH season surfaces (the panel the
ask was made from and the sheet's own list), the fact held in the cache by
`features/media/queued-seasons.ts`, the verb reporting its own outcome. R138
(`harness/queued_ask_mark.py`) green at 7 holds, and **mutated**: removing the mark makes holds 3
and 4 fall with `0 mark(s)`.

**LANDED**: R124's residue. Both panel actions are now pressed through `PRESS_THE_ACTION`, which
hit-tests the action's own centre. **Mutation-proved by raising the scrim over the sheet**
(`z-[46]` → `z-[60]`): four holds fall and name the coverer by its class. Before the change the
rule used `act.click()`, which dispatches on the node whatever covers it — so under that same
mutation the OLD rule would have been entirely green over a panel no finger could use. R124 is
11 holds.

**NO NAMED STATE, and it is B-352**: `states.js` is 786 against a record of 786. Road B (funding a
state by subtracting inside the file) was REFUSED by the orchestrator; road C is the operator's.
**DESIGN § 4.0 carries the hand path instead** — Arrivées → start the pipeline → a follow → ask for
a season — which works because the mock decides `queued()` from `pipelineState`, not from
`setOperationOutcome`.

**OWED, and it is the plan's « then add this wave's holds »**: the THREE new operations
(`grabSeasonForFollow`, `requeueJourney`, `rescrapeJourney`) under `busy.py`'s scenario, each
queued, said, and never 409 / never « occupé ». R125 and R126 already cover the season grab and the
journey verbs under a busy pipeline; what phase 6 asks is that `busy.py` read them too.

---

## 6. What is OWED, in order

### 6.1 FIRST, AND BEFORE ANYTHING ELSE

**Push.** Three commits are local only: `e1b2a1838`, `b0cb73555`, `131b7b51d`. A push in this
repository runs the parallel suite through its pre-push hook, so **it IS a heavy run and is wrapped
like one, every time**:

    PYTEST_XDIST_AUTO_NUM_WORKERS=3 HEAVY_FREE_FLOOR_MB=3072 sh scripts/heavy.sh l21 \
      git push origin feat/maquette-l21 > <a file> 2>&1

then prove it with `git ls-remote --heads origin feat/maquette-l21` against the local sha (B-360).
An unwrapped push once ran pytest at EIGHT workers beside another wave's browser suite; the
orchestrator killed it.

### 6.2 Then

1. **Phase 6's remaining holds** — § 5.
2. **Phase 7** — B-313 (a panel's actions counted BY LABEL, a label twice refused; red on `main`'s
   follow panel for a medium with no sheet), B-247's producer half in `persistence.py`, then the
   close: the intent map's DOIT-3/DOIT-4 rows to `served`, the « guards green over what they do not
   read » recount (**zero included**), `IMPLEMENTATION.md`'s In-flight row, `REPORT.md`, the patch
   bump.
3. **The wave gate**: full `run.sh`, `--a11y`, `harness-hold-counts.py --compare` with `failed`
   read FIRST, the oracle, `make check`, the ledger, the six-verb grep.

---

## 7. The machine, and the two traps that live in it

**One served copy machine-wide.** Announce every harness run to the orchestrator
(`personalscraper-bf`) and to whoever else holds it.

⚠ **The 8899 host does NOT survive a `run.sh` started under `scripts/heavy.sh`** (B-371, filed by
the desktop-frame wave). `run.sh` forks the host inside its own run; `heavy.sh` signals the whole
process group on release, so the host dies with the invocation. Harmless for `run.sh`, which starts
one whenever nothing is listening — **lethal for `scripts/mutate.sh`, which starts none**: it met a
refused port and printed « NO RULE FELL. That is the finding. », the exact words it prints for a
rule that read the page and was unmoved.

**A host started with `nohup` OUTSIDE the wrapper survives**, because `heavy.sh` signals only its
own command's process group. One was left listening at pid 52469. **Check
`lsof -nP -iTCP:8899 -sTCP:LISTEN` before trusting ANY mutation verdict.**

⚠ **`mutate.sh` REFUSES a dirty tree**, which is its whole correctness. Commit first, then mutate,
then the restore is guaranteed — the discipline is fix → gates → commit → mutate → restore.

---

## 8. The one thing not to repeat

Every defect this session found in its own work was found by RUNNING an instrument, never by reading
it — and three of the five were holds that PASSED over the thing they existed to catch. A rule that
is green has not been shown to measure anything. **The mutation is not a formality at the end; it is
the only evidence that a hold has a subject.** R137's docstring argued, at length and persuasively,
against the very design the mutation then forced on it.
