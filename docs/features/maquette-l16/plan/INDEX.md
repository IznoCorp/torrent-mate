# L16 — §18, the ratio · PLAN

Design: `docs/features/maquette-l16/DESIGN.md`. Contract: `docs/reference/frontend-architecture.md`
§ 4, entry `#### L16 — §18, the ratio`.

---

## THE PHASES CHAIN. THEY DO NOT PAUSE.

**The operator arbitrates the SCOPE, never the cadence.** A phase that finishes goes straight into
the next one — L12, L14, L19, L21 and L20 each carry this paragraph for the same reason: the chat
gets compacted and this file does not.

**Self-check, at the end of every phase, before anything else:** « Am I about to report instead of
continuing? » If the answer is yes and the next phase exists, and neither STOP below is the reason,
**continue**. The only permitted halts are:

- **STOP A** — the oracle diverging on a state this wave did not touch.
- **STOP B** — the pull request.

**There is one open question this lot carries into its opening — DESIGN § 5, the trackers domain's
placement (bar or drawer).** It is not a STOP: phase 2 draws the list identically either way and
writes the navigation row under whichever reading the operator has ruled by the time phase 2 opens,
or under **Reading B** (the drawer) if it has not — the reading this plan takes as its default
because D12's Q6 refusal of a fifth bar slot is the closer precedent, amended in place the moment
the operator's word lands (DESIGN § 5's own instruction). Anything else believed necessary outside
the contract: STOP and ask the steward first.

---

## The rule that governs every phase

**Rule first, seen RED against `main`, then the move, then the same rule green with its holds
counted.** Here the red is the strongest form this repository asks for and needs no mutation:
**none of these surfaces exists on `main`**, so every hold fails there for the reason it was
written. Each phase says so explicitly, and the report records the red reading per rule.

**Commit BEFORE every mutation**, and mutate with `scripts/mutate.sh <file> <expression> <rule…>` —
by hand leaves the served copy of the PREVIOUS build in place (B-303). It cannot judge a GUARD
(B-273): a guard's exit code is read by hand.

**The labels `R-L16-a … R-L16-h` (DESIGN § 4.8) are NOT rule numbers.** `R194` is the highest in
the suite as measured on this branch at its opening (`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py
| sort -V | tail -1`, run 2026-09-15 on `08400a22a`). **Phase 1 re-takes that command against
`origin/main` at the moment it runs and binds every label to a number then**, writing the mapping
into the report — a number taken from this design without re-measuring is a collision, and several
lots (L13b, L13c, the settings micro-wave) are in flight ahead of L16 in the plan's order and will
have claimed numbers by the time this lot opens.

**Every heavy run is wrapped.** The shared lock for anything touching the one served copy or the
8899 host:

    HEAVY_FREE_FLOOR_MB=2560 TM_HARNESS_JOBS=2 sh scripts/heavy.sh l16 <command>

The wave's OWN lock for everything else heavy (`npm ci`, `npm run build`, `make check`, `pytest`, a
`git push`):

    HEAVY_LOCK=/private/tmp/tm-heavy-l16/holder HEAVY_FREE_FLOOR_MB=2560 \
      PYTEST_XDIST_AUTO_NUM_WORKERS=3 sh scripts/heavy.sh l16 <command>

A run holding the SHARED lock is announced to the steward in one line before it starts and one
after (« done, exit N »). Never a build beside a parallel run of your own. Output to a FILE, exit
code read in the same tool call, **never `| tail -N` on a long gate**. Kill what you start, prove
it with `ps`.

