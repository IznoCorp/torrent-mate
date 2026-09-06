# L21 — where the wave stands, for whoever picks it up

Written at 54 % context by the session that opened the lot. Read `BRIEF.md`, `DESIGN.md` and
`plan/INDEX.md` first — this file says only what is TRUE NOW and what the plan does not.

**Branch** `feat/maquette-l21`, pull request **#572** (draft). **Version** 0.98.75 — it was
0.98.74 and moved because the departure micro-wave, which merges first, holds that number;
**re-read `main` and bump past it at the close**, whatever else has merged meanwhile. **Base**
`origin/main` at `ae1b8de48`, which commit `27a2ef6a9` on this branch has ALREADY MERGED —
`git merge-base HEAD origin/main` answers `ae1b8de48` and `git diff --name-only <base>
origin/main` answers zero files. § 6's « merge `main` first » is therefore discharged; it said
the opposite until this line, and a sentence that outlives its subject is read as current.

---

## 1. Done, with the reading that proves it

| Phase                               | State           | Proof                                                                                              |
| ----------------------------------- | --------------- | -------------------------------------------------------------------------------------------------- |
| 1 — the contract                    | **DONE**        | 3 operations + types + register together; § 2c added; mocks answer and MOVE state                  |
| 2 — the season grab (B-301)         | **DONE**        | R125 **16 holds, no violation**; mutation falls 6 holds naming the right defects                   |
| 3 — the journey's two verbs (B-302) | **DONE**        | R126 **16 holds, no violation**; red first at 9 violations; mutation falls exactly the stages hold |
| 4 — the five acts                   | **not started** | —                                                                                                  |
| 5 — the release take                | **not started** | —                                                                                                  |
| 6 — the pastille + R124             | **not started** | —                                                                                                  |
| 7 — B-313 + close                   | **not started** | —                                                                                                  |

**Gates on the current head**: `run.sh --contracts` → 18 rules + 27 guards, no violation. Oracle →
87 states × 34 regions, 2 958 measurements, **no divergence** (phase 1; not re-run since the
button landed — **expect and ACCEPT divergences on the states whose seasons panel or journey panel
gained a button**, D8, each with B-301 / B-302 as its reason). `tsc -b`, vitest 104, build,
`check-no-french` 15 arms, `check-mock-seeds` 7 arms, `check-markup-contracts` 87 tests: clean.

---

## 2. What this wave built that the plan did not foresee

**`lib/verbs.ts` — a tap registry, and phase 4 depends on it.** B-302's verbs had NO reader: a
panel action emits only `data-*`, `ui/panel` attaches no handler by contract, and every such
attribute was read by the dying engine — so a verb that never existed there needed a branch in
`legacy.js`, which D5 forbids. The registry is domain-free (`registerVerb(name, act)`) with one
delegated listener in capture, `stopPropagation` on a match so the engine cannot also act.
**Phase 4 moves the five acts onto this same registry** rather than inventing a mechanism then.

**`mocks/answered.ts` — the record a rule reads a CALL from.** See § 3.

---

## 3. The instrument facts that change how you write every remaining rule

1. **A mocked call reaches NO network.** `mocks/index.ts` replaces `globalThis.fetch`. Measured: a
   verb that demonstrably ran produced **zero** Playwright request events with an unfiltered
   listener attached. **Any hold written as `page.on("request")` or `page.on("response")` over a
   mocked operation is green whatever the interface does.** Read the call on
   `window.__mocks.answered()` instead.
   ⚠ **`busy.py`'s « no mutation was answered 409 » is vacuous for this reason.** It is phase 6's
   to repair, and until then R124's green has never included that clause.
2. **The message is NOT in `#toast`.** That element is the dying engine's; the message layer is
   React. Read `window.__toast.read()` — `{ message, shown }`, published for rules.
3. **`window.__go` RE-SEEDS the mock layer.** Put the machine to work AFTER driving the state, or
   the act lands against an idle layer while the « pipeline is busy » hold stays green over a
   reading already discarded.
4. **A panel producer has NO OBSERVER.** `invalidateQueries` refetches what is being observed and
   marks the rest stale; a producer is a function from the cache to a descriptor. Use
   `refetchQueries` or the sheet does not move.
