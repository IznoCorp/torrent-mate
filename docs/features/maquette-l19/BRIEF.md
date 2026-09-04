# L19 — The producers

You open **L19**, the second lot of Phase 5 and the largest that remains: every surface the dying
engine still PRODUCES moves to its feature, its share of the fixture dies with it, and nothing on
the screen moves. Nothing is open on it: no design, no plan, no branch. You begin by writing them.

**Your contract is in the plan, not here.** `docs/reference/frontend-architecture.md` § 4, entry
`#### L19 — The producers`, carries the objective, the ten producers and the Découvrir feed, why the
lot exists (the last lot's debt, named and moved), where a producer lives (invariant 10), the one
kind of change it makes, what it must not do, the debts it owns and the « Done when ». **This brief
does not restate it** — a contract copied into a second file is a contract wrong in one of them.
What follows is what the plan does not say, measured on 2026-09-04 at `cb2128220`.

---

## What you read before acting

1. `CLAUDE.md` — the repository's rules. They outrank everything here, this brief included.
2. `docs/reference/documentation-model.md` — **BINDING**: your folder is deleted at the post-merge
   gesture and cited by commit; there is no `docs/archive/`.
3. `docs/reference/frontend-architecture.md` — **BINDING**: § 0 (selection), § 2 — D5 (the engine
   is subtracted from; its one exception, written at L14, is for data-destroying defects only), D7
   (the data contract is the maquette's; a mock is seeded from the backend's shape), D8 (what the
   oracle proves and what a RULE must read instead), D9 (motion) —, § 3 invariants 6, 7, 10, 11,
   **§ 4's L19 entry — your contract**, § 4's L21 entry (the verbs that are NOT yours), § 5 (method,
   gates, the instruments' debts block — **B-306 is yours**), § 6 (the traps), § 7.1 (how to amend).
4. `docs/reference/frame-model.md` — Part 12 (the popover: the frame places, the feature says the
   sentence) and the properties P2 and P29; `docs/reference/frame-survey.md` § 1.1 — the inventory
   command your « Done when » is read through.
5. `docs/reference/product-intent.md` — §13 (real data), §17 (a restart cuts the household), §20 (a
   tunnel per media: the journey sheet IS the tunnel seen by the operator), DOIT-3, DOIT-4, DOIT-8,
   NE-DOIT-PAS-3, NE-DOIT-PAS-9; `docs/reference/product-intent-map.md` — the four rows that name
   L19 as owner of their missing instrument, and the § 4 list of operations with an L19 verdict.
6. `git show 9ce9b0508:docs/features/maquette-l14/REPORT.md` — L14's report, from history: the
   React 19 `innerHTML` identity mechanism (32 sites repaired through `ui/markup.tsx`), the seven
   review rounds and where each round's sharpest finding sat (inside the previous round's repair).
7. `docs/reference/frontend-steward.md` § « What a review costs, and the five rules » — they bind
   your review from round one — and § « Instrument hygiene ».
8. `frontend/maquette/README.md` — the method, the named states, the traps already paid for.
9. `IMPLEMENTATION.md` § « Where the frontend work stands » — and `BUGS.md`: B-247 (its producer
   half is yours), B-249 (the SHAPE you inherit at seven sites), B-299 and B-300 (the two banners),
   B-303 and B-304 (two traps L14 paid, both yours to avoid), B-306 (yours), B-305 (ruled: an open
   swipe stays open — you do not restore the snap).

---

## Verify the state; do not believe it

    git remote update origin >/dev/null && git log --oneline origin/main -3
    grep -o "Landed, in order\*\*[^|]*| [^*]\{0,150\}" IMPLEMENTATION.md
    grep -o "| \*\*Next\*\*[^|]*| [^.]\{0,80\}" IMPLEMENTATION.md
    python3 scripts/check-bug-register.py --next
    grep -o "| \*\*Total\*\* | \*\*[0-9]*\*\*" BUGS.md
    grep -c "panel\.open(" frontend/maquette/design/src/engine/legacy.js
    grep -nE '\.(innerHTML|outerHTML)\s*=|insertAdjacentHTML\(|\.(appendChild|append|prepend|replaceChildren)\(' frontend/maquette/design/src/engine/legacy.js | grep -v '^\s*//' | wc -l
    grep -c "closest\.dataset\." frontend/maquette/design/src/engine/legacy.js
    grep -n "setTimeout(.*260" frontend/maquette/design/src/engine/legacy.js
    grep -n "install[A-Za-z]*(" frontend/maquette/design/src/app/shell.tsx | grep -vc "^\s*//"
    python3 scripts/check-frontend-boundaries.py --arm size | grep -E "at or over|shell|add-screen|stream"
    python3 scripts/check-frame-domain.py | tail -1
    grep -cve '^[[:space:]]*$' frontend/maquette/design/src/engine/legacy.js

**Every figure carries the command that produces it. Run them.** Read on 2026-09-04 at
`cb2128220`: `panel.open(` **10**; the inventory command **9** sites (seven are the Découvrir feed,
two are the harness panel at `legacy.js:9480` and `:9504`); `closest.dataset.` **132** delegation
reads; **7** `setTimeout(…, 260)` sites; **25** `install*(` calls in `app/shell.tsx`, of which seven
are feature seams exported from a feature's `queries.ts`; the three files under the ceiling by one,
two and five lines — `mocks/stream.ts` **399**, `app/shell.tsx` **398**,
`features/acquisition/add-screen.tsx` **395**; the frame's floors `ui/ 0, lib/ 18, app/ 129`;
`legacy.js` **32 461** non-blank; the counter at **211**; `--next` says **B-308**.

---

## The ten things the plan does not tell you

### 1. The ten producers, by name — and what each one's descriptor already renders through

`grep -n "panel\.open(" legacy.js` at `cb2128220`, each with the function that owns it:

| Line   | Producer                                     | Feature it moves to     | Address       |
| ------ | -------------------------------------------- | ----------------------- | ------------- |
| 5827   | a maintenance action (`openActionMaintenance`) | `features/maintenance`  | `action:<id>` |
| 7521   | a secret (`openSecret`)                        | `features/settings`     | —             |
| 7574   | a setting (`openSetting`)                      | `features/settings`     | `setting:<id>`|
| 8133   | the account menu (`openUserSheet`)             | `features/account`      | —             |
| 8421   | a suggestion (`openSugSheet`)                  | `features/acquisition`  | —             |
| 8498   | a search result to add (`openAddSheet`)        | `features/acquisition`  | —             |
| 10007  | the library's sort sheet (`data-sort`)         | `features/library`      | —             |
| 31642  | the follow sheet (`openFollowSheet`)           | `features/acquisition`  | `follow:<t>`  |
| 31813  | the journey (`openJourneySheet`)               | `features/acquisition`  | `journey:<t>` |
| 31866  | « Veille et obligations » (`openMoreSheet`)    | `features/acquisition`  | —             |

Plus two producers that do not go through `panel.open`: the Découvrir feed (`deckHTML`,
`mountDeck`, `refreshDeck`, `advanceDeck`, the list and the footer — the seven inventory sites
between `legacy.js:8315` and `:8540`), and the episode popover's SENTENCE (`openPopEp`,
`legacy.js:31542`, driven from the delegation at `:9911`; the frame half already lives in
`app/popover-host.ts` behind `{ anchor, content }`).

