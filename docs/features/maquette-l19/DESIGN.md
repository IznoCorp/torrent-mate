# L19 — The producers

**The contract is `docs/reference/frontend-architecture.md` § 4, entry `#### L19 — The
producers`.** It is not restated here: a contract copied into a second file is a contract wrong
in one of them. This document says HOW the contract is met — the seam a producer moves through,
where each one lands, what proves each move, and the readings taken on the way.

**Version.** The wave opened at 0.98.68 off `446b0e921`; `main` moved to `4c0e274a7` while
phase 02 was being written and had itself reached 0.98.68, so the branch was rebased and the
bump re-taken to **0.98.69**. Recorded here because a version written once and silently
corrected is the shape `check-implementation-state.py` exists to catch.

**Constitution served.** §13 (real data — a producer reads the cache, never a fixture),
§17 (a restart cuts the household — B-300), §20 (a tunnel per media — the journey sheet moves
into the feature that owns the tunnel), DOIT-3, DOIT-4, DOIT-8, NE-DOIT-PAS-3, NE-DOIT-PAS-9,
NE-DOIT-PAS-6's spirit (B-300).

---

## 0. The state this design was written against

Measured on 2026-09-04, on `feat/maquette-l19` at `446b0e921`, each with the command that
produces it. **These figures are the design's starting point and are NOT the wave's report** —
the fifth review rule says a figure is written once, on the final head, and `REPORT.md` is where
that happens.

| Reading | Command | Value |
| --- | --- | --- |
| producers | `grep -c "panel\.open(" …/engine/legacy.js` | 10 |
| markup writes | the survey's inventory command (`frame-survey.md` § 1.1) | 9 |
| delegation reads | `grep -c "closest\.dataset\." …/legacy.js` | 132 |
| dismissal waits | `grep -n "setTimeout(.*260" …/legacy.js` | 7 |
| shell seams | `grep -n "install[A-Za-z]*(" app/shell.tsx \| grep -vc "^\s*//"` | 25 |
| the three under the ceiling | `check-frontend-boundaries.py --arm size` | `mocks/stream.ts` 399 · `app/shell.tsx` 398 · `features/acquisition/add-screen.tsx` 395 |
| frame floors | `check-frame-domain.py` | `ui/ 0, lib/ 18, app/ 129` |
| engine | `grep -cve '^[[:space:]]*$' …/legacy.js` | 32 461 |
| fixture families over 100 lines | D5's bracket-match method | 9 declarations, 26 375 lines |

The last row differs from the plan's 26 366 by nine lines. The plan measured at `9ce9b0508` and
this reading is at `446b0e921`; the method is the same and is re-run on the final head. **The
difference is the deliverable, never the absolute.**

---

## 1. The seam a producer moves through

A producer is called from a click delegation, in the middle of a task that cannot await. It is
therefore **not a hook and not a component**: invariant 10's own words, « a function from the
cache to a descriptor ». Three pieces carry that, and only the first is new.

### 1.1 `registerProducer` — the door, beside `registerBlock`

`ui/panel/contract.ts` already carries the half of this that exists: a feature ADDS a block kind
by declaration merging and REGISTERS what draws it. A producer is the same shape one level up —
a feature adds a panel kind and registers what PRODUCES it — so it goes through the same file,
which is the one file both sides may depend on without depending on each other.

```ts
export type PanelCache = { held: <Result>(key: readonly unknown[]) => Result | undefined };
export type PanelProducer = (subject: string, cache: PanelCache) => PanelDescriptor | null;
export function registerProducer(kind: string, produce: PanelProducer): void;
export function producerFor(kind: string): PanelProducer | null;
export function refuseProducer(kind: string): never;
```

**`PanelCache` is structural on purpose.** `ui/` may not import a feature (invariant 7) and
carries a domain-word ceiling of ZERO (invariant 10); a `QueryClient` type would import the
library into the primitive and a query KEY would name a domain. `held` takes an opaque key and
answers what is cached under it. `ui/` learns nothing.

