# maquette-mock-layer — the mock answers the declared code, one season family, two verbs that send

Register: **B-379**, **B-383** (two of its four verbs, plus a fifth of its class this wave files),
**B-396**, **B-380**. Rules **R170**–. Constitution: NE-DOIT-PAS-1 (« ne jamais affirmer ce qui n'a pas
eu lieu »), NE-DOIT-PAS-5 (« ne jamais masquer une erreur »), §13 (real data), §5 (season by season).
Decisions: D7 (the contract is the maquette's and it is what the interface REQUIRES), D8 (the oracle
measures geometry and computed style), D5 (the engine only shrinks).

A micro-wave on the layer the rules measure against, and on its seeds. It is one subject — a mock that
answers what the contract declares, over data that agrees with itself — which is why the four entries
travel together.

## 0. What moved, at a glance

| Entry | What was wrong | What closes it | Rule |
| --- | --- | --- | --- |
| B-379 | the layer answered 200 whatever the contract declared | the declared success code, read off `contract/openapi.json` | R170 |
| B-383 | « Re-scraper les métadonnées » (follow panel AND media sheet) and « Lancer à blanc » said a sentence and sent nothing | each verb calls its operation; the mock moves the state it answers about | R171 |
| B-396 | one queued folder offered candidates, so the undo window's riskiest path had no finger proof | a second ambiguous folder in the seed, and a walk by a real touch | R172 |
| B-380 | the sheet counted the catalogue's total as « aired » | aired is DERIVED from the catalogue's own episode dates; the season family and the two families that sum it corrected towards it | R173 |

---

## 1. B-379 — the mock answers what the contract declares

### The defect, measured

`design/src/mocks/scenario.ts:145` computed every outcome as
`status: armed ? (asked.status ?? 200) : 200`. The contract declares **201** for
`grabSeasonForFollow` and **202** for `requeueJourney` and `rescrapeJourney`; the layer answered **200**
to all three. It was read, not reasoned: R158's first run saw four season grabs and four `status: 200`
in `window.__mocks.answered()`, and every hold written on the literal code was red for a reason that
was not the act.

```
$ python3 - <<'PY'
import json, collections
contract = json.load(open('frontend/maquette/contract/openapi.json'))
codes = collections.Counter()
for path, item in contract['paths'].items():
    for method, operation in item.items():
        if method in ('get','post','put','patch','delete'):
            codes[tuple(k for k in operation['responses'] if k.isdigit() and k.startswith('2'))] += 1
print(codes)
PY
Counter({('200',): 55, ('202',): 2, ('201',): 1})
```

### The repair

`design/src/mocks/declared-status.ts` — a new module that IMPORTS the contract
(`frontend/maquette/contract/openapi.json`, the same artefact
`mocks/contract-conformance.test.ts` already reads) and builds
`operationId → the lowest declared 2xx`, once, at module evaluation. `scenario.ts`'s `outcomeFor`
reads it on **both** branches of its conditional:

```ts
const success = declaredSuccessStatus(operationId);
return { status: armed ? (asked.status ?? success) : success, … };
```

Both branches, because « unarmed » means « answer normally » and normal is what the contract declares;
a repair that touched only the other one would leave an operation with a latency dial answering 200.

**Never a hand-written table.** A map from operation to status declared a second time is the shape of
every drift this repository has paid for: the day the contract gains an operation answering 201, a
table stays right about everything it already knew. **An operation the contract does not declare
answers 200 rather than raising** — this function runs inside the answer path of every request, so
raising would turn a table/contract drift into a page that cannot load, hiding the drift behind a
symptom; the drift itself is R85's, which refuses a route the contract does not declare.

**What it costs**: the contract travels in the bundle, 144 KB beside the 2.1 MB of seeds this layer
already carries, and the whole module is dropped with the layer when `__MOCKS_BUILT_IN__` is false.

**What it does NOT change**: nothing in the application. `lib/query-client.ts` reads `answer.ok` and
names 204/205/304 as the bodiless ones; 201 and 202 were always inside both readings.

### The rule — R170 (`harness/declared_codes.py`), on the `--contracts` tier