**The seasons block is already React.** `features/media/panel-seasons.tsx` registers `"saisons"`
through `ui/panel/contract`'s `registerBlock` — the precedent the plan calls « a feature ADDS a
block kind ». What the follow producer at `:31707` still does is BUILD the descriptor that names
that block. Move the descriptor; the block needs nothing.

### 2. A descriptor is the contract, so the oracle proves the move — and here is what it cannot see

`ui/panel` renders a descriptor the same whichever side produced it, which is why each move is
provable at zero divergence over the oracle's 2 958 measurements (`make maquette-oracle`, its
figure printed at every run). Three things the oracle measures at rest and cannot see, each with the
rule that reads it instead:

- **Node identity across a store write** — B-247's producer half, yours. `persistence.py`'s hold
  (f) drives `window.__store.write({})` on nine named states and asks `isSameNode` on the page's own
  nodes; a moved producer's panel body and the Découvrir containers are added to that list, and the
  hold must FALL on a producer that re-keys or rewrites its `innerHTML` (mutate it, see it red,
  restore). L14 measured the mechanism you will meet: React 19 assigns `innerHTML` on the prop
  OBJECT's identity, so markup written inline as `{ __html }` recreates its children on every
  render — `ui/markup.tsx`'s `useMarkup` / `Markup` is the one door, and `scripts/check-component-once.py`
  will not let you write a second.