5. **`mutate.sh` takes a rule PATH, not a name** — a bad path prints « NO RULE FELL. That is the
   finding. » See B-330. It cost a false finding that was nearly written down.
6. **The heavy floor**: `HEAVY_FREE_FLOOR_MB=3584` is approved by the steward for the mutation and
   the contracts tier at `TM_HARNESS_JOBS=1`; the full suite waits for 4096.
7. **A PUSH ON THIS REPOSITORY IS A HEAVY RUN** — the pre-push hook runs the whole pytest suite at
   `-n auto` (8 workers on 8 cores). Always
   `PYTEST_XDIST_AUTO_NUM_WORKERS=3 … sh scripts/heavy.sh l21 git push …`.
8. **Read the PUSH's own output, never the task notification's exit code.** Two pushes reported
   « exit code 0 » from the wrapper while git had refused the ref. `git ls-remote --heads origin`
   is the only proof.

---

## 4. Corrections to the brief, already written into it on this branch

- **§ 4's `busy.py` paragraph**: the repair it orders LANDED inside L19 (`raise_by_finger`,
  `9fa13da57`). L19's report § 6 row 16 records it and its § 9 says it was left undone — § 9 is
  the stale half. What remains is the ACTION click at `busy.py:172,222`, not hit-tested.
- **§ 2's « one action per season row printed `to_grab` »**: there is **no `to_grab` cell anywhere
  in the fixture**. `epState` colours a hole by the FOLLOW's status. The mark is
  `[data-part="season/missing"]`, and the fixture holds exactly ONE subject: **Silo, season 3,
  7 aired, 6 held**.

---

## 5. Register numbers, and they are not the ones `--next` says

The steward and a micro-wave hold blocks. **Your next free is B-351+ and R128+.** B-329, B-330 and
B-350 are this branch's. `--next` on `main` disagrees with everyone until the merges — say so in
the pull request rather than renumbering.