| Hold | What it reads |
| --- | --- |
| the families | one operation per declared family is really asked for, and the layer answers the contract's own code — read from `window.__mocks.answered()`, never from the browser's request events (the seam replaces `fetch`, so a mocked call fires none) |
| the record | what `answered()` reports IS what the response carried. A rule reading only the record would be green over a layer that recorded one code and sent another |
| the corpus | every operation the contract declares a non-200 success for is among the ones the rule asks for. The floor that makes the holds above mean something |
| the dial | a scenario asking only for a latency still gets the declared success (the branch a half-repair would leave at 200); a scenario asking for a failure still gets exactly it |

It is on the contracts tier because a declared code is a NAME the contract chose, and B-379 is exactly
one that had moved on one side only. It reads no database and costs one page.

**The mutation**: `const success = declaredSuccessStatus(operationId)` forced to `const success = 200`
in `scenario.ts`.

---

## 2. B-383 — « said, not done », two of its four verbs and a fifth of its class

### Whose half this is

B-383 names four verbs. **Two are this wave's**: « Re-scraper les métadonnées » on the follow panel
and « Lancer à blanc » on a maintenance command. **Two are not**: « Remplacer la valeur » on a
secret belongs to the settings wave (B-334, #588) and « Lancer la veille maintenant » to L20 — it is
DOIT-6's operation, `POST /api/acquisition/detect`, ruled so by the operator on 2026-09-12. That
split is written into B-383's own body, and the entry closes only when all four owners have landed.

**A FIFTH verb of the same class was found and is filed as B-470**: the media sheet carries the SAME
« Re-scraper les métadonnées », drawn as `data-toast`. It was outside B-383's reading because round
two swept panel PRODUCERS and a sheet is a screen. Repaired here, in the same commit family, on the
orchestrator's ruling — one verb for both surfaces, because leaving a canned twin beside a repaired
one in the wave that builds the operation is the shape nobody later dares delete.

### The operation, and why the contract gains one

**The contract had none.** Its 58 operations carry `rescrapeJourney`, and `journey-verbs.ts` says in
its own header that this is NOT the media sheet's metadata re-scrape — it re-runs the tunnel's scrape
for one tracked staging item. The follow panel's verb is offered on `facts.inLibrary`, a medium of
the library, which may have no journey at all. The only relative is the maintenance command
`library-rescrape`, which is global.

So D7 applies to the letter: the verb exists on a validated surface, therefore the interface REQUIRES
an operation, and the maquette's contract declares it.

```
POST /api/media/{provider}/{providerId}/rescrape   →  rescrapeMedia
202  { provider, providerId, queued, runUid }      (required, all four)
```

`queued` and `runUid` are `requeueJourney`'s and `rescrapeJourney`'s, so the three relaunch verbs read
alike; the identity is echoed because the surface must know which sheet to re-read. Addressed by
PROVIDER IDENTITY and never by title (DOIT-11): twenty identities in this fixture are carried by two
title keys at once (B-088). The callers hold a title, so the crossing happens in the verb, through
`window.__referentiel.addressIdsFor` — the same reader `history-bridge.ts` already crosses with, not
a second translator. The three artefacts move in one commit, as `contract/README.md` requires:
`openapi.json`, the regenerated `src/contract/types.d.ts`, and
`docs/reference/frontend-backend-demands.md` recomputed by `compare-contracts.py --write` (the
register goes from 58 required operations to 59, and from 14 missing to 15).

### What the mock MOVES, and what the sheet reads

`MediaSheet` gains `metadataRefreshedAt` (nullable ISO date), and this is a DEMAND the code itself
had already filed: `media-details.tsx` drew a row « Métadonnées rafraîchies » whose value was the
constant `screens.media.metadataRefreshedValue` = « 10 août, 04 h 12 », with a comment saying « this
date is a CONSTANT, printed as a fact in every state […] correcting it means the backend serving when
the metadata was last read ». A fixed date printed as a fact is NE-DOIT-PAS-1 in one line.

- the layer holds `metadataRefreshedAt` in `mockState()` — **never in the seed**, so
  `check-mock-seeds.py --arm correspondence` is untouched;
- the handler writes it for EVERY title the identity names, and reads it back the same way;
- the instant is the layer's **frozen clock** (`scenario().now`), never `Date.now()`: this layer is
  deterministic by contract and a wall-clock stamp would put the oracle out of reach;
- the row reads it, with the constant as the **null** case and only as that — nothing has been
  re-read in a session that has just begun.

### What the engine loses (D5)

`legacy.js`'s `data-rescrape` branch is **deleted**, not duplicated — five lines, and the ledger is
re-recorded downward in the same commit (`engine/legacy.js` 31 466 → 31 460 non-blank). The reader
moves onto `lib/verbs.ts`, which is what D5 prescribes for a verb that gains a behaviour.

`installVerbs()` now publishes `window.__verbNames`. That is **B-473**: `registeredVerbNames` carried
the sentence « published for the rule that reads the seam from outside » and had no caller anywhere,
so the seam did not exist.

### Two consequences of the move, said rather than glossed

1. **`app/feature-verbs.ts` is new, and `shell.tsx` did not grow.** Three install lines in the shell
   took it to 402 non-blank against the 400 ceiling invariant 6 says is never extended. `lib/verbs.ts`
   holds the registry and may import no feature; a feature may import no other feature (invariant 7).
   So the list of features owning a tap verb lives in the frame — one import per feature, the species
   invariant 10 blesses by name. It costs **exactly 4** domain words in `app/` (measured with the
   change removed: 126; with it: 130), and the ceiling is raised to 130 in
   `scripts/frame-domain-baseline.json` with that arithmetic written beside it.
2. **A command that offers no blank run cannot be run blank.** The panel computed
   `dry = deletes ? true : store.maintBlanc` and labels its button from `action.blanc`, which is a
   different question — the capability, not the switch. While the button sent nothing the two could
   not contradict each other; the moment it sends, they can. The ask carries `action.blanc && dry`.
   Measured: with `dry` alone, « Lancer » on `library-status` (`dryRun: false`) asked for a BLANK run
   and R171's m4 read the pipeline still idle.

### The rule — R171 (`harness/said_and_done.py`), full suite

It reads the NETWORK and the STATE, never the message — a screen-reading hold passes over a build
that draws the right thing and sends nothing, which is what these verbs did for a whole wave under a
green gate.

| Hold | What it reads |
| --- | --- |
| m1 | the sheet's act is under a real finger; it sends `rescrapeMedia` with the **202** the contract declares (R170's repair, read from the other end); the layer held **no** instant before and holds one after; and the row on screen moved with it |
| m2 | the follow panel's twin sends the SAME operation, by a finger, on the one follow the library holds |
| m3 | the registry answers `rescrape` and the dying engine no longer does — a name answered on both sides acts twice |
| m4 | « Lancer » sends, and the layer's pipeline was `idle` before and is not after |
| m5 | « Lancer à blanc » sends, and the machine is still `idle` afterwards — a call that leaves beside a state that does not move, which is the whole of what « à blanc » means |