- **The dismissal's timing** — B-249's shape. `exits.py` (R103) measures a layer's exit and PRINTS
  the 260 ms gap where the delegation still holds it. Seven sites carry `setTimeout(…, 260)` today
  (`legacy.js:9792, 9861, 9882, 9885, 10215, 10249, 10255`); the `data-mediasheet` site lost its
  wait at L12 and the plan keeps saying so. A producer that moves takes its site with it and lets
  the panel leave inside the navigation's own commit; when the last site goes, R103 REFUSES the gap
  instead of printing it, and that reversal is one commit with its mutation.
- **The popover's placement** — the frame's, not yours, and already held; what you move is the
  sentence, and a rule reads the sentence's TEXT on the episode the reader tapped, not the layer.

### 3. Two behaviour phases, each in its own commit: the settings' banners

B-299 and B-300 are the only two places this lot changes what the interface DOES, and each is its
own phase with its own rule seen red — the five review rules' first one (« a conversion wave does not
carry a behaviour repair ») is honoured by keeping them at the end of the plan, after every producer
has moved at zero divergence.

- **The version conflict (B-299).** `SettingsState.conflict` (`features/settings/reference.ts:55`)
  and `mocks/state.ts:135,187` declare it and set it `false`; nothing raises it, no `fr.json` key
  names it (`grep -c "conflit" fr.json` → 0). Production answers **412** on
  `PUT /api/config/files/{name}` when the file changed under the editor — D7: the mock answers that
  shape, seeded from the contract (`contract/types.d.ts`), the banner draws from the query's error
  and offers reload; the rule drives a save over a mocked 412 and reads the banner, then mutates the
  reader and sees it red.
- **The restart confirmation (B-300).** `legacy.js:9590` sets `redemarrage = true` on the setting's
  save and the `dataset.restart` branch drops it with a toast; production confirms first. The
  confirmation is `ui/dialog` (its paragraph colour and danger contrast held by R116 since L12), the
  copy lives in `fr.json`, and the rule walks the tap, reads the dialog, cancels, reads the flag still
  up, confirms, reads the toast. §17 is the clause: a restart cuts the service for every account.

Neither adds a verb the map does not already draw; L21's three verbs stay out.

### 4. The two delegation verbs move with a rule written BEFORE the move — because none holds them today

The plan says a verb that moves « lands in its own commit with the rule that held it before,
unchanged in count ». **Measured on 2026-09-04: no rule reads either verb.**
`grep -ln 'data-take' frontend/maquette/harness/*.py` and `grep -ln 'cancelsetting' …` both return
nothing. `data-take` is EMITTED by React (`features/releases/releases-screen.tsx:113`) and READ by the
engine (`legacy.js:9889`, through the 260 ms site at `:10255`); `data-cancelsetting` is emitted and
read by the engine (`:7607`, `:9578`). So the order is: write the rule that walks each verb on the
engine's side and see it red under a mutation of the engine's branch; THEN move the reader into the
feature and see the same rule green, count unchanged. A rule written after the move proves only that
it agrees with the move. The plan's sentence is amended to say so.

### 5. The four map rows you turn to `served` — and the one whose copy does not exist

`docs/reference/product-intent-map.md` names L19 as the owner of a missing INSTRUMENT on four rows;
each row's « Unproved » clause is the rule's specification:

- **DOIT-8** — the confirmation before replacing a film the library owns is ONE line
  (`legacy.js:10788–10789`) and the toast after it (`:10811`); no rule walks « add a film the
  library owns » and reads it. Yours with `openAddSheet`.
- **NE-DOIT-PAS-9** — the LIST rows (a follow row, an arrival row, a search result) and the
  galleries outside `harness/gallery.py`'s five (`/add`'s results, `acq-now`) must each carry a
  path to the medium's sheet. Yours with the producers that draw them.
- **NE-DOIT-PAS-3** — every mutation under a busy scenario is not refused with a 409 or an
  « occupé ». One instrument with DOIT-4.
