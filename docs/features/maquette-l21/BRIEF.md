# L21 — The tunnel's verbs

You open **L21**, the third lot of Phase 5 and the first BEHAVIOUR lot after two conversions: three
verbs a tunnel owes and does not offer, five acts of acquisition that still run through the dying
engine, one verb moved by half, and one pastille the constitution names and nobody drew. Nothing is
open on it: no design, no plan, no branch. You begin by writing them.

**Your contract is in the plan, not here.** `docs/reference/frontend-architecture.md` § 4, entry
`#### L21 — The tunnel's verbs`, carries the objective, why it is a lot of its own, where a verb
lives (invariants 7 and 10), what it must hold, the « Done when », and the four things carried into
it — L19's five acquisition acts on 2026-09-05, and the steward's two placements the same day
(DOIT-4's pastille and `data-take`'s release-screen half, both ratified by the operator). **This
brief does not restate it** — a contract copied into a second file is a contract wrong in one of
them. What follows is what the plan does not say, measured on 2026-09-05 at `79e34b38d`.

---

## The question at the top, before the reading list

**« What does this actually read? »** L19's agent closed its wave with this sentence, and the
steward puts it first: the three defects that cost that review most had one shape — a reading that
agreed with its control, a filtered view showing nine where ten were expected, a fact asserted by
SEARCHING a file's text instead of parsing it — and each was caught by someone asking that question,
never by a gate. Ask it of every hold you write, every figure you take, every probe you run: what is
this reading, and what would it still read if the behaviour were gone? A behaviour lot is where the
question bites hardest, because a conversion's oracle is no proof of anything you add.

---

## What you read before acting

1. `CLAUDE.md` — the repository's rules. They outrank everything here, this brief included.
2. `docs/reference/documentation-model.md` — **BINDING**: your folder is deleted at the post-merge
   gesture and cited by commit; there is no `docs/archive/`.
3. `docs/reference/frontend-architecture.md` — **BINDING**: § 0 (selection, and « one kind of
   change per wave » — yours is BEHAVIOUR, every verb lands with its rule seen red first), § 2 —
   D5 (the engine dies by subtraction; the ledger refuses `legacy.js` upward), D7 (the contract is
   the maquette's; every divergence from the backend is a DEMAND, computed and never written by
   hand), D8 (the oracle measures geometry at rest; a divergence a verb causes is ACCEPTED with its
   reason, never repaired by moving the interface back) —, § 3 invariants 4, 5, 6, 7, 10, 11,
   **§ 4's L21 entry — your contract**, § 4's L13 entry (the five surface-opening verbs that are
   NOT yours) and L20's (the global levers that are NOT yours), § 5 (method, gates, the
   instruments' debts block — **B-323's instrument half is yours**, see § 5 below), § 6, § 7.1.