Filed by this wave: **B-329** (the backend's generated contract does not declare the 409 its route
raises — so no diff can compute that demand, which is why B-302 keeps a HAND-written one),
**B-330** (`mutate.sh` cannot tell a typo from a rule that does not bite), **B-350** (a paused
series is dimmed and says nothing while a paused film says « en pause » — operator-reported,
measured, not this lot's doing).

---

## 5a-ter. THE TRAPS THIS SESSION PAID FOR — read before writing a rule or a move

**Every one of these was found by a reading, and four of them were in MY OWN instruments.**

1. **A hold can pass for the wrong reason and look like a pass.** R132's « the panel offers the
   pause » matched « pause » OR « cherch » and found « Chercher maintenant » — a different act. The
   act is « Ne plus chercher » for a FILM and « Mettre en pause » for a series (§5 from the
   interface's side), so no word finds both. **Find a panel action by its ATTRIBUTE.**
2. **A mutation finds vacuities in the RULE, not only in the code.** R131's undo hold read « the
   position is not in `sugGone` » — true, under the mutation, because nothing had ever been
   removed. It reads the TRANSITION now. **Mutate hold by hold; a rule-level mutation would have
   said « the rule falls » and taught nothing.**
3. **A guard is only as wide as its corpus.** ARM 7 accepted a read only in `engine/legacy.js`, and
   refused `data-sugidx` the moment `follow` moved — a DATUM the act's own handler reads. Widened
   to the whole tree.
4. **`--record` can FREEZE a violation.** The comment baseline's `--record` entered my rule's lot
   code as that file's allowance. **The signal is a NEW KEY in `files`; `read: N → N+1` is the
   benign half.**
5. **A stale rectangle looks exactly like a covered button.** Measuring `getBoundingClientRect`
   in the same turn as `scrollIntoView` returned the ROOT element from `elementFromPoint`. Scroll,
   let it settle, then hit-test — and print the covering element WITH its class.
6. **A button below the fold is not a defect.** The media sheet's follow button sits at y=1661 on
   an 844-tall frame. A hand scrolls; the rule must too.
7. **The swipe drawers are the other way round.** `swipeHTML` puts the pause and the removal in
   `data-side="right"`, uncovered by the card travelling LEFT. Rightward reveals « Chercher »,
   which exists only for a pending follow.
8. **`app/shell.tsx` stands ONE LINE under a 400-line hard block.** Two acts with an import and a
   call each took it over and twelve boundary tests fell on the push. Feature contributions go in
   `app/panel-contributions.ts` and declare themselves at MODULE EVALUATION — that file exists for
   this and says so in its own header.
9. **Read the push's OWN LOG, never the task notification.** It reported « exit code 0 » twice
   today over a wrapper that exited 1 and 141 with git refusing the ref. `git ls-remote` is the
   only proof.
10. **`data-go` is not the frame's navigation.** It is a cross-reference an author placed inside a
    page. The bar a thumb uses is `[data-page]` (`app/tab-bar.tsx`).

## 5b. What phase 3 OWES, and it is phase 4's first task

**The registry now has its rule — LANDED, 2026-09-06.** The steward approved `lib/verbs.ts` on two
conditions: the decision recorded (DESIGN.md § 3.1d, with the alternatives refused) and a contract
rule refusing a `data-*` verb that markup emits and no feature registers, seen red once on purpose.
Both are done. The rule is **ARM 7** of `check-markup-contracts` (`scripts/markup_verbs.py`, the
emitting side parsed by `harness/panel_verbs.mjs`); it reads 34 verbs over 33 action targets, all
answered, and it was seen red by removing the `journey-requeue` declaration on the real tree — exit
1, naming `panel-journey.ts:92`, back to 0 on restore. **By hand, not through `mutate.sh`, which
cannot judge a guard (B-273).** Detail and the two shapes it had to be taught: DESIGN.md § 3.1d.

**And one correction to carry**: the phase-3 commit calls `ui/variants/controls`'s `actionButton`
an ORPHAN. It is not — it has two users (`app/not-found.tsx`,
`features/releases/releases-screen.tsx`) and both compose it with `cfoot`, which paints. It is a
LAYOUT variant; the defect was using it alone. DESIGN.md § 3.1e carries the correction; the commit
message cannot be edited and is wrong on that one sentence.

---

## 5a-bis. WHERE PHASE 4 STANDS — written 2026-09-06, and it is the only true account

**Landed on the branch, each with its rule and its reading:**

| Part | Commit | Proof |
| --- | --- | --- |
| ARM 7 — the registry's owed rule (§ 5b) | `32b08c011` + `faf5ef5ee` | 34 verbs over 33 action targets, all answered; red by hand on a removed `registerVerb`, naming `panel-journey.ts:92` |
| B-350 — a paused tile says so, and keeps its figure | `3150d2bc8` | R129, 6 holds over 14 tiles: « 4/9 · en pause », and none of the other 12 carries the word |
| B-345 — the seeds offer their states to a HAND | `b36d67521` | R128, 10 holds; RED at five before the fixture moved |
| the record — #572 draft, 0.98.75, B-350 `fixed`, B-351 filed | `b9983bc7a` | `check-implementation-state` clean on both arms |

**Gates on that head**: `run.sh --contracts` → 18 rules + 27 guards, no violation. CI on
`67580575d` → thirteen check-runs, the negative query (`select(.conclusion != "success")`)
returning EMPTY. The served copy's stamp identical at both ends of the tier and of both rules.

**The five acts, one at a time — TWO OF FIVE ARE DONE:**

| Act | State | Proof |
| --- | --- | --- |
| `follow` | **DONE** `6026840e1` + `5a58b6e52` | R130, 10 holds before and after; red by mutation on exactly the two behaviour holds; ledger 31 591 → 31 542 |
| `dropsug` | **DONE** `327f8fc3e` + `e35eca13e` + `e3bde6c66` | R131, 8 holds before and after; red by mutation on three of four; ledger 31 542 → 31 536 |
| `sugmore` | **RULED, not coded** | the operator's ruling below — it is a BEHAVIOUR change |
| `pause` | **rule landed, move NOT done** | R132 `43b969842`, 9 holds green against the engine |
| `remove` | not started | — |

**NOT DONE besides**: B-316; B-315 (a); B-337's real-finger measurement.

**`sugmore` — THE OPERATOR RULED IT ON 2026-09-06, and it is a BEHAVIOUR change.** The engine's
branch does `store.write({ sugGone: new Set(), sugOrder: null })` and re-renders — it CLEARS
everything the operator dismissed and reshuffles the same reserve, then says « Nouveau lot chargé —
30 suggestions de plus. », which is not true of what it did. **The ruling, verbatim through the
orchestrator**: « A press asks the layer for THIRTY MORE suggestions, the reserve grows, nothing
already dismissed comes back, and the message is true of what happened. » So:

- the mock layer GAINS the operation, seeded from the backend's shapes (D7) — read
  `docs/reference/frontend-backend-demands.md` for the suggestions route first; **if the backend
  has no such operation it is a DEMAND recorded in the register**, as B-302's was, and the
  maquette's contract declares it;
- the verb registered on `lib/verbs.ts` calls it, and the engine's branch is deleted;
- the rule holds: dismissed positions STAY GONE across the press, the count grows by thirty (or by
  what the reserve has left, and it says so), and the message names the number it added;
- **it is RED against the engine today with no mutation needed** — the engine un-dismisses, so the
  hold « dismissed stays gone » falls against it as it stands. That is the strongest form of « seen
  red first » and it is free here.

**`[data-sugmore]` GETS NO NAMED STATE, and that is settled — B-352.** It is drawn only by
`deckHTML()` when the pile is spent, no state reaches that, and one CANNOT be added: `states.js` is
grandfathered at 786 non-blank lines, the size arm refuses the growth, and it refuses the raise of
the record too (« raising it legalises the growth in the same commit that commits it, which is the
ratchet refusing nothing »). Both refusals were measured on this branch and reverted; the plan's
sentence ordering the state is STRUCK where it stood, with the refusals quoted. **So the rule builds
the spent pile itself** — `window.__store.write({ sugMode: "deck", sugGone: … })` — and holds the
button's DRAWING by its own geometry: its rectangle inside the viewport, uncovered at its centre,
its label read. The oracle cannot see a state nobody named, and that cost is filed as B-352 with
L13 as its owner.

**`pause` — THE RULE IS LANDED AND THE MOVE IS NOT.** R132 (`harness/pause_verb.py`, `43b969842`)
reads 9 holds green against the engine: the panel's act moves the state against WHAT IT WAS (the
act toggles, so a rule naming the destination asserts the fixture), the undo puts it back, and
B-337's half. What the move must answer, and it is more than the plan's table says:

- the panel's `data-pause` is the easy half — one `registerVerb`, and the engine's branch at
  `dataset.pause` deleted;
- **the ROW's revealed action is dispatched by CLASS**, not by an attribute: `legacy.js`'s click
  delegation reads `closest.classList.contains("act")`, then `.pause` / `.remove`, and takes the
  subject from `.ctitle`'s TEXT CONTENT. `data-swipeact` and `data-action` on those buttons are
  emitted and read by NOTHING — measured, `grep -rn "dataset.swipeact"` answers nothing at all.
  So moving `actionPause` means that branch calls the feature's door (the `data-take` shape) or the
  swipe's own dispatch moves with it.

**B-337 DID NOT REPRODUCE, and that is a negative reading rather than a repair.** R132 drives a
REAL touch — touch start, eight moves, a dwell, touch end over CDP — then ONE tap on the revealed
action, and the follow moved `pending → disabled` on that first tap. The operator sees the defect on
an Android; a CDP touch in headless Chrome is closer to a finger than `page.touchscreen.tap` and is
still not a finger. **The entry stays open**, with the reading recorded in it, and the next attempt
belongs on the device.

**The `window.__followVerbs` seam is the ENGINE's and only the engine's** — `grep -rn
"__followVerbs" design/src` answers three lines: the declaration, the assignment, and
`engine/legacy.js:9537`. It dies with the engine, so this lot adds no product read of a `window.__`
seam, which L13's « Done when » counts.

**What the ground reading already establishes, so the next hand does not re-earn it:**

- `dismissSug` ALREADY LIVES IN THE FEATURE (`discover-feed.ts:244`) — only its READER is the
  engine's, at `legacy.js:9132`. `dropsug` is the cheapest of the five.
- **`sugmore` is not a transposition.** The engine's branch (`:9110`) does
  `store.write({ sugGone: new Set(), sugOrder: null })` and re-renders — it CLEARS what was
  dismissed and reshuffles. It does not add thirty. So B-315 (b)'s « one press adds thirty and the
  reserve is intact » is a BEHAVIOUR decision, not a move, and it needs saying out loud before it
  is coded.
- **`[data-sugmore]` is drawn only by `deckHTML()` when the pile is empty**, and no named state
  reaches that, which is why the phase owes one.
- **The deck card does NOT share a node**, whatever a first reading suggests: `data-panel="sug:N"`
  is on the `<article>` and `data-mediasheet` on its child `<button class="p">`, which covers the
  card — functionally the same defect, differently shaped. The POSTER TILE is the same-node case.
- **The engine's `panelUnderFinger` already resolves `[data-panel]` from a child**
  (`legacy.js:7889`), so « the long press cannot reach the panel » must be MEASURED before it is
  believed. Reason is not a reading here.

## 5c. OPEN, live, and unexplained — the operator's 10:36 reading

**« le bouton récupérer saison 3 de Silo ne semble rien faire, en tout cas il se passe rien
visuellement »**, on the design host on his Android, with Silo's panel showing « 6/7 · 1 manquant »
and the button drawn as a plain `sact`. **This is not closed and must not be assumed closed.**

What was RULED OUT, each by a reading:

- **Not a stale build.** The served bundle is `dist/vite/index-DHK4FCS-.js`, built **10:33**, three
  minutes BEFORE his reading, and `grep` finds both `grab-season` and `journey-requeue` inside it.
- **Not the mock layer being off.** `__MOCKS_BUILT_IN__` is `JSON.stringify(true)` in
  `vite.config.mjs:161`, so the layer is installed in that build; if it were not, the prototype
  would carry no Silo at all.
- **Not the press arbitration's swallow, as far as it can be reasoned.** `swallowClick` is armed
  only by a long press and is cleared by the FIRST click after it, whatever the distance — so a
  later, separate tap on the button is not the one it eats. *Reasoned, not measured — do not treat
  this as settled.*

What is TRUE on the harness: R125 taps that button at its hit-tested centre and the act fires — the
operation is recorded, the follow moves `pending → acquiring`, the message reads back through
`window.__toast.read()`. **And that is exactly the limit**: `page.touchscreen.tap` is a synthetic
touch with no movement and no dwell, so it cannot reproduce a finger, and **it therefore cannot
rule out the class of defect B-337 already documents** — a first tap that does nothing on a real
phone while every synthetic one works.

**Phase 4 owes a measurement on the real path**, not another synthetic tap: B-337 and this reading
are plausibly the same defect, and B-337 is already ratified into this lot.

---

## 6. What phase 4 must read before it starts

- **B-339** and **B-337** on `main` (ratified into L21 by the operator): a disabled panel action is
  drawn like an enabled one (`.sact` has no `:disabled`) — the queued state has no not-available
  form to inherit; and a swiped-open follow card ignores the FIRST tap on its revealed action,
  whose actions ARE `pause` and `remove`, this phase's verbs. **Measure with a real touch which
  listener eats the click**; if it is the swipe rather than the tap path, it goes back to L13 and
  the steward is told.
- ~~**Merge `main` into this branch first**~~ — **DISCHARGED, and it was already false when
  written here.** `git merge-base HEAD origin/main` answers `ae1b8de48`, which IS `main`'s
  head, and `git diff --name-only <base> origin/main` answers ZERO files: commit `27a2ef6a9`
  on this branch merged it. No merge was run for phase 4 and none was needed.
- **B-316 is RULED**: a TAP opens the media sheet, a LONG PRESS opens the suggestion panel,
  reusing L14's gesture, and the two attributes stop sharing a node. **B-315 (a) is now in
  scope** — the button's size, at the catalogue's scale for a secondary action in a feed footer.

---

## 7. The one thing not to repeat

Every defect this wave found was found by asking what a hold actually READS — never by a gate. The
rules were green, the guards were green, and the readings were empty: a network with no traffic on
it, a toast element nothing writes to, a query nobody observes, a mutation tool answering the same
sentence whether it measured something or nothing. **Ask it of every hold you write.**