- **DOIT-4** — « toujours accepter une action légitime, mise en file visible ». The row says the
  resolve queue's own « En file » pastille « has no copy in `fr.json` and no rule ». **Read that
  against your contract**: « no surface changes ». If the queued state is drawn today, the rule reads
  it and the row turns `served`; if the pastille does not exist, drawing it is a behaviour change
  and it is NOT yours — file it with an owner (L21 is the behaviour lot on these producers) and let
  the row read `partly` with the reason. Do not draw a surface to make a row green.

### 6. Where a producer lives, and what the frame gives back when it leaves

Invariant 10: a producer is a function from the cache to a descriptor and lives in
`features/<domain>/`, reading the query cache through the feature's `queries.ts`, never the
engine's accessors. Two files shrink when you do this right, and the plan names both:

- `app/engine-data.ts` — « what the dying engine reads with no component to ask for it », a list
  named `NEEDED` (`FOLLOWS`, `MAINT_ACTIONS`, …). Every producer you move removes its family from
  that list, because a React producer asks for what it draws. The file dies at L13; you empty it.
- `app/shell.tsx` — **398 of 400**, and it FALLS: each moved producer takes its `installX` seam out
  of the shell (the seven feature seams are the `install*` exports of `features/*/queries.ts`).
  A line ADDED to the shell fails the size arm; a line removed is the lot working.

The frame's floors (`ui/ 0, lib/ 18, app/ 129`) are ceilings held from going up; `app/` should go
DOWN here, and the guard prints a « lower it » note when it does — lower it in the same commit.

### 7. Three files sit one, two and five lines under a hard block, and you write beside all three

`mocks/stream.ts` **399**, `app/shell.tsx` **398**, `features/acquisition/add-screen.tsx` **395**.
The ceiling is 400 and the grandfather list holds only the engine's two. So: `openAddSheet` becomes
a new file beside `add-screen.tsx`, never a function in it; the 412 mock lands in a new file under
`mocks/`, never in `stream.ts`; and the shell only loses lines. A single added line in any of the
three is a red gate in the phase that adds it, and L14's audit said this sentence belongs in your
plan rather than in your phase 3's log.

### 8. B-306 is yours: the size arm learns to count

`scripts/check-frontend-boundaries.py`'s `GRANDFATHERED` dict (`:332`) maps a file to a LABEL and
nothing else; the arm checks the label exists and never that the file shrank. L14 added 77 non-blank
lines to the engine under « dies by subtraction » and the arm printed clean. You are the next wave
that subtracts from the engine, so § 5's debts block gives you the repair: one recorded count per
entry, refused upward, re-recorded DOWNWARD in each of your phases that subtracts. Its mutation is
one added line to `legacy.js` with the arm read RED — and `scripts/mutate.sh` cannot judge a guard
(B-273: it reads journal `FAIL` lines, which a guard never prints), so you read the arm's exit code
by hand and write both readings in the phase.

### 9. Two traps L14 paid on exactly your kind of work

- **B-303** — a mutation applied BY HAND leaves the served copy of the PREVIOUS build in place, so
  the next reading measures code nobody is testing; and a restore by `git checkout --` over
  `design/src` destroys whatever else is uncommitted there. `scripts/mutate.sh` exists for both
  reasons: it refuses a dirty tree, rebuilds and republishes under `served_copy.py`'s lock, restores
  from the index. Use it for every rule; commit before every mutation.
- **B-304** — `git add -f` on a PATH swept 28 375 files into a commit, `node_modules` entire.
  `docs/` is ignored globally (B-251), so your three documents are added by FILE:
  `git add -f docs/features/maquette-l19/DESIGN.md`, never `git add -f docs/features/maquette-l19/`.

### 10. What « the fixture dies with the producer » means, and how it is read

D5's method: bracket-match every `const X = [` / `const X = {` declaration in `legacy.js` and sum
the spans over 100 lines. The plan reads **9** declarations over 100 lines on 2026-09-03 (26 366
lines); a reading restricted to upper-case names reads **8** spanning 25 060 — `POSTERS`,
`HERO_IMAGES`, `OWNED`, `LIBRARY`, `MAINT_ACTIONS`, `SETTINGS`, `CAST`, `SHEETS_RAW` (20 538 alone).
Re-derive the list with the plan's method before you write a figure, and write the figure ONCE, on
the final head (the fifth review rule): each moved producer takes its families with it, and the
« Done when » reads the difference, not a number remembered from this brief.