**How the pipeline state is read**, since no `GET` answers it: by asking for a BLANK run and reading
the `state` it answers. A dry run changes nothing by contract, so it is a probe and not an act; every
probe is taken after the calls under test have been counted.

**Why m5 exists beside m4**: a rule holding only m4 would be green over a blank run that had quietly
started the machine, which is the worse of the two defects.

**The subject the rule names** — « Dark Matter » — is measured and not chosen: `inLibrary` matches
`window.LIBRARY` on an exact title, and of the fourteen follows it is the ONLY one that does. B-383's
own reading named three, which was read on another scenario.

**The run**: 15 holds EXECUTED, no violation.

---

## 3. B-396 — a second subject, so the window's riskiest path has a finger

### The seed, and why it costs almost nothing

The entry asks for « a SECOND queued folder with candidate cards ». It was found
rather than invented: **« S.W.A.T. » is already a queued folder** (`seeds/stuck-loaded.json`)
and its own card carries the reason

> « Deux correspondances possibles — TVDB 328724 (2017) et TVDB 71663 (1975). Il faut choisir. »

— a folder whose text states two candidates over a resolution screen that offered none. It now
carries exactly those two as a pending decision.

**What that costs, checked rather than assumed.** `PENDING_DECISIONS` is a CONVERTED family, so
`check-mock-seeds.py --arm correspondence` does not re-derive it from `legacy.js` and no engine
fixture moves. **No queue count changes** — the card was already there. **No named state changes
subject**: nothing outside the resolution screen itself draws the pending decisions (`readDecisions`
has one reader, `features/arrivals/queries.ts`), and « Backrooms » — whose empty candidate list IS
the named state `arr-resolution` (« résolution, aucun candidat ») — is untouched. The two candidates
are the two the seed's own sentence names: a fixture contradicting its own reason is B-369's shape
wearing a new coat.

