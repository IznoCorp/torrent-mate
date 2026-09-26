# L17 — §19, cross-seed is seen and decided · PLAN

Design: `docs/features/maquette-l17/DESIGN.md`. Contract: `docs/reference/frontend-architecture.md` § 4, entry
`#### L17 — §19, cross-seed` (its « Where it lives » and « Done when » lines).

**Written 2026-09-27 on `origin/main` at `46806a88d`, before the lot opens** (auditor's order 47: a drawing ruled before the code
costs zero rework). Every phase file carries an **opening measure** (auditor's order 42) taken on THAT head, by the commands a
STOP D would run on this tree. **Two things this plan cannot measure today, and says so in every phase they touch**: L22 (the
Acquisition lot) and L16 (the Trackers lot) land before this lot opens, so `frontend/maquette/design/src/features/trackers/`,
`mocks/handlers/trackers.ts` and `harness/states/trackers.ts` do not exist on this head (`ls
frontend/maquette/design/src/features/` → `account`, `acquisition`, `arrivals`, `library`, `maintenance`, `media`, `settings`,
`system`, `releases`), and the figures about them are taken from L16's plan (`docs/features/maquette-l16/plan/`), named beside
each. **The lot's implementer re-takes each phase's figures at the moment that phase opens** — the head will have moved — and
reports a difference before moving anything.

**Where L17 opens in the order: after L16.** The order is L13 · L22 · L16 · L17 · L18. L17 extends the page L16 lands and never
opens between L16's phases.

---

## THE PHASES CHAIN. THEY DO NOT PAUSE.

**The operator arbitrates the SCOPE, never the cadence.** A phase that finishes goes straight into the next one — L12, L14, L19,
L20, L21, L22 and L16 each carry this paragraph for the same reason: the chat gets compacted and this file does not.

**Self-check, at the end of every phase, before anything else:** « Am I about to report instead of continuing? » If the answer is
yes, the next phase exists, and none of the STOPs below is the reason, **continue**. The only permitted halts:

- **STOP A** — the oracle diverging on a state the phase did not name (DESIGN § 4.1).
- **STOP B** — the pull request.
- **STOP C** — an OPEN question of DESIGN § 7.2 that the phase reads and the operator has not ruled. The phase does not choose: it
  asks the steward, with the question's two readings and what each costs the phase (its file says). **Eight OPEN questions, none
  ruled at this writing**; the phases that read them: OPEN 1 (the media block's gate) phases 1, 3, 10, 11; OPEN 2 (the switch's
  home) phase 9; OPEN 3 (« provoke ») phases 14, 15; OPEN 4 (a feed) phases 16, 17; OPEN 5 (a pair with nothing found) phases 2, 4,
  6; OPEN 6 (« stoppé » against « tracker sans cross-seed ») phases 1, 2, 3; OPEN 7 (the engine's own switch) phase 5; OPEN 8
  (which refusals the badge counts) phase 12. **A ruled question is read, not asked**: the phase's file names the ruling.
- **STOP D** — a measurement that contradicts a home the design decided. The phase re-takes its own figures before it moves
  anything; a figure that no longer supports the home is reported to the steward with the command, and the phase does not improvise
  a new home. **One is already known**: phase 2 (the scenario that carries « actif » — DESIGN § 2.3 — needs a home, because
  `mocks/state.ts` is 398 non-blank lines of 400).

Anything believed necessary outside the contract: STOP and ask the steward first.

---

## The rule that governs every phase

**Rule first, seen RED, then the move, then the same rule green with its holds counted.** Here the red is the strongest form this
repository asks for and needs no mutation: **none of these surfaces exists on `main`**, so every hold fails there for the reason it was
written. Each phase says so and the report records the red reading per rule. Where a phase re-aims a rule an earlier phase wrote, the
mutation comes after the move: break it on purpose, confirm the rule falls and NAMES the right defect, restore.

**Commit BEFORE every mutation**, and mutate with `scripts/mutate.sh <file> <expression> <rule…>` — by hand leaves the served copy of
the PREVIOUS build in place (B-303). It cannot judge a GUARD (B-273): a guard's exit code is read by hand.

**The labels `R-L17-a … R-L17-k` (DESIGN § 5) are NOT rule numbers.** `R223` is the highest in the suite as measured at this writing
(`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1`, run 2026-09-27 on `46806a88d`). L22 and L16 run ahead
of this lot and take numbers too, so **phase 4 — the first phase that writes a rule — re-takes that command against `origin/main` at
the moment it runs and binds every label to a number then**, writing the mapping into the report. A number chosen from this file
without re-measuring is a collision.

**Every heavy run is wrapped in the machine's mutex** — `sh scripts/heavy.sh --class browser|test|rule l17 <command>` — with no
`HEAVY_LOCK=` override; the harness is one per machine and `sh scripts/heavy.sh --held` names its holder. A run holding the lock is
announced to the steward in one line before it starts and one after (« done, exit N »). Output to a FILE, exit code read in the same
tool call, **never `| tail -N` on a long gate**. Kill what you start, prove it with `ps`.

**Never `cd` into `frontend/maquette/design/src`** (B-384): absolute paths from the worktree root. **Documents are added BY FILE**:
`git add docs/features/maquette-l17/<name>.md` (B-304 — a directory add once swept `node_modules` into a commit). **No `git stash`** in
this repository, ever.

**A renamed identifier goes through `scripts/rename-identifiers.py`**, never by hand and never by an ad-hoc regex (`CLAUDE.md` § Code
Conventions).

**The mock is INVENTED** (DESIGN, opening). Every seed row this lot adds is marked `x-unseeded`, and the fixture register says so; a
phase that writes a row and does not mark it is refused by `python3 scripts/check-mock-seeds.py` — its exit code is read by OUTPUT, not
by its status (B-346).

---

## Points, and the mean (measures 11 and 19)

**A phase carries at most 15 points at its opening** (measure 11: the context budget; measure 19: the cadre). The scale is declared
once, here — the scale L22's plan declared and L16's re-used — so every figure in a phase file is reproducible:

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

A new file's length is estimated from the nearest measured analogue, named in the phase (`features/account/page.tsx` 79 non-blank lines,
`features/system/run-list.tsx` 176, `features/settings/panel-field.tsx` 182, `mocks/handlers/staging.ts` 121); the opening re-measure
replaces the estimate with the file as it stands. Halves are rounded up.

**The pre-cut clause.** A phase whose re-measure at its opening exceeds 15 is CUT at that opening, never begun; the plan's numbers after
it shift by one and the steward is told. **The clause was applied three times while this plan was written**, in the plan and not at an
opening, by the KIND of change: the media block was first one phase at 17 and is now phases 10 (the block) and 11 (its gate); « provoke »
was first one phase at 16 and is now 14 (its contract and mock) and 15 (the act); and the obligation's read was moved out of the contract
phase into the phase that draws it (8), because a demand is filed where its surface is drawn (L22's precedent). **One phase is drawn AT
the ceiling** (6, 15) and says what to cut; two stand at 14 (4 and 17).

| # | Phase | What it lands | Rules | Reads | Points |
| ---: | --- | --- | --- | --- | ---: |
| 1 | [The reads' contract](phase-01-contract.md) | the summary read extended, the tracker's section read and the media block read declared new, marked invented; the demands regenerated | — | 1, 6 | 13 |
| 2 | [The invented seed](phase-02-the-invented-seed.md) | the cases of DESIGN § 2.3 as a seed file, every row marked; the fixture register; the scenario that carries « actif » — **STOP D** on its home | — | 5, 6 | 12 |
| 3 | [The mocks that move](phase-03-the-mocks-that-move.md) | the section's and the block's routes answer from the seed; the summary derives its counts from the SAME rows | — | 1, 6 | 13 |
| 4 | [The four words, and the reasons' sentences](phase-04-the-four-words.md) | the states' words and tones, the twelve reasons' sentences, the rule labels bound to numbers | a | 5 | 14 |
| 5 | [The roster's line](phase-05-the-rosters-line.md) | each tracker row says its cross-seed state and counts; one derivation | b | 7 | 11 |
| 6 | [The tracker's section](phase-06-the-trackers-section.md) | the section of `/trackers/$name`: a row per torrent with its state; its four states; one read per visit | b, k | 5 | 15 |
| 7 | [A refusal is readable](phase-07-a-refusal-is-readable.md) | the reason's sentence, its kind of trouble, its candidate and source, on the « erreur » row | c | 5 | 10 |
| 8 | [An obligation says where it came from](phase-08-an-obligation-says-where-it-came-from.md) | the obligations read extended (demand D); the mark and the path to the origin | d | — | 13 |
| 9 | [The off switch](phase-09-the-off-switch.md) | the switch's state in the head and its control, or its link to Réglages — no new operation | e | 2 | 10 |
| 10 | [The media sheet's block](phase-10-the-media-sheet-block.md) | the block per tracker, composed at the route | b (re-aimed) | 1 | 11 |
| 11 | [The block's gate](phase-11-the-blocks-gate.md) | the administrator fact, a second identity, the block ABSENT for the other | f | 1 | 11 |
| 12 | [The badge's second term](phase-12-the-badges-second-term.md) | `trackersBadge` counts the refusals; R-L16-e re-aimed | g | 8 | 8 |
| 13 | [The stream](phase-13-the-stream.md) | the two events claimed by `features/trackers/live.ts`; the exemption shrinks; R91 re-aimed | h | — | 10 |
| 14 | [« Provoke »: its contract and mock](phase-14-provoke-contract-and-mock.md) | demand E, its route, the throttle's answer, the quota on the section's read | — | 3 | 8 |
| 15 | [« Provoke »: the act](phase-15-provoke-the-act.md) | « Chercher un partage croisé » on a row, bounded, visible | i | 3 | 9 |
| 16 | [The feed: its contract and mock](phase-16-the-feed-contract-and-mock.md) | demand F, its route, the event rows | — | 4 | 10 |
| 17 | [The feed: its surface](phase-17-the-feed-surface.md) | the chronological list and its four states | j | 4 | 14 |
| 18 | [The records](phase-18-the-records.md) | oracle, accessibility, regions, hold counts | — | — | 8 |
| 19 | [The close](phase-19-the-close.md) | the register, the map's proposal, the demands' counters, the report | — | — | 8 |

**Opening measures (2026-09-27, on `46806a88d`), each phase file's own head**: 13, 12, 13, 14, 11, 15, 10, 13, 10, 11, 11, 8, 10, 8, 9,
10, 14, 8, 8 — **sum 208 over 19 phases, mean ≈ 10.9, max 15** (phase 6), none above measure 19's 15-point ceiling, three cuts applied
at this writing (above). **That is the full lot: every reading that ADDS a phase is drawn in.** The readings that REMOVE them, taken all
at once, leave **135 over 13 phases, mean ≈ 10.4**: OPEN 1 = B removes phases 10 and 11 and 6 points of the media route in phases 1 and 3
(−28); OPEN 2 = B lowers phase 9 from 10 to 6 (−4); OPEN 3 = B removes phases 14 and 15 (−17); OPEN 4 = A removes phases 16 and 17
(−24). OPEN 7 = A adds 2 to phase 5; OPEN 8 = A adds 1 to phase 12. OPEN 5 and 6 add or remove seed rows inside phases 2–4, ≈ 1 point each.

---

## Why nineteen phases, and what a phase costs

**A phase is a unit of attribution, not a gate.** Each is ONE commit (two where the phase says « commit before the mutation »), and its
gate is the contracts tier plus the oracle — minutes, not the full suite. The full gate runs ONCE, before the pull request (STOP B). The
count follows from two rules, not from appetite: **one kind of change per phase** (a contract, a seed and a handler are three commits) and
**the 15-point ceiling**.

**The contract is first** (1) because `scripts/compare-contracts.py --check` refuses the three artefacts apart and because the demands are
what make the design's proposals decisions rather than discoveries. **The seed is second** (2) and **the mocks third** (3): a seed with no
contract cannot be checked against it (`check-mock-seeds.py`'s `schema` arm), and a handler with no seed answers nothing. **The words come
before any surface** (4): a surface that draws a state draws the operator's word, and the rule that holds « no bare code » is written before
the first place a code could leak.

**The roster's line precedes the section** (5 before 6): the line is the tracker's summary, the section is its list, and R-L17-b's first
hold — the count on the line equals the rows of the section — needs the line to exist first. **The refusal's reading follows the section**
(7): a refusal is a row of it. **The obligation's origin follows** (8), because it is a mark on an obligation L16 draws and it needs the
section's rows to agree with.

**The switch comes after the surfaces that READ it** (9 after 5–6), so the state it moves is on screen; **the media block after the tracker
surfaces** (10, 11) because it reads the same rows, and its gate is its own phase so the block's drawing and its absence are never one
commit. **The badge follows every surface that counts a refusal** (12), **and the stream follows the badge** (13), so the event has three
places to move and each is already drawn.

**The two optional acts and the feed come last** (14–17), in the order the operator's answers make them exist or vanish; **the records
are one phase** (18) and **the close is last** (19) and re-reads the map and the register rather than trusting what the phases claimed.

---

## Gates

**Per phase**: the shared-lock `frontend/maquette/harness/run.sh --contracts` — the contract rules AND the repository's cheap guards, the
script prints how many of each — and the oracle, with divergences ONLY on the states DESIGN § 4.1 names for that phase, each accepted with
its written reason (D8). Every other state at zero, or it is **STOP A**.

**Before the pull request** (the maquette wave's own gate — a maquette wave does not run `make check`; CI's `test` job is the authority,
`frontend-steward.md` measure 19): `make lint`; the full suite (`frontend/maquette/harness/run.sh`, not the `--contracts` tier), expected no
failure; the `--a11y` tier at 0 over the states this lot adds (nine to eighteen, DESIGN § 4); `python3 scripts/harness-hold-counts.py
--compare` with **`failed` read FIRST** (B-291 — the baseline is NOT re-recorded while a rule is failing) and every movement written down;
the pre-push pytest; `python3 scripts/check-intent-map.py`, `python3 scripts/check-bug-register.py` and `python3
scripts/check-docs-cited-paths.py` read by OUTPUT, not by exit code (B-346). The pull request bumps the version (patch) — the
`version-bump` job enforces it — because it changes `frontend/maquette/design/src/`.

**The steward is told BEFORE a full-suite run.** The harness is one per machine — `served_copy.py` is its lock and its stamp (B-256) — and
a rule that falls while another session held it is re-run alone before it is read, with the re-run's loss of load said in the same breath
(B-277, B-307).

**The « In flight » row is written when the pull request opens** — pull request number first, then the version;
`scripts/check-implementation-state.py` holds the row by both. **A DRAFT pull request runs no CI** (`CLAUDE.md` § Commit Convention): open it
READY, or add `run-ci-on-draft` and read the run that label dispatches — never both in one breath.

---

## What this plan believes the CONTRACT gets wrong

Recorded here as § 7.1 asks, and written in full in the design (§ 8). **No file outside `docs/features/maquette-l17/` is edited for it,
except the one dated line under the L17 heading of `docs/reference/frontend-architecture.md`** — the steward amends the plan and the
operator amends the constitution and the map.

1. **« In the media sheet's descriptor … the `panel-seasons` precedent »** — the sheet is a screen composed in a route
   (`frontend/maquette/design/src/routes/media-sheet.tsx`, 42 non-blank lines); `panel-seasons` registers a block into the bottom panel.
   Phases 10 and 11 draw the block in `features/trackers` and compose it at the route, as the follows are.
2. **« Behind the served role the backend already exposes »** — no account carries a role in either contract; the backend serves only the
   instance's deployment role (DESIGN fact 11). OPEN 1 is what follows.
3. **« Active by default »** is not what the engine does — both defaults are `False` (DESIGN fact 5). Demand H: the engine's default
   becomes ON, the backend following the interface; the operator's live switches, off, are his own setting and stay.
4. **« The two events reach the stream »** and « nothing relays them » are both written in the registers (DESIGN fact 10): demand I.
5. **§ 19 point 1 names a « rejet pour politique de tracker »** the engine has no code for (DESIGN fact 3): the design draws the policy
   case as a state.
6. **`CrossSeedInjected.source_tracker` names the TARGET tracker** (DESIGN fact 2); the contract this lot declares says `tracker`.
</content>