---

## What you do not do

- **You do not move a pixel.** Every part's rendering is validated (mission of 2026-08-19); a
  conversion lot's oracle is green at zero divergence or the divergence is a defect.
- **You do not add a verb.** « Récupérer cette saison », « Remettre en file », « Re-scraper » are
  L21's, on the producers you have just moved; a producer here offers exactly what it offered.
- **You do not extend a grandfathered file or the three under the ceiling** (§ 7), and you do not
  add to the engine: D5's exception is for a defect that destroys data, and none is expected here.
- **You do not restore the swipe's snap** (B-305, ruled 2026-09-04): a row a reader opened stays
  open across a write that did not concern it.
- **You do not touch `docs/production/`**, and you do not re-create `docs/archive/`.
- **No backend work** (D7). A 412 the backend already answers is mocked from its shape; a right, a
  ratio, a cross-seed are other lots'.
- **You do not relitigate settled arbitrations** — D1 to D12, invariants 1 to 15, the operator's
  answers of 2026-08-30 and 2026-09-02, §17, §18, §19 and §20 as dictated.
- **You do not stop between phases.** Phases chain without pause — the operator arbitrates the
  SCOPE, never the cadence; write that constraint at the head of your plan's INDEX with its
  self-check, as L12 and L14 did. The only stops are the ones your plan names.

---

## The gates

**Per phase**: the oracle (green at zero divergence — this is a conversion lot), the contract rules,
the repository's cheap guards — `run.sh --contracts` prints how many.

**Before merging**: the full suite — `frontend/maquette/harness/run.sh`, not the `--contracts`
tier — the `--a11y` tier, `scripts/harness-hold-counts.py --compare` (every movement written down;
read `failed` in the totals before you trust a record, B-291), and `make check` at zero failures and
**zero errors**.

**The machine is an instrument.** Every run that starts browsers, builds or a parallel test run is
wrapped: `TM_HARNESS_JOBS=2 sh scripts/heavy.sh <who> <command>`. Two browser groups machine-wide, a
parallel test run at three workers, never a build beside a run. Kill what you start, delete what you
build, and verify with `ps` — a sentence saying « stopped » is not a reading. The host on 8899 is
`run.sh`'s and is left running by design; the harness is one per machine (`served_copy.py` is its
lock and stamp); a rule that falls while another session held the harness is re-run alone before it
is read, and a re-run that removes the load the failure needed is said in the same breath (B-277,
B-307).

**Every rule lands with its mutation, seen red and restored**, at the moment it is written.

---

## How you deliver

One branch `feat/maquette-l19`, one pull request, **title and body in English**, then squash
merge. The version bumps.

**The adversarial review is independent of you, or it is not adversarial**, and it costs what the
five rules say it costs. When your pull request is ready you message the steward (`ListAgents`
names the session); the steward launches the readers on a worktree pinned at your head, and **from
round one they build your head and a control of the previous head and WALK the interface** — every
blocker L14 had was found by walking, none by reading. You alone write. **No head is reviewed until
every item of the previous round arrives with the probe reading that closes it**, taken on a build
of the candidate against the control — or with a sentence saying what the fixtures cannot show.
**Every repair lands with the rule that falls when it is reverted.** Figures are written ONCE, on
the final head; a stale figure during a repair round is not a finding and you are not asked to
re-measure it.

**Write your « In flight » row when the pull request opens** — pull request number first, then
the version: `scripts/check-implementation-state.py` holds the row by both.

**The register is written DURING the wave**, and your report lands in your folder with your design
and plan before the pull request is marked ready.

**Cite the constitution's §§ your work serves.**

---

## One last thing

L13 said the sixty fixture families « belong to surfaces the ENGINE still draws — their literals
cannot leave before their markup does ». The markup left with the pages; the families stayed because
their readers are producers, and no lot owed those. You are the lot that owes them. When
`grep -c "panel\.open(" legacy.js` reads 0, what is left of the engine is the frame's delegation,
the boot and the harness seam — L13's, and small.
