# L17 — §19, cross-seed is seen and decided · PLAN

Design: `docs/features/maquette-l17/DESIGN.md`. Contract: `docs/reference/frontend-architecture.md` § 4, entry
`#### L17 — §19, cross-seed` (its « Where it lives » and « Done when » lines).

**Written before the lot opens, on `1d1282567`**, under the operator's and the auditor's rulings of 2026-09-27
(`docs/reference/operator-method.md`); the plan's history, its first cut included, is
`docs/features/maquette-l17/plan/INDEX.md@0e523349f`. **Every OPEN question is ruled: no phase below reads a live
STOP C.** Every phase file carries an **opening measure** taken on THAT tree, by the commands a STOP D would run. L22 and L16 land before this lot opens, so
`frontend/maquette/design/src/features/trackers/`, `mocks/handlers/trackers.ts` and `harness/states/trackers.ts` do
not exist on that head — their figures are taken from L16's own plan, named beside each. **The lot's implementer
re-takes each phase's figures at the moment that phase opens** and reports a difference before moving anything.

**Where L17 opens in the order: after L16.** The order is L13 · L22 · L16 · L17 · L18. L17 extends the two tabs L16
lands and never opens between L16's phases.

---

## THE PHASES CHAIN. THEY DO NOT PAUSE.

**The operator arbitrates the SCOPE, never the cadence.** A phase that finishes goes straight into the next one —
L12, L14, L19, L20, L21, L22 and L16 each carry this paragraph for the same reason: the chat gets compacted and this
file does not.

**Self-check, at the end of every phase, before anything else:** « Am I about to report instead of continuing? » If
the answer is yes, the next phase exists, and none of the STOPs below is the reason, **continue**. The only
permitted halts:

- **STOP A** — the oracle diverging on a state the phase did not name (DESIGN § 4.1).
- **STOP B** — the pull request.
- **STOP C** — none of DESIGN § 7.2's eight questions is open any longer; this STOP is retired for this lot's own
  plan. **If a phase finds a NEW question a ruling did not answer, it is written OPEN with two readings and no
  choice, and the phase STOPs on it** — the same discipline, applied only to something genuinely new.
- **STOP D** — a measurement that contradicts a home the design decided. The phase re-takes its own figures before
  it moves anything; a figure that no longer supports the home is reported to the steward with the command, and the
  phase does not improvise a new home. **One is already known**: phase 2 (the scenario dial that carries the
  default's live states and the named « engine coupé » / per-tracker-off scenarios needs a home, because
  `mocks/state.ts` is 398 non-blank lines of 400).

Anything believed necessary outside the contract: STOP and ask the steward first.

---

## The rule that governs every phase

**Rule first, seen RED, then the move, then the same rule green with its holds counted.** Here the red is the
strongest form this repository asks for and needs no mutation: **none of these surfaces exists on `main`**, so
every hold fails there for the reason it was written. Each phase says so and the report records the red reading per
rule. Where a phase re-aims a rule an earlier phase wrote, the mutation comes after the move: break it on purpose,
confirm the rule falls and NAMES the right defect, restore.

**Commit BEFORE every mutation**, and mutate with `scripts/mutate.sh <file> <expression> <rule…>` — by hand leaves
the served copy of the PREVIOUS build in place (B-303). It cannot judge a GUARD (B-273): a guard's exit code is read
by hand.

**The labels `R-L17-a … R-L17-k` (DESIGN § 5) are NOT rule numbers.** Every parallel branch's own highest number
matters too (F68): **phase 4 — the first phase that writes a rule — re-takes the R-number command against the
highest of `origin/main` and every open branch running beside this one, at the moment it runs, and binds every
label to a consecutive free number then**, writing the mapping into the report. A number chosen from this file
without re-measuring is a collision.