**The engine gains no line.** This lot draws an entirely new domain (`features/trackers/` does not
exist today — `ls frontend/maquette/design/src/features/` names `account`, `acquisition`,
`arrivals`, `library`, `maintenance`, `media`, `releases`, `settings`, `system`, and no `legacy.js`
surface answers any of §18's clauses) — there is nothing of this lot's subject in the engine to
subtract, and nothing is added to it either.

**Never `cd` into `frontend/maquette/design/src`** (B-384) — absolute paths from the worktree root.

**Documents are added BY FILE**: `git add -f docs/features/maquette-l16/<name>.md`, never the
folder (B-304 — `git add -f` on a path swept `node_modules` into a commit).

---

## Phases

**Mean stated once, here: 10 phases' worth of points, 82 total ≈ 10.25 per phase — no phase over
15.**

| # | Phase | What it lands | Register | Points |
| --- | --- | --- | --- | --- |
| 1 | [The contract and its demands](phase-01-contract.md) | four existing operations declared, five new demand rows filed, the mocks that MOVE, the rule labels bound to numbers | — | ≈ 10 |
| 2 | [The trackers list, and its host](phase-02-list.md) | the page exists, its navigation row (bar or drawer per the ruling), the roster with ratio / trend / volumes | DOIT-13 | ≈ 9 |
| 3 | [A tracker's detail](phase-03-detail.md) | `/trackers/$name`, the obligations and the active torrents each with their deadline and ratio | DOIT-13 | ≈ 11 |
| 4 | [The policy panel](phase-04-policy.md) | `min_ratio` / `min_seed_time` / the alert threshold, writable from the tracker's own screen | DOIT-3 | ≈ 9 |
| 5 | [The obligation's release verb](phase-05-release.md) | the confirmation, the release call, the external-removal HANDLED case | § 18, DOIT-2 | ≈ 13 |
| 6 | [The alert, and DOIT-2's ratio reason](phase-06-alert-and-stalled.md) | the threshold crossed shown at S1/S2, the stuck queue's ratio-specific reason cross-referencing the tracker | DOIT-2 | ≈ 12 |
| 7 | [The ranking editor](phase-07-ranking-editor.md) | `/settings/ranking`, the live preview, B-298 closed | B-298 | ≈ 13 |
| 8 | [The close](phase-08-close.md) | the map, the register, the states counted, the report | all | ≈ 5 |

### The ordering, and its reason

**The contract is FIRST** because every surface below calls one of its operations, and because the
demands filed there (DESIGN § 2.3) are what make the divergences decisions rather than discoveries
— the same reason L20's phase 1 opens its own plan.

**The list comes before the detail** because a row's path needs a list to leave from (L20's own
history-list-before-detail reasoning, identical shape here).

**The detail comes before the policy panel** because the panel is a SCREEN STATE of the detail
(DESIGN § 3) — a query parameter on an address that must already resolve.

**The release verb comes after the policy panel**, not before it, though § 18 names the release
first: the release confirmation's own copy names what is LOST (the ratio still owed against the
policy's `min_ratio`), so the phase that draws it reads a policy the panel phase already put on
screen, rather than a number invented for the confirmation alone.

**The alert and DOIT-2's reason share one phase** because both are the SAME kind of change — a
derived read, already answered by an operation phase 1 declared, surfaced where an existing
reader already looks (S1's badge, S2's block, Arrivées' stuck row) — never a write, never a new
list. Splitting them would not change what either rule reads.

**The ranking editor is LAST of the behaviour phases** because it is the one surface this lot draws
outside `features/trackers/` (DESIGN § 4.7, under the settings page by design), and because its
ratio-aware criterion (DESIGN § 2.3 item 4) is a demand the earlier phases do not need — nothing
before it depends on the scored field existing.

**The close is last** and re-reads the map and the register rather than trusting what the phases
claimed, per every prior lot's own phase 9 / phase-close convention.

---

## Gates

**Per phase**: the shared-lock `run.sh --contracts` — the contract rules AND the repository's cheap
guards — and the oracle, with divergences ONLY on the states DESIGN § 4 names for that phase, each
accepted with its written reason (D8). Every other state at zero, or it is **STOP A**.

**Before merging**: the full suite (`frontend/maquette/harness/run.sh`, not the `--contracts`
tier), expected no failure; the `--a11y` tier at 0 over the new named states;
`scripts/harness-hold-counts.py --compare` with **`failed` read FIRST** (B-291) and every movement
written down; `python3 scripts/check-intent-map.py` and `python3 scripts/check-bug-register.py`
read by OUTPUT, not by exit code (B-346). Per measure 19 (`frontend-steward.md`), **no local `make
check`** before the pull request — CI's `test` job is the authority; the pre-PR gate is `make lint`
+ the full harness suite + `--a11y` + `--compare` + the pre-push pytest.

**The steward is told BEFORE a full-suite run.** The harness is one per machine —
`served_copy.py` is its lock and its stamp (B-256) — and a rule that falls while another session
held it is re-run alone before it is read, with the re-run's loss of load said in the same breath
(B-277, B-307).

**The « In flight » row is written when the pull request opens** — pull request number first, then
the version; `scripts/check-implementation-state.py` holds the row by both.

---

## What this plan believes the CONTRACT gets right, and where it goes further

Recorded here as § 7.1 asks — this design finds no clause of `frontend-architecture.md`'s L16 entry
that has lost its subject, only gaps the contract does not yet name (DESIGN § 2.3, filed as
demands, not asserted). **No file outside `docs/features/maquette-l16/` is edited for it**; the
steward amends the plan.

1. **DESIGN § 2.3 items 1–3** — the tracker-level summary, the per-active-torrent tracker/ratio/
   deadline, and whether they are one read or two, is left to phase 1's own measurement of where
   the mock can carry it without breaching `acquisition.ts`'s 400-line ceiling
   (`grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/handlers/acquisition.ts` → 338
   at this design's writing).
2. **DESIGN § 2.3 item 4** — the ranking's ratio-aware field is a NEW demand this design proposes;
   the map does not send it to L16 today (`product-intent-map.md`'s DOIT-13 row names the three
   existing reads only).
3. **The trackers domain's placement (bar or drawer)** is the operator's open question (DESIGN
   § 5), not this plan's to answer — phase 2 opens under Reading B by default and is amended the
   moment a ruling lands.