**`refuseProducer` mirrors `refuseBlock`, and for the same measured reason.** A kind nobody
registered must raise loudly rather than open an empty panel — that is the shape a forgotten
registration wears, and silence would blame the data. `window.__unknownProducer` publishes it
for the rule, exactly as `window.__unknownPanel` does.

### 1.2 `app/panel-host.ts` — who holds the cache and who dispatches

`installPanelHost(store)` becomes `installPanelHost(store, queryClient)` — **an edited line in
the shell, not an added one** — and publishes one more verb:

```ts
window.__panel.produce = (kind: string, subject?: string) => { … }
```

It looks the kind up, calls the producer with `{ held }` over the query client, and opens the
descriptor it answers. A producer that answers `null` opens nothing: that is the honest reply
for a subject the cache does not hold yet, and it is the reply the engine's own producers give
today by returning early.

`kind` and `subject` are opaque strings here. `app/`'s domain-word count does not rise.

### 1.3 A producer module, and where it is named at boot

`features/<domain>/panel-<subject>.ts`, registering at module evaluation — the shape
`features/media/panel-seasons.tsx` already has and `app/shell.tsx` already imports for its side
effect. One module per feature is named in the shell; that module imports the feature's other
panel modules, so **the shell's list is one line per contributing feature and never one per
producer.**

**The shell may only FALL** (§ 7 of the brief). Its ledger is kept per phase in the phase file
and totalled in `REPORT.md`; what it loses is named in § 5 below. A phase that would add a line
without having removed one first is a phase in the wrong order, and the size arm says so at the
commit that takes it.

### 1.4 What the engine keeps until L13

The delegation branch stays and becomes one line — `panel.produce("follow", title)` in place of
`openFollowSheet(title)`. **The verb is still the engine's**; what leaves is everything behind
it. That is what makes each move provable at zero divergence: the same tap, the same descriptor,
the same `ui/panel` rendering it.

---

## 2. The ten producers, and where each one lands

Spans measured by bracket-matching each declaration in `legacy.js` at `446b0e921`.

| Producer | Lines | Feature | Panel kind | Family it takes |
| --- | ---: | --- | --- | --- |
| `openUserSheet` | 26 | `features/account` | `account` | `ACCOUNT` |
| `openActionMaintenance` | 57 | `features/maintenance` | `action` | `MAINT_ACTIONS` |
| `openSecret` | 45 | `features/settings` | `secret` | `SECRETS` |
| `openSetting` | 51 | `features/settings` | `setting` | `SETTINGS`, `SETTINGS_STATE` |
| the sort sheet (`data-sort`) | inline | `features/library` | `sort` | `TRIS` |
| `openSugSheet` | 45 | `features/acquisition` | `suggestion` | `SUGGESTIONS` |
| `openAddSheet` | 37 | `features/acquisition` | `add` | `SEARCH` results |
| `openMoreSheet` | 28 | `features/acquisition` | `more` | — |
| `openJourneySheet` | 44 | `features/acquisition` | `journey` | journey stages |
| `openFollowSheet` | 207 | `features/acquisition` | `follow` | `LIBRARY`, `OWNED`, `SHEETS_RAW`, `INCOMPLETE` |

Plus, outside `panel.open`:

- **The Découvrir feed** — `deckHTML` (19), `advanceDeck` (48), `mountDeck` (13), `refreshDeck`
  (6), `fillSug` and `sugFoot`; the seven inventory sites between `legacy.js:8315` and `:8540`.
- **The episode popover's SENTENCE** — `openPopEp` (24), driven from `legacy.js:9911`. The
  frame's half already lives in `app/popover-host.ts` behind `{ anchor, content }` and is NOT
  touched (`frame-model.md` Part 12: the frame places, the feature says the sentence).

### 2.1 The seasons block is already React, and it stays

`features/media/panel-seasons.tsx` registers `"saisons"` through `registerBlock`. What
`legacy.js:31707` still does is BUILD the descriptor that names that block. **The descriptor
moves; the block needs nothing.** The follow producer lands in `features/acquisition/` and names
a block `features/media/` registered — which is not a feature import (invariant 7 holds): the
name crosses through `ui/panel/contract`, which is exactly what an open union is for.