### What the walk found on the way — B-474

**No finger reaches a named folder's arbitration today.** Both ways in were tried:

- the arrivals card's « Résoudre → » carries `data-act="resolve"`, whose engine branch calls
  `screens.resolution()` with **no argument** — it answers the first stuck folder whatever card
  was tapped;
- the folder PANEL's « Résoudre → » carries `data-resolve="<folder>"`, and the engine reads that
  attribute as the **chosen candidate** for `currentState().resolveTarget`. Measured: with
  « Lucky »'s screen current, a finger on S.W.A.T.'s panel act answered « Identifié comme
  « S.W.A.T. » » **about Lucky**.

Filed as **B-474**, not repaired: the repair is the ORDER of the engine's delegation branches and
D5 says the engine only shrinks. R172 therefore NAVIGATES through `window.__screens.resolution`,
which is what every rule here navigates with, and says so in its own text. What B-396 asks to be a
finger is the **pick**, and every pick in the rule is one.

### The rule — R172 (`harness/two_picks.py`), full suite

| Hold | What it reads |
| --- | --- |
| t1 | « Lucky » is picked by a finger and leaves the queue at once |
| t2 | B's screen opens, B is picked by a finger INSIDE A's window, both are out and neither send has gone |
| t3 | only the LATEST message carries a way back |
| t4 | « Annuler » under the finger puts back ONE card at the index it held, and A stays out |
| t5 | and A's send is the one that leaves — the undo cancels its own send and no other |
| t6 | the put-back read on a list that has REALLY moved: a third folder settled by a finger between the pick and the undo, the list going from three to one |

**t6's put-back goes through the seam, and t3 is the reason**: the third act speaks, its message
replaces the pick's, and the pick's way back is out of a finger's reach by the interface's own rule.
t4 walks the undo with a finger on the ordinary case. What B-396 says was missing is not the finger
but a list that has really MOVED under the splice — which R162's w6 could not produce.

**What t6 asserts and what it only reads.** It asserts the card comes back **exactly once**. WHERE
it lands on a shortened list is read and printed — `putOneBack` splices at the index of the BEFORE
snapshot and `slice` absorbs an overflow, which B-396 records as reasoning rather than a reading.
**The reading**: it left index 1 of `[Backrooms, S.W.A.T., doc_fr_2026_final]` and landed at index 1
of `[Backrooms]` → `[Backrooms, S.W.A.T.]`. A rule asserting a position nobody has decided would be
writing a contract instead of holding one.

**The run**: 16 holds EXECUTED, no violation.

---

## 4. B-380 — one season family

### The rulings

The operator, 2026-09-11, quoted in B-380's body: « Manquant : les épisodes diffusés et non possédés !
S'il n'existe pas (pas encore diffusé) alors je ne peux pas les avoir donc ils ne manquent pas encore,
mais ils sont là pour informer l'utilisateur de sorties à venir d'épisodes. »

The orchestrator, 2026-09-12, binding on this wave: AIRED is DERIVED from the catalogue's own episode
`airDate`s at the referential's TODAY (2026-08-10) — no count typed a second time; the season family
is corrected TOWARDS what really aired, at the SOURCE (`engine/legacy.js`) and then
`build-mock-seeds.py --write`, never in a generated seed; Silo S3's hole is kept by a DATE only if
R128 still needs it (it does, below); an owned count above what aired is a trap to read (below);
the two families that SUM the season family are aligned in the same movement.

### The defect, measured

Over every season both families know, aired-by-dates against `seasons.json`'s `aired`:

```
$ python3 measure_aired.py        # scratchpad; counts sheet episodes with airDate <= 2026-08-10
agree=39 disagree=5 without_dates=0
  American Dad! S16: seasons.json aired=24 owned=24 | aired by dates=20 | catalogue total=20
  Silo S3: seasons.json aired=7 owned=6 | aired by dates=6 | catalogue total=10
  Les Animaniacs S1: seasons.json aired=134 owned=93 | aired by dates=172 | catalogue total=172
  Les Animaniacs S2: seasons.json aired=15 owned=11 | aired by dates=12 | catalogue total=12
  Les Animaniacs S3: seasons.json aired=26 owned=13 | aired by dates=46 | catalogue total=46
```

