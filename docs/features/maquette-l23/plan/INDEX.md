# L23 — the upload to a tracker (§ 19 point 5) · PLAN

Design: `docs/features/maquette-l23/DESIGN.md`. Contract: `docs/reference/frontend-architecture.md` § 4, entry
`#### L23 — §19 point 5, upload to a tracker` (its « Where it lives » and « Done when » lines, once written).

## Executed 2026-10-01 — read this first

The plan below is older than the method's reset (`docs/reference/method.md`, 2026-09-30) and than round 11
(DESIGN § 7, all five ruled). Its cut was kept, its figures re-taken on the tree, and its lines on retired
controls (mutations, the oracle, hold counts, `check-mock-seeds.py`, the `--contracts` and `--a11y` tiers,
`regions.json`) are struck. What was built, on `feat/maquette-l23` (L17's branch merged in):

| Plan phases | Commit | What landed |
| --- | --- | --- |
| 1–3 | contract, seed, mock | `uploadCrossSeed` (Q); `creation_failed`, `publish_failed` in place of L17's reserved `upload_failed` (R); a pair's `via`, `trackerReason`, `uploading` (S, filed: Q5 was ruled B); a tracker's `acceptsUploads` and its setting `tracker.providers.<name>.accepts_uploads` (Q2 = B); a client entry's `origin` boolean became `provenance` — `downloaded`, `crossSeed`, `published` (Q5 = B); the seed invented, the handler moving the pair by the SAME two events |
| 4–7 | the gesture, the switch, the mark | the act beside the search on `noMatch`/`error`/`notSearched`, the origin seeding (Q1 = A); the confirmation naming the tracker and the release; « en file »; « publié par vous le … » or the code's sentence and the tracker's own reason (Q3 = A, Q4 = A); the badge counting both codes with no new term; the tracker panel's « accepte les uploads » switch; the third origin mark « Publié par vous » |
| 8 | — | struck: every instrument it re-ran is retired |
| 9 | the close | this section, `IMPLEMENTATION.md`, the version bump |

**Rule numbers** (bound at the first rule-writing phase, from the brief's R450–R479): R450 = R-L23-a, R451 = b,
R452 = c, R453 = d, R454 = e (re-aims R-L17-g/h) — `harness/cross_seed_upload.py`; R455 (the « accepte les
uploads » switch) and R456 (the third origin mark) — `harness/cross_seed_upload_marks.py`. Each was seen red on
`2b69c0fdf` (no act, no state), then green. `cross_seed_mark.py` and `trackers_roster.py` were re-aimed by the
intended change.

**The right, wired once L18 reached `main`** (#663): `trackers.upload` (DESIGN § 0.2) is in the contract's `Right`
set, the model's write rights and « Comptes »' words; no shipped role carries it (Admin by its bypass);
`uploadCrossSeed` asks for it (`operation-rights.ts`), and the panel offers the act only to its holder, the search
staying `trackers.control`'s. R457 = R-L23-f — `harness/cross_seed_upload_right.py`, its two halves under four
identities — was seen red on the merged head `408340aa6` (six violations), then green.

**Named states** (DESIGN § 3): 1–6 real; 7 (`-rule-refused`) and 8 (`tracker-upload-failures`) dropped — Q3 and Q4
ruled A; `torrents-cross-seed-published` added for Q5 = B.

---

**Written 2026-09-27, on `main` at `7d40969f4`**, before L23 itself is next in the order — at the time, L16, L17 and
L18 had each landed as a design-and-plan pull request, none yet as code (`docs/features/maquette-l16/`, `-l17/`,
`-l18/` were all still on the tree; `docs/reference/frontend-architecture.md` § 4, « Landed, in order » named none of
them). **L16 has since landed as code** (PR #634, squash `f3d8fed01`) and its folder is gone (`docs/features/maquette-l16/plan/INDEX.md@f3d8fed01` reads its own plan); `-l17/` and `-l18/` remain design-only, still on the tree.
**Every figure this plan cites about a file `features/trackers/` will hold is taken from
L17's OWN plan** (`docs/features/maquette-l17/plan/`, already written and merged), never from a file this worktree
can read today — `ls frontend/maquette/design/src/features/trackers` answers no such directory, measured at this
plan's own opening. **The implementer of L23's OWN execution wave re-takes every figure below at the moment each
phase actually opens** (the same discipline L17's plan used for L16's not-yet-landed files) — a number here is a
PROJECTION, not a promise.

**Where L23 opens in the order: after L18.** `docs/reference/frontend-architecture.md` § 1, § 4 Phase 5: « L14 ·
L19 · L21 · L13 · L20 · L22 · L16 · L17 · L18 · L23 ». L23 extends L17's own surfaces and never opens before them.

---

## THE PHASES CHAIN, ONCE OPEN. THEY DO NOT PAUSE — BUT THIS PLAN DOES, TODAY.

**This plan is written to be READ before it is RUN.** Unlike every other plan on this tree, it is published while
its own five questions (DESIGN § 7) are still open, on purpose — so the operator can answer them now, cheaply,
from this document, rather than after an implementer has already guessed. **A sixth question the brief itself
named — who holds the upload right by default — is NOT among them**: organisation ruling 21 makes a right's
default holder configuration (Comptes), never a design choice, so DESIGN § 0.2 draws the right's own name and a
proposed starting value instead of asking. **No phase below opens until the lot itself is next in
`frontend-architecture.md`'s order AND every open question a phase depends on is ruled.** Once both are true, the
phases chain exactly as every other lot's do:

- ~~**STOP A** — the oracle diverging on a state the phase did not name.~~
- **STOP B** — the pull request.
- **STOP C — LIVE for this plan, unlike L16/L17/L18's own by the time their plans ran.** Five questions are open
  (DESIGN § 7); every phase below names which ones it needs ruled before it can open, and a phase with a live STOP
  C is not begun — the steward relays the question through the auditor, the operator answers in
  `docs/reference/operator-method.md`, and THIS document is amended in one line per answer (DESIGN § 0's own
  promise). **Phases 1, 4, 6, 7, 8 and 9 carry no STOP C** — their content is drawn from what round 8 Q8/Q18 and
  organisation ruling 21 already ruled, and nothing live in DESIGN § 7 touches them. **Phases 2, 3 and 5 each
  carry one.**
- **STOP D** — a measurement that contradicts a home the design decided. Certain here already: every phase's
  opening figure about `features/trackers/`, `mocks/handlers/trackers.ts` or `harness/states/trackers.ts` is taken
  from L17's plan, not from this tree, and the re-measure at the phase's real opening is EXPECTED to move — that
  is not itself a STOP D, only a re-taken figure; a STOP D is a figure that no longer supports the PHASE'S OWN
  cut (e.g. a file already past 400 non-blank lines when this plan assumed room).

Anything believed necessary outside the contract: STOP and ask the steward first.

---

## The rule that governs every phase

**Rule first, seen RED, then the move, then the same rule green with its holds counted.** Every rule this plan
proposes is red for the same reason every prior lot's was at its own opening: none of `features/trackers/`'s
upload surface exists anywhere this plan can read, on `main` or on L16/L17/L18's own branches (all three already
~~merged as docs, none as code) — the red needs no mutation to be seen, and the mutation comes after the move, as~~
everywhere else on this tree.

**The labels `R-L23-a … R-L23-f` (DESIGN § 4) are NOT rule numbers.** The phase that first writes a rule re-takes
the highest number across `origin/main` and every open branch running beside L23 at that moment, and binds each
label to a consecutive free one, writing the mapping into its report — a number chosen from DESIGN § 4 without
re-measuring is a collision, exactly as L17's own plan warns.

**Every heavy run is wrapped in the machine's mutex** — `sh scripts/heavy.sh --class browser|test|rule l23
<command>`, no `HEAVY_LOCK=` override — announced to the steward one line before it starts and one after. Output
to a file, exit code read in the same tool call, never `| tail -N` on a long gate. Kill what you start, prove it
with `ps`.

**Never `cd` into `frontend/maquette/design/src`**: absolute paths from the worktree root. **Documents are added BY
FILE**: `git add docs/features/maquette-l23/<name>.md`. **No `git stash`**, ever, in this repository.

**A renamed identifier goes through `scripts/rename-identifiers.py`**, never by hand and never by an ad-hoc regex.

**The mock is INVENTED**, exactly as L17's own was for cross-seed (DESIGN § 2.2 of that design, unchanged in kind
~~here): every seed row L23 adds is marked `x-unseeded`, and a phase that writes one and does not mark it is refused~~
~~by `python3 scripts/check-mock-seeds.py`, its exit code read by OUTPUT, never by status (B-346).~~

---

## Points, and the mean

**A phase carries at most 15 points at its opening.** The scale is unchanged from every prior lot's:

| Thing | Points |
| --- | ---: |
| a line **edited or deleted** in a site | 1 per 5 |
| a line **written new** | 1 per 10 |
| a file moved, or a file deleted | 1 · ½ |
| a new rule with its mutation(s) | 3 |
| a rule file re-aimed (its walk changes) · one id swapped | 1 · ½ |
| a new named state (re-using a seed) · (needing a new seed row) | 1 · 2 |
| a contract operation edited · declared new | 1 · 2 |
| a mock handler re-answered · a new route | 1 · 2 |
| a sentence rewritten (its key and readers) | 1 |
| a documentation row (the close) | 1 |

**The pre-cut clause.** A phase whose re-measure at its OWN opening exceeds 15 is cut at that opening, never
begun; the plan's numbers after it shift by one and the steward is told. None of the nine below is pre-cut today
— the ceiling is measured against L17's own file projections, and the largest (phase 5, the gesture answered) sits
at 12, three under it.

| # | Phase | What it lands | Rules | Points | STOP C on |
| ---: | --- | --- | --- | ---: | --- |
| 1 | [The contract](phase-01-the-contract.md) | demand Q (`uploadCrossSeed`), the two new reason codes (R), the register's own regeneration | — | 10 | none |
| 2 | [The invented seed](phase-02-the-invented-seed.md) | every case DESIGN § 3 needs reachable, each row marked `x-unseeded`, including one identity holding `trackers.control` but not `trackers.upload` (proving § 0.2's two rights independent) | — | 9 | Q1 (what a seed row represents) |
| 3 | [The mocks that move](phase-03-the-mocks-that-move.md) | `uploadCrossSeed` moves the seed exactly as `searchCrossSeed`/`cutCrossSeed` already do (success, and each of the two failures) | — | 8 | Q3 (what a refusal answers) |
| 4 | [The gesture offered](phase-04-the-gesture-offered.md) | the act drawn on the eligible states, absent on the others, on an excluded pair, and for an account without `trackers.upload` (§ 0.2) | b | 7 | none |
| 5 | [The gesture answered](phase-05-the-gesture-answered.md) | the confirmation, the call, the visible « en file », the refusal's own reading | a, c, d, f | 12 | Q1, Q3 |
| 6 | [The badge's slot filled](phase-06-the-badges-slot-filled.md) | `crossSeed.failed` already counts the two new codes; R-L17-g re-aimed, not re-derived | e | 6 | none |
| 7 | [The stream](phase-07-the-stream.md) | the SAME two events, now also fired by an upload's own outcome; R-L17-h re-aimed | — | 6 | none |
| 8 | [The records](phase-08-the-records.md) | oracle, accessibility, regions, hold counts | — | 6 | none |
| 9 | [The close](phase-09-the-close.md) | the register, the map's proposal, the demands' counters, the report | — | 6 | none |

**Sum 70 over 9 phases, mean ≈ 7.8, max 12** (phase 5) — every phase at least 3 points under the 15-point ceiling,
because most of this lot's cost is a SECOND act on a row L17 already draws, never a new surface of its own.
**Against nothing** — this is the FIRST cut, not a re-cut: there is no prior count to compare it to.

---

## Why nine phases, and what a phase costs

**A phase is a unit of attribution, not a gate.** Each is one commit, and its own gate is the contracts tier plus
~~the oracle. **The contract is first** (1), because `scripts/compare-contracts.py --check` refuses the demand and~~
the schema apart, and because the two new codes are what makes round 8 Q8's own ruling typed rather than merely
quoted. **The seed is second** (2) and **the mocks third** (3): a seed with no contract cannot be checked against
it, and a handler with no seed answers nothing — the SAME ordering L16, L17 and L18 all used.

**The gesture's OFFER precedes its ANSWER** (4 before 5): a row must draw the act before the act can be tapped,
and R-L23-b's own hold (offered only where nothing already cross-seeds) needs the drawn row to exist first. **The
badge follows the gesture that can fail** (6), because a code nothing emits yet cannot be counted meaningfully —
and it is DELIBERATELY small (6 points): filling a slot L17's own derivation already sums is a RE-AIM, never a
new component, and the phase's whole job is to prove that re-aim rather than to build a new one. **The stream
follows the badge** (7), so the event has a place to move that already counts it. **The records are one phase**
(8) and **the close is last** (9), re-reading the map and the register rather than trusting what the phases
claimed — the same shape every prior lot's own closing phase already takes.

---

## Gates

~~**Per phase**: the shared-lock `frontend/maquette/harness/run.sh --contracts`, and the oracle, with divergences~~
ONLY on states DESIGN § 4.1 of this design would name (none is named yet — S1 is a wholly new act on an existing
~~row, and the oracle is blind to a state nothing has walked before this lot's own phases run); every other state at~~
~~zero, or it is STOP A.~~

**Before the pull request** (the maquette wave's own gate, once L23 actually opens): `make lint`; the full suite;
~~the `--a11y` tier at 0 over the states this lot adds; `python3 scripts/harness-hold-counts.py --compare` with~~
~~`failed` read FIRST; the pre-push pytest; `check-intent-map.py`, `check-bug-register.py` and~~
~~`check-docs-cited-paths.py`, each read by OUTPUT. The pull request bumps the version (patch) because it changes~~
`frontend/maquette/design/src/`.

**None of this applies to THIS docs pull request.** This plan is prose and numbers; the gate this PR itself
~~answers to is `docs/features/BRIEF-design-l23.md`'s own — `check-docs-cited-paths.py`, `check-no-french.py`,~~
`make lint` — read once, over the three commits this PR carries, never over a code change that does not exist yet.

---

## What this plan cannot measure today, and says so

Five things, all shared with DESIGN § 7 and none decided by this plan. **A sixth, once listed here as Q3 — whether
phase 5's refusal-side rule binds to `trackers.control` or to a new `trackers.upload` — is no longer one of them**:
DESIGN § 0.2 draws the right's own name (`trackers.upload`, distinct from `trackers.control`) as a SETTLED fact,
per organisation ruling 21, and phase 4/5's own rule `f` reads whichever role Comptes has assigned it to, at
whatever moment the rule runs — nothing here is void pending an operator's choice on this point any more.

1. **Whether phase 4's gesture is reachable from `features/trackers` alone, or also from the library / the media
   sheet** — DESIGN § 7 Q1. A reading of B re-cuts phases 4 and 5 into at least four, and this plan's own point
   count is void for them until the operator rules.
2. **Whether phase 2's seed needs a per-tracker upload-switch case** — Q2. Costs one more seeded tracker row,
   cheap, but a case this plan's phase 2 does not name until ruled.
3. **Whether phase 1 declares a tracker-rule read, and phase 5 a pre-validating form** — Q3. A reading of B adds a
   phase of its own between 1 and 2, and every later phase's number shifts.
4. **Whether phase 6 gains a sibling — a per-tracker « N publications échouées » sub-surface** — Q4. A reading of
   B adds one phase after 6, at roughly the size L16's own broken-obligations phase cost (its own plan's figure,
   re-read at that time).
5. **Whether phase 3's mock also writes L16's own origin-colour field** — Q5. A reading of B touches a file L16
   draws, never L23's own, and is a one-line change to phase 3's own move, not a new phase.
