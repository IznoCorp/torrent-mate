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