4. `docs/reference/product-intent.md` — **§20** whole (a tunnel per media: a tunnel « reprend là
   où il s'est arrêté, par l'opérateur »; a media arriving at the bound « s'enfile visiblement »),
   **DOIT-3**, **DOIT-4** (« En file — pipeline en cours », never « occupé »), **DOIT-5**, §17 (the
   verbs land unconditional here; the rights are L18's), NE-DOIT-PAS-3, NE-DOIT-PAS-9;
   `docs/reference/product-intent-map.md` — the DOIT-3 row (your three verbs, named), the DOIT-4 row
   (`partly`, the pastille), the NE-DOIT-PAS-3 row (R124).
5. `frontend/maquette/contract/README.md` — how the contract is changed, in three files that
   cannot separate; `docs/reference/frontend-backend-demands.md` § 1, § 2b and § 4 — your three
   operations are in § 4 today, « the backend has and the interface does not use ».
6. `git show 9fa13da57:docs/features/maquette-l19/REPORT.md` — L19's report, from history: § 4
   (R103's reversal), § 5 (what nobody had measured), § 6 (eighteen guards green over what they do
   not read — read the shapes, you will write the same kind of instrument), § 9 (what it owes you:
   `busy.py` raising panels through the seam), § 12 and § 13 (where each round's sharpest finding
   sat: inside the previous round's repair). And `git show 9fa13da57:docs/features/maquette-l19/BRIEF.md`
   § 4 — the recipe for moving a verb with a rule written FIRST.
7. `docs/reference/frontend-steward.md` § « What a review costs, and the five rules » — they bind
   your review from round one — and § « Instrument hygiene ».
8. `frontend/maquette/README.md` — the method, the named states, the traps already paid for.
9. `IMPLEMENTATION.md` § « Where the frontend work stands » — and `BUGS.md`: **B-301**, **B-302**
   (the three verbs), **B-313** (the follow panel's doubled action — yours, ratified by the operator on
   2026-09-05), **B-316** (the suggestion producer no
   finger reaches — its surface is yours, its DRAWING decision is the operator's), **B-315** (b) and
   (c) (`data-sugmore` is yours), **B-320** (yours only if you open the acquisition page's non-ready
   branches), **B-322** and **B-323** (the release screen's take, its two toasts, its 260 ms wait),
   **B-247** (the producer half: a moved surface keeps its nodes across a store write — the hold
   exists, your surfaces are added to its list), **B-305** (ruled: an open swipe stays open).

---

## Verify the state; do not believe it

    git remote update origin >/dev/null && git log --oneline origin/main -3
    grep -o "Landed, in order\*\*[^|]*| [^*]\{0,150\}" IMPLEMENTATION.md
    grep -o "| \*\*Next\*\*[^|]*| [^.]\{0,80\}" IMPLEMENTATION.md
    python3 scripts/check-bug-register.py --next
    grep -o "| \*\*Total\*\* | \*\*[0-9]*\*\*" BUGS.md
    grep -cE "closest\.dataset\.(follow|pause|remove|dropsug|sugmore|take)\b" frontend/maquette/design/src/engine/legacy.js
    grep -c ', 260)' frontend/maquette/design/src/engine/legacy.js
    grep -c ', 240)' frontend/maquette/design/src/engine/legacy.js
    grep -cve '^[[:space:]]*$' frontend/maquette/design/src/engine/legacy.js
    grep -n "engine/legacy.js" scripts/frontend_size_ledger.py
    grep -c "seasons/{season}/grab\|journeys/{infoHash}/requeue\|journeys/{infoHash}/rescrape" frontend/maquette/contract/openapi.json
    grep -n "Remettre en file\|Récupérer cette saison" frontend/maquette/design/src/i18n/fr.json
    python3 scripts/check-frontend-boundaries.py --arm size | grep -E "at or over|GRANDFATHERED"
    python3 -c "import json;d=json.load(open('frontend/maquette/hold-counts-baseline.json'));print(d['taken_at_commit'][:9], d['totals'])"
    TM_HARNESS_JOBS=1 sh scripts/heavy.sh <you> python3 frontend/maquette/harness/machine.py 2>&1 | tail -1

**Every figure carries the command that produces it. Run them.** Read on 2026-09-05 at
`79e34b38d`: the six verbs read **12** times by the engine (`sugmore` once; `follow`, `dropsug`,
`pause` and `remove` twice each — the test and the read; `take` three times — the door and the
branch); **7**
`setTimeout(…, 260)` sites and **6** `setTimeout(…, 240)`; `legacy.js` **31 645** non-blank, the
ledger recording the same; the three operations **0** times in the maquette's contract; the three
sentences **0** times in `fr.json` (« Re-scraper les métadonnées » is there twice and is the MEDIA
SHEET's metadata rescrape, another subject — B-302 says so); the two grandfathered files at their records; the hold-count
baseline at `64c43d0e7` with 87 rules and `failed: 0`; `--next` says **B-324**.

**Two of those readings decide whether you may start.** The B-308 micro-wave
(`docs/features/maquette-schedulers/BRIEF.md`, branch `fix/maquette-schedulers`) runs BEFORE you: it
turns `machine.py` green and re-records the hold-count baseline with `failed` read first. If
`machine.py` still fails, or the baseline's `taken_at_commit` is still `64c43d0e7`, that wave has
not landed — **STOP, tell the steward, and wait**: a wave that opens over a red suite inherits « one
red, it is known », which is B-277's habit and the reason the micro-wave exists.

---

## The ten things the plan does not tell you

### 1. Your three operations are the BACKEND's, and the maquette's contract does not have them

`frontend/maquette/contract/openapi.json` declares `POST /api/acquisition/followed/{followedId}/grab`
(`grabForFollow`) and nothing else you need. The backend has all three, and its generated contract
(`frontend/openapi.json`) gives their shapes:

| Operation (backend)                                                 | Answers | Body                                  |
| ------------------------------------------------------------------- | ------- | ------------------------------------- |
| `POST /api/acquisition/follows/{followed_id}/seasons/{season}/grab` | **201** | `SeasonGrabResponse`                  |
| `POST /api/acquisition/journeys/{info_hash}/requeue`                | **202** | `GrabTriggerResponse` — `{ run_uid }` |
| `POST /api/acquisition/journeys/{info_hash}/rescrape`               | **202** | `GrabTriggerResponse` — `{ run_uid }` |

D7 in force: the interface DECLARES what it requires, seeded from these shapes, and the difference
is a demand. So your first phase is the contract — add the three operations to
`contract/openapi.json`, `npm run generate-contract-types` in `frontend/maquette/design/`, then
`python3 scripts/compare-contracts.py --write`, and commit the three together (`--check` refuses
them apart). Three demands come out of it, and you record them rather than reconcile them:

- **Identity.** The interface knows a follow by its TITLE (`Follow.t`, no id in
  `features/acquisition/reference.ts:19`) and a journey by the title too — `panel-journey.ts`
  reads `/api/acquisition/journeys/{infoHash}` with a title, and says so in its own comment. The
  mock keys `followedId` by title already (`handlers/acquisition.ts`, `followFor`); yours key the
  same way. The backend wants `followed_id` and `info_hash`: that is § 2b's spelling demand plus an
  identity demand, and it is the backend's to answer after the freeze, not yours to fake.
- **No 409.** `personalscraper/web/routes/acquisition_triggers.py:642` answers **409** « when a
  requeue for this item is » already in flight. NE-DOIT-PAS-3 and §20 forbid the interface to show
  that: an ask at the bound is QUEUED, visibly. The contract you write declares 202 and a queued
  state for that case, the mock answers it, and the register carries « the backend answers 409
  where the interface requires a queued 202 » as the demand.
- **The season grab's 201.** A creation, in the backend's reading; the interface treats it like the
  other two — the season's state moves. Declare what the interface requires and let the diff say the
  rest.

### 2. Where each verb lands — and the seam it replaces

**The season grab** lands in `features/media/panel-seasons.tsx` (200 lines; a `saisons` block
registered through `ui/panel/contract`'s `registerBlock`, one action per season row printed
`to_grab`). Invariant 7: the media feature never imports `features/acquisition/`; it calls the
OPERATION through its own `features/media/queries.ts`, exactly as the plan says. **The verb is a
new file beside the block**, never a growth of `panel-seasons.tsx`.

**Requeue and rescrape** land in `features/acquisition/panel-journey.ts` (88 lines), whose
`actions` block today offers one action — « Voir la fiche ». The producer's header already says the
verbs « belong to the lot that wires the tunnel's verbs ». Copy goes in `fr.json` under
`panels.journey.*` — three keys exist there today, `metaBefore`, `provenanceNote`, `seeSheet`.

**The five acts** are read by the engine's delegation at `legacy.js:9167` (`sugmore`), `:9189`
(`dropsug`), `:9195` (`follow`, with `sugidx` and `fkind` read off the same node), `:9307` (`pause`)
and `:9313` (`remove`). Their EMITTERS are React already: `panel-suggestion.ts:60,77`
(`follow` + `sugidx`, `dropsug`), `media-details.tsx:147` (`follow`), `follow-actions.ts` (`pause`,
`remove` — a panel action's `target` IS its `data-*` map, `ui/panel/contract.ts:33`),
`discover-feed.ts:107` (`sugmore`). Each act's body is an engine function — `actionFollow`
(`:5622`), `actionPause` (`:5587`), `actionRetirer` (`:5611`), the suggestion's dismissal, and the
deck's refill — and each of those already calls a FEATURE seam to do the real work:
`window.__followActions.setStatus / remove / add` (`features/acquisition/queries.ts:113`, the
optimistic writes: cache first, `HELD` when offline, put back on refusal). **Moving a verb is
moving its reader onto that seam's owner and deleting the engine's branch and body**; when the
last engine caller of `__followActions` goes, the `declare global` seam goes with it — product code
reads no `window.__` at L13, and you are the lot that empties this one.

**Two things travel with `pause` and `remove` that the plan does not name.** (a) Their branches
wait: `setTimeout(() => actionPause(pause), 240)` and the same for `actionRetirer` — two of the six
`, 240)` sites, B-249's shape with a different number. The panel leaves inside the navigation's own
commit now (L12); the wait goes with the branch. (b) Their UNDO: `toastUndo` (`legacy.js:8080`)
offers to put the follow back and calls the seam again. The header of `queries.ts` says « the undo
is the engine's and it stays » — that was true while the verb was the engine's. The undo is
interface, and it moves with the verb it undoes.

**`data-take`'s release-screen half** (B-323, ratified L21's): `legacy.js:9352` asks the arrivals
door — `window.__arrivalsVerbs?.take(…)`, `features/arrivals/verbs.ts:77`, which answers the panel's
TITLE take since B-309 — and `:9353-9364` is the engine's own INDEX branch behind it: `releases()[Number(…)]`,
`bridge.back()`, a 260 ms wait, `actionTake`, and B-322's two toasts into one element. The door
already decides by asking the QUEUE whether a value is its own (« is it a number? » was refused as
a rule about spelling); extend the same door, or give the releases feature one of its own, so that
`grep -c "closest\.dataset\.take" legacy.js` reads **0**, the wait is gone, and the take says ONE
sentence (B-322 closes with it). R123 (`take.py`) holds both takes already and walks the release
screen; it must stay green with its count unchanged, and B-322's sentence needs a hold of its own
that samples the toast element across the gesture.

### 3. DOIT-4's pastille is a surface you DRAW, and the oracle will say so

The map's DOIT-4 row reads `partly`: R124 (`busy.py`) proves that a legitimate act under a busy
pipeline is ACCEPTED, and « the resolve queue's own « En file » pastille » — the VISIBLE half, the
constitution's own words « En file — pipeline en cours » — does not exist. Measured: `fr.json`
holds one key, `screens.arrivals.queuedBold` = « en file », the pipeline PASS's own strip on
Arrivées (`features/arrivals/page.tsx:129`, `data-part="live-activity"`, R66 reads it). Nothing
says it of a MEDIUM.

**So this is the one place this lot draws.** The method is the maquette's (§15, README): a named
state FIRST in `engine/states.js` — a queue item whose ask arrived while the pipeline runs, or while
§20's bound is met — then the rule that reads the pastille on that state and on the act under
`busy.py`'s scenario (`mocks/scenario.ts`, `setOperationOutcome`), seen red, then the drawing.
**The operator judges it on his phone**: the design host on 8712 serves your `dist`, so the state
you name is the state he sees. The oracle WILL read divergences on the states whose panels gain a
button and on the pastille's state — that is D8's « accepted with reasons »: each divergence is
accepted with the register entry or clause it serves (DOIT-4, B-301, B-302, B-323), never by moving
the interface back, and the reference is re-recorded ONCE at the post-merge gesture, not by you.
**A divergence on any OTHER state is a defect**, and the only stop your plan names besides the
two below.

### 4. Every verb lands with its rule seen RED first — and here is what each rule reads

The five review rules' fourth: a repair held by nothing returns with its sign turned round. L19
paid for it on `data-take` (R123 was red against the engine with no mutation needed — B-309) and
the recipe is its brief's § 4: **rule first, on the engine's side, red under a mutation of the
engine's branch; then the move; then the same rule green, count unchanged.** What each reads, and
what would leave it green over nothing:

- **The season grab**: the operation is CALLED (read on the NETWORK — the mock records what it
  answered; a hold reading the screen alone passes a build that toasted and sent nothing), the
  season's state moves out of `to_grab` on the panel, and under the busy scenario the ask is queued
  and the pastille draws — never a 409, never « occupé ».
- **Requeue and rescrape**: the operation is called; the journey's stages move (a `now` pip where a
  `todo` was, read on the LAYER's answer and never on a literal — `panel-journey.ts` reads its
  stages from the query cache since L19, so the mock has to move them); under the busy scenario,
  queued and said.
- **Each of the five acts**: what R123 reads for the take, transposed — the STATE moves (a follow
  paused reads `disabled` in the follows cache and on the row; a follow removed is absent; a
  suggestion dismissed is gone from the deck AND from the cache the deck reads; a batch loaded is
  thirty more cards; a follow added is at the head of « Suivis », marked new), no error is raised,
  and the undo puts it back. Written against the engine, red under a mutation of the engine's
  branch, green after the move.
- **B-313**: a panel's actions are COUNTED BY LABEL and a label appearing twice is refused —
  written first, red on `main`'s follow panel for a medium that has no sheet (the primary ladder
  falls through to the journey and the secondary row emits it unconditionally,
  `follow-actions.ts:91`), then the one-condition repair mirroring « Voir la fiche »'s guard. The
  rule is named in B-313's body so it is not invented twice.
- **B-247's hold** (`persistence.py` (f)): the panels you touch are added to its list; a producer
  that re-keys its rows falls it.

**And `busy.py` is yours to repair, not to extend as it is.** L19's report § 9 and § 6 row 16 say
it: R124 raises its panels THROUGH THE SEAM (`window.__panel.produce`), so a `data-panel` lost on a
busy page is invisible to it. The correction is the one R103 took (`exits.py:208`): drive the
delegation — a finger on the row, never the seam. Do it before you add your holds to it, or you add
holds to a rule that does not walk the path a finger takes.

### 5. R103's inventory, and B-323's instrument half

`harness/exits.py:186-204` names the remaining `setTimeout(…, 260)` sites by the call they wrap and
counts them with `grep -n "setTimeout(.*260)"` — a command that reads a site only when its call and
its delay share a line, which is how two sites went uncounted (B-323). You remove one of the seven —
the release screen's take — so you touch the inventory, and § 5's rule gives you its debt: re-take it
with `grep -n ', 260)'`, name all six that remain by the call they wrap (the `add:` identify branch
at `legacy.js:9597-9602`, `actionResolve` after `bridge.rewind`, is the one nobody had named), and
say in the comment which command counts them. Do not widen R103 into a blanket refusal — five of the
six are L13's and the rule against the wrong subject was refused once already.

### 6. Files at the ceiling, and the ones you write beside

Hard block at 400 non-blank lines, soft warning at 250, the grandfather list holding only the
engine's two. Where you write, today: `add-screen.tsx` **395**, `app/shell.tsx` **392**,
`discover-feed.ts` **344** (the `sugmore` emitter), `media-screen.tsx` **335**, `lib/queue.ts`
**306**, `season-list.tsx` **285**, `follows-tab.tsx` **254**, `mocks/handlers/acquisition.ts`
**233**, `panel-seasons.tsx` **200**. A verb is a NEW FILE beside its panel — `features/media/`
for the season grab, `features/acquisition/` for the journey's two and the five acts — and the mock
handlers for the three operations are a new file under `mocks/handlers/`, never a growth of
`acquisition.ts` past the soft line without saying why. `lib/queue.ts` is invariant 10's one
tolerated line and it holds ONE resource: the queue. A verb on a follow is not the queue's; do not
put it there because it is shared.

### 7. The engine only SHRINKS, and the ledger reads it

D5 and B-306: `scripts/frontend_size_ledger.py` records `legacy.js` at **31 645** and refuses it
upward, compared with the record at your branch's base. Every verb you move deletes its delegation
branch and, when it was the last caller, the `action*` function behind it; every phase that
subtracts re-records the count DOWNWARD in the same commit (the arm prints the new figure; a growth
is refused with an exit code). **You do not add a line to `legacy.js`** — a verb that needs one
line in the engine to work is a verb whose reader has not really moved.

### 8. B-316 is a drawing decision, and it is the operator's — a named STOP

On Découvrir's poster tile `data-panel="sug:N"` and `data-mediasheet` sit on the SAME node; on the
deck card the media verb is on the tile's child. Ten finger points on two card kinds: the media
SCREEN opens every time, `panelOpen: false`. The suggestion producer is right and unreachable, on
`main` as on L19's head. You move `data-follow`, `data-dropsug` and `data-sugmore` on those very
cards, so you WILL open that file — and which of the two a tap means (the sheet, or the panel that
carries « Ajouter / Voir la fiche / Pas intéressé ») is a drawing decision on a surface the
mission of 2026-08-19 declares validated. **STOP A**: before drawing, send the steward the two
readings with what each costs (a long press for the panel, as the library's rows do since L14; or
the panel on the tap and the sheet from inside it), and wait. The steward relays to the operator.

**B-315 beside it, in three parts you do not confuse.** (a) the button's size is the operator's
amendment and NOT yours unless he dictates it; (b) one press adds thirty and the reserve is intact —
your `sugmore` rule reads that, on a NAMED STATE for the deck's empty state, which B-315's fourth
finding says does not exist yet (`[data-sugmore]` is reachable from no state: give it one, a named
state is harness and not surface); (c) the end mark exists on `acq-discover-exhausted` and says the
reserve is spent — your rule reads it there too.

### 9. Two traps L14 paid on exactly your kind of work, and one L19 paid

- **B-303** — a mutation applied by hand leaves the served copy of the PREVIOUS build in place;
  `scripts/mutate.sh <file> <expression> <rule…>` rebuilds and republishes under `served_copy.py`'s
  lock and restores from the index. Use it for every rule; commit before every mutation. It cannot
  judge a GUARD (B-273): a guard's exit code is read by hand.
- **B-304** — `git add -f` on a PATH swept `node_modules` into a commit. `docs/` is ignored
  globally: add your documents BY FILE, `git add -f docs/features/maquette-l21/DESIGN.md`, never the
  folder.
- **L19's own**: a hold that evicts a query key this interface does not have walks a WARM cache
  and passes with the repair removed (B-321's first rule). When a hold drops a key, it reads the
  eviction back before it goes on — `getQueryData` undefined for every key it asked — or it has
  measured nothing.

### 10. What stays out, said once so the pull request does not argue it

The global levers — the parallelism bound, pause and resume of everything, « relancer la veille » —
are **L20**'s (§20 point 3); the tracker policy from the ratio surface is **L16**'s; who may act on
whose tunnel is **L18**'s gate (§17), and your verbs land unconditional and get hidden per role
later; the five surface-opening verbs (`data-mediasheet`, `data-journey`, `data-resolve`,
`data-releases`, `data-profile`) move with the delegation in **L13**. B-320's hook order is yours
only if you open `now-tab.tsx` or `page.tsx`'s non-ready branches; if you do not, leave it filed.

---

## What you do not do

- **You do not draw a pixel that is not a verb's button or the pastille.** Every other part's
  rendering is validated (mission of 2026-08-19); a divergence on a state your verbs do not touch
  is a defect, and the one stop your plan names besides Stop A.
- **You do not add a line to `legacy.js`** — the ledger refuses it, D5 forbids it, and a verb that
  needs one has not moved.
- **You do not touch the backend** (D7). A 409 the backend answers is recorded as a demand and
  mocked as the interface requires; `personalscraper/` is not opened.
- **You do not restore the swipe's snap** (B-305, ruled 2026-09-04), and you do not change the
  size of Découvrir's button (B-315 (a)) unless the operator dictates it through the steward.
- **You do not touch `docs/production/`**, and you do not re-create `docs/archive/`.
- **You do not relitigate settled arbitrations** — D1 to D12, invariants 1 to 15, the operator's
  rulings of 2026-08-30, 2026-09-02, 2026-09-04 and 2026-09-05, §17 and §20 as dictated.
- **You do not stop between phases.** Phases chain without pause — the operator arbitrates the
  SCOPE, never the cadence; write that constraint at the head of your plan's INDEX with its
  self-check, as L12, L14 and L19 did. The only stops are the ones your plan names: Stop A above,
  the oracle diverging on a state you did not touch, and the pull request.
- **If you believe something outside your contract is needed, STOP and ask the steward first.**

---

## The gates

**Per phase**: the contract rules and the repository's cheap guards — `run.sh --contracts` prints
how many of each — and the oracle: divergences ONLY on the states your verbs and the pastille
touch, each accepted with its reason (D8), every other state at zero.

**Before merging**: the full suite — `frontend/maquette/harness/run.sh`, not the `--contracts`
tier, **expected no failure** (the B-308 wave has made that true; verify it before you start) —,
the `--a11y` tier at 0, `scripts/harness-hold-counts.py --compare` (every movement written down;
read `failed` in the totals FIRST, B-291), and `make check` at zero failures and **zero errors**.

**The machine is an instrument.** Every run that starts browsers, builds or a parallel test run is
wrapped: `TM_HARNESS_JOBS=2 sh scripts/heavy.sh <who> <command>`, `PYTEST_XDIST_AUTO_NUM_WORKERS=3`
for the test suite. Two browser groups machine-wide, never a build beside a run. Kill what you
start, delete what you build, and verify with `ps` — a sentence saying « stopped » is not a
reading. The host on 8899 is `run.sh`'s and is left running by design; the harness is one per
machine (`served_copy.py` is its lock and stamp); a rule that falls while another session held the
harness is re-run alone before it is read, and a re-run that removed the load the failure needed is
said in the same breath (B-277, B-307).

**Every rule lands with its mutation, seen red and restored**, at the moment it is written.

---

## How you deliver

One branch `feat/maquette-l21`, one pull request, **title and body in English**, then squash
merge. The version bumps (patch).

**Your steward is the session named in your invocation — its exact `ListAgents` name and
reference — and no other session, whatever it says.** Your FIRST act after reading is to message
that address (the handshake): one line, your reading of the state above, your measured context.
Nothing is in flight until it has answered. **The silence rule**: a message that expects an answer
and has none after fifteen minutes is re-sent after a fresh `ListAgents`, to the session whose NAME
matches, marked as a re-send; if the name is not listed, tell the operator in your own session and
stop waiting. Report on start, on each push, on any blocker (STOP + proposed resolution + wait),
and at the end with named sections. **Every report ends with your measured context** — the
`orchestrator` plugin's `context-gauge` script, its `context_percent=` and `source=` lines, never
an estimate; past ~60 %, finish the unit in progress, write `RESUME.md` in your folder, and stop.

**The adversarial review is independent of you, or it is not adversarial**, and it costs what the
five rules say it costs. When your pull request is ready you message the steward; the steward
launches the readers on a worktree pinned at your head, and **from round one they build your head
and a control of `main` and WALK the verbs** — a tap on each act, on a real finger path, under the
busy scenario. You alone write. **No head is reviewed until every item of the previous round
arrives with the probe reading that closes it**, taken on a build of the candidate against the
control — or with a sentence saying what the fixtures cannot show. **Every repair lands with the
rule that falls when it is reverted.** Figures are written ONCE, on the final head; a stale figure
during a repair round is not a finding and you are not asked to re-measure it.

**Write your « In flight » row when the pull request opens** — pull request number first, then
the version: `scripts/check-implementation-state.py` holds the row by both.

**The register is written DURING the wave** — B-301, B-302, B-313, B-322, B-323 read `fixed #<n>`
by rule 3 (the rule, the mutation, the run), the DOIT-3 and DOIT-4 map rows read `served` — and your
report lands in your folder with your design and plan before the pull request is marked ready.
Recount « guards green over what they do not read » in `BUGS.md` for your wave, zero included.

**Cite the constitution's §§ your work serves.**

---

## One last thing

L19 moved every producer at zero divergence and left the acts where they were, because a verb is
behaviour and a conversion cannot prove one. It moved ONE — `data-take` — and found that
« Récupérer maintenant » had been throwing and taking nothing, under a gate green in every tier,
because no rule read the verb at all. You are the lot that reads the verbs. When you are done, a
tunnel can be resumed from where the operator looks at it, a season can be taken from where its
hole is printed, an ask at the wrong moment says « En file » instead of failing quietly, and the
engine's delegation reads none of the acts that were never its own.
