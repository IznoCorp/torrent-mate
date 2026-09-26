# L16 — §18, the ratio · PLAN

Design: `docs/features/maquette-l16/DESIGN.md`. Contract: `docs/reference/frontend-architecture.md`
§ 4, entry `#### L16 — §18, the ratio`.

**Written 2026-09-15 on `08400a22a`; re-measured 2026-09-26 on `dafe29ec1`** after the operator's organisation
rulings 10–15 and his ruling on L22's OPEN 2 (`docs/reference/operator-method.md`; the design's § 0.1 says what
each moved). Every phase file carries an **opening measure** taken on that head, by the commands a STOP D
would run on this tree, and a « Re-measured » line that says what moved its figure. The tree moved a great deal
between the two heads (`git diff --stat 08400a22a dafe29ec1 -- frontend/maquette scripts` → 92 files changed:
L13c and the lots after it merged), so no figure of the first drawing is carried over unread. **The lot's
implementer re-takes each phase's figures at the moment that phase opens** — L22 will have moved the tree again
— and reports a difference before moving anything.

**Where L16 opens in the order: after L22b.** L22b's phase 19 takes Système out of the bar and its phase 25 deletes
the `arr` row (`docs/features/maquette-l22/plan/INDEX.md`; L22a = phases 1–14, L22b = phases 15–27). Until
then the bar holds four buttons and a Trackers button would be a fifth; the lot never opens between the two
sub-lots. The order is L13 · L22 · L16 · L17 · L18.

---

## THE PHASES CHAIN. THEY DO NOT PAUSE.

**The operator arbitrates the SCOPE, never the cadence.** A phase that finishes goes straight into
the next one — L12, L14, L19, L20, L21 and L22 each carry this paragraph for the same reason: the chat
gets compacted and this file does not.

**Self-check, at the end of every phase, before anything else:** « Am I about to report instead of
continuing? » If the answer is yes and the next phase exists, and none of the STOPs below is the reason,
**continue**. The only permitted halts are:

