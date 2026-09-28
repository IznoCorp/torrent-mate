# L22 — Arrivées dans Acquisition · PLAN

Design: `docs/features/maquette-l22/DESIGN.md`. Contract: `docs/reference/frontend-architecture.md` § 4, entry
`#### L22 — Arrivées dans Acquisition` (its « Where it lives » and « Done when » lines).

**Written 2026-09-26 on `origin/main` at `94a369879`, before the lot opens; re-measured the same day on `ba6a36cc9` after the
operator's eleven rulings on the design's OPEN questions (DESIGN § 7.2).** Every phase file carries an **opening measure**
(auditor's order 42) taken on THAT head, by the commands a STOP D would run on this tree; a phase the rulings touched
carries a « Re-measured » line that says which ruling moved it. The frontend tree did not move between the two heads
(`git diff --stat 94a369879 ba6a36cc9 -- frontend/maquette scripts config.example` → empty; only documents changed), so a
figure taken on the first is the figure on the second. The lot's implementer re-takes each phase's figures at the moment
that phase opens (the head will have moved) and reports a difference before moving anything.

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
  improvise a new home. **Three are already known**: phase 9 (the tunnel-error section has no real seed row), phase 10 (nor
  has the Plex-match section) and phase 13 (how many of the sixteen walks that arrive at Acquisition unnamed fall when the
  default tab changes).

**The eleven OPEN questions are ruled (DESIGN § 7.2, the operator's round of 2026-09-26); none is a STOP and none waits.**
Each phase the rulings touch says which one moved it: OPEN 1 (the tabs read « Suivis · En cours · À traiter · Découvrir »)
in phase 8; OPEN 2 (the bar draws only its present buttons, in equal shares of 1/n — a frame rule) in phase 19, and read
again in phase 37; OPEN 3 (an arrival is never in « Suivis ») in phases 6 and 17; OPEN 4 (eight rungs) in phases 4 and 5;
OPEN 5 (`/arrivals` is the not-found page) in phase 37; OPEN 6 (« Lancer » and « Arrêter » die, the four harness rules
re-aim out loud) in phases 35 and 37; OPEN 7 (the progression dies with « Suivant ») in phase 14; OPEN 8 (Système's badge
counts maintenance facts AND the machine's faults) in phase 28; OPEN 9 (« Confirmer » and « Corriger » on the Plex match)
in phase 10; OPEN 10 (« Abandonner » quarantines, after a confirmation naming the medium) in phase 11; OPEN 11 (the
reassign gesture is L18's) in phase 7. **Ruling 9 and 10 are why phase 9 of the first drawing is now three phases** (9, 10,
11): see « Points, and the mean ».

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
numbers after it shift by one and the steward is told. **The clause was applied once while the rulings were transcribed**: the
first drawing's phase 9 stood at 14, and the rulings on OPEN 9 and 10 added a verb on the Plex match (with its contract
operation and its mock) and a quarantine with its confirmation — well over 15 — so it was CUT, in this plan and not at its
opening, into phases 9, 10 and 11, and every number after it shifted by two. Three phases are drawn AT the ceiling (5, 19 and 31,
15 each) and say what to cut.

| # | Phase | What it lands | Rules | Points |
| ---: | --- | --- | --- | ---: |
| 1 | [The contract](phase-01-contract.md) | arrival cards, the ladder's optional fields, the reclassification and the non-media destinations declared; the mocks that MOVE; the demands regenerated; the rule labels bound to numbers | — | 12 |
| 2 | [The candidates screen changes hands](phase-02-resolution-changes-hands.md) | the screen, its cards, its vocabulary, its verbs, its decision reads and its live rules move to Acquisition; the parent of `/resolution/$folder` becomes `acq` | n | 13 |
| 3 | [The two surviving states take their names](phase-03-states-take-their-names.md) | `arr-resolution` → `acq-resolution-none`, `arr-decision` → `acq-resolution-tie`; ten rule files re-aimed; the states' home `harness/states/tunnel.ts` | — | 8 |
| 4 | [The strip counts its cells](phase-04-strip-counts-its-cells.md) | the card strip takes N cells, an optional label, two more cell states — the ladder's eight are the first consumer (OPEN 4) | unit | 6 |
| 5 | [One ladder, two readers](phase-05-one-ladder.md) | **eight** rungs from ONE source, read by the card (« n sur 8 ») and the journey sheet, which opens « rangé » into its three steps (OPEN 4; was 14) | f | 15 |
| 6 | [Arrivals join « En cours »](phase-06-arrivals-join-en-cours.md) | the arrival family draws — in « En cours » or « À traiter », never in « Suivis » (OPEN 3); a card without identity; a card `waiting` | g | 14 |
| 7 | [The requester line](phase-07-the-requester-line.md) | « ajouté par Izno, dans qBittorrent », from the answer — the line only, the reassign gesture is L18's (OPEN 11) | k | 7 |
| 8 | [The fourth tab exists, and fits](phase-08-the-fourth-tab.md) | « À traiter » as a tab, empty, in the order « Suivis · En cours · À traiter · Découvrir » (OPEN 1); four labels at 390 px | e | 8 |
| 9 | [« À traiter » holds its cards](phase-09-todo-holds-its-cards.md) | two sections (to resolve, tunnel error) with « Résoudre → » and « Relancer »; the `blocked` section leaves « En cours »; **STOP D on the error seed** (was 14 with three sections and both acts; cut by OPEN 9 and 10) | h | 13 |
| 10 | [The Plex match is confirmed or corrected](phase-10-the-plex-match-confirms-or-corrects.md) | the third section; « Confirmer » and « Corriger » on the match; demand E filed and mocked; **STOP D on the Plex seed** (new, OPEN 9) | t | 13 |
| 11 | [« Abandonner » quarantines](phase-11-abandonner-quarantines.md) | `discardStagedMedia` re-declared and mocked; the confirmation that names the medium; the card leaves « À traiter » (new, OPEN 10) | u | 12 |
| 12 | [The badge and the count](phase-12-the-badge-and-the-count.md) | the bar's badge counts « À traiter » alone; R16 re-aimed | b | 6 |
| 13 | [The default tab](phase-13-the-default-tab.md) | the tab opened by default — which may be the third of the row; the walks that land unnamed re-run | a | 13 |
| 14 | [« Suivant » dies](phase-14-suivant-dies.md) | the button, its verb and its progression « n sur m en attente » go; one returns to « À traiter »; R57's hold inverted (OPEN 7; was 11) | d | 13 |
| 14-bis | [« En cours » holds « En vol » alone](phase-14b-en-cours-holds-en-vol.md) | added 2026-09-26 (DESIGN § 7.3): the three sections leave « En cours », « rien en cours », `acq-card-rungs` re-anchored — a REMOVAL | v | 14 |
| 14-ter | [« Récupérer maintenant » lives on the follow's sheet](phase-14c-recuperer-on-the-follow.md) | added 2026-09-26 (DESIGN § 7.3): « trouvé, récupéré à la prochaine passe, à <heure> » and the act on the sheet | w | 9 |
| 15 | [« Laisser tel quel » means later](phase-15-laisser-tel-quel-is-later.md) | the card is kept, set aside, in « Mis de côté »; R57's leave half re-aimed | i | 14 |
| 16 | [« Ce n'est pas un média »](phase-16-not-a-media.md) | the new exit, its choice, its reclassification | j | 13 |
| 17 | [« Suivre », proposed](phase-17-suivre-proposed.md) | the offer on an arrived series, never done unasked; no arrival card in « Suivis » (OPEN 3) | l | 8 |
| 18 | [A film's follow ends alone](phase-18-film-follow-ends.md) | the follow leaves « Suivis » at the last rung | m | 10 |
| 19 | [Système leaves the bar](phase-19-systeme-leaves-the-bar.md) | `sys` out of the bar, into the drawer; five readers re-aimed; **the bar's frame rule: only the present buttons, in equal shares of 1/n** (OPEN 2; was 12) | q, s | 15 |
| 19-bis-a | [« Découvrir » becomes a bar page](phase-19-systeme-leaves-the-bar.md) | BUILT 2026-09-27 (RULINGS 18, 19, 20; round 8 Q20): the page is born, the bar at four until phase 37 | R234 | ≈ 10 |
| 19-bis-b | [« Découvrir » leaves Acquisition's tabs](phase-19-systeme-leaves-the-bar.md) | BUILT 2026-09-27: the tab dies, three tabs, the `acq-discover*` ids renamed by the tool | R206, R202 | ≈ 10 |
| 20 | [The `waiting` tone reads its own text token](phase-20-the-waiting-tone-reads-its-text.md) | was « 18-ter » (round 8 Q19): `--color-waiting-text`, phase 18's state back | R230 | ≈ 8 |
| 21 | [A pull begun on a card refreshes](phase-21-a-pull-begun-on-a-card-refreshes.md) | B-556: the pull is no longer excluded on a swipe row; every list pulled from ON a card | new | ≈ 8 |
| 22 | [Three tabs and a lit badge fit at 390 and 369 px](phase-22-three-tabs-fit.md) | B-557 (A4 of round A22, already repaired by 19-bis-b): the proof, badge lit with the longest plausible count | new | ≈ 5 |
| 23 | [« Supprimer » deletes a set-aside folder for real](phase-23-supprimer-deletes-for-real.md) | was « 15b » (round 8 Q16): the deletion, its confirmation naming the folder (neutral case), demand F — cut at its opening (≈ 31 → 23, 24, 25) | R227 | ≈ 15 |
| 24 | [The confirmation reads its case at the gesture](phase-24-the-case-read-at-the-gesture.md) | M2: the case read from qBittorrent when the confirmation opens; three wordings | R227 | ≈ 12 |
| 25 | [`notFound` and `doneToday` leave the contract](phase-25-not-found-and-done-today-leave-the-contract.md) | F40, a move | — | ≈ 7 |
| 26 | [Paused follows fold at the end of « Suivis »](phase-26-paused-follows-fold.md) | was « 18-bis » (round 8 Q17): the fold, the pill dies | R233 | ≈ 12 |
| 27 | [The Plex match waits on a disagreement](phase-27-the-plex-match-waits-on-a-disagreement.md) | triage F3: only a disagreement waits, « Corriger » through demand E, « Confirmer » lays the rung done | t, R230 | ≈ 14 |
| 28 | [Every badge row declares its reads](phase-28-the-menu-buttons-badge.md) | BUILT 2026-09-27 (F1 + C2, cut at the opening): the frame observes each drawn row's reads; the original row was | the badge on the static header's button, one derivation counting the maintenance facts AND the machine's faults (OPEN 8; was 12) | c | 13 |
| 29 | [The boot list becomes the rows' declarations](phase-28-the-menu-buttons-badge.md) | a MOVE, cut out of 28 at its opening: `engine-data.ts`'s staging and queue prefetch pass into `useBadgeReads` | R236 | ≈ 8 |
| 30 | [The menu button's badge](phase-28-the-menu-buttons-badge.md) | cut out of 28 at its opening: `systemBadge`, Système's declared reads, the button; M3's no-rights half | c | ≈ 14 |
| 31 | [A direct-add card lived no rung before « arrivé »](phase-31-a-direct-add-card-lived-no-rung-before-arrival.md) | triage F5, after the MIDPOINT: a domain-free cell state, no borrowed time | f, k | ≈ 10 |
| 32 | [The follow sheet searches live](phase-32-the-follow-sheet-searches-and-grabs.md) | BUILT 2026-09-27 (F6, R237; cut at the opening); the original row was | triage F6 + F42: `searchForFollow`, the per-follow grab, `takeQueued` retires | new, R225 | ≈ 16, likely cut |
| 33 | [« Récupérer maintenant » through the per-follow grab](phase-32-the-follow-sheet-searches-and-grabs.md) | F42, cut out of 32 at its opening: `grabForFollow` re-declared on the backend's meaning, the picker's operation filed as a demand, `takeQueued` retires | R225 | ≈ 8 |
| 34 | [« Abandonner » on a follow's card](phase-34-abandonner-on-a-follows-card.md) | M1: the release set aside, another searched; round 10 Q6's dated line | u | ≈ 9 |
| 35 | [One item, one card](phase-35-one-off-acquisitions.md) | BUILT 2026-09-28 (round 10 Q1's real half, R238, RULINGS 27; cut at the opening); the original row was | round 10 Q1 + Q2: a hand-added arrival joins the follow it matches; a season of an unfollowed series is one-off | new | ≈ 16, likely cut |
| 36 | [A season of an unfollowed series is one-off](phase-35-one-off-acquisitions.md) | BUILT 2026-09-28 (R158 re-aimed; cut at the opening); the original row was | round 10 Q2, cut out of 35 at its opening: taking a season of an owned, unfollowed series creates a one-off acquisition, never a follow; L21's form reopened, its readers re-aimed | new | ≈ 10 |
| 37 | [A one-off season's card offers « Suivre »](phase-35-one-off-acquisitions.md) | round 10 Q2's second half, cut out of 36 at its opening: the offer reads the one-off card, not only the arrivals | l | ≈ 6 |
| 38 | [The sentences that sent the reader to Arrivées](phase-38-the-five-sentences.md) | five sentences rewritten; Acquisition's cross-reference dies | p | 13 |
| 39 | [Readers re-aimed: the page's states](phase-39-readers-the-pages-states.md) | thirteen rule files and one state file leave `arr-*` | — | 14 |
| 40 | [Readers re-aimed: identity and launch bar](phase-40-readers-identity-and-launch-bar.md) | ten files leave the page's id, its path and its `data-pipe`; the four rules that started a pass by finger re-aim, out loud (OPEN 6); `journey.py`, a reader the first drawing missed (was 14) | — | 15 |
| 41 | [The live rule Système was borrowing](phase-41-the-live-rule-systeme-was-borrowing.md) | the pipeline-status rule moves to Système | r | 5 |
| 42 | [The death of Arrivées](phase-42-the-death-of-arrivees.md) | page, route, row, keys, states, launch bar removed; `/arrivals` is the not-found page (OPEN 5); the bar reads at two; the residual grep at zero | o | 12 |
| 43 | [The records of a dead page](phase-43-the-records-of-a-dead-page.md) | regions, oracle, accessibility, ratchets, fixture register | — | 10 |
| 44 | [The close](phase-44-the-close.md) | the register, the README, the debts, the report | — | 9 |

**Opening measures (2026-09-26, on `ba6a36cc9`, after the eleven rulings; auditor's order 42), each phase file's own head**:
12, 13, 8, 6, 15, 14, 7, 8, 13, 13, 12, 6, 13, 13, 14, 13, 8, 10, 15, 13, 13, 14, 15, 5, 12, 10, 9 — **sum 304 over 27
phases, mean ≈ 11.3, max 15** (phases 5, 19 and 23), none above measure 19's 15-point ceiling, 1 cut at this writing (the first
drawing's phase 9 became 9, 10 and 11; every number after it shifted by two). The first drawing, on `94a369879`, read 12, 13,
8, 6, 14, 14, 7, 8, 14, 6, 13, 11, 14, 13, 8, 10, 12, 12, 13, 14, 14, 5, 12, 10, 9 — sum 272 over 25 phases, mean ≈ 10.9,
max 14. **Six of the first drawing's 25 rows changed their figure** — phase 5: 14 → 15 (OPEN 4); phase 9: 14 → 13 (cut by OPEN 9
and 10); the former phase 12, now 14: 11 → 13 (OPEN 7, and two readers the first drawing charged that read nothing); the former 17,
now 19: 12 → 15 (OPEN 2); the former 18, then 20, now 24: 12 → 13 (OPEN 8); the former 21, then 23, now 31: 14 → 15 (OPEN 6 moved its drawing, and the
re-measure found a ninth reader) — and **two rows were born**, phases 10 (13) and 11 (12). The other nineteen kept their figure
and, from phase 12 on, changed number; the phase files the rulings touched say so in a « Re-measured » line, the others only
changed number.

---

## Why twenty-seven phases, and what a phase costs

**A phase is a unit of attribution, not a gate.** Each is ONE commit (two where the phase says « commit before the
mutation »), and its gate is the contracts tier plus the oracle — minutes, not the full suite. The full gate runs ONCE, before
the pull request (STOP B). The count follows from two rules, not from appetite: **one kind of change per phase** (a move
and a redraw cannot share a commit) and **the 15-point ceiling** (a phase that would exceed it is cut, as phases 4, 7, 12
and 13 were cut out of larger ones while this plan was written).

**The contract is first** because `scripts/compare-contracts.py --check` refuses the three artefacts apart and because the
demands are what make the design's proposals decisions rather than discoveries.

**The candidates screen moves BEFORE anything is redrawn** (phase 2), so every later phase draws in Acquisition's own
feature; and its two states are renamed in a phase of their own (phase 3) so a rename never shares a commit with a move.

**The primitive is its own phase** (4) so the ladder's oracle divergence names the ladder alone. **The ladder precedes the
arrivals** (5 before 6) because the arrival cards ARE ladder cards; **the requester line follows** (7) because it is a line
ON that card.

**The tab exists before it holds** (8 before 9) so the four-label fit at 390 px is proved on its own; **it holds before the
badge counts it** (9, 10 and 11 before 12) and **the badge before the default rule reads it** (12 before 13) — the default tab
reads a count that must already be right.

**« À traiter » is filled in three phases, cut by the KIND of change** (9, 10, 11): the tab and the two sections whose acts
exist today (« Résoudre → », « Relancer ») come first; then the Plex-match section with its verbs, which needs a contract
operation and its mock (demand E); then « Abandonner », which needs a re-declared operation and a confirmation. A card is
never drawn with a foot that does nothing, so each act lands WITH its section or after it, never before.

**The return to the list and « Suivant » (14) come before the two new meanings** (15, 16): a resolution that returns to
the list is the floor on which « Laisser tel quel » and « Ce n'est pas un média » both land.

**« Suivre » before the follow's end** (17 before 18): the proposal creates the follows the ladder's last rung then ends for
films; the two are different kinds of change on one list.

**The bar and the drawer come after the surfaces they carry** (19, 20), so the badge counts something real — and the bar's
frame rule (R-L22-s) rides with the first phase that draws a bar of other than four buttons; **the sentences next** (21), so
nothing points at the page when it goes.

**The readers are re-aimed BEFORE the page dies** (34, 35), in two phases cut by what they read (the page's states / its
identity and the launch bar) — never by the count of the word (DESIGN § 1.5) — **so the death phase has zero readers to
break** and the residual grep is its gate. **The live rule moves BEFORE the death** (24): the page was holding it for
Système (DESIGN § 1.1).

**The death is its own phase** (25), **and the records of a dead page are another** (26): the memory the tooling keeps of
a page — regions, oracle, accessibility, ratchets — is not the page, and a ratchet that does not fall after a deletion is
a guard reading nothing.

**The close is last** (27) and re-reads the map and the register rather than trusting what the phases claimed.

---

## Gates

**Per phase**: the shared-lock `frontend/maquette/harness/run.sh --contracts` — the contract rules AND the repository's
cheap guards, the script prints how many of each — and the oracle, with divergences ONLY on the states DESIGN § 4.1 names
for that phase, each accepted with its written reason (D8). Every other state at zero, or it is **STOP A**.

**Before the pull request** (the maquette wave's own gate — a maquette wave does not run `make check`; CI's `test` job is
the authority, `frontend-steward.md` measure 19): `make lint`; the full suite (`frontend/maquette/harness/run.sh`, not the
`--contracts` tier), expected no failure; the `--a11y` tier at 0 over the new states (amended 2026-09-27, F50: the states the phases declared, counted at the close by the design's command, not « 23 »);
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
2. **The constitution sentences the plan relied on were amended** (§ 20 point 3, § 16 point 3, § 17 point 4 — « dicté le
   2026-09-26 ») and the amendment is on `main` since #611 (`455d3ab7e`); the design cites the constitution, not an annex.
3. **Ruling 2 revises L20's Q1 = B**, and L20's levers do not carry the two acts the pilot's bar carried
   (DESIGN § 1.2, OPEN 6): « leviers à Système › Pipeline depuis L20 » is true of five acts and not of « Lancer » and
   « Arrêter ». **The operator ruled on 2026-09-26 that those two acts die** with the bar (OPEN 6, A); no lever replaces them.
4. **The Arrivées page held a live rule for Système** (DESIGN § 1.1): deleting it silently would have frozen the levers.
5. **Five sentences name the page, not two** (DESIGN § 1.6), and **the harness reads it in twenty-eight files, not
   thirty-three** (DESIGN § 1.5).
6. **The six clause-map rows and the README's cut table** name `features/arrivals` and « A medium in trouble → Arrivées »
   (DESIGN § 6.3): the operator amends the map; the close rewrites the README.

---

## Amended 2026-09-26 (evening) — the operator's rounds 6 and 7 (DESIGN § 7.3)

- **Phase 13** reads the REPLACED default-tab rule: « Suivis » on the first opening, then the last tab opened from
  local storage (try/catch, « Suivis » on an empty or unreadable storage). Its file is amended on L22a's branch by its
  implementer (one dated line); R-L22-a is mutated on both cases.
- **Two phases are ADDED to L22a after phase 14** (the auditor's method decision, 23:2x): **14-bis** « En cours » holds
  « En vol » alone (≈ 14, a removal) and **14-ter** « Récupérer maintenant » lives on the follow's sheet (≈ 9) — both
  measured by the steward against L22a's branch and RE-TAKEN at their opening; rule labels v, w take the next free
  numbers (R224 and up — R223 is the repair train's).
- **Phase 15 (L22b)** reads ruling 16: « Mis de côté » is a FOLDED section at the END of « À traiter », outside its
  count and the bar's badge, where the operator sees, deletes (with a confirmation like the Médiathèque's), deletes
  from disk, or handles each item — re-measured at its opening.
- **L22a is now phases 1–14 plus 14-bis and 14-ter**: 153 + 23 = **176 points over 16 phases**; L22b is unchanged
  at 151 over 13 until phase 15's re-measure. The whole lot: **327 points over 29 phases, mean ≈ 11.3, max 15**.
- **Amended 2026-09-27 (RULINGS 9, l22a):** the order after phase 14 is **14-ter** (with the take path re-aimed onto the sheet: busy.py, actions.py, page_host.py), then **14-bis-a** (the readers re-anchored before the removal: one_ladder.py / `acq-card-rungs`, requester_line.py, release_candidates.py, R47 understood), then **14-bis-b** (the move, R224, the section readers) — every gate green.
- **Amended 2026-09-27 (L22b, steward):** phase 15 is cut at its opening into **15a** (the card set aside in the folded « Mis de côté », R226) and **15b** (« Supprimer » with its confirmation, R227); 15b waits for the operator's word on the delete's operation and runs after the phases that do not depend on it (16 onward), at the first unit boundary after the word.
- **Amended 2026-09-27 (L22b, steward, on the operator's rulings of the morning):** the order after phase 19 is **19-bis** « Découvrir » leaves Acquisition (a bar page, the bar at Acquisition · Médiathèque · Découvrir), **18-ter** the `waiting` tone's text token and the return of phase 18's state (RULINGS 16), **15b** « Supprimer » as a real deletion naming its case (copied / moved), **18-bis** paused follows fold at the end of « Suivis » (the « En pause » pill dies, R233), then 20 onward; each re-measured at its opening.
- **Amended 2026-09-27 (L22b, RULINGS 18):** 19-bis is cut at its opening into **19-bis-a** (the « Découvrir » page is born, the bar at four until 25, R234, the tab still drawn) and **19-bis-b** (the tab dies, R206 at three, R202's fallback, the eight `acq-discover*` ids renamed by the tool).


- **Amended 2026-09-27 (L22b, the coherence triage § B — F50, F51):** the phases still to build are numbered with **integers** (the operator's order 38): 18-ter → **20**, 15b → **21**, 18-bis → **22**, F3 → **23** (new), the menu button's badge 20 → **24** (HELD: F1 + C2 and M3 at its opening; the MIDPOINT full suite after it), F5 → **25** (new), F6 + F42 → **26** (new), M1 → **27** (new), round 10 Q1 + Q2 → **28** (new), and the former 21–27 → **29–35**. The phases built keep their names as history (15a, 19-bis-a, 19-bis-b); the measures of 2026-09-26 above keep the numbering of their date. The line « 15b waits for the operator's word » is superseded by the next (the word came: round 8 Q16 = B). **The phases to come, 20–35: ≈ 192 points over 16 phases** (estimates; each RE-MEASURED at its opening; 21, 26 and 28 likely cut), the ceiling 15 unchanged. The rows above carry them; DESIGN § 7.4 carries the rulings.

- **Amended 2026-09-27 (L22b, the steward, on the operator's two reports of ~15:05 on tm-design):** **B-556** « Onglet suivi : impossible de tirer pour rafraîchir » → phase **21**, **B-557** « Menu d'onglets: cassé voir capture » → phase **22**; every phase from the former 21 shifts by two (**23–37**). The phases to come are 21–37.
- **Amended 2026-09-27 (L22b, at phase 23's opening):** phase 23 re-measured ≈ 31 on `3551e8125` → CUT into **23** (the deletion), **24** (the case read at the gesture, M2) and **25** (F40); every phase from the former 24 shifts by two (**26–39**).
- **Amended 2026-09-27 (L22b, at phase 28's opening, steward accepted):** phase 28 re-measured ≈ 30 on `8a9500c43` → CUT into **28** (F1 + C2: each badge row declares its reads, the frame observes them per drawn row, R236), **29** (a MOVE: `engine-data.ts`'s boot list passes into those declarations) and **30** (the menu button's badge, M3's no-rights half); every phase from the former 29 shifts by two (**31–41**); the MIDPOINT full suite runs after 30.
- **Amended 2026-09-27 (L22b, at phase 32's opening):** phase 32 re-measured ≈ 16 → CUT into **32** (F6, the live search) and **33** (F42, the per-follow grab); every phase from the former 33 shifts by one (**34–42**). Phase 31 is held on RULINGS 25 (condition 3 only), and runs next.
- **Amended 2026-09-28 (L22b, at phase 35's opening):** phase 35 re-measured ≈ 16 → CUT into **35** (Q1's real half: one item, one card — RULINGS 27) and **36** (Q2); every phase from the former 36 shifts by one (**37–43**).
- **Amended 2026-09-28 (L22b, at phase 36's opening):** phase 36 re-measured ≈ 16 → CUT into **36** (the season is one-off, no follow) and **37** (its card offers « Suivre »); every phase from the former 37 shifts by one (**38–44**).
- **Amended 2026-09-28 (L22b, at phase 38's opening, steward accepted):** phase 38 re-measured ≈ 17 → CUT into **38** (the sentences, R239) and **39** (F7, the landing on « À traiter » by a dial the control carries); every phase from the former 39 shifts by one (**40–45**).
- **Amended 2026-09-28 (L22b, at phase 40's opening, steward approved):** phase 40 re-measured ≈ 30 → CUT into **40** (F41), **41** (the readers) and **42** (F53); every phase from the former 41 shifts by two (**43–47**).
- **Amended 2026-09-28 (L22b, at phase 41, steward approved — RULINGS 29):** R139's B-313 hold is set aside in 41 and given back in a NEW phase **42** on a posed case; F53 → **43**, the rest **44–48**.
- **Amended 2026-09-28 (L22b, at phase 43's opening, steward (A)):** F53's « check doc_fr_2026_final the same way » found the same case — no video file, and `personalscraper/sorter/file_type.py:178–200` types an archive-only folder a film only when its NAME carries a video-release signal (`_looks_like_video_release`), so it is OTHER, filed under 098-AUTRES, out of the acquisitions (ruling 1). **43** = the game folder out (as measured); a NEW **44** = doc_fr_2026_final out of `stuck-loaded.json`, its readers re-aimed out loud; the rest **45–49**.
- **Amended 2026-09-28 (L22b, at phase 45's opening, steward approved):** the readers phase (`phase-40-readers-identity-and-launch-bar.md`) re-measured ≈ 15 on `ed55084bd` → CUT by nature: **45a** the launch walks (R185, R184 `locks.py`, R77 `page_host.py`; OPEN 6 = A) and **45b** the page's identity (back, sweep, url_state, journey + common, R138's and R67's sentences); the rest **46–50** (the live rule, the death of Arrivées, the records of a dead page, the close).
- **Amended 2026-09-28 (L22b, at phase 47's opening, steward approved):** the death of Arrivées (`phase-42-the-death-of-arrivees.md`) re-measured ≈ 18 → CUT: **47a** the readers without a deletion (the three Acquisition messages renamed out of `verbs.arrivals`, R239's page name), **47b** the death — and the six `arr-*` ids leave the oracle reference and the three accessibility ledgers IN 47b, by named deletion, since removing the states file removes the states; the rest **48–50**.
