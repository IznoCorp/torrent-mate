# L16 — §18, the ratio · PLAN

Design: `docs/features/maquette-l16/DESIGN.md`. Contract: `docs/reference/frontend-architecture.md`
§ 4, entry `#### L16 — §18, the ratio`.

**Written 2026-09-15 on `08400a22a`; re-measured 2026-09-26 on `dafe29ec1`; RE-CUT 2026-09-27 on
`5e5ecd052`** after organisation rulings 18–20 and rounds 7–9 of the coherence audit
(`review-archive/coherence-2026-09-27.md`, its triage `-triage.md` § C), which replace the design's
own surface (DESIGN § 0.1 says what moved). **This is not a renumbering of the prior fifteen
phases**: ruling 19 kills the tracker-detail screen (the prior phases 4, 5, 7, 8) outright and
replaces it with a two-tab page, so this plan is cut FRESH from the redrawn design, phase by phase,
not patched. Every phase file carries an **opening measure** taken on this head, by the commands a
STOP D would run on this tree, and the implementer re-takes each phase's figures at the moment that
phase opens — the tree will have moved again by L22b's landing.

**Where L16 opens in the order: after L22b.** L22b's phase 19 takes Système out of the bar, its
phase 25 deletes the `arr` row, and its own porting of round 8's Q20 puts Découvrir in the bar as a
third button (`docs/features/maquette-l22/plan/INDEX.md`; L22a = phases 1–14, L22b = phases 15–27).
The order is L13 · L22 · L16 · L17 · L18, and an upload-to-tracker lot (L23 proposed) is drawn ahead
of time in the second slot after L18 (round 8 Q18).

---

## THE PHASES CHAIN. THEY DO NOT PAUSE.

**The operator arbitrates the SCOPE, never the cadence.** A phase that finishes goes straight into
the next one — L12, L14, L19, L20, L21 and L22 each carry this paragraph for the same reason: the
chat gets compacted and this file does not.

**Self-check, at the end of every phase, before anything else:** « Am I about to report instead of
continuing? » If the answer is yes and the next phase exists, and none of the STOPs below is the
reason, **continue**. The only permitted halts are:

- **STOP A** — the oracle diverging on a state this wave did not touch.
- **STOP B** — the pull request.
- **STOP C** — an OPEN question of DESIGN § 5 the operator has not ruled. The phase does not choose:
  it asks the steward, with the question's two readings and what each costs the phase (its file
  says). **One phase reads one** — **phase 2** (OPEN 4, which tab opens by default). The design's
  earlier OPEN 1–3 are RULED (DESIGN § 5): they are read, not asked.
- **STOP D** — a measurement that contradicts a home the design decided. The phase re-takes its own
  figures before it moves anything; a figure that no longer supports the home is reported to the
  steward with the command, and the phase does not improvise a new home. **One is already known**:
  phase 4 (whether the tracker's policy fields compose through the settings panel's existing
  `setting` kind at a coarser subject, or through a block the Trackers feature registers itself —
  DESIGN § 3, § 4.2). **One more, inherited and re-read**: phase 11's seed for a card deferred for a
  reason no mock seed carries (DESIGN § 4.6), now across three kinds, not one.

**The placement of the trackers domain and its FORM are both ruled** (DESIGN § 5, « Ruled »):
organisation ruling 11 (a bar button, by rights), ruling 20 (inserted between Médiathèque and
Découvrir, four equal shares), ruling 19 (two tabs, « Torrents » and « Trackers », the accordion form
chosen here). None of this is a question this plan defaults on. Anything else believed necessary
outside the contract: STOP and ask the steward first.

---

## The rule that governs every phase

**Rule first, seen RED against `main`, then the move, then the same rule green with its holds
counted.** Here the red is the strongest form this repository asks for and needs no mutation:
**none of these surfaces exists on `main`**, so every hold fails there for the reason it was
written. Each phase says so explicitly, and the report records the red reading per rule. Where a
phase re-aims a rule an earlier phase wrote, the mutation comes after the move: break it on purpose,
confirm the rule falls and NAMES the right defect, restore.

**Commit BEFORE every mutation**, and mutate with `scripts/mutate.sh <file> <expression> <rule…>` —
by hand leaves the served copy of the PREVIOUS build in place (B-303). It cannot judge a GUARD
(B-273): a guard's exit code is read by hand.

**The labels `R-L16-a … R-L16-h` (DESIGN § 4.8) are NOT rule numbers.** `R225` is the highest in the
suite as measured at this re-cut (`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V
| tail -1`, run 2026-09-27 on `5e5ecd052`; it read `R201` at the prior re-read). **Phase 1 — the
first phase that writes a rule — re-takes that command against `origin/main` at the moment it runs
and binds every label to a number then**, writing the mapping into the report — a number taken from
this design without re-measuring is a collision, and L22 (whose `R-L22-a … t` take numbers too) runs
ahead of L16. The rule is written in the phase that first needs it and each later phase that re-aims
it says so.