### 2.2 The copy moves to `fr.json` in the same commit as its producer

Every producer's French is written into `legacy.js` today, under the engine's french-debt
allowance (`check_french_debt` refuses those words to every file but the dying engine). A
producer landing in a feature carries no French: its strings are **extracted, never retyped** —
a retyped string renders correctly while the reference is broken — into `i18n/fr.json` under a
`panels.<kind>.*` namespace, read through `useTranslation`'s `t` outside React via `i18next`'s
own `t` (a producer is not a component and cannot call the hook).

**This is the one place where a conversion could move a pixel by accident**, and it is where the
oracle earns its keep: a character lost in extraction changes a rectangle, and the oracle is
read at zero divergence on every phase.

---

## 3. What proves a move

Four instruments, and each answers something the others cannot.

### 3.1 The oracle — the move itself

`make maquette-oracle`, green at **zero divergence**. This is a conversion lot: a descriptor
rendered by `ui/panel` from a React producer is the same descriptor rendered from the engine's.
A divergence is a defect, not an accepted difference.

### 3.2 R100 hold (f) — node identity across a store write (B-247's producer half)

`harness/persistence.py`'s hold (f) reads a PAGE's own nodes across `window.__store.write({})`
and asks `isSameNode`. Its docstring says today, in its own words, that it does NOT read « the
containers the dying engine fills on Découvrir » because « those are the producers' half of the
same defect, and no surface here owns them ». **This lot owns them.**

The hold gains, phase by phase:

- the **panel body's** own nodes, on the states that open one (`sheet-user`, `sheet-more`,
  `sheet-journey`, `followsheet-complete`, `followsheet-gaps`, `settings-field-*`,
  `maintenance-topic`), with a floor per state so a panel drawing nothing cannot pass as kept;
- the **Découvrir containers** — `#sugitems` and the deck — on `acq-discover-*`.