- **STOP A** — the oracle diverging on a state this wave did not touch.
- **STOP B** — the pull request.
- **STOP C** — an OPEN question of DESIGN § 5 that the phase reads and the operator has not ruled. The phase does
  not choose: it asks the steward, with the question's two readings and what each costs the phase (its file says).
  Two phases read them — **phase 2** (OPEN 1, the bar row's home, and OPEN 2, the right that opens it) and
  **phase 10** (OPEN 1 again, and OPEN 3, what the tab's badge counts). **All three were ruled on 2026-09-26**
  (OPEN 1 = A, OPEN 2 = A, OPEN 3 = B, DESIGN § 5): they are read, not asked.
- **STOP D** — a measurement that contradicts a home the design decided. The phase re-takes its own figures
  before it moves anything; a figure that no longer supports the home is reported to the steward with the
  command, and the phase does not improvise a new home. **Two are already known**: phase 6 (the policy panel's
  address names the kind `setting`, which is the settings feature's — DESIGN § 3) and phase 11 (no card of the
  mock's seeds is deferred for ratio — DESIGN § 4.6).

**The placement of the trackers domain is ruled** (DESIGN § 5, « Ruled »: organisation ruling 11 — a bar button,
by rights). It is no longer a question this plan defaults on: the first drawing opened phase 2 « under Reading
B by default », and that reading is not what he ruled. Anything else believed necessary outside the contract:
STOP and ask the steward first.

---

## The rule that governs every phase

**Rule first, seen RED against `main`, then the move, then the same rule green with its holds
counted.** Here the red is the strongest form this repository asks for and needs no mutation:
**none of these surfaces exists on `main`**, so every hold fails there for the reason it was
written. Each phase says so explicitly, and the report records the red reading per rule. Where a phase
re-aims a rule an earlier phase wrote, the mutation comes after the move: break it on purpose, confirm the
rule falls and NAMES the right defect, restore.

**Commit BEFORE every mutation**, and mutate with `scripts/mutate.sh <file> <expression> <rule…>` —
by hand leaves the served copy of the PREVIOUS build in place (B-303). It cannot judge a GUARD
(B-273): a guard's exit code is read by hand.

**The labels `R-L16-a … R-L16-h` (DESIGN § 4.8) are NOT rule numbers.** `R201` is the highest in the suite as
measured at this re-read (`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1`,
run 2026-09-26 on `dafe29ec1`; it read `R194` on `08400a22a`). **Phase 2 — the first phase that writes a rule —
re-takes that command against `origin/main` at the moment it runs and binds every label to a number then**,
writing the mapping into the report — a number taken from this design without re-measuring is a collision, and
L22 (whose R-L22-a … t take numbers too) runs ahead of L16. The rule is written in the phase that first needs
it and each later phase that re-aims it says so.

**Every heavy run is wrapped in the machine's mutex** — `sh scripts/heavy.sh --class browser|test|rule l16
<command>` — with no `HEAVY_LOCK=` override; the harness is one per machine and `sh scripts/heavy.sh --held`
names its holder. A run holding the lock is announced to the steward in one line before it starts and one after
(« done, exit N »). Output to a FILE, exit code read in the same tool call, **never `| tail -N` on a long gate**.
Kill what you start, prove it with `ps`. (The first drawing carried an older recipe — a wave-owned lock, `HEAVY_LOCK=`
and `HEAVY_FREE_FLOOR_MB` — which `scripts/heavy.sh` now forbids under a named class.)

**The engine gains no line.** This lot draws an entirely new domain (`features/trackers/` does not exist —
`ls frontend/maquette/design/src/features/` names `account`, `acquisition`, `arrivals`, `library`, `maintenance`,
`media`, `releases`, `settings`, `system`, and no surface of the engine answers any of §18's clauses) — there is
nothing of this lot's subject in the engine to subtract, and nothing is added to it either.

**Never `cd` into `frontend/maquette/design/src`** (B-384) — absolute paths from the worktree root.

**Documents are added BY FILE**: `git add docs/features/maquette-l16/<name>.md`, never the folder (B-304 — a
directory add once swept `node_modules` into a commit). **No `git stash`** in this repository, ever.

**A renamed identifier goes through `scripts/rename-identifiers.py`**, never by hand and never by an ad-hoc
regex (`CLAUDE.md` § Code Conventions).

---

## Points, and the mean (measures 11 and 19)

**A phase carries at most 15 points at its opening** (measure 11: the context budget; measure 19: the cadre). The
first drawing scored each phase by a scale it did not state (its phase 1 stood at 10 for four operations declared,
five demands filed and the mocks; one operation was worth one point there). **This re-read declares the scale
L22's plan declared, once, so every figure in a phase file is reproducible**, and re-scores every phase by it:

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

A new file's length is estimated from the nearest measured analogue, named in the phase (`features/account/page.tsx`
79 non-blank lines, `features/system/page.tsx` 129, `features/system/run-list.tsx` 176, `features/settings/panel-field.tsx`
182); the opening re-measure replaces the estimate with the file as it stands. Halves are rounded up.

**The pre-cut clause.** A phase whose re-measure at its opening exceeds 15 is CUT at that opening, never begun; the
plan's numbers after it shift by one and the steward is told. **The clause was applied while this plan was
re-written**: on the scale, the first drawing's phases 2 (the list, its host), 3 (the detail), 5 (the release), 6 (the alert
and DOIT-2's reason) and 7 (the ranking editor) each crossed 15, and its phase 1 (the contract) crossed with them. They are cut
here, in the plan and not at an opening, by the KIND of change. Four phases are drawn AT the ceiling (2, 6, 7 and 13, 15 each)
and each says what to cut.

| # | Phase | What it lands | Rules | Points |
| ---: | --- | --- | --- | ---: |
| 1 | [The reads' contract](phase-01-reads-contract.md) | three operations declared — the tracker summary, the obligations, the downloads with their tracker, ratio and deadline — seeded and mocked; the demands filed | — | 14 |
| 2 | [The Trackers tab exists](phase-02-the-tab.md) | the navigation row **in the bar**, the route, the page shell; the bar reads three equal shares; the empty roster | h | 15 |
| 3 | [The roster](phase-03-roster.md) | one row per tracker — ratio, trend, volumes — never averaged; its four states | a | 13 |
| 4 | [A tracker's detail: the head](phase-04-detail-head.md) | `/trackers/$name`, its head repeating the row, its parent and its push | a, h | 13 |
| 5 | [The detail's obligations and active torrents](phase-05-detail-lists.md) | each with its deadline and its ratio owed against observed | a | 14 |
| 6 | [The policy panel](phase-06-policy.md) | the policy write declared and mocked; `min_ratio` / `min_seed_time` / the alert threshold set from the tracker's own screen; **STOP D** on the panel's address kind | d | 15 |
| 7 | [The obligation's release verb](phase-07-release.md) | the release operation, the confirmation naming what is lost | b | 15 |
| 8 | [An external removal is handled](phase-08-external-removal.md) | « Libérée — retrait externe », on a seeded obligation no call released | c | 8 |
| 9 | [The alert on the page](phase-09-alert-on-page.md) | one derivation read at the row, the block and the panel | e | 11 |
| 10 | [The alert on the bar](phase-10-alert-on-bar.md) | the Trackers tab's badge, the stream's ratio events claimed by this feature | e (re-aimed) | 11 |
| 11 | [A card deferred for ratio names its tracker](phase-11-card-ratio-reason.md) | `stalled-grabs` declared and mocked; « Voir le tracker » on the acquisition card; **STOP D** on its seed | g | 12 |
| 12 | [The ranking's contract](phase-12-ranking-contract.md) | the preview operation declared and mocked, the ratio-derived criterion field filed | — | 9 |
| 13 | [The ranking editor lists its criteria](phase-13-ranking-editor.md) | `/settings/ranking`; the rubric's dead end and the quality screen's toast close | — | 15 |
| 14 | [The live preview](phase-14-ranking-preview.md) | the preview panel, excluded rows sunk and still visible; B-298's promise kept | f | 9 |
| 15 | [The close](phase-15-close.md) | the map, the register, the states counted, the report | — | 7 |

**Opening measures (2026-09-26, on `dafe29ec1`), each phase file's own head**: 14, 15, 13, 13, 14, 15, 15, 8, 11, 11,
12, 9, 15, 9, 7 — **sum 181 over 15 phases, mean ≈ 12.1, max 15** (phase 10 re-read at 11 on the operator's
OPEN 3 = B, 2026-09-26) (phases 2, 6, 7 and 13), none above measure 19's
15-point ceiling. The first drawing, on `08400a22a`, read 10, 9, 11, 9, 13, 12, 13, 5 — sum 82 over 8 phases, mean 10.25,
max 13. **Every one of its eight rows changed**, for two reasons said apart: **the scale** (the first drawing's phases
1, 2, 3, 5, 6, 7 were scored on a scale it did not state, and the declared one puts each over 15 or near it — the cause of most
of the growth: phase 1 10 → 14, the list 9 → 15 + 13, the detail 11 → 13 + 14, the release 13 → 15 + 8, the ranking editor
13 → 9 + 15 + 9), and **the rulings** (three additions, each carried by the phase that says so: phase 2's
bar row and its rule, phase 10's tab badge, and phase 11's card in place of Arrivées' stuck row). One addition is the
first drawing's own gap, not a ruling's: the contract's « Done when » says the stream's ratio events are claimed by a rule
(R91's fan-out) and no phase of the first drawing claimed them — phase 10 does.

---

## Why fifteen phases, and what a phase costs

**A phase is a unit of attribution, not a gate.** Each is ONE commit (two where the phase says « commit before the
mutation »), and its gate is the contracts tier plus the oracle — minutes, not the full suite. The full gate runs
ONCE, before the pull request (STOP B). The count follows from two rules, not from appetite: **one kind of change per
phase** (a declaration, a page, a write and a read cannot share a commit) and **the 15-point ceiling**.

**The contract is FIRST**, and it is the reads only. Every surface below calls one of its operations, and the demands
filed there (DESIGN § 2.3) are what make the divergences decisions rather than discoveries — the same reason L20's
phase 1 opens its own plan. **A write's operation is declared in the phase that draws its surface** (the policy in 6,
the release in 7, the ranking preview in 12), which is L22's precedent (its phase 10 files the Plex-match verb): two
operations more in phase 1 would have crossed the ceiling, and a verb declared before its first caller is an
operation with no reader to prove it. The five demand rows are therefore filed across phases 1 (the summary read and the extended download), 6 (the policy write), 7 (the release verb) and 12 (the ratio-derived scoring field), each
by the phase that draws what it serves; phase 11's `stalled-grabs` is an existing operation the maquette declares, not a demand row.

**The tab exists before it holds** (2 before 3), so the bar's three equal shares and the route are proved on their own,
before any row is drawn; the same cut L22 made between its phases 8 and 9.

**The list comes before the detail** because a row's path needs a list to leave from. **The detail's head comes before its
lists** (4 before 5) so the address and its push are proved before what hangs off it.

**The detail comes before the policy panel** because the panel is a SCREEN STATE of the detail (DESIGN § 3) — a query
parameter on an address that must already resolve.

**The release verb comes after the policy panel**, not before it, though § 18 names the release first: the release
confirmation's own copy names what is LOST (the ratio still owed against the policy's `min_ratio`), so the phase that
draws it reads a policy the panel phase already put on screen. **The external removal is its own phase** (8) because it
is a READ of a state the interface must recognise without having caused it, seeded by hand: the same clause (§ 4.4), a
different kind of change.

**The alert on the page (9) precedes the alert on the bar (10)** because the bar's badge is a fourth reader of the fact
the first three already read from one field; **the tab's badge and the stream's claim share phase 10** because the
badge is the reason the stream must be claimed (it moves without a refetch). **A card's ratio reason (11) comes after
both** because it names a tracker the operator can now open and a threshold he can now read.

**The ranking is the last of the behaviour phases** because it is the one surface this lot draws outside
`features/trackers/` (DESIGN § 4.7, under the settings page by design), and because its ratio-aware criterion is a
demand the earlier phases do not need. **It is three phases** — its contract (12), its criteria (13), its live preview
(14) — because the screen alone is over the ceiling and the preview is the one part that calls an operation.

**The close is last** and re-reads the map and the register rather than trusting what the phases claimed, per every
prior lot's own closing convention.

---

## Gates

**Per phase**: `sh scripts/heavy.sh --class rule l16 frontend/maquette/harness/run.sh --contracts` — the contract rules
AND the repository's cheap guards — and the oracle, with divergences ONLY on the states DESIGN § 4 names for that
phase, each accepted with its written reason (D8). Every other state at zero, or it is **STOP A**.

**Before merging**: the full suite (`frontend/maquette/harness/run.sh`, not the `--contracts` tier), expected no
failure; the `--a11y` tier at 0 over the new named states; `scripts/harness-hold-counts.py --compare` with **`failed`
read FIRST** (B-291) and every movement written down; `python3 scripts/check-intent-map.py` and `python3
scripts/check-bug-register.py` read by OUTPUT, not by exit code (B-346). Per measure 19 (`frontend-steward.md`), **no
local `make check`** before the pull request — CI's `test` job is the authority; the pre-PR gate is `make lint` + the
full harness suite + `--a11y` + `--compare` + the pre-push pytest.

**The steward is told BEFORE a full-suite run.** The harness is one per machine — `served_copy.py` is its lock and its
stamp (B-256) — and a rule that falls while another session held it is re-run alone before it is read, with the
re-run's loss of load said in the same breath (B-277, B-307).

**The « In flight » row is written when the pull request opens** — pull request number first, then the version;
`scripts/check-implementation-state.py` holds the row by both.

---

## What this plan believes the CONTRACT gets right, and where it goes further

Recorded here as § 7.1 asks — this design finds no clause of `frontend-architecture.md`'s L16 entry that has lost its
subject, only gaps the contract does not yet name (DESIGN § 2.3, filed as demands, not asserted). **No file outside
`docs/features/maquette-l16/` is edited for it, but the entry's own line naming this design** (`frontend-architecture.md`
§ 4, « Design and plan written … ») **which this re-read amends**; the steward amends the rest.

1. **DESIGN § 2.3 items 1–3** — the tracker-level summary, the per-active-torrent tracker/ratio/deadline, and whether they
   are one read or two, is left to phase 1's own measurement of where the mock can carry it without breaching
   `acquisition.ts`'s 400-line ceiling (`grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/handlers/acquisition.ts`
   → 359 on `dafe29ec1`, 338 on `08400a22a`).
2. **DESIGN § 2.3 item 4** — the ranking's ratio-aware field is a NEW demand this design proposes; the map does not send it
   to L16 today (`product-intent-map.md`'s DOIT-13 row names the three existing reads only).
3. **The contract's entry defers the bar-or-drawer question to this design** (`frontend-architecture.md` § 4, L16, « Where it lives »: « the wave's design says which, drawn first »). The
   design now says: the bar, by rights (DESIGN § 5, « Ruled »). The entry's parenthesis stays true as written; nothing in it needs amending for the ruling.
4. **The contract's « Done when » wants the ratio events claimed by a rule** (R91's fan-out). No phase of the first drawing did
   it; phase 10 does, and removes the four names from `acquisitionLiveExemptions`.