**Every heavy run is wrapped in the machine's mutex** — `sh scripts/heavy.sh --class browser|test|rule
l16 <command>` — with no `HEAVY_LOCK=` override; the harness is one per machine and `sh
scripts/heavy.sh --held` names its holder. A run holding the lock is announced to the steward in one
line before it starts and one after (« done, exit N »). Output to a FILE, exit code read in the same
tool call, **never `| tail -N` on a long gate**. Kill what you start, prove it with `ps`.

**The engine gains no line.** This lot draws an entirely new domain (`features/trackers/` does not
exist — `ls frontend/maquette/design/src/features/` names `account`, `acquisition`, `arrivals`,
`library`, `maintenance`, `media`, `releases`, `settings`, `system`, and no surface of the engine
answers any of §18's clauses) — there is nothing of this lot's subject in the engine to subtract, and
nothing is added to it either.

**Never `cd` into `frontend/maquette/design/src`** (B-384) — absolute paths from the worktree root.

**Documents are added BY FILE**: `git add docs/features/maquette-l16/<name>.md`, never the folder
(B-304 — a directory add once swept `node_modules` into a commit). **No `git stash`** in this
repository, ever.

**A renamed identifier goes through `scripts/rename-identifiers.py`**, never by hand and never by an
ad-hoc regex (`CLAUDE.md` § Code Conventions).

---

## Points, and the mean (measures 11 and 19)

**A phase carries at most 15 points at its opening** (measure 11: the context budget; measure 19:
the cadre). The scale L22's plan declared, once, so every figure in a phase file is reproducible:

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

A new file's length is estimated from the nearest measured analogue, named in the phase
(`features/account/page.tsx` 79 non-blank lines, `features/system/locks.tsx` 141,
`features/settings/panel-field.tsx` 182, `ui/disclosure.tsx` 34); the opening re-measure replaces
the estimate with the file as it stands. Halves are rounded up.

**The pre-cut clause.** A phase whose re-measure at its opening exceeds 15 is CUT at that opening,
never begun; the plan's numbers after it shift by one and the steward is told. **Two removal phases
are split by KIND of change, not by appetite** (6 and 7): the write and its default confirmation
first, the shared-files consequence and the external-removal read second — the same cut the design's
own release-and-external-removal split made under the prior reading.

| # | Phase | What it lands | Rules | Points |
| ---: | --- | --- | --- | ---: |
| 1 | [The reads' contract](phase-01-reads-contract.md) | the tracker summary (ratio, volumes, trend, the alert threshold, the refused-identifier health fact), the obligations, the extended downloads (per-entry tracker, ratio-on-size, deadline, origin) — seeded and mocked; the demands filed | — | 14 |
| 2 | [The Trackers page and its two tabs](phase-02-the-page-and-tabs.md) | the bar button (inserted between Médiathèque and Découvrir), the route, the two dials (`tab`, `tracker`), the page shell; **STOP C** on the default tab | h | 15 |
| 3 | [The « Trackers » tab — one entry per tracker](phase-03-trackers-tab.md) | the roster, collapsed: ratio, trend, volumes, never averaged; its states | a | 13 |
| 4 | [The tracker's policy and alert threshold](phase-04-trackers-tab-policy.md) | `min_ratio` / `min_seed_time` / the alert threshold, set from the entry that shows the ratio, through the SAME write Réglages already uses; **STOP D** on how the three fields compose | b | 13 |
| 5 | [The « Torrents » tab — every active entry, once](phase-05-torrents-tab.md) | one row per qBittorrent entry, any tracker, with its ratio on that tracker's size, its origin colour, its obligation marks, a path to the media sheet, a tracker filter | a (re-aimed) | 14 |
| 6 | [Retirer de qBittorrent](phase-06-remove-from-qbittorrent.md) | the removal operation, the verb, a default confirmation (files deleted, checked by default) | c | 15 |
| 7 | [The removal's shared files, and the external read](phase-07-remove-shared-files.md) | the grouped removal across shared entries, the confirmation's consequence and hit-and-run naming; a torrent removed by hand in qBittorrent reads as simply gone | c (re-aimed) | 9 |
| 8 | [The ratio alert on the page](phase-08-alert-on-page.md) | one derivation, three components (threshold, breach, refused identifier), read at the entry and the row | d | 12 |
| 9 | [The ratio alert on the bar](phase-09-alert-on-bar.md) | the Trackers tab's badge, the stream's ratio and obligation events claimed | d (re-aimed) | 10 |
| 10 | [Acquisition's panel drops its hard-coded ratio facts](phase-10-panel-more-drops-ratio.md) | « Ratio global » and « Obligations en cours » removed from the « ⋮ » sheet | — | 4 |
| 11 | [A card deferred names its tracker](phase-11-card-deferred-reason.md) | the deferral reason read for all three DOIT-2 kinds (ratio, space, missing), a tracker link for the ratio kind; **STOP D** on the seed | g | 13 |
| 12 | [The ranking's contract](phase-12-ranking-contract.md) | the preview operation declared and mocked, the ratio-derived criterion field filed | — | 9 |
| 13 | [The ranking editor reads the saved weights](phase-13-ranking-editor-reads.md) | `/settings/ranking`; the criteria READ from `ranking.json5`, never invented; the rubric's and the toast's dead ends both close | f | 15 |
| 14 | [The ranking editor saves](phase-14-ranking-editor-saves.md) | the save through `updateConfigurationFile`, the conflict read | f (re-aimed) | 10 |
| 15 | [The live preview](phase-15-live-preview.md) | the preview panel, excluded rows sunk and still visible; B-298's promise kept | e | 9 |
| 16 | [The close](phase-16-close.md) | the map, the register, the README's cut-table row, the states counted, the report | — | 8 |

**Opening measures (2026-09-27, on `5e5ecd052`), each phase file's own head**: 14, 15, 13, 13, 14, 15,
9, 12, 10, 4, 13, 9, 15, 10, 9, 8 — **sum 183 over 16 phases, mean ≈ 11.4, max 15** (phases 2, 6, 13).
The prior re-read, on `dafe29ec1`, read 181 over 15 phases, mean ≈ 12.1. **Every phase from 4 onward
changed**, for one reason: **ruling 19 replaces the tracker-detail screen with a two-tab page**, so
the prior phases 4 (the head), 5 (the lists), 7 (the release verb) and 8 (the external removal) have
no surface left to draw — their substance is redistributed across the new phases 3–7, and the prior
9–15 shift down while gaining two new phases this redraw's own findings require: **phase 10** (F17,
`panel-more.ts`'s hard-coded ratio facts, no home in the prior plan) and **phase 11's** three-kind
generalisation (F14) replacing the prior single-kind phase.

---

## Why sixteen phases, and what a phase costs

**A phase is a unit of attribution, not a gate.** Each is ONE commit (two where the phase says
« commit before the mutation »), and its gate is the contracts tier plus the oracle — minutes, not
the full suite. The full gate runs ONCE, before the pull request (STOP B). The count follows from two
rules, not from appetite: **one kind of change per phase** (a declaration, a page, a write and a read
cannot share a commit) and **the 15-point ceiling**.

**The contract is FIRST**, and it is the reads only. Every surface below calls one of its operations,
and the demands filed there (DESIGN § 2.3) are what make the divergences decisions rather than
discoveries. **A write's operation is declared in the phase that draws its surface** (the removal in
6, the ranking's save reuses an EXISTING operation so it declares nothing new in 14): two writes more
in phase 1 would have crossed the ceiling, and a verb declared before its first caller is an
operation with no reader to prove it.

**The page and its tabs come before either tab holds anything** (2 before 3), so the bar's shares,
the two dials and the route are proved on their own — the same cut L22 made between its phases 8 and
9, and the same reason the prior reading's phase 2 gave.

**« Trackers » comes before « Torrents »** (3–4 before 5) because a torrent's row on the Torrents tab
names the SAME ratio and the SAME alert the Trackers-tab entry already draws (§13 — one derivation
proved once, read a second time, never invented twice for the second tab).

**The tracker's policy (4) comes before the Torrents tab's marks (5)**, not the reverse, because a
row's « en infraction » mark and the ratio it draws are read against the SAME threshold and floor
the policy phase puts on screen — proving the write before the read that depends on it, per the
same discipline the prior reading held between its phase 6 and 7.

**The removal (6–7) comes after both tabs**, not before: the confirmation names what is lost against
the policy already on screen (6), and the shared-files consequence (7) needs entries from more than
one tracker to name, which only exists once the Torrents tab draws every active entry (5). **It is
split in two** (6, 7) for the same KIND-of-change reason the prior release/external-removal split
gave: a WRITE with its own confirmation, then a READ of a state (the external case) and an EXTENSION
of that write's own hold (the grouped removal) — two different kinds, cut apart rather than forced
into one phase over the ceiling.

**The alert (8–9) comes after the removal** because its third component — an obligation in breach —
is drawn on rows the removal phase's own hold (a removed row disappears) must not contradict: proving
the alert against a Torrents tab whose removal already works avoids re-opening 8 or 9 when 6–7 land
later. **The page (8) precedes the bar (9)** because the bar's badge is a further reader of a fact
the page's two readers already read from one field; **the bar's badge and the stream's claim share
phase 9** because the badge is the reason the stream must be claimed.

**`panel-more.ts`'s fix (10) comes right after the alert lands**, not before: removing « Ratio global »
without the Trackers page yet existing would leave the operator with strictly less than today: no
hard-coded fact AND no real one to replace it. Once phase 9 lands, the real surface exists to point
the operator toward, even though this phase draws no `crossReference()` of its own (DESIGN's own
choice: remove, do not replace with a link — § 4.9 of the design's reasoning under phase 10's file).

**A card's ratio reason (11) comes after the alert**, not only after the removal, because it names a
tracker the operator can now open and a threshold he can now read — the same ordering reason the
prior reading gave its own phase 11.

**The ranking (12–15) is the last of the behaviour phases**, unchanged in its own internal ordering
from the prior reading, because it is the one surface this lot draws outside `features/trackers/`
(DESIGN § 4.7) and its demand (a ratio-aware criterion) is not needed by anything earlier. **It is
FOUR phases, not three**: F16 splits what the prior reading folded into one screen phase into a READ
(13) and a SAVE (14), because a screen that reads a real file and a screen that writes one back are
two different kinds of change, and the read must be proved (and its dead ends closed) before a save
that reads back what it wrote can be proved against it.

**The close is last** and re-reads the map, the register and `frontend/maquette/README.md`'s cut
table rather than trusting what the phases claimed, per every prior lot's own closing convention —
and per C9, it is the phase that writes the README's own missing row, not L17's close.

---

## Gates

**Per phase**: `sh scripts/heavy.sh --class rule l16 frontend/maquette/harness/run.sh --contracts` —
the contract rules AND the repository's cheap guards — and the oracle, with divergences ONLY on the
states DESIGN § 4 names for that phase, each accepted with its written reason (D8). Every other state
at zero, or it is **STOP A**.

**Before merging**: the full suite (`frontend/maquette/harness/run.sh`, not the `--contracts` tier),
expected no failure; the `--a11y` tier at 0 over the new named states; `scripts/harness-hold-counts.py
--compare` with **`failed` read FIRST** (B-291) and every movement written down; `python3
scripts/check-intent-map.py` and `python3 scripts/check-bug-register.py` read by OUTPUT, not by exit
code (B-346). Per measure 19 (`frontend-steward.md`), **no local `make check`** before the pull
request — CI's `test` job is the authority; the pre-PR gate is `make lint` + the full harness suite +
`--a11y` + `--compare` + the pre-push pytest.

**The steward is told BEFORE a full-suite run.** The harness is one per machine — `served_copy.py` is
its lock and its stamp (B-256) — and a rule that falls while another session held it is re-run alone
before it is read, with the re-run's loss of load said in the same breath (B-277, B-307).

**The « In flight » row is written when the pull request opens** — pull request number first, then
the version; `scripts/check-implementation-state.py` holds the row by both.

---

## What this plan believes the CONTRACT gets right, and where it goes further

Recorded here as § 7.1 asks — this design finds no clause of `frontend-architecture.md`'s L16 entry
that has lost its subject, only gaps the contract does not yet name (DESIGN § 2.3, filed as demands,
not asserted), and stale claims the audit found and this redraw corrects in the SAME PR (C10). **No
file outside `docs/features/maquette-l16/` is edited for it, but the entry's own paragraphs this
redraw amends** are listed in the entry itself, per this PR's scope item 3.

1. **DESIGN § 2.3 items 1–3** — the tracker-level summary (with the alert threshold and the refused
   identifier), the per-entry tracker/ratio/deadline/origin, is left to phase 1's own measurement of
   where the mock can carry it without breaching `acquisition.ts`'s 400-line ceiling
   (`grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/handlers/acquisition.ts` → 395 on
   `5e5ecd052`).
2. **DESIGN § 2.3 item 4** — the ranking's ratio-aware field is a NEW demand this design proposes; the
   map does not send it to L16 today (`product-intent-map.md`'s DOIT-13 row names the two existing
   reads only, after F14 drops `stalled-grabs` as this lot's own operation).
3. **The contract's entry defers the bar-or-drawer question and understates the policy write** — both
   corrected in this PR's own edit to `frontend-architecture.md` § 4 (C10): the bar, by rights, with
   Trackers inserted before Découvrir (ruling 20); the write already exists
   (`updateConfigurationFile`), only the alert-threshold key is new (F11).
4. **The contract's « Done when » wants the ratio events claimed by a rule** (R91's fan-out). Phase 9
   does it, and removes the four names from `acquisitionLiveExemptions`.