**Every heavy run is wrapped in the machine's mutex** — `sh scripts/heavy.sh --class browser|test|rule l17
<command>` — with no `HEAVY_LOCK=` override; the harness is one per machine and `sh scripts/heavy.sh --held` names
its holder. A run holding the lock is announced to the steward in one line before it starts and one after (« done,
exit N »). Output to a FILE, exit code read in the same tool call, **never `| tail -N` on a long gate**. Kill what
you start, prove it with `ps`.

**Never `cd` into `frontend/maquette/design/src`** (B-384): absolute paths from the worktree root. **Documents are
added BY FILE**: `git add docs/features/maquette-l17/<name>.md` (B-304). **No `git stash`** in this repository,
ever.

**A renamed identifier goes through `scripts/rename-identifiers.py`**, never by hand and never by an ad-hoc regex
(`CLAUDE.md` § Code Conventions) — this lot renames Réglages' « Partage croisé » key (round 9 Q10) through it.

**The mock is INVENTED** (DESIGN, opening). Every seed row this lot adds is marked `x-unseeded`, and the fixture
register says so; a phase that writes a row and does not mark it is refused by `python3 scripts/check-mock-seeds.py`
— its exit code is read by OUTPUT, not by its status (B-346).

---

## Points, and the mean (measures 11 and 19)

**A phase carries at most 15 points at its opening** (measure 11: the context budget; measure 19: the cadre). The
scale is L22's and L16's own:

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

A new file's length is estimated from the nearest measured analogue, named in the phase; the opening re-measure
replaces the estimate with the file as it stands. Halves are rounded up.

**The pre-cut clause.** A phase whose re-measure at its opening exceeds 15 is CUT at that opening, never begun; the
plan's numbers after it shift by one and the steward is told. Phase 6's virtual window is already cut into its own
phase (16) on that clause.

| # | Phase | What it lands | Rules | Reads | Points |
| ---: | --- | --- | --- | --- | ---: |
| 1 | [The reads' contract](phase-01-contract.md) | the summary read extended (A), the downloads read extended with the cross-seed array (B), the obligations read's field declared (D filed at 8); the six-word and reason enums; demands regenerated | — | — | 13 |
| 2 | [The invented seed](phase-02-the-invented-seed.md) | the cases of DESIGN § 2.3 as a seed file, every row marked; the fixture register; the scenario dial that carries the DEFAULT live states and the named off-scenarios — **STOP D** on its home | — | — | 13 |
| 3 | [The mocks that move](phase-03-the-mocks-that-move.md) | the extended reads answer from the seed; the summary derives its counts from the SAME rows | — | — | 11 |
| 4 | [The six words, and the reasons' sentences](phase-04-the-six-words.md) | the states' words and tones (six, not four), the twelve reasons' sentences and their two counted families, the « Cross-seed » rename everywhere including Réglages, the rule labels bound to numbers | a | 5 | 15 |
| 5 | [The roster's line](phase-05-the-rosters-line.md) | each tracker entry says its cross-seed state and count, the engine-off variant; one derivation | b | 7 | 11 |
| 6 | [The torrent's cross-seed mark](phase-06-the-torrents-cross-seed-mark.md) | the mark on the Torrents tab's origin row: a row per other eligible tracker, its state, the row order (F64); one read per visit | b, k | 5 | 15 |
| 7 | [A refusal is readable](phase-07-a-refusal-is-readable.md) | the reason's sentence, its kind of trouble, its candidate and source, on an « erreur » row; the counted/not-counted split | c | 5 | 10 |
| 8 | [An obligation says where it came from](phase-08-an-obligation-says-where-it-came-from.md) | the obligations read extended (demand D); the mark and the path to the origin | d | — | 13 |
| 9 | [The switch, and its confirmation](phase-09-the-switch-and-its-confirmation.md) | the switch's state and control on the tracker's entry; cuts NEW cross-seeds only; the confirmation's unchecked-by-default option | e | 2 | 13 |
| 10 | [Cutting one tracker's cross-seed](phase-10-cutting-one-trackers-cross-seed.md) | « couper le cross-seed sur ce tracker » on an active pair; removes the entry without files; marks « stoppé »; closes the obligation « libérée » | f | 9-bis | 13 |
| 11 | [The exclusion memory](phase-11-the-exclusion-memory.md) | a cut pair excluded from future passes; « Ne plus partager ce titre » excludes the whole title; the undo | j | 9 | 11 |
| 12 | [The badge counts failures](phase-12-the-badges-second-term.md) | `trackersBadge` counts the cross-seed FAILURES only, the reserved slot named; R-L16-d re-aimed | g | 11 | 9 |
| 13 | [The stream](phase-13-the-stream.md) | the two events plus a search-outcome event, claimed by `features/trackers/live.ts`; the exemption shrinks; R91 re-aimed | h | 6 | 10 |
| 14 | [« Chercher un cross-seed »: its contract and mock](phase-14-provoke-contract-and-mock.md) | demand E, its route keyed by torrent and tracker, the throttle's answer, the quota on the mark's read — bounded by the quota and the delay ONLY | — | 9, 10 | 8 |
| 15 | [« Chercher un cross-seed »: the act](phase-15-provoke-the-act.md) | the act on a mark's row, offered only on the three eligible states, bounded, visible, resolving within the visit | i | 9, 9-bis | 10 |
| 16 | [The virtual window](phase-16-the-virtual-window.md) | `ui/virtual-rows.tsx` in fixed-size mode for the mark's rows once they pass a screenful; the opened-refusal row measured against it | — | — | 9 |
| 17 | [The records](phase-17-the-records.md) | oracle, accessibility, regions, hold counts | — | — | 8 |
| 18 | [The close](phase-18-the-close.md) | the register, the map's proposal, the demands' counters, the README's row extended, the report | — | 14 | 8 |

**Opening measures**, each phase file's own head: 13, 13, 11, 15, 11, 15, 10, 13, 13, 13, 11, 9, 10, 8, 10, 9, 8,
8 — **sum 201 over 18 phases, mean ≈ 11.2, max 15** (phases 4 and 6), none above the 15-point ceiling.

---

## Why eighteen phases, and what a phase costs

**A phase is a unit of attribution, not a gate.** Each is ONE commit (two where the phase says « commit before the
mutation »), and its gate is the contracts tier plus the oracle — minutes, not the full suite. The full gate runs
ONCE, before the pull request (STOP B). The count follows from two rules, not from appetite: **one kind of change
per phase** (a contract, a seed and a handler are three commits) and **the 15-point ceiling**.

**The contract is first** (1) because `scripts/compare-contracts.py --check` refuses the three artefacts apart and
because the demands are what make the design's proposals decisions rather than discoveries. **The seed is second**
(2) and **the mocks third** (3): a seed with no contract cannot be checked against it, and a handler with no seed
answers nothing. **The words come before any surface** (4): a surface that draws a state draws the operator's word,
and the rule that holds « no bare code » is written before the first place a code could leak — this is also where
Réglages' rename lands, because the vocabulary is one thing named once.

**The roster's line precedes the mark** (5 before 6): the line is the tracker's summary, the mark is the per-torrent
detail, and R-L17-b's first hold — the line's count equals the mark's rows in that state, summed across every torrent
— needs the line to exist first. **The refusal's reading follows the mark** (7): a refusal is a row of it. **The
obligation's origin follows** (8), because it is a mark on an obligation L16 draws and it needs the mark's own rows
to agree with.

**The switch comes after the surfaces that READ it** (9 after 5–7), so the state it moves is on screen. **Cutting
one tracker's cross-seed follows the switch** (10): both are confirmed writes that end a running obligation, and
the switch's own confirmation copy (round 9 Q5's naming discipline) is the pattern the cut reuses, not invents
twice. **The exclusion follows the cut** (11), because a cut is what makes a pair excludable in the first place.

**The badge follows every surface that counts a failure** (12), **and the stream follows the badge** (13), so the
event has every place to move already drawn. **The act — « Chercher un cross-seed » — comes after the exclusion**
(14–15), because an excluded pair is exactly the case the act must refuse to offer twice. **The virtual window comes
last among the surfaces** (16), because it is a COST of the mark growing with the library, never a surface of its
own — cutting it out of phase 6 rather than folding it in is what keeps phase 6 at the ceiling instead of over it.
**The records are one phase** (17) and **the close is last** (18) and re-reads the map and the register rather than
trusting what the phases claimed.

---

## Gates

**Per phase**: the shared-lock `frontend/maquette/harness/run.sh --contracts` — the contract rules AND the
repository's cheap guards, the script prints how many of each — and the oracle, with divergences ONLY on the states
DESIGN § 4.1 names for that phase, each accepted with its written reason (D8). Every other state at zero, or it is
**STOP A**.

**Before the pull request** (the maquette wave's own gate — a maquette wave does not run `make check`; CI's `test`
job is the authority, `frontend-steward.md` measure 19): `make lint`; the full suite (`frontend/maquette/harness/run.sh`,
not the `--contracts` tier), expected no failure; the `--a11y` tier at 0 over the states this lot adds (twelve,
DESIGN § 4); `python3 scripts/harness-hold-counts.py --compare` with **`failed` read FIRST** (B-291) and every
movement written down; the pre-push pytest; `python3 scripts/check-intent-map.py`, `python3 scripts/check-bug-register.py`
and `python3 scripts/check-docs-cited-paths.py` read by OUTPUT, not by exit code (B-346). The pull request bumps the
version (patch) — the `version-bump` job enforces it — because it changes `frontend/maquette/design/src/`.

**The steward is told BEFORE a full-suite run.** The harness is one per machine — `served_copy.py` is its lock and
its stamp (B-256) — and a rule that falls while another session held it is re-run alone before it is read, with the
re-run's loss of load said in the same breath (B-277, B-307). **A chute is proved a regression, never accepted as
« charge », by REPEATED comparison against `main` at comparable load — never a single green relaunch** (ordre 48,
amended): at least ten runs of each side, or as many as it takes to separate the two rates beyond what chance
explains.

**The « In flight » row is written when the pull request opens** — pull request number first, then the version;
`scripts/check-implementation-state.py` holds the row by both. **A DRAFT pull request runs no CI** (`CLAUDE.md` §
Commit Convention): open it READY, or add `run-ci-on-draft` and read the run that label dispatches — never both in
one breath.

---

## What this plan believes the CONTRACT gets wrong

Recorded here as § 7.1 asks, and written in full in the design (§ 8). **No file outside
`docs/features/maquette-l17/` is edited for it, except the two dated lines, one under the L17 heading of
`docs/reference/frontend-architecture.md` and one in `docs/reference/backend-demands-architecture.md` § 5** — the
steward amends the plan and the architecture entries, and the operator amends the constitution and the map.

1. **« Behind the served role the backend already exposes »** and **« a block in the media sheet's descriptor »** —
   both are L18's question now (OPEN 1 = B); DESIGN § 8 point 1.
2. **« Active by default »** is not what the engine does today, and round 9 Q9 fixes WHEN it becomes true (at the
   switchover) — demand H.
3. **« The two events reach the stream »** and « nothing relays them » disagree in the registers — demand I, now a
   third, search-outcome event too (F59).
4. **§ 19 point 1 names a « rejet pour politique de tracker »** the engine has no code for — the design draws the
   policy case as a state.
5. **`CrossSeedInjected.source_tracker` names the TARGET tracker** — the contract this lot declares says `tracker`.
6. **The engine tries only the FIRST verified tracker**, though § 19 wants a state on EVERY eligible one (F26) —
   demand B is extended to ask for an attempt per eligible, switched-on tracker.