**The mutation is not optional and it is specific**: a producer that writes its markup inline as
`{ __html }` re-creates its children on every render (B-295 — React 19 assigns `innerHTML` on
the prop OBJECT's identity), so the mutation is exactly that — remove the memo at the site, see
the hold fall naming the right nodes, restore. `ui/markup.tsx` is the one door and
`scripts/check-component-once.py` refuses a second.

### 3.3 R103 — the dismissal's gap (B-249's SHAPE)

`harness/exits.py` measures the gap the producer's `setTimeout(…, 260)` leaves and **PRINTS**
it, refusing nothing, because « the wait belongs to the PRODUCER … and a producer is Part 12's —
L19's ».

Seven sites carry that wait, and **all seven are in the DELEGATION, not in a producer's body** —
measured, and it is the correction this design makes to the brief's own § 2, which reads as
though a producer carried its site:

| Site | Verb | Owner |
| --- | --- | --- |
| 9792 | `data-` add-from-resolution | arrivals' — not this lot's |
| 9861 | `data-releases` | releases' — not this lot's |
| 9882, 9885 | `data-profile` | settings/releases — not this lot's |
| 10215 | `data-journey` | **the journey producer's** |
| 10249 | `data-resolve` | arrivals' — not this lot's |
| 10255 | `data-take` | **the arrivals' verb, and this lot moves it** |

So **two of the seven go with this lot** and five do not. The reversal R103 is promised —
« REFUSES the gap instead of printing it » — is owed **when the last site goes**, and the last
site is not this lot's. This design records that plainly rather than claiming a reversal it
cannot make: R103 gains a **named, refused floor on the two sites that leave** (the gap on the
journey path and on the take path must be zero) and keeps printing the rest. The clause in the
contract that says R103 « then REFUSES the gap » is answered for what this lot owns and is
carried forward for the rest, in `REPORT.md`, with the five sites named and their owners.

### 3.4 The guards — and B-306, which is this wave's to build

`check-frontend-boundaries.py --arm size`, `--arm reference-slice` (a slice member the engine no
longer publishes is a type that lies — it drops in the same commit as its publisher),
`check-frame-domain.py` (`app/` must go DOWN), `check-no-french.py`, `check-component-once.py`,
`check-mock-seeds.py`.

**B-306 is built FIRST, in phase 1**, because every later phase is read through it.

---

## 4. B-306 — the size arm learns to count

`GRANDFATHERED` maps a file to a LABEL and nothing else, so a grandfathered file may grow
without limit and the arm prints clean; L14 added 77 non-blank lines to the engine under a
decision titled « dies by subtraction » and nothing said so.

**The repair.** Each entry carries a label AND a recorded count:

```python
GRANDFATHERED = {
    "engine/legacy.js": ("L13 — the engine dies by subtraction, surface by surface", 32461),
    "engine/states.js": ("L13 — the scenario table goes with the engine it drives", NNN),
}
```

- **above the recorded count → violation**, naming the file, the record and the reading;
- **below it → printed**, with « re-record it in this phase », and it IS re-recorded in the same
  commit that subtracts. A count re-recorded later is a count nobody compared.
- The recorded count is measured the same way the arm measures the file — non-blank lines — so
  the two readings cannot drift apart by definition.

**Its mutation is read by hand.** `scripts/mutate.sh` decides by reading journal `FAIL` lines
and a guard never prints one (B-273), so it answers « no hold fell » whatever the guard says.
The mutation is therefore applied by hand — one line added to `legacy.js` — and **the arm's EXIT
CODE is the reading**, with both exit codes written into the phase file. `git status` is
verified empty after the restore.

---

## 5. The shell's ledger

`app/shell.tsx` stands at 398 of 400. It may only fall.

**What it loses**, and each is tied to the phase that takes it:

| Line | Phase | Why it dies |
| --- | --- | --- |
| `installSuggestionsLookup` import + call | Découvrir | `window.__suggestions` existed for the deck to index into; the deck reads its own feature's cache |
| `installEngineData` import + call + its two comment lines | the last producer that empties `NEEDED` | « what the engine reads with no component to ask for it » — a React producer asks for what it draws |

**What it gains**: one side-effect import per contributing feature. `features/settings/panel-field`
is already one of them and its target changes rather than its count.

**The order therefore matters**: a phase that adds a shell line runs after a phase that removed
one, and the size arm refuses the mistake at the commit that makes it. Where the ledger cannot
be made to balance for a phase, that phase **installs its producers from the nearest installer
that boots once and owns no surface** — the precedent is `installPanelHost`'s own
`installArtworkArrival()` call, taken at L14 for exactly this ceiling.

`mocks/stream.ts` (399) and `features/acquisition/add-screen.tsx` (395) are **not written in**:
the 412 mock is a NEW file under `mocks/`, and `openAddSheet` becomes a new file BESIDE
`add-screen.tsx`. A single added line in either is a red gate in the phase that adds it.

---

## 6. The two verbs, and the rule written before the move

`grep -ln 'data-take' frontend/maquette/harness/*.py` and `grep -ln 'cancelsetting' …` both
return nothing: **no rule holds either verb today.**

So each verb takes **two commits**:

1. **The rule, on the ENGINE's side**, seen red under a mutation of the engine's own branch —
   `scripts/mutate.sh` on `legacy.js`, the rule falling and naming the right defect, restored.
   A rule written after the move proves only that it agrees with the move.
2. **The move**, read green by the same rule, its assertion count unchanged.

- **`data-take`** — emitted by React (`features/releases/releases-screen.tsx:113`), read by the
  engine (`legacy.js:9889`, through the 260 ms site at `:10255`). It is the arrivals' verb.
- **`data-cancelsetting`** — emitted and read by the engine (`:7607`, `:9578`). It is the
  settings feature's.

**No third verb moves.** The contract's « the delegation handles only the frame's verbs » is
read against the measurement: 132 delegation reads over 71 verbs, of which the frame owns six.
Moving sixty-five verb readers is a behaviour surface the first review rule forbids a conversion
wave from carrying, and the brief that opens this lot names exactly two and says « you do not
add a verb ». **This design executes the two, measures the residue, and `REPORT.md` names every
remaining verb with the lot that owes it** — so the clause is discharged by a named inventory
rather than by a claim. (§ 7.1: a reading of the contract is written down, not assumed.)

---

## 7. The four map rows

`product-intent-map.md` names L19 as the owner of a missing **instrument** on four rows. Each
row's « Unproved » clause is the rule's specification; **no surface is drawn to make a row
green.**

- **DOIT-8** — the confirmation before replacing a film the library owns is one line
  (`legacy.js:10788–10789`) plus the toast at `:10811`. The rule walks « add a film the library
  owns » on `/add` and reads both. Lands with `openAddSheet`.
- **NE-DOIT-PAS-9** — every LIST row naming an identified medium, and the galleries outside
  `harness/gallery.py`'s five (`/add`'s results, `acq-now`), carries a path to the medium's
  sheet. Lands with the producers that draw those rows.
