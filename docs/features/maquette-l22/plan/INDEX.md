# L22 — Arrivées dans Acquisition · PLAN

Design: `docs/features/maquette-l22/DESIGN.md`. Contract: `docs/reference/frontend-architecture.md` § 4, entry
`#### L22 — Arrivées dans Acquisition` (its « Where it lives » and « Done when » lines).

**Written 2026-09-26 on `origin/main` at `94a369879`, before the lot opens.** Every phase file carries an **opening measure**
(auditor's order 42) taken on THAT head, by the commands a STOP D would run on this tree. The lot's implementer re-takes
each phase's figures at the moment that phase opens (the head will have moved) and reports a difference before moving
anything.

---

## THE PHASES CHAIN. THEY DO NOT PAUSE.

**The operator arbitrates the SCOPE, never the cadence.** A phase that finishes goes straight into the next one. Stopping to
announce « phase N done » is the failure mode L12, L14, L19, L20 and L21 each wrote this paragraph to prevent, and it is
written HERE because the chat gets compacted and this file does not.

**Self-check, at the end of every phase, before anything else:** « Am I about to report instead of continuing? » If the
answer is yes, the next phase exists, and none of the STOPs below is the reason, **continue**. The only permitted halts:

- **STOP A** — the oracle diverging on a state the phase did not name (DESIGN § 4.1).
- **STOP B** — the pull request.
- **STOP D** — a measurement that contradicts a home the design decided. The phase re-takes its own figures before it moves
  anything; a figure that no longer supports the home is reported to the steward with the command, and the phase does not
  improvise a new home. **Two are already known**: phase 9 (two of « À traiter »'s three sections have no real seed row)
  and phase 11 (how many of the sixteen walks that arrive at Acquisition unnamed fall when the default tab changes).

**OPEN questions are not STOPs.** DESIGN § 7.2 lists eleven; each phase says which one it touches (OPEN 1 the tabs' order
in phase 8, OPEN 3 in phase 15, OPEN 4 in phase 5, OPEN 5 in phase 23, OPEN 6 in phases 21 and 23, OPEN 7 in phase 12,
OPEN 8 in phase 18, OPEN 9 and 10 in phase 9, OPEN 11 in phase 7, OPEN 2 in phase 17) and builds so that either reading
costs the same phase. The steward relays the operator's word and the design is amended in one line.

Anything believed necessary outside the contract: STOP and ask the steward first.

---

## The rule that governs every phase

**Rule first, seen RED, then the move, then the same rule green with its holds counted.** Where a surface does not exist on
`main`, the rule is red for that reason and needs no mutation. Where a phase reverses a behaviour that exists, the rule
is written against the assertion as it stands (DESIGN § 5.1 lists the six that assert what this lot reverses) and the
mutation comes after the move: break it on purpose, confirm the rule falls and NAMES the right defect, restore.

**Commit BEFORE every mutation**, and mutate with `scripts/mutate.sh <file> <expression> <rule…>` — by hand leaves the
served copy of the PREVIOUS build in place (B-303). It cannot judge a GUARD (B-273): a guard's exit code is read by hand.

**The numbers R-L22-a … r are LABELS, not rule numbers.** Phase 1 re-takes
`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` against `origin/main` at the moment it runs
and binds every label to a number then, writing the mapping into the report. A number chosen from this file without
re-measuring is a collision.

**Every heavy run is wrapped in the machine's mutex** — `sh scripts/heavy.sh --class browser|test|rule l22 <command>` — with
no `HEAVY_LOCK=` override. A run holding the lock is announced to the steward in one line before it starts and one after
(« done, exit N »). Output to a FILE, exit code read in the same tool call, **never `| tail -N` on a long gate**. Kill what
you start, prove it with `ps`.

**Never `cd` into `frontend/maquette/design/src`** (B-384): absolute paths from the worktree root. **Documents are added BY
FILE**: `git add docs/features/maquette-l22/<name>.md` (B-304 — a directory add once swept `node_modules` into a commit).
**No `git stash`** in this repository, ever.

**A renamed identifier goes through `scripts/rename-identifiers.py`**, never by hand and never by an ad-hoc regex
(`CLAUDE.md` § Code Conventions); its read-back is skipped for `--values` runs and for Python files, so the diff is
re-read and the harness suite re-run — an oracle OUTSIDE the tool.

---

## Points, and the mean (measures 11 and 19)

**A phase carries at most 15 points at its opening** (measure 11: the context budget; measure 19: the cadre). The scale is
declared once, here, so every figure in a phase file is reproducible:

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

**The pre-cut clause.** A phase whose re-measure at its opening exceeds 15 is CUT at that opening, never begun; the plan's
numbers after it shift by one and the steward is told. Two phases are drawn at or near the ceiling (9 at 14, 11 at 13) and
say what to cut.

| # | Phase | What it lands | Rules | Points |
| ---: | --- | --- | --- | ---: |
| 1 | [The contract](phase-01-contract.md) | arrival cards, the ladder's optional fields, the reclassification and the non-media destinations declared; the mocks that MOVE; the demands regenerated; the rule labels bound to numbers | — | 12 |
| 2 | [The candidates screen changes hands](phase-02-resolution-changes-hands.md) | the screen, its cards, its vocabulary, its verbs, its decision reads and its live rules move to Acquisition; the parent of `/resolution/$folder` becomes `acq` | n | 13 |
| 3 | [The two surviving states take their names](phase-03-states-take-their-names.md) | `arr-resolution` → `acq-resolution-none`, `arr-decision` → `acq-resolution-tie`; ten rule files re-aimed; the states' home `harness/states/tunnel.ts` | — | 8 |
| 4 | [The strip counts its cells](phase-04-strip-counts-its-cells.md) | the card strip takes N cells, an optional label, two more cell states | unit | 6 |
| 5 | [One ladder, two readers](phase-05-one-ladder.md) | ten rungs from ONE source, read by the card and the journey sheet | f | 14 |
| 6 | [Arrivals join « En cours »](phase-06-arrivals-join-en-cours.md) | the arrival family draws; a card without identity; a card `waiting` | g | 14 |
| 7 | [The requester line](phase-07-the-requester-line.md) | « ajouté par Izno, dans qBittorrent », from the answer | k | 7 |
| 8 | [The fourth tab exists, and fits](phase-08-the-fourth-tab.md) | « À traiter » as a tab, empty; four labels at 390 px | e | 8 |
| 9 | [« À traiter » holds its cards](phase-09-todo-holds-its-cards.md) | three sections; the `blocked` section leaves « En cours »; **STOP D on two seeds** | h | 14 |
| 10 | [The badge and the count](phase-10-the-badge-and-the-count.md) | the bar's badge counts « À traiter » alone; R16 re-aimed | b | 6 |
| 11 | [The default tab](phase-11-the-default-tab.md) | the tab opened by default; the walks that land unnamed re-run | a | 13 |
| 12 | [« Suivant » dies](phase-12-suivant-dies.md) | the button and its verb go; one returns to « À traiter »; R57's hold inverted | d | 11 |
| 13 | [« Laisser tel quel » means later](phase-13-laisser-tel-quel-is-later.md) | the card is kept, set aside, in « Mis de côté »; R57's leave half re-aimed | i | 14 |
| 14 | [« Ce n'est pas un média »](phase-14-not-a-media.md) | the new exit, its choice, its reclassification | j | 13 |
| 15 | [« Suivre », proposed](phase-15-suivre-proposed.md) | the offer on an arrived series, never done unasked | l | 8 |
| 16 | [A film's follow ends alone](phase-16-film-follow-ends.md) | the follow leaves « Suivis » at the last rung | m | 10 |
| 17 | [Système leaves the bar](phase-17-systeme-leaves-the-bar.md) | `sys` out of the bar, into the drawer; five readers re-aimed | q | 12 |
| 18 | [The menu button's badge](phase-18-the-menu-buttons-badge.md) | the badge on the static header's button, one derivation | c | 12 |
| 19 | [The sentences that sent the reader to Arrivées](phase-19-the-five-sentences.md) | five sentences rewritten; Acquisition's cross-reference dies | p | 13 |
| 20 | [Readers re-aimed: the page's states](phase-20-readers-the-pages-states.md) | thirteen rule files and one state file leave `arr-*` | — | 14 |
| 21 | [Readers re-aimed: identity and launch bar](phase-21-readers-identity-and-launch-bar.md) | nine files leave the page's id, its path and its `data-pipe` | — | 14 |
| 22 | [The live rule Système was borrowing](phase-22-the-live-rule-systeme-was-borrowing.md) | the pipeline-status rule moves to Système | r | 5 |
| 23 | [The death of Arrivées](phase-23-the-death-of-arrivees.md) | page, route, row, keys, states, launch bar removed; the residual grep at zero | o | 12 |
| 24 | [The records of a dead page](phase-24-the-records-of-a-dead-page.md) | regions, oracle, accessibility, ratchets, fixture register | — | 10 |
| 25 | [The close](phase-25-the-close.md) | the register, the README, the debts, the report | — | 9 |

**Opening measures (2026-09-26, on `94a369879`; auditor's order 42), each phase file's own head**: 12, 13, 8, 6, 14, 14, 7,
8, 14, 6, 13, 11, 14, 13, 8, 10, 12, 12, 13, 14, 14, 5, 12, 10, 9 — **sum 272 over 25 phases, mean ≈ 10.9**, none above
14, none past measure 11's 15-point ceiling, 0 cut at this writing.

---

## Why twenty-five phases, and what a phase costs

**A phase is a unit of attribution, not a gate.** Each is ONE commit (two where the phase says « commit before the
mutation »), and its gate is the contracts tier plus the oracle — minutes, not the full suite. The full gate runs ONCE, before
the pull request (STOP B). The count follows from two rules, not from appetite: **one kind of change per phase** (a move
and a redraw cannot share a commit) and **the 15-point ceiling** (a phase that would exceed it is cut, as phases 4, 7, 10
and 11 were cut out of larger ones while this plan was written).

**The contract is first** because `scripts/compare-contracts.py --check` refuses the three artefacts apart and because the
demands are what make the design's proposals decisions rather than discoveries.

**The candidates screen moves BEFORE anything is redrawn** (phase 2), so every later phase draws in Acquisition's own
feature; and its two states are renamed in a phase of their own (phase 3) so a rename never shares a commit with a move.

**The primitive is its own phase** (4) so the ladder's oracle divergence names the ladder alone. **The ladder precedes the
arrivals** (5 before 6) because the arrival cards ARE ladder cards; **the requester line follows** (7) because it is a line
ON that card.

**The tab exists before it holds** (8 before 9) so the four-label fit at 390 px is proved on its own; **it holds before the
badge counts it** (9 before 10) and **the badge before the default rule reads it** (10 before 11) — the default tab reads a
count that must already be right.

**The return to the list and « Suivant » (12) come before the two new meanings** (13, 14): a resolution that returns to
the list is the floor on which « Laisser tel quel » and « Ce n'est pas un média » both land.

**« Suivre » before the follow's end** (15 before 16): the proposal creates the follows the ladder's last rung then ends for
films; the two are different kinds of change on one list.

**The bar and the drawer come after the surfaces they carry** (17, 18), so the badge counts something real; **the sentences
next** (19), so nothing points at the page when it goes.

**The readers are re-aimed BEFORE the page dies** (20, 21), in two phases cut by what they read (the page's states / its
identity and the launch bar) — never by the count of the word (DESIGN § 1.5) — **so the death phase has zero readers to
break** and the residual grep is its gate. **The live rule moves BEFORE the death** (22): the page was holding it for
Système (DESIGN § 1.1).

**The death is its own phase** (23), **and the records of a dead page are another** (24): the memory the tooling keeps of
a page — regions, oracle, accessibility, ratchets — is not the page, and a ratchet that does not fall after a deletion is
a guard reading nothing.

**The close is last** (25) and re-reads the map and the register rather than trusting what the phases claimed.

---

## Gates

**Per phase**: the shared-lock `frontend/maquette/harness/run.sh --contracts` — the contract rules AND the repository's
cheap guards, the script prints how many of each — and the oracle, with divergences ONLY on the states DESIGN § 4.1 names
for that phase, each accepted with its written reason (D8). Every other state at zero, or it is **STOP A**.

**Before the pull request** (the maquette wave's own gate — a maquette wave does not run `make check`; CI's `test` job is
the authority, `frontend-steward.md` measure 19): `make lint`; the full suite (`frontend/maquette/harness/run.sh`, not the
`--contracts` tier), expected no failure; the `--a11y` tier at 0 over the 22 new states;
`python3 scripts/harness-hold-counts.py --compare` with **`failed` read FIRST** (B-291 — the baseline is NOT re-recorded
while a rule is failing) and every movement written down; the pre-push pytest; `python3 scripts/check-intent-map.py`,
`python3 scripts/check-bug-register.py` and `python3 scripts/check-docs-cited-paths.py` read by OUTPUT, not by exit code
(B-346). The pull request bumps the version (patch) — the `version-bump` job enforces it — because it changes
`frontend/maquette/design/src/`.

**The steward is told BEFORE a full-suite run.** The harness is one per machine — `served_copy.py` is its lock and its
stamp (B-256) — and a rule that falls while another session held it is re-run alone before it is read, with the re-run's
loss of load said in the same breath (B-277, B-307).

**The « In flight » row is written when the pull request opens** — pull request number first, then the version;
`scripts/check-implementation-state.py` holds the row by both. **A DRAFT pull request runs no CI** (`CLAUDE.md` § Commit
Convention): open it READY, or add `run-ci-on-draft` and read the run that label dispatches — never both in one breath.

---

## What this plan believes the CONTRACT gets wrong

Recorded here as § 7.1 asks, and written in full in the design. **No file outside `docs/features/maquette-l22/` is edited
for it, except the one dated line under the L22 heading of `docs/reference/frontend-architecture.md`** — the steward
amends the plan and the operator amends the constitution and the map.

1. **« Nine organisation rulings »** — the L22 entry says its design is nine tenths dictated by the nine rulings of
   2026-09-15. **There are fifteen** (six of 2026-09-26, rulings 10–15), and « Done when » (« as the operator's nine rulings
   dictate ») reads short by six: the bar's composition, Système's place, the badges, the fourth tab.
2. **The constitution sentence the plan relied on is amended** (§ 20 point 3, § 16 point 3, § 17 point 4 — dictated
   2026-09-26) and the amendment is not on `main`; this design reads it from the operator's annex. The operator commits it.
3. **Ruling 2 revises L20's Q1 = B**, and L20's levers do not carry the two acts the pilot's bar carried
   (DESIGN § 1.2, OPEN 6): « leviers à Système › Pipeline depuis L20 » is true of five acts and not of « Lancer » and
   « Arrêter ».
4. **The Arrivées page held a live rule for Système** (DESIGN § 1.1): deleting it silently would have frozen the levers.
5. **Five sentences name the page, not two** (DESIGN § 1.6), and **the harness reads it in twenty-eight files, not
   thirty-three** (DESIGN § 1.5).
6. **The six clause-map rows and the README's cut table** name `features/arrivals` and « A medium in trouble → Arrivées »
   (DESIGN § 6.3): the operator amends the map; the close rewrites the README.