**Eight of the register's thirteen « disagreements » were not data**: Silo S3's 10, Furious S1's 8,
President Curtis S1's 10, Strange New Worlds S4's 10, Ted Lasso S4's 10 and American Dad! S22's 13
are catalogue TOTALS, announced episodes included, read in the place of `seasons.json`'s `aired` —
which agrees with the dates on every one of them. The defect was the sheet's DENOMINATOR:
`features/media/queries.ts` read `season.ep`, the catalogue's total, as aired.

### The seeds — corrected at the source

| Family (source) | Line | Before | After | Why |
| --- | --- | --- | --- | --- |
| `SEASONS` (`legacy.js`) | American Dad! S16 | 24 aired / 24 owned | **20 / 20** | aired by dates; owned by the sheet's derivation, below |
| `SEASONS` | Les Animaniacs S1 | 134 / 93 | **172** / 93 | aired by dates |
| `SEASONS` | Les Animaniacs S2 | 15 / 11 | **12 / 4** | aired by dates; owned by the sheet's derivation, below |
| `SEASONS` | Les Animaniacs S3 | 26 / 13 | **46** / 13 | aired by dates |
| `SHEETS_RAW` (`legacy.js`), under both `Silo (2023)` and `Silo` | S3E7 « Radio » | airs 2026-08-13 | **2026-08-06** | keeps Silo S3's hole, below |
| `INCOMPLETE` (`legacy.js`) | Les Animaniacs | 117 / 175 | **110 / 230** | the season family's sums |
| `follows.json` (converted — the seed is its own source) | American Dad! | 403 / 403 | **399 / 399** | the season family's sums |

Every number is replaced in place; no line is added to `legacy.js`, whose ledger reads
**31 460 → 31 460**. `build-mock-seeds.py --write` regenerated `seasons.json`, `media-sheets.json`
and `incomplete-shows.json`; `check-mock-seeds.py` is clean. After the correction the same command
reads **44 agree / 0 disagree / 0 without dates**.

**Silo S3's hole is kept by its seventh episode's DATE, and the measurement decides it.** After the
correction the seasons with a hole are Les aventures de Tintin S1–S3 and Les Animaniacs S1–S3 — every
one of them on a show NOBODY FOLLOWS — and R128 (a season with a hole at rest), R125, R124, R138 and
R159 all take their subject from `window.SEASONS` filtered on the FOLLOWS. Corrected by its count,
Silo S3 would read 6/6 and all five would lose their only subject. So `seasons.json` keeps 7 aired / 6
owned, and the catalogue's seventh episode moves before TODAY so that 7 is what the dates say. The
sentence is written beside the line in `legacy.js`.

**The trap: owned numbers above what aired.** American Dad! S16's library holds episode numbers
1–24 where the catalogue lists 20; Les Animaniacs S2 holds `[1, 4, 7, 9, 76–82]` where the catalogue
lists 12. These are not miscounts: they are two NUMBERING ORDERS — the library's and the catalogue
provider's — meeting at one season. `seasonsHeld` already counts only the numbers at or below what
aired (« a season of which ten have aired cannot be eleven-tenths complete »), so the owned count of
the season family is set to that same derivation, and the sheet and the follow panel agree BY
CONSTRUCTION. « 24/20 » was refused: it is not a correction. What the correction does NOT do is make
the four and seven files beyond the catalogue visible — they are counted and drawn nowhere — and that
is filed as **B-475**, open, a product question about numbering orders the operator rules on.

