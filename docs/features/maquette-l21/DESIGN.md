# L21 — The tunnel's verbs · DESIGN

**Lot** L21, the third of Phase 5 and the first BEHAVIOUR lot after two conversions.
**Contract** `docs/reference/frontend-architecture.md` § 4, entry `#### L21 — The tunnel's verbs`.
That entry is the contract and is not restated here; this document says HOW it is met, and every
figure below carries the command that produced it.

**Constitution served**: §20 (a tunnel per media, resumed « par l'opérateur »), DOIT-3 (« agir là
où l'on observe »), DOIT-4 (« En file — pipeline en cours », never « occupé »), DOIT-5, §17 (the
verbs land unconditional; rights are L18's), NE-DOIT-PAS-3 (no 409 on a legitimate ask),
NE-DOIT-PAS-9 (nothing here draws a medium).

---

## 1. The state this wave opens on, measured

Read on 2026-09-06 at `origin/main` = `7fecb0258`, which is three commits past the brief's own
measurement at `79e34b38d` (#567, #568, #569 landed in between). **Four of the brief's figures
have moved and the moved ones are the ones that govern**:

| Reading               | Command                                                      |      Brief (79e34b38d) |                                 Measured (7fecb0258) |
| --------------------- | ------------------------------------------------------------ | ---------------------: | ---------------------------------------------------: |
| `legacy.js` non-blank | `grep -cve '^[[:space:]]*$' …/engine/legacy.js`              |                 31 645 |                                           **31 591** |
| the ledger's record   | `grep -n "engine/legacy.js" scripts/frontend_size_ledger.py` |                 31 645 |                                 **31 591** (line 95) |
| hold-count baseline   | `python3 -c` over `hold-counts-baseline.json`                | 87 rules @ `64c43d0e7` | **92 rules @ `e9820e6a4`**, 2 180 holds, `failed: 0` |
| next register number  | `python3 scripts/check-bug-register.py --next`               |                  B-324 |                                            **B-329** |
| `BUGS.md` total       | `grep -o "\| \*\*Total\*\* \| \*\*[0-9]*\*\*" BUGS.md`       |                      — |                                              **246** |

**Unchanged, and each re-run rather than believed**: the six verbs are read **12** times by the
engine's delegation; **7** `setTimeout(…, 260)` sites and **6** `, 240)`; the three operations
appear **0** times in `frontend/maquette/contract/openapi.json`; « Remettre en file » and
« Récupérer cette saison » appear **0** times in `i18n/fr.json`.

**The two gating readings both pass, and neither was taken on trust.**

- `TM_HARNESS_JOBS=1 sh scripts/heavy.sh l21 python3 frontend/maquette/harness/machine.py` →
  « 92 rules EXECUTED — no violation », exit 0. ⚠ **That 92 is `machine.py`'s own holds, not the
  suite's 92 rule files.** The two are equal by coincidence at this commit, and reading the first
  as the second would turn a one-rule run into a whole-suite claim.
- `git merge-base --is-ancestor e9820e6a4 origin/main` → true, and `e9820e6a4` is later than
  `64c43d0e7`, with `failed: 0` read FIRST (B-291).

### 1.1 One instruction in the brief has lost its subject — `busy.py` is already repaired

The brief's § 4 says « `busy.py` is yours to repair, not to extend as it is », citing L19's report
§ 9: R124 raises its panels THROUGH THE SEAM, so a `data-panel` lost on a busy page is invisible
to it. **Measured on `main`, that is no longer true.**

    grep -n "__panel.produce" frontend/maquette/harness/busy.py    # one hit, and it is a COMMENT (line 155)

`busy.py` raises BOTH of its panels with `raise_by_finger` — a hit test at the row's own centre
via `elementFromPoint`, the covering toast emptied first, and the tap's own answer held so a
missing path FAILS rather than opening nothing quietly. The repair landed inside L19 itself
(`3d67325f9`, squashed into `9fa13da57`), and driving it by a finger went red and exposed the
finding under the finding: the pause half had been walking the acquisitions page, where a followed
medium not in flight has no row at all. That half now runs on `acq-follows-list`.

**L19's report contradicts itself here, and the file is the arbiter.** § 6 row 16 records the
repair and its red reading; § 9 (« what it owes you ») was written before that round and says it
was « left as it is rather than repaired blind ». § 9 is the stale half. This is the exact species
the brief warns about — a sentence that outlives its subject, read as current by the next session.

**Consequence for this plan**: phase 6 does not repair `busy.py`. It (a) proves the existing
repair still bites, by mutation, before adding anything to it, and (b) adds this wave's holds. The
effort that would have gone into the repair goes into the one residue the finger-driving did not
cover: the ACTION inside the raised panel is still clicked with `act.click()` and not hit-tested,
so a button covered on a busy page is invisible to R124. That is named and read, not assumed.

---

## 2. The contract comes first, and it produces three demands

D7 in force: the interface DECLARES what it requires, seeded from the running backend's shapes,
and every difference is a demand rather than a reconciliation. `frontend/maquette/contract/README.md`
§ « How to change it » is the procedure, and the three artefacts commit together because
`compare-contracts.py --check` refuses them apart.

Seeded from `frontend/openapi.json` (the generated contract of the backend that exists):

| Operation the interface requires                                   | Backend answers        | Backend body                                                                                              |
| ------------------------------------------------------------------ | ---------------------- | --------------------------------------------------------------------------------------------------------- |
| `POST /api/acquisition/follows/{followedId}/seasons/{season}/grab` | **201** (200 on reuse) | `SeasonGrabResponse` — `season_wanted_id`, `season`, `absorbed_count`, `reused`, `run_started`, `run_uid` |
| `POST /api/acquisition/journeys/{infoHash}/requeue`                | **202**                | `GrabTriggerResponse` — `{ run_uid }`                                                                     |
| `POST /api/acquisition/journeys/{infoHash}/rescrape`               | **202**                | `GrabTriggerResponse` — `{ run_uid }`                                                                     |

Their `operationId`s in the maquette's contract follow the neighbours already there
(`grabForFollow`, `searchForFollow`): **`grabSeasonForFollow`**, **`requeueJourney`**,
**`rescrapeJourney`**. They are what `setOperationOutcome` keys on, so the busy scenario can name
them.

### The three demands, recorded and not reconciled

1. **Identity.** The interface knows a follow by its TITLE — `Follow` is `{ t, k, st, … }` with no
   id (`features/acquisition/reference.ts`) — and a journey by the title too: `panel-journey.ts`
   reads `/api/acquisition/journeys/{infoHash}` with a title and says so in its own comment. The
   mock already keys `followedId` by title (`handlers/acquisition.ts`, `followFor`); the three new
   handlers key the same way. The backend wants `followed_id` (a rowid) and `info_hash`. That is
   § 2b's spelling demand PLUS an identity demand, and it is the backend's to answer after the
   freeze — **never faked here by inventing an id the interface does not hold.**
2. **No 409.** `personalscraper/web/routes/acquisition_triggers.py` answers **409** when a requeue
   or a re-scrape for this item is already in flight. NE-DOIT-PAS-3 and §20 forbid the interface
   showing that: an ask at the bound is QUEUED, visibly. **The contract declares 202 and a queued
   state for that case**, the mock answers it, and the register carries « the backend answers 409
   where the interface requires a queued 202 » as the demand.
3. **The season grab's 201.** A creation in the backend's reading; the interface treats it like the
   other two — the season's state moves and the operator is told. The contract declares what the
   interface requires and the computed diff says the rest.

---

## 3. Where each verb lands, and the seam it replaces

Invariant 10: a verb belongs with what makes it change. Invariant 7: `features/media/` never
imports `features/acquisition/` — it calls the OPERATION through its own `features/media/queries.ts`,
and a mutation on the contract is not a feature import. Invariant 6: **a verb is a NEW FILE beside
its panel**, never a growth of the producer.

### 3.1 « Récupérer cette saison » — B-301

**Where.** `features/media/panel-seasons.tsx` (200 non-blank) draws the `saisons` block: a legend
and one `<details data-part="season">` per season, whose `<summary>` already prints
`owned/aired` and a `.miss` count. The verb is one action per season row that has a hole and whose
episodes read `to_grab` — the state `epState` already computes.

**The new file**: `features/media/season-grab.ts` — the mutation, keyed by title + season number,
calling `grabSeasonForFollow` through `features/media/queries.ts`. `panel-seasons.tsx` gains the
button and its `data-*`, nothing else.

**Why not `features/acquisition/`**: the season matrix is drawn on the media side and invariant 7
is absolute. The acquisition feature is not imported; the OPERATION is called.

### 3.1b What phase 2 measured, and it corrects the brief

**There is no `to_grab` season anywhere in the fixture.** The brief and the lot's
contract both describe the seasons panel as « printing a season as `to_grab` and offering
nothing ». Measured: `epState` colours a missing episode by the FOLLOW's status, so the one
follow that has a hole (`Silo`, `pending`) draws it `pending`, and every other follow is
`up_to_date` with nothing missing. A rule looking for a `to_grab` cell is red for a reason
unrelated to the verb — it would have stayed red after the repair and then been « fixed »
into a green that read nothing.

**What the panel really prints over a hole is `[data-part="season/missing"]`** — the
« N manquants » mark, drawn exactly when owned is short of what aired. That is the anchor,
and the subject is chosen from `window.SEASONS` (owned < aired) BEFORE a finger moves.

**The fixture offers exactly one subject**: `Silo`, season 3, 7 aired, 6 held. Thin, and
said so here rather than discovered by the next reader.

### 3.1c Four instrument defects phase 2 found, none of them by a gate

1. **A mocked call reaches no network.** `mocks/index.ts` replaces `globalThis.fetch`, so
   Playwright's request/response events never fire for an API call — measured, a verb that
   demonstrably ran produced ZERO page requests. **Every hold written as `page.on("response")`
   over a mocked operation is green whatever the interface does.** `mocks/answered.ts` records
   what the layer answered; rules read the CALL there. ⚠ **`busy.py`'s « no mutation was
   answered 409 » hold is vacuous for this reason** — it listens for a 409 on a wire nothing
   is put on. Phase 6 owns `busy.py` and repairs it there.
2. **The message is not in `#toast`.** That element is the dying engine's; the message layer
   is React. `#toast` stayed EMPTY through a verb whose message was on screen throughout.
   Rules read `window.__toast.read()`, the door the host publishes for exactly this.
3. **`window.__go` re-seeds the mock layer.** A pipeline set running before the state was
   driven is idle again by the time the act lands. The busy half measured a clause it had
   switched off, while the hold saying « the pipeline really is busy » was green over a
   reading already discarded.
4. **Two sources for one fact.** The absorbed count crossed the sheet's provider CATALOGUE
   with the owned-episode seed and answered **10** for a season the interface was printing
   as « 1 manquant ». `seasons.json` is what the matrix is drawn from.

### 3.1d A DECISION, not a file that appeared: `lib/verbs.ts`

**The problem, and it only exists for a verb that is NEW rather than moved.** A panel action is
`{ text, icone, target }` where `target` is a map of DATA attributes; `ui/panel` draws them and
attaches no handler of its own, by contract. Every such attribute was read by the dying engine's
document delegation. So B-302's two verbs — which had never existed anywhere — had **nobody to
answer them**, and the obvious move (a branch in `legacy.js`) is forbidden by D5 and refused by
the size ledger.

**What was chosen**: a domain-free registry in `lib/` — `registerVerb(name, act)` plus one
delegated listener, in capture, stopping propagation on a match so the engine cannot also act.
Features declare what they own; `lib/` carries the SHAPE and never the subject (invariant 10).

**The alternatives, and why they were refused:**

| Refused | Why |
| --- | --- |
| a branch in `legacy.js` calling a feature door, as `data-take` does | D5: the engine dies by SUBTRACTION. It is the right shape for MOVING a verb that already has a branch; it is the wrong shape for creating one, because it grows the file the ledger refuses upward. |
| a listener per feature | Every feature would own a document listener, their order would decide who wins a shared node, and the engine's death would leave nine of them to reconcile. One listener, many declarations. |
| a handler on the `Action` itself (`onSelect`) | `ui/panel`'s contract says a target IS its data attributes and the component adds no `onClick`. Changing that makes the panel know what a verb is. |

**What it commits the next lots to.** Phase 4 moves the five acts onto this registry instead of
inventing a mechanism at that moment, and **L13 inherits it**: when the engine's delegation dies,
its branches move here. It is therefore a decision for `frontend-architecture.md` § 2, not a file —
the steward writes it in at the audit under § 7.1.

**What it OWED, and phase 4 landed first**: a contract rule refusing a `data-*` verb that markup
emits and no feature registers — the same shape as the invented anchors `check-markup-contracts`
caught from the markup end. It is **ARM 7** of that guard (`scripts/markup_verbs.py`, emitting side
parsed by `harness/panel_verbs.mjs`), and it accepts two answers and no others: a `registerVerb`
declaration, or a read in the dying engine — `dataset.name`, `[data-name]`,
`getAttribute("data-name")`, the two spellings resolved to one name. **The engine dies by
subtraction, so the day a branch goes before its verb reaches the registry, this arm falls on it.**

**Seen red on purpose, on the real tree**: the `registerVerb("journey-requeue", …)` declaration was
removed by hand, the guard exited **1** naming `features/acquisition/panel-journey.ts:92` and
« nothing answers a tap on `data-journey-requeue` », and it returned to **0** on restore. By hand
rather than through `scripts/mutate.sh`, which cannot judge a guard (B-273): a guard's exit code is
read by hand.

**Reading on this tree**: 34 verbs over 33 action targets, every one answered — 2 by a declaration,
the rest by the engine; 1 dialog action set aside, 0 computed keys and 0 unresolved targets skipped.

**Three refusals came with it**, each because the alternative is silence: a panel action asking for
an already-prefixed `data-x` (`ui/panel` writes the prefix itself, so it renders `data-data-x`,
which nothing reads); a `registerVerb` call whose name is not a literal (an answer the arm cannot
see would refuse a verb that IS answered); and a corpus under its floor (a parse that read nothing
prints the same line as one that read every panel).

**And two shapes it had to be taught, both measured rather than foreseen.** A regular expression
over the same corpus answered `add` for ``target: { act: `add:${position}` }`` and
`panels.maintenance.launchedDry` for a translated value — keys that exist nowhere — which is why
the emitting side is parsed. And `panel-sort.ts` writes its target as a conditional through an
`as`, deliberately (two shapes rather than one with an undefined field, because an undefined value
still emits the attribute): a reader matching only a bare object literal skipped that map whole and
was one verb short with no sign that it had.

### 3.1e A correction to this document and to a commit message

**`ui/variants/controls`'s `actionButton` is NOT an orphan, and the phase-3 commit says it is.**
Measured properly afterwards: it has **two** real users — `app/not-found.tsx` and
`features/releases/releases-screen.tsx` — and BOTH compose it with `cfoot`, which is what paints
(`legacy.css:746`: border, background, colour). It is a LAYOUT variant, correctly used only in
composition.

**The defect was therefore mine and differently shaped than first stated**: the season-grab button
used `actionButton()` ALONE, so it took layout with no paint and drew as the inherited colour on a
pale panel. The repair — wearing `sact`, like every other action in a panel — is unchanged and
right. The first reading came from a grep that excluded the wrong paths and concluded « nothing
uses it »; a claim about absence is exactly the kind that has to be re-run before it is written
down.

### 3.2 « Remettre en file » and « Re-scraper » — B-302

**Where.** `features/acquisition/panel-journey.ts` (88 non-blank), whose `actions` block offers
exactly one action today — « Voir la fiche » — and whose header already says the verbs « belong to
the lot that wires the tunnel's verbs ».

**The new file**: `features/acquisition/journey-verbs.ts`. Copy goes in `fr.json` under
`panels.journey.*`, beside the three keys that exist (`metaBefore`, `provenanceNote`, `seeSheet`).

⚠ **« Re-scraper » here is NOT the media sheet's metadata re-scrape.** `fr.json` already holds
« Re-scraper les métadonnées » twice and that is another subject (B-302 says so); the journey's
verb re-runs the tunnel's scrape for one tracked staging item. Two keys, two sentences, and the
rule reads the journey's own.

**The stages must MOVE, and they are read from the layer.** `panel-journey.ts` reads its stages
from the query cache (`["/api/acquisition/journeys", subject]`) since L19, so the rule reads a
`now` pip where a `todo` was **on the layer's answer**, never on a literal — which means the mock
has to move them. A rule reading a hard-coded stage list would be green over a build that called
nothing.

### 3.3 The five acts of acquisition

Each act's EMITTER is React already; only the READER is the engine's. Moving a verb is moving its
reader onto the seam's owner and deleting the engine's branch and body.

| Act       | Emitter (React, unchanged)                                          | Engine branch    | Engine body             | Seam it already calls         |
| --------- | ------------------------------------------------------------------- | ---------------- | ----------------------- | ----------------------------- |
| `follow`  | `panel-suggestion.ts` (+ `sugidx`), `media-details.tsx` (+ `fkind`) | `legacy.js:9138` | `actionFollow` `:5567`  | `__followActions.add`         |
| `dropsug` | `panel-suggestion.ts`                                               | `:9132`          | `dismissSug`            | the deck's own store          |
| `sugmore` | `discover-feed.ts:107`                                              | `:9110`          | inline                  | `__refillSuggestions` / store |
| `pause`   | `follow-actions.ts` (`target: { pause }`)                           | `:9250`          | `actionPause` `:5532`   | `__followActions.setStatus`   |
| `remove`  | `follow-actions.ts` (`target: { remove }`)                          | `:9256`          | `actionRetirer` `:5556` | `__followActions.remove`      |

**The new file**: `features/acquisition/follow-verbs.ts` (pause, remove, follow) and
`features/acquisition/deck-verbs.ts` (dropsug, sugmore) — the deck's two are the discover surface's
and pausing a follow is not the deck's business.

**Two things travel with `pause` and `remove` that the contract does not name.**

- **Their 240 ms wait.** `setTimeout(() => actionPause(pause), 240)` and the same for
  `actionRetirer` — two of the six `, 240)` sites, B-249's shape with a different number. The panel
  leaves inside the navigation's own commit since L12, so **the wait goes with the branch**: the
  act happens in the tap's own commit, as `verbs.ts`'s take already does.
- **Their UNDO.** `toastUndo` (`legacy.js:8023`) offers to put the follow back and calls the seam
  again. `queries.ts`'s header says « the undo is the engine's and it stays » — true while the verb
  was the engine's. **The undo is interface and it moves with the verb it undoes**, and that header
  sentence is corrected in the same commit.

**When the last engine caller of `__followActions` goes, the `declare global` seam goes with it.**
Product code reads no `window.__` at L13, and this lot is the one that empties this one. `all()`
is read by `busy.py` and by the engine's `follows()`; whichever survives is named in the report
rather than removed blind.

### 3.3b A DECISION the acts produced: a removal is SOFT, and the undo restores

**The operator ruled this on 2026-09-06 and the ruling is « fix it in this lot ».** It is recorded
here rather than left in the register because it changes the CONTRACT, and a contract change that
exists only as a bug entry is a decision nobody can find.

**What was wrong.** « Retirer de la liste », then « Annuler », put back a follow with year 0, no
« suivi depuis » and no search count — a stranger wearing the same name. The optimistic half was
correct: the undo wrote the whole record back. What undid the undo was the refetch behind it. The
layer's removal DROPPED the record, so the only road back was a CREATE, and
`POST /api/acquisition/followed` accepts `title`, `kind`, `year`, `provider`, `providerId` — no
`since`, no `searches`, no `status`. **No undo can be honest over a create.**

**It was not this lot's doing.** The engine's `actionRetirer` offered the same undo through the
same seam, so the defect predates the act's move and travelled with it unchanged. It surfaced
because moving the act meant writing down what the undo promises, and a promise written down is a
promise something can read (B-353).

**The three alternatives, and why this one.** Widening the create's body to carry the history was
refused: it makes every create able to assert a past the interface should not be able to invent,
and a « create » that back-dates a follow is a create in name only. Recording the demand and
deferring was refused by the operator with the lot open. What is built instead is the shape a
backend can actually implement:

- **The removal is SOFT** — the layer keeps the record aside, whole, instead of destroying it.
- **`POST /api/acquisition/followed/{followedId}/restore` (`restoreFollow`)** answers the follow as
  it was, and **404** where nothing removed under that name is still restorable. Answering an
  invented record there would be the create's own lie arrived at from the layer's side.
- **The tombstone is held ASIDE, never flagged in place**, so `follows` keeps exactly the shape the
  contract declares. A tombstone field on a follow is a field every reader of the listing has to
  know to ignore, and one of them eventually would not.
- **`__followActions.restore(follow)`** takes the whole record, because the optimistic write is on
  this side; the layer's own record replaces it when the refetch lands.

**What it demands of the backend**, recorded in `docs/reference/frontend-backend-demands.md` § 1 in
B-302's shape: an operation that RESTORES a removed follow. The interface names the form it asks
for — a soft delete with a restore — because the backend follows the interface.

**Held by R133's eleventh hold**, which compares the restored follow field for field against what
was taken away. Both halves are mutation-proved: reverting the undo to a create fails that hold
ALONE, and making the layer's removal hard again fails it together with the undo's own hold, the
follow having gone entirely — the optimistic write is rolled back rather than left as a phantom row.

---

### 3.4 `data-take`'s release-screen half — B-323, B-322

`legacy.js:9295` asks the arrivals door (`window.__arrivalsVerbs?.take(…)`,
`features/arrivals/verbs.ts`), which answers the panel's TITLE take since B-309. `:9296-9308` is
the engine's own INDEX branch behind it: `releases()[Number(…)]`, `bridge.back()`, a **260 ms**
wait, `actionTake`, and a toast.

**B-322: it says TWO sentences.** `actionTake` toasts « … récupéré — suivez-le dans « En vol ». »
and the delegation toasts « « res src lang » retenue — récupération lancée. » — two writes into one
`#toast` element, so the second overwrites the first and which one the operator reads is a race.

**The move**: the releases feature gets its own door — `features/releases/verbs.ts` — deciding the
same way the arrivals door does: **by asking whether the value is its own**, never « is it a
number? » (refused once already as a rule about spelling: `2012`, `1917`, `300` are titles). The
release screen's door asks its own offered list. Done when
`grep -c "closest\.dataset\.take" …/legacy.js` reads **0**, the 260 ms wait is gone, and the take
says **one** sentence.

R123 (`take.py`) holds both takes and walks the release screen; **it stays green with its count
unchanged**, and B-322's sentence gets a hold of its own that samples the toast element ACROSS the
gesture — a hold reading it only at the end sees one sentence whether or not two were written.

---

## 4. DOIT-4's pastille — the one surface this lot DRAWS

The map's DOIT-4 row reads `partly`: R124 proves a legitimate act under a busy pipeline is
ACCEPTED; the VISIBLE half — the constitution's own « En file — pipeline en cours » said of a
MEDIUM — does not exist. Measured: `fr.json` holds one key, `screens.arrivals.queuedBold` =
« en file » (line 466), and it belongs to the pipeline PASS's own strip on Arrivées
(`features/arrivals/page.tsx`, `data-part="live-activity"`, R66 reads it). **Nothing says it of a
medium.**

**Method, in this order and no other** (§15, the maquette's README):

1. **A named state first**, in `engine/states.js`: a queue item whose ask arrived while the
   pipeline runs, or while §20's bound is met. A named state is harness, not surface.
2. **Then the rule**, red: it reads the pastille on that state AND on the act under `busy.py`'s
   scenario (`setOperationOutcome` on the three new operationIds).
3. **Then the drawing.**

**The operator judges it on his phone** — the design host on 8712 serves the built `dist`, so the
state named here is the state he sees.

**D8, and it is the only expected divergence.** The oracle WILL read divergences on the states
whose panels gain a button and on the pastille's own state. Each is accepted WITH the register
entry or clause it serves (DOIT-4, B-301, B-302, B-323) — never by moving the interface back — and
the reference is re-recorded ONCE at the post-merge gesture, not by this wave. **A divergence on
any other state is a defect and a STOP.**

---

## 5. B-313 — the follow panel's doubled action

Measured in `features/acquisition/follow-actions.ts`: `primaryAction` falls through to
`{ text: say("seeJourney"), target: { journey } }` for a medium with no sheet that is not followed,
and `secondaryActions` emits `{ text: say("seeJourney"), … }` **unconditionally** — where
« Voir la fiche » beside it is guarded by `facts.hasSheet && (…)`. So the panel offers « Voir le
parcours » twice.

**The rule first, and it is written before the repair**: a panel's actions are counted **BY LABEL**
and a label appearing twice is refused. Red on `main`'s follow panel for a medium that has no
sheet. Then one condition, mirroring the `seeSheet` guard.

---

## 6. The instruments, and the debts that come with touching them

- **B-323's instrument half.** `harness/exits.py` names the engine's `setTimeout(…, 260)` sites in
  its own comment and counts them with `grep -n "setTimeout(.*260)"` — a command that sees a site
  only when its call and its delay share a line, which is how two went uncounted. This wave removes
  one of the seven (the release screen's take), so it touches the inventory and takes its debt:
  **re-take it with `grep -n ', 260)'`, name all six that remain by the call they wrap** — the
  `add:` identify branch (`actionResolve` after `bridge.rewind`) is the one nobody had named — **and
  say in the comment which command counts them.** R103 is NOT widened into a blanket refusal: five
  of the six are L13's, and the rule against the wrong subject was refused once already.
- **B-247's producer half.** Every panel this wave touches is added to `persistence.py` (f)'s list:
  a moved surface keeps its nodes across a store write.
- **B-305.** Ruled 2026-09-04: an open swipe stays open. Not restored, not relitigated.
- **B-315.** Three parts, not confused: (a) the button's SIZE is the operator's amendment and is
  **not touched**; (b) one press adds thirty and the reserve is intact — the `sugmore` rule reads
  that on a NAMED STATE for the deck's empty state, **which does not exist yet**
  (`[data-sugmore]` is reachable from no state), so this wave gives it one; (c) the end mark on
  `acq-discover-exhausted` says the reserve is spent, and the rule reads it there too.
- **B-320.** Filed, and opened only if this wave opens `now-tab.tsx` or `page.tsx`'s non-ready
  branches. It does not plan to.

---

## 7. Named STOPS

- **Stop A — B-316, a drawing decision that is the operator's.** On Découvrir's poster tile
  `data-panel="sug:N"` and `data-mediasheet` sit on the SAME node; on the deck card the media verb
  is on the tile's child. Ten finger points on two card kinds, and the media SCREEN opens every
  time — the suggestion producer is right and unreachable. This wave moves `data-follow`,
  `data-dropsug` and `data-sugmore` on those very cards, so it WILL open that file. **Before
  drawing, the two readings and what each costs go to the steward, who relays to the operator, and
  this wave waits**: (i) a long press for the panel, as the library's rows do since L14; (ii) the
  panel on the tap, with the sheet reached from inside it.
- **Stop B — the oracle diverging on a state this wave did not touch.**
- **Stop C — the pull request.**

Anything believed necessary outside the contract: STOP and ask the steward first.

## 8. What stays out, said once

The global levers (parallelism bound, pause/resume of everything, « relancer la veille ») are
**L20**'s; the tracker policy is **L16**'s; who may act on whose tunnel is **L18**'s gate — the
verbs land **unconditional** here and are hidden per role later; the five surface-opening verbs
(`data-mediasheet`, `data-journey`, `data-resolve`, `data-releases`, `data-profile`) move with the
delegation in **L13**. No pixel is drawn that is not a verb's button or the pastille. **No line is
added to `legacy.js`** — the ledger refuses it, D5 forbids it, and a verb needing one has not
moved. `personalscraper/` is not opened (D7). `docs/production/` is not touched.

## 9. Done when

1. The three operations are declared, generated and mocked; three demands recorded in
   `docs/reference/frontend-backend-demands.md` by `compare-contracts.py --write`.
2. Each of the three verbs is CALLED (read on the network) and its state moves; under the busy
   scenario the ask is queued and said, never a 409 and never « occupé ».
3. `grep -cE "closest\.dataset\.(follow|pause|remove|dropsug|sugmore|take)\b" …/legacy.js` reads
   **0** (from 12).
4. `legacy.js` is strictly BELOW 31 591 non-blank and the ledger re-records it downward in the
   same commit as each subtraction.
5. DOIT-4's pastille exists on a named state, with a rule that reads it; the map's DOIT-3 and
   DOIT-4 rows read `served`.
6. B-301, B-302, B-313, B-322, B-323 read `fixed #<n>` by rule 3 (the rule, the mutation, the run).
7. Every rule landed with its mutation, seen red and restored, at the moment it was written.