- **NE-DOIT-PAS-3** — no mutation under a busy scenario is refused with a 409 or an « occupé ».
- **DOIT-4** — a legitimate action asked during a run is queued VISIBLY. **One instrument with
  NE-DOIT-PAS-3.** The row says the resolve queue's « En file » pastille « has no copy in
  `fr.json` and no rule ». **Read against « no surface changes »**: if the queued state is drawn
  today, the rule reads it and the row turns `served`; **if the pastille does not exist, drawing
  it is a behaviour change and it is NOT this lot's** — it is filed with L21 as its owner and
  the row reads `partly` with the reason. Which of the two it is, is measured in that phase and
  recorded there.

---

## 8. The two behaviour phases — LAST, each in its own commit

The first review rule: a conversion wave does not carry a behaviour repair. These two are the
contract's, so they are kept at the very end, after every producer has moved at zero divergence,
and each lands alone with its rule **seen red first**.

### 8.1 B-299 — the version conflict

`SettingsState.conflict` (`features/settings/reference.ts:55`) and `mocks/state.ts:135,187`
declare it and set it `false`; nothing raises it and no `fr.json` key names it
(`grep -c "conflit" fr.json` → 0). Production answers **412** on
`PUT /api/config/files/{name}` when the file changed under the editor.

**D7**: the mock answers that shape, seeded from the contract (`contract/types.d.ts`), in a NEW
file under `mocks/` — never in `stream.ts`, which is at 399. The banner draws from the query's
error and offers reload; the copy is `fr.json`'s. **The rule drives a save over a mocked 412,
reads the banner, then mutates the reader and sees it red.**

No backend work: a 412 the backend already answers is mocked from its shape.

### 8.2 B-300 — the restart confirmation

`legacy.js:9590` sets `redemarrage = true` on the setting's save and the `dataset.restart`
branch drops it with a toast. Production confirms first. §17 is the clause: a restart cuts the
service for every account of the household.

The confirmation is `ui/dialog` (its paragraph colour and danger contrast held by R116 since
L12); the copy is `fr.json`'s. **The rule walks the tap, reads the dialog, cancels, reads the
flag STILL UP, confirms, reads the toast** — the cancel half is what separates a confirmation
from a delay.

Neither adds a verb the map does not already draw. **L21's three verbs stay out.**

---

## 9. What this design does not do

- **No pixel moves.** Every part's rendering is validated (the mission of 2026-08-19).
- **No verb is added.** « Récupérer cette saison », « Remettre en file », « Re-scraper » are
  L21's, on the producers this lot has just moved.
- **No grandfathered file is extended**, and none of the three files under the ceiling grows.
- **The swipe's snap is not restored** (B-305, ruled 2026-09-04).
- **`docs/production/` is not touched**, and `docs/archive/` is not re-created.
- **No backend work** (D7).
- **The frame's popover placement is not touched** — only the sentence it carries.
- **`app/engine-data.ts` is emptied, not repurposed.** It dies at L13; this lot removes each
  family from `NEEDED` as the producer that needed it moves, and deletes the file if `NEEDED`
  empties.

---

## 10. Deviations

Recorded in the phase file that takes them, never here. **This document is what was decided.**
`REPORT.md` counts them by following the phase files, which is the only order that stops the
drift L14 measured three times.