**The class, and its members now.** B-088's class — two families keyed the same way are not the same
answer — has two more members beside B-380, found while writing R173 and filed OPEN, owner « the wave
that next touches the seeds' identity »: **B-476** (« Dexter: Resurrection » is followed under a title
no sheet carries, and its follow's totals 96/96 are not its seasons' 10/10) and **B-477** (House of the
Dragon, Ted Lasso and Strange New Worlds are followed « à jour » while their sheets say `owned: false`,
the holdings keyed under a year-suffixed title the sheet's identity does not name, or absent).
Repairing B-476 here would move « Suivis » named states, which is B-369's cost and not B-380's subject.

### The layer, the contract and the client — one derivation

- **`mocks/handlers/media.ts`**: `readMediaSeasons` answers `aired: {"<season>": n}` beside its `owned`,
  derived by `airedBySeason` from the sheet's episode dates against the layer's frozen clock
  (`scenario().now`). A season the catalogue lists with no episode and no list has aired 0; one with a
  total and no list is null rather than a guess (measured: none today); a title with no sheet answers
  its season family's counts.
- **`contract/openapi.json`**: the field is declared, required, with its derivation in its description;
  the operation keeps its `x-seeded-from`. Types regenerated; `compare-contracts.py --write` leaves the
  demand register unchanged — a response field is not an operation.
- **`features/media/queries.ts`**: `MediaSeasons.aired`, and `seasonsHeld` reads it — the ONE line the
  defect lived in. `season-list.tsx`'s catalogue branch (a sheet not owned) reads the same answer
  instead of `season.ep`.
- **« à venir » (c)**: a season row draws `[data-part="season/upcoming"]` — « 3 à venir · dès le 20 août
  2026 » — from `announcedAfter`, the dates after TODAY; a season that aired nothing draws only « dès le
  … », and nothing when its row already prints its date. It offers nothing: `seasonUpcoming` already
  gates the act. Its look is `upcomingMark` — the muted tone the air date wears, NOT `.miss`'s: an
  announced episode is not a shortfall. Copy in `i18n/fr.json` (`upcomingEpisodes`, `upcomingFrom`).
  `season-list.tsx` 372 → 383 non-blank (ceiling 400).

### R160 re-aimed, and said out loud

R160 (`followed_sheet_act.py`) held « the sheet offers the season act » on Silo, Furious and President
Curtis. Furious and President Curtis hold everything that has aired: their sheets offered the act
ONLY because they divided by the catalogue's total — « 5/8 · 3 manquants » is what put an act under a
finger. With the denominator repaired the act is gone, which is right. The hold now reads the season
family first, and where no aired episode is missing it holds the OPPOSITE — the sheet offers nothing;
the walk under a finger stays on Silo, the subject with a hole. What is lost, and said: R160 no longer
presses an act that answers zero; with a correct denominator no finger reaches one on this surface.

### The rule — R173 (`harness/season_family.py`), full suite

| Hold | What it reads |
| --- | --- |
| the families | on EVERY followed show the season family holds, through the layer's own answers (`fetch` is the seam): the follow's totals are its seasons' sums; every season's aired count is the layer's derivation; where the sheet is owned, every owned count is the sheet's derivation. On every incomplete show it holds, the totals are the sums |
| the named exclusion | « Dexter: Resurrection » STILL disagrees (B-476) — asserted, not filtered, so it falls the day B-476 is repaired |
| the surfaces | on Silo S3, Furious S1, American Dad! S22 — the three followed seasons whose catalogue announces more than has aired, the only ones where the two denominators draw apart: the sheet and the follow panel draw the same « owned/aired » and the same « manquants », equal to the season family, and the sheet says how many are coming and from when |
| not yet aired | « Reine rouge » S2: drawn « à venir » with its date, no act, nothing missing. NOT « Scrubs », whose unaired S2 holds episodes: its sheet is the revival's and its owned numbers the original show's |
| aired long ago | « Les Animaniacs » S5 (1997) keeps its act, all 23 missing |

**Seen RED first**, on the private build with the seeds and the layer corrected and the client not:
48 holds EXECUTED, **10 violations**, all on the sheet — « 6/10 », « 5/8 », « 11/13 », their
« manquants », no announced information, and « Reine rouge »'s row. **Green** after the client: 48 holds,
no violation.

### Named states whose drawn numbers move, and the only divergences accepted (D8)

Predicted from the edits and measured against every named state that opens a sheet or a panel (the
other five sheet states — The Venture Bros, Superman, Marjorie Prime, Broadchurch, Widow's Bay — have no
row that changes): **`mediasheet-series`** (Silo S3 « 6/7 · 1 manquant · 3 à venir », its seventh
episode aired), **`followsheet-complete`** (American Dad! S16 « 20/20 »), **`acq-follows-list`**,
**`acq-follows-group`**, **`acq-follows-grid`** (American Dad!'s totals, summed from its seasons), and
**`lib-incomplete`** (Les Animaniacs « 110/230 »). Any oracle divergence elsewhere is a STOP.

