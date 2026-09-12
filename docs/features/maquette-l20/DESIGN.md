# L20 — The global levers and the history · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L20 — The global levers and
the history`. It is not restated here; what follows is the drawing the plan executes.

This document is written for a session that has none of the context it was produced in. Every
figure carries the command that produces it, every decision carries its reason, every screen
carries its named states. **Nothing under `frontend/maquette/design/` was touched to write it.**

---

## 0. What L20 owes, said once

§20 removed the subject of a page showing THE run: the pipeline is followed per media, through the
acquisition tunnel L19 has already drawn. What remains global is four things, and they are not one
surface:

| # | The thing | The operation | Its clause |
| --- | --- | --- | --- |
| 1 | the **parallelism bound** — how many tunnels run at once | **none: it does not exist** (§ 8.3) | §20-1 |
| 2 | **pause and resume of everything** | `POST /api/pipeline/pause`, `/resume` | DOIT-3 |
| 3 | the **watcher's on/off** AND **« relancer la veille »** — two operations, not one (§ 8.1) | `POST /api/pipeline/watcher` · `POST /api/acquisition/detect` | DOIT-3, DOIT-6 |
| 4 | the **history** of passages, a run's **detail**, its **raw log folded**, and the **locks** | `GET /api/pipeline/history`, `/history/{run_uid}`, `GET /api/maintenance/locks` | DOIT-6, B-296, B-297 |

And one defect whose owner L20 is: **B-371** — DOIT-4's « En file » pastille is drawn, its rules
pass, and no path a hand can take makes it appear, because the hand moves the engine's interface
store and the pastille reads the layer's `pipelineState`, which no surface calls. Closing it is
§ 4.6.

---

## 1. The arbitration, and how it was settled

**The question.** Where the levers land — a page of their own, or a section of Système.

**Reading A — a page of their own.** `features/pipeline/`, a `NAVIGATION` row under the `system`
group, path `/pipeline`, the history as its second half.

**Reading B — a « Pipeline » section of Système, the history where it already is.**

**What decided it, measured.** Système ALREADY draws the history:

    grep -n "screens.system.runs\|usePipelineHistory" frontend/maquette/design/src/features/system/page.tsx
    grep -n "usePipelineHistory" frontend/maquette/design/src/features/system/queries.ts

`features/system/page.tsx` renders a « Les passages » section over `usePipelineHistory()` →
`GET /api/pipeline/history`, six seeded rows
(`python3 -c "import json;print(len(json.load(open('frontend/maquette/design/src/mocks/seeds/pipeline-executions.json'))))"`
→ `6`), followed by a cross-reference button to Arrivées. The history's entry point is therefore
not to be created; it is to be given a run's DETAIL and its figures.

Five reasons for B, in the order that decides:

1. **The surface exists and is validated.** §15 — « ce que la maquette porte déjà est VALIDÉ par
   l'opérateur. On ne le rejuge pas. » Reading A moves a validated surface to a new page.
2. **A « Pipeline » destination is the subject §20 removed.** D12 and the operator's Q6 refused a
   Pipeline tab and a pipeline badge. A page carrying that name invites the surface back even when
   its content is only levers.
3. **B-297 already puts the locks on Système, by name** — « the orphan sweep is a machine fact — a
   block of Système ». The levers and the STATE they read (the lock, the two sentinels) then sit in
   one place, which is §13's one-derivation-per-question said about a surface.
4. **No navigation row, no drawer growth.** The drawer's non-bar list stays at three
   (`grep -c "inBar: false" frontend/maquette/design/src/app/navigation.ts` → 4, of which one is
   the `404` row that has no group).
5. **The frame is untouched.** A lever is an ACT; `docs/reference/frame-model.md` Part 6 gives the
   chrome geometry, the z-order and the badge's pointer — never an act. **A lever is not a frame
   concern, and this document says so because the brief asked the question.**

**What B costs, stated rather than hidden.** `features/system/page.tsx` declares in its own header
that Système « is a pure renderer — it writes nothing, ever ». That property dies the day a lever
lands there. It is a property of the implementation, not a clause of the constitution, and the
sentence is rewritten in the same commit as the first lever — a header that outlives its subject is
read as current by the next session (the species `CLAUDE.md` records twice). Second cost: a section
has no address of its own under D1, so the levers are reached by scrolling Système. Mitigated
because the two things worth addressing are addressed anyway — the run's detail is a screen (§ 4.5)
and the bound's editor is a panel (§ 4.1).

**Where it lives (invariant 10), therefore.** `features/system/`, in new files beside `page.tsx`,
never as a growth of it. **Not `features/pipeline/`**, and the reason is invariant 7 rather than
taste: `routes/system.tsx` is thin (`component: () => null`) and a page's body comes from
`NAVIGATION.Body`, so there is no route to compose two features in. A `features/pipeline/` component
imported by `features/system/page.tsx` would be a feature importing a feature, which invariant 7
forbids absolutely. The contract's own sentence — « `features/pipeline/` for the levers and the
history, **or the Système feature if the design puts them there** » — blesses this.

**RULED BY THE OPERATOR, 2026-09-12 — « Q1: B ».** The levers land in a « Pipeline » section of
Système, the history stays Système's and gains the run's detail and its figures, and start/stop
stay on Arrivées' pilot's bar, which becomes the surface B-371 wires. **Reading A is written above
with its cost so the next reader sees what was refused**, not so it can be reopened.

**And the plan is cut so that the ruling touched ONE phase, which is why the host is a phase of its
own.** Phase 3 creates the HOST and nothing later decides anything about it: under B a section
container in `features/system/`, under A a `NAVIGATION` row, a `PAGE_PATHS` entry, a route file and
a page. Every later phase adds a BLOCK into that host, which is one import line either way — so
phases 1, 2, 4, 5, 6, 7, 8 and 9 were identical under both readings. Cut by surface, with each phase
naming its own host, the ruling would have touched four of them.

### The four batched questions, and their rulings

| # | Question | Ruling | By whom |
| --- | --- | --- | --- |
| Q2 | the history row's figures — which of DOIT-6's numbers | the ROW keeps the composite line it already draws; the per-step counts and `reasons[]` live in the DETAIL. DOIT-6 is served by **two** operations, and the clause map's row must say so | steward, relayed to the operator as a confirmation |
| Q3 | the bound's control — stepper or field | **no new control.** The bound is a setting, edited by the settings feature's existing `number` field — already a named state. Système DISPLAYS it and offers the path to its panel | steward, overturnable |
| Q4 | the raw log's fold | **one `ui/` disclosure primitive** | steward, overturnable |
| Q5 | « relancer la veille » names the wrong operation | **BOTH are L20's**: the watcher's on/off (one lever, no figure) and the veille's relaunch (DOIT-6's figures). B-383's « Lancer la veille maintenant » half moves to L20; its three other verbs stay the mock-layer wave's | steward |

**Q4 carries a correction to this document's own first measurement, and it is recorded rather than
quietly fixed.** The arbitration said « the maquette has NO disclosure primitive ». That is true of
`ui/` and false of the tree:

    grep -rn "<details" frontend/maquette/design/src/ | grep -v engine/

reads three feature files — `features/acquisition/add-screen.tsx:350`,
`features/media/season-list.tsx:247`, `features/media/panel-seasons.tsx:143` — each writing
`<details>` raw, plus the dying engine at `legacy.js:30695`. So the primitive **consolidates three
existing sites**, and consolidating them is a CONVERSION of three surfaces this lot does not own.
**L20 writes the primitive and uses it once**; converting the three is named as a debt (§ 9) and is
not this lot's, because « one kind of change per wave » forbids a behaviour lot carrying a
three-surface conversion.

---

## 2. The addresses (D1)

| Surface | Tier | Address |
| --- | --- | --- |
| the levers, the locks, the history list | a section of a page | `/system` — no address of their own |
| the bound's editing panel | screen state | `/system?panel=setting:<settingId>` — the existing panel parameter, `<kind>:<subject>` |
| **a run's detail** | **content** | **`/run/$runUid`**, a SCREEN whose parent is `sys` |
| the raw log's fold | transient | **no URL.** Native `<details>` — adjusting, not arriving |

**Why the run's detail is a SCREEN and not a panel.** D1's content tier is « a media sheet, its
releases, a resolution » — a thing being LOOKED AT, identified. A run is identified by its
`run_uid`, is shareable and reloadable, and DOIT-10 owes it a URL. `SCREEN_PARENTS` gains
`"/run/$runUid": "sys"`, which is exactly the shape the five existing entries have
(`sed -n '/SCREEN_PARENTS/,/};/p' frontend/maquette/design/src/lib/addresses.ts`): a top-level path
with the page it belongs to. A cold `/run/<uid>` therefore renders Système beneath it and closing
the screen reveals a page already in place (D1b rule 3).

**Why the fold carries no URL.** It is a SETTING of a screen under D1b rule 1 — adjusting a
surface replaces, it does not arrive — and the three existing `<details>` sites carry no address
either. A fold that pushed a history entry would make Back undo a disclosure where the reader
wanted to leave the screen, which is §16's own named failure.

---

## 3. The contract (D7) — and it comes FIRST

The maquette's contract declares seven of the operations L20 needs and four of them not at all:

    python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sorted(p for p in d['paths'] if 'pipeline' in p or 'locks' in p or 'detect' in p))"

reads `/api/acquisition/detect`, `/api/pipeline/history`, `/api/pipeline/kill`, `/api/pipeline/pause`,
`/api/pipeline/resume`, `/api/pipeline/run`, `/api/pipeline/status` — and **not**
`/api/pipeline/watcher`, **not** `/api/pipeline/history/{run_uid}`, **not** `/api/maintenance/locks`,
**not** `/api/pipeline/stages`.

**A demand is FILED BY EDITING THE CONTRACT, never by editing the register.**
`docs/reference/frontend-backend-demands.md` says so in its own first line — « COMPUTED, NEVER
WRITTEN », built by `python3 scripts/compare-contracts.py --write` from the diff of
`frontend/maquette/contract/openapi.json` against `frontend/openapi.json`, with `--check` refusing
a committed register that differs. So every demand below is one edit to the maquette's contract
plus one regeneration, and the wording under « what it is for » is the demand's text.

### 3.1 What each operation must answer, and what the mock must MOVE

D7: « a mock that answers without moving certifies nothing ». So each line says what the layer's
state changes by.

| Operation (`operationId`) | Answers | What the mock MOVES |
| --- | --- | --- |
| `POST /api/pipeline/pause` (`pausePipeline`) | `{state}` | `pipelineState` RUNNING → PAUSED, and the `pause` sentinel of the locks read to `true` with an age |
| `POST /api/pipeline/resume` (`resumePipeline`) | `{state}` | PAUSED → RUNNING, the sentinel back to `false` |
| `POST /api/pipeline/watcher` (`setWatcher`, **new**) | `{watcherEnabled}` | `watcherEnabled`, AND the locks read's `sentinels.watcherPaused` — they are ONE fact and two readers |
| `POST /api/acquisition/detect` (`runDetection`, **re-shaped**) | `{runUid}`, 202 | a new run appended to the history with `outcome: "running"`, then — on the layer's own clock — ended with its counts |
| `GET /api/pipeline/history` (`readPipelineHistory`, **re-shaped**) | `{runs[], total, degraded}` | nothing; it READS what the verbs appended |
| `GET /api/pipeline/history/{runUid}` (`readRun`, **new**) | `RunDetail` | nothing |
| `GET /api/maintenance/locks` (`readLocks`, **new**) | `{pipelineLock, sentinels, sweep}` | nothing; the verbs above move what it reads |

**The two facts that must not become two truths.** `watcherEnabled` is answered by
`GET /api/pipeline/status` AND by `GET /api/maintenance/locks` (as `sentinels.watcherPaused`,
inverted). The pipeline's state is answered by `status.state` AND implied by
`locks.pipelineLock.held`. §13 — « une seule dérivation par question » — so the mock holds ONE
field and both reads project it, and R-L20-g reads the agreement. Two mock fields that can disagree
is the defect, not the interface's problem to reconcile.

### 3.2 The demands, in the register's own form

| operation | operationId | what it is for |
| --- | --- | --- |
| `POST /api/pipeline/watcher` | `setWatcher` | Turn the automatic trigger on or off, and say which it now is |
| `GET /api/pipeline/history/{runUid}` | `readRun` | One passage: what triggered it, how it ended, its steps with their counts and their reasons, and its raw output |
| `GET /api/maintenance/locks` | `readLocks` | What holds the pipeline, whether it is paused, whether the automatic trigger is paused, and what temporary entries a crash left behind |
| — (a configuration key) | — | **How many tunnels may run at once** (§20-1). The key does not exist: § 8.3 |

And four divergences of SHAPE, each with the side the interface follows:

1. **`GET /api/pipeline/history` — the interface follows the BACKEND.** The maquette's contract
   answers a bare array of `PipelineExecution`; the backend answers
   `{runs: RunSummary[], total, degraded}` with `limit`, `offset`, `sort`, `kind`
   (`sed -n '/^@router.get("\/history")/,/^    if sort not in/p' personalscraper/web/routes/pipeline.py`).
   Both additions are load-bearing: a history grows without bound so it pages, and **`degraded:
   true` means the read FAILED and the list may be silently short** — printing a short list as a
   complete one is NE-DOIT-PAS-5 exactly. The interface therefore takes the backend's shape, and the
   demand is only the naming convention (camelCase, as every other operation of the maquette's
   contract) plus the pre-formatted-line question of point 4.
2. **`POST /api/acquisition/detect` — the interface follows the BACKEND, and the design is stronger
   for it.** The maquette's contract answers `{detected, available, grabbed}` synchronously at 200
   (`mocks/handlers/acquisition.ts:191` answers exactly that). The backend answers
   `GrabTriggerResponse {run_uid}` at 202, and its own docstring says how the figures arrive: « the
   frontend polls `GET /api/pipeline/history/{run_uid}` for its outcome »
   (`python3 -c "import json;print(json.load(open('frontend/openapi.json'))['components']['schemas']['GrabTriggerResponse']['description'])"`).
   A synchronous answer is a lie about a run that takes minutes — DOIT-6 asks for « lancé → en
   cours → chiffré », which is three states, and the contract that returns the numbers at once has
   no second state to draw. **So the veille's figures come from `readRun`**, which makes that one
   operation serve both the history and DOIT-6.
   **And they arrive by the STREAM, not by a poll** — NE-DOIT-PAS-8, held by
   `scripts/check-live-relay.py`'s poll arm: `features/system/live.ts` already maps
   `WatcherRunTriggered`, `PipelineStarted` and `PipelineEnded` to the history key
   (`grep -n "WatcherRunTriggered" frontend/maquette/design/src/features/system/live.ts`), and L20
   adds the ACTIVE run's detail key to that same rule.
3. **`POST /api/pipeline/run` — the interface follows the BACKEND, and a named state's premise
   moves.** The mock queues a second pipeline run
   (`sed -n '143,147p' frontend/maquette/design/src/mocks/handlers/staging.ts`: `IDLE ? RUNNING :
   QUEUED`). The backend answers **409** for a second PIPELINE run — the strict duplicate §6
   permits, in its own words « la même action, sur la même cible, déjà en cours » — and queues only
   when a **maintenance** run holds the lock
   (`sed -n '196,231p' personalscraper/web/routes/pipeline.py`). The interface follows the backend
   because §6 is the constitution and the mock is wrong about it. **Consequence, named because a
   fixture change moves named states (B-369):** `arr-queued`'s precondition changes from « ask twice »
   to « ask while a maintenance run holds the lock », and R138's own arrangement of busy-ness reads
   the same field. The DRAWING does not change; the scenario does. § 6 carries the risk.
4. **The pre-formatted line.** `RunSummary` carries no result line; the maquette's seed carries
   `result: "1 rangé · 1 bloqué · 1 min 44"` — French, composed, from the wire. The register counts
   25 such fields already (`fields carried pre-formatted` in
   `docs/reference/frontend-backend-demands.md`), and `frontend-backend-demands-stream.md` § 7 is the
   ruling: the narrative is built by the INTERFACE from codes and parameters, never received as
   French. So the row's composite line is COMPOSED in `features/system/` from the counts, and the
   demand is that the backend carry the counts on the summary — today they are only in the detail's
   `steps[]`, which would mean N+1 reads to draw one list.
   **The one exception, on purpose:** `output_tail` IS raw output, « data displayed verbatim and
   folded (L20), not copy » — § 7's own words. It is not i18n and never will be.

---

## 4. The surfaces, drawn

Copy is given in « guillemets » exactly as `fr.json` will carry it, with the English key beside it.
**No string is retyped where one exists** — a retyped string renders correctly while the reference
is broken.

### 4.0 What is shared, and declared once

**The verbs.** L21 built the registry — `frontend/maquette/design/src/lib/verbs.ts`, nine verbs
registered today (`grep -rn "registerVerb(" frontend/maquette/design/src/ | grep -vc "lib/verbs.ts"`
→ 9). L20 registers five more, in `features/system/`, and **adds no line to the engine**:

| Verb | Value | What it does |
| --- | --- | --- |
| `data-pipeline-pause` | — | pauses everything |
| `data-pipeline-resume` | — | resumes everything |
| `data-watcher` | `on` \| `off` | sets the automatic trigger |
| `data-watch-now` | — | relaunches the veille |
| `data-run` | the `runUid` | opens `/run/<uid>` |

**`data-watch-now` is emitted from TWO surfaces and registered ONCE**, and that is §13 satisfied
rather than broken: the clause is one DERIVATION per question, not one button per act. The existing
button is `panels.standby.runNow` = « Lancer la veille maintenant » (the « ⋮ » sheet's « Veille et
obligations » panel, named state `sheet-more`), which B-383 measured as sending nothing; the levers
section emits the same verb. DOIT-3 — « agir là où l'on observe » — is then true of both surfaces,
and R-L20-c reads the act from each.

**The disclosure.** `ui/disclosure.tsx` + its variant: a native `<details>`/`<summary>` behind the
component API D2 asks for. Used once here (§ 4.5); three existing raw sites are a debt (§ 9).

### 4.1 S1 — Système § « Le pipeline » (the levers)

**Its place.** A section of `/system`, after « Les planificateurs » and before « Les passages » —
the levers stand between what SCHEDULES a run and what a run LEFT. New file
`features/system/pipeline-levers.tsx`, imported by `page.tsx`; the page gains one element and its
header's « pure renderer » sentence is rewritten in the same commit.

**What is on the screen.**

- the section heading « Le pipeline » (`screens.system.pipeline`);
- a guidance line, in the shape the schedulers' already has (`guidance()`): « Ces réglages valent
  pour tous les médias à la fois. » (`screens.system.pipelineGuidance`);
- **the bound** — a `topicRow()`-shaped row: « Tunnels en parallèle »
  (`screens.system.bound`) · its value, from the settings read · « Régler »
  (`screens.system.boundEdit`), which opens `?panel=setting:<settingId>`. It is a PATH, not a
  control (Q3);
- **pause / resume** — ONE state-dependent button, never both: « Mettre tout en pause »
  (`screens.system.pauseAll`, `data-pipeline-pause`) when the state is `running`; « Reprendre »
  (`screens.system.resumeAll`, `data-pipeline-resume`) when it is `paused`; and when it is `idle`,
  neither — with the reason said, « Rien ne tourne. » (`screens.system.nothingRunning`), because §8
  refuses a control that is simply absent;
- **the automatic trigger** — a two-state control: « Déclenchement automatique »
  (`screens.system.automaticTrigger`, `data-watcher`), and beneath it, when it is off, the
  consequence in words: « Les téléchargements terminés n'ouvrent plus de passage tout seuls. »
  (`screens.system.automaticTriggerOff`) with the sentinel's age. DOIT-2: a « rien ne se passe »
  with its reason;
- **the veille** — its last run and its figures, read from the history, with « Lancer la veille
  maintenant » (`panels.standby.runNow`, EXTRACTED, `data-watch-now`). Its states are § 4.2.

**`data-part` names** (English, D4, namespaced by `/`): `levers`, `levers/bound`,
`levers/bound-value`, `levers/pause`, `levers/resume`, `levers/watcher`, `levers/watch-now`,
`levers/figures`. `data-region="system/levers"` for the oracle.

**What changes when the operation answers.** The pause button becomes the resume button and the
locks block's `pause` sentinel turns to « Activée — <age> » in the SAME render, from the SAME read
— that is the agreement R-L20-g holds.

### 4.2 S2 — « Relancer la veille » and DOIT-6's figures

DOIT-6 is a SEQUENCE, and the contract's 202 is what makes it drawable (§ 3.2 point 2).

| Named state | What is on the screen |
| --- | --- |
| `veille-idle` | « Dernière veille : <when> » and its last figures, or « Jamais lancée » when the history holds none. The button offered |
| `veille-running` | « En cours… » (`screens.system.watchRunning`) with the live dot the pilot's bar already uses (`liveDot()`); the button NOT re-offered as idle, and not disabled-looking either — B-339's floor |
| `veille-figures` | « 3 nouveaux épisodes détectés, 2 disponibles, 1 récupéré » — `screens.system.watchFigures` with `{detected, available, grabbed}` as parameters, plural forms included |
| `veille-nothing` | « Rien de nouveau. » (`screens.system.watchNothing`) — the zero case is a real answer and is SAID, never an empty space |
| `veille-error` | the real error, loudly, through `SurfaceError`'s vocabulary: « La veille n'a pas pu s'exécuter. » plus the reason. **NE-DOIT-PAS-1: no success message on a dead run** |

**The figures are the LAYER's, never a constant.** They are read from `readRun` of the run the 202
named. R-L20-c compares what is drawn against what the layer answered — a hold reading the screen
alone passes a build that prints three plausible numbers.

### 4.3 S3 — The locks (B-297)

**Its place.** A section of `/system`, immediately after the levers, because three of the four
facts it carries ARE the levers' state. New file `features/system/locks.tsx`.

**What is on the screen** — `factRowsHTML`-shaped rows, the emitter Système already reuses verbatim:

- « Verrou du pipeline » (`screens.system.pipelineLock`) → « Libre » · « Pris — <age> » · « Verrou
  obsolète » when `stale` (the file exists and its PID is dead). The stale case says what to do and
  offers the path to the Maintenance command, never a repair button of its own;
- « Pause » (`screens.system.pauseSentinel`) → « Activée — <age> » | « Inactive »;
- « Déclenchement automatique » (`screens.system.watcherSentinel`) → « Désactivé — <age> » |
  « Actif »;
- « Entrées temporaires » (`screens.system.tmpOrphans`) → the sweep. `status: "pending"` draws a
  skeleton **on this block only** — the contract says so explicitly, and a skeleton over the whole
  section would hide three facts that have already answered. Ready: the count, and the entries with
  their ages; zero is « Aucune. ». Its repair is a Maintenance command, as the index's is — the path
  is a `crossReference()` to `maint`, which is the button Système already emits.

**`data-part`**: `locks`, `locks/pipeline`, `locks/pause-sentinel`, `locks/watcher-sentinel`,
`locks/sweep`, `locks/orphan`. `data-region="system/locks"`.

**No PID is printed.** Production prints « Pris — PID 41225 »
(`grep -n "PID" frontend/src/components/maintenance/LocksPanel.tsx`). NE-DOIT-PAS-4 — a process id
is jargon to the reader this interface is for, and §12 says the width is the rare resource. What is
printed is the AGE, which is what the operator decides on. The pid remains in the answer and is
drawn nowhere; if the operator asks for it, it is one line.

### 4.4 S4 — The history list

**Its place.** The existing « Les passages » section of `/system`, which keeps its heading and its
cross-reference to Arrivées. What changes: each row becomes a PATH to its run
(`data-run="<runUid>"`), and three states appear that the surface does not have.

| Named state | What is on the screen |
| --- | --- |
| `runs-list` | the passages, newest first. Per row: when · the trigger in words · « réussi » / « échoué » · the composite line, COMPOSED here from the counts (§ 3.2 point 4) |
| `runs-empty` | « Aucun passage enregistré. » (`screens.system.noRuns`) — a fresh install, and a real state |
| `runs-degraded` | `degraded: true`: « Cette liste peut être incomplète — la base des passages n'a pas répondu. » (`screens.system.runsDegraded`), drawn ABOVE the rows it qualifies. NE-DOIT-PAS-5 |
| `runs-loading` | the skeleton this page already draws (`skelCardsInner`) |
| `runs-error` | `SurfaceError` |

**The trigger is written in words, never as a legend.** `trigger` is `"cli"` / `"web"` /
`"watcher"` / `"cron"`; the row carries the sentence
(`screens.system.triggerWatcher` = « la veille », …). Production's `TriggerLegend` is refused, and
the refusal is already on the record in D12's list of standing absences.

**Both kinds are listed.** `kind` defaults to `"all"`, so maintenance runs appear beside pipeline
runs — which is what the operator sees today. A maintenance row names its `command` in words.

### 4.5 S5 — A run's detail, and its raw log FOLDED (B-296)

**Its place.** A SCREEN at `/run/$runUid`, parent `sys` (§ 2). New files
`features/system/run-screen.tsx` and `routes/run.tsx`; `SCREEN_PARENTS` gains its entry.

| Named state | What is on the screen |
| --- | --- |
| `run-detail` | the head — « réussi » with its tone, the trigger in words, the duration, `dry_run` said when true. Then the steps: one row per `StepTiming`, its name in French, its status, its elapsed time, and its counts — « 2 réussis · 1 ignoré · 1 non identifié ». Then `reasons[]`, each line as it is: §8's « chaque rien a sa raison ». Then the folded log. Then a `crossReference()` to Arrivées — « Ce que ce passage a laissé » — which is the LINK to L19's per-media half, never a redrawing of it |
| `run-detail-running` | `ended_at` null, `outcome: "running"`: the steps drawn as far as they go and the rest **not printed as answers** — §13. « Étape en cours » on the live one, and the remaining steps as « — », never as « pas faite » (§14: the interface says « inconnue ») |
| `run-detail-failed` | `outcome: "error"` with `error` drawn in full, and the step that failed marked. The failure is LOUD |
| `run-detail-log` | the fold OPEN — what a tap reveals. `output_tail` verbatim, monospaced, in its own scroll container (a raw line is wider than 390 px and only this block may scroll horizontally) |
| `run-detail-no-log` | `output_tail: null` — a legacy row recorded before output capture existed. « Sortie non conservée pour ce passage. » (`screens.run.noLog`). **§13: never an empty log box, which reads as « nothing happened »** |
| `run-detail-maintenance` | `kind: "maintenance"`: its `command` in words, its `options_json` as a fact row, and the same log |
| `run-detail-not-found` | a `runUid` nobody holds. « Ce passage n'existe pas ou n'est plus enregistré. » plus the path back to the list. DOIT-7 — a door out, never a dead end |
| `run-detail-loading` · `run-detail-error` | the two the contract requires of every surface |

**The fold is closed by default, and that is B-296's whole ruling.** « Journal brut »
(`screens.run.rawLog`) is the `<summary>`; DOIT-1 asks for clear French and raw lines are not that,
so the narrative of a passage is the steps above and the raw output is a secondary disclosure for
diagnosis.

**`data-part`**: `run`, `run/outcome`, `run/trigger`, `run/duration`, `run/step`,
`run/step-counts`, `run/reason`, `run/log`, `run/log-toggle`. `data-region="run/body"`.

### 4.6 S6 — B-371: the queued pastille reachable by a HAND

B-371 is not a drawing; it is a PATH that does not exist. Two pipeline notions and nothing joins
them: the layer's `pipelineState`, written only by the mock handlers for
`POST /api/pipeline/{run,pause,resume,kill}` which **no surface calls**; and the engine's interface
store `pipe`, which Arrivées' « Lancer le pipeline » writes at `legacy.js:9207` while touching no
network at all.

    grep -rn "runPipeline\|/api/pipeline/run" frontend/maquette/design/src --include=*.ts --include=*.tsx
    grep -n "closest.dataset.pipe" frontend/maquette/design/src/engine/legacy.js

**The repair, and it is the one L20 owes.** `data-pipe` moves onto `lib/verbs.ts` — the registry L21
built for exactly this — in `features/arrivals/`, and its handler CALLS `runPipeline` / `killPipeline`
instead of writing the store. The store's `pipe` field then derives from the layer's answer, which is
invariant 4 (« server state is never copied into client state ») applied to the one field that broke
it. The engine's branch is SUBTRACTED in the same commit — D5, and the size ledger is re-recorded
downward.

**What this makes true, and it is the point:** a hand taps « Lancer le pipeline » on Arrivées, the
layer's `pipelineState` moves, and DOIT-4's pastille — already drawn, already held by R138 — appears
on a path a person can walk. The pilot's bar keeps start and stop, where the operator already has
them; pause, resume, the bound and the automatic trigger are the levers' (§ 1). One control is not
in two places: START is Arrivées', PAUSE is Système's, and that cut is the page's own — « a machine
in trouble is Système's business; a medium in trouble is this page's »
(`sed -n '6,9p' frontend/maquette/design/src/features/arrivals/page.tsx`).

**The `arr-queued` consequence is § 3.2 point 3's**, and it is carried by the plan's phase 8 with
its oracle divergence named.

---

## 5. The named states

**Measured before naming them**: 87 states exist
(`python3 -c "import re;print(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"', open('frontend/maquette/design/src/engine/states.js').read(), re.M)))"`).
⚠ `frontend/maquette/README.md` says 54 twice and the constitution says 82; **both are stale, and
this document does not correct them — the wave's report does, with this command.**

L20 adds **26**, and every one is reachable by `window.__go("<id>")` with an English id:

| # | id | Label (French, as the panel lists it) |
| --- | --- | --- |
| 1 | `levers-idle` | Leviers — rien ne tourne |
| 2 | `levers-running` | Leviers — un passage en cours |
| 3 | `levers-paused` | Leviers — tout est en pause |
| 4 | `levers-queued` | Leviers — un levier demandé pendant une maintenance |
| 5 | `levers-trigger-off` | Leviers — déclenchement automatique coupé |
| 6 | `levers-loading` | Leviers — chargement |
| 7 | `levers-error` | Leviers — erreur |
| 8 | `veille-idle` | Veille — au repos |
| 9 | `veille-running` | Veille — en cours |
| 10 | `veille-figures` | Veille — le résultat chiffré |
| 11 | `veille-nothing` | Veille — rien de nouveau |
| 12 | `veille-error` | Veille — le run a échoué |
| 13 | `locks-free` | Verrous — tout est libre |
| 14 | `locks-held` | Verrous — le pipeline tient le verrou |
| 15 | `locks-stale` | Verrous — verrou obsolète |
| 16 | `locks-sweep-pending` | Verrous — le balayage n'a pas fini |
| 17 | `locks-orphans` | Verrous — des entrées temporaires restent |
| 18 | `runs-list` | Les passages — la liste |
| 19 | `runs-empty` | Les passages — aucun |
| 20 | `runs-degraded` | Les passages — la liste peut être incomplète |
| 21 | `run-detail` | Un passage — réussi |
| 22 | `run-detail-running` | Un passage — encore en cours |
| 23 | `run-detail-failed` | Un passage — échoué |
| 24 | `run-detail-log` | Un passage — le journal brut déplié |
| 25 | `run-detail-no-log` | Un passage — sortie non conservée |
| 26 | `run-detail-maintenance` | Un passage — une commande de maintenance |

**`run-detail-not-found`, `run-detail-loading` and `run-detail-error` are NOT in that list, and
saying why matters.** The loading and error phases of every surface are driven by the orthogonal
`phase` dial, not by an id of their own — `harness/states.py` walks every state through all three
(`sed -n '/Surface phase/p' frontend/maquette/README.md`). `levers-loading` and `levers-error` ARE
named because §13's « unknown parts are not printed as answers » is a DRAWING decision on this
surface — a bound printed as `0` while its read is in flight is a lie, and the dial alone cannot
name that hold. `run-detail-not-found` is reached by an ADDRESS (`/run/nobody`) rather than a state,
like `not-found` itself, and R-L20-j walks it.

**Where they LIVE is not where the 87 live**, and that is § 8.4's finding: `engine/states.js` is
grandfathered at 786 non-blank lines and the size arm refuses the count going up, so this lot's 26
are declared in `design/src/states/system.ts` with Système's own four moved beside them. The engine's
table imports and spreads them, shrinks, and its record is re-recorded downward.

**`harness/states.py` is seeded with all 26** — it asserts each renders content, has no horizontal
overflow at 390 px and raises no JS error. That is DOIT-9's half of this lot's « Done when », and it
is a SEED into an existing rule rather than a rule of its own.

---

## 6. The rules that bite

Numbers: **R160 is the highest in the suite on this branch**
(`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1`). R161–R164 are on
#585's unmerged branch and the settings micro-wave takes R165+, so this design writes
`R-L20-a…j` and **the implementer binds the numbers on the day**, re-taking that command first.

| Rule | File | What it READS | The mutation that fells it |
| --- | --- | --- | --- |
| **R-L20-a** — a lever ACTS | `harness/levers.py` | each lever pressed BY A FINGER (`elementFromPoint` at its own centre, what covers it named); the OPERATION on the network (`window.__mocks.answered()`); and the STATE moved afterwards | make the handler message without calling → the network hold falls naming the operation. Seen RED before the move: against `main` no lever exists |
| **R-L20-b** — DOIT-4 on a lever | `harness/levers.py` | a lever asked with the lock held by a maintenance run: QUEUED and SAID, nothing answered 409, nothing says « occupé » (R124's word list) | make the mock 409 the pause → the network hold falls |
| **R-L20-c** — DOIT-6's figures | `harness/watch_run.py` | the veille walked by a finger **from both emitters** (the « ⋮ » panel and the levers); the three numbers DRAWN compared against what `readRun` ANSWERED; and the zero case saying « rien de nouveau » rather than nothing | return different counts from the layer → the comparison falls. Print a constant → it falls too. This is the hold B-383 was missing |
| **R-L20-d** — §13, no answer that is not held | `harness/levers.py` | under the `loading` phase: the bound, the lock and the trigger carry NO printed value | print `0` for the bound while loading → falls |
| **R-L20-e** — the history and its detail | `harness/run_history.py` | a row leads to its OWN address (`/run/<uid>`, read on the URL); the detail's per-step counts equal the layer's; `degraded` is SAID above the rows | drop the degraded line → falls. Compose the counts from the drawn rows instead of the answer → falls |
| **R-L20-f** — B-296, the fold | `harness/raw_log.py` | at rest the disclosure is CLOSED and its text is not rendered (`offsetParent === null`, not merely `open` absent); a tap opens it; `output_tail: null` draws the sentence and never an empty box | add `open` → falls. Answer `null` and draw an empty box → falls |
| **R-L20-g** — B-297, the locks and the agreement | `harness/locks.py` | the four facts drawn with their ages; and the LEVERS agreeing with the lock read — pause offered only when the pause sentinel is absent (§13, one derivation) | set the pause sentinel in the layer and leave the pause button offered → falls |
| **R-L20-h** — B-371, the path a HAND takes | `harness/queued_by_hand.py` | Arrivées, « Lancer le pipeline » tapped by a finger; the layer's run operation ANSWERED (the network, not the store); then a season asked and the pastille present. **No `__go` anywhere in the walk** — that is the defect's own shape | revert `data-pipe` to the store write → the network hold falls and the pastille never appears |
| **R-L20-j** — the addresses | seeded into `harness/screen_addresses.py` and `harness/back.py` | `/run/$runUid` declared with `sys` as its parent; opening the detail PUSHES (asserted on `history.length`, never on the address alone); the fold ADJUSTS and pushes nothing; a cold `/run/<uid>` renders Système beneath | make the fold push → the `history.length` hold falls |

**R-L20-i does not exist**: DOIT-9 is the states seed of § 5, and inventing a numbered rule for
what `states.py` already reads would be a second instrument for one question.

**Every one is seen RED against `main` with no mutation needed** — the surfaces do not exist there.
That is the strongest form this repository asks for, and the report records it per rule.

---

## 7. What the oracle will do (D8)

The surfaces are **NEW**, so the reference RECORDS them and proves nothing about them: a state that
did not exist cannot have a divergence. What the oracle is for here is the other direction — **no
existing state may diverge**, and that is the gate on every phase.

New region roots in `frontend/maquette/regions.json` → `regions`: `system/levers`, `system/locks`,
`system/runs`, `run/body`. Each is anchored on `data-region`, never on a class (D4; the floor is a
hard zero). The 26 new states × 4 regions are recorded by
`python3 frontend/maquette/oracle.py --record` at the close.

**Two phases WILL move an existing state, and each divergence is named as its decision's:**

- **phases 3 and 4** — Système gains two sections, so `system`, `system-outage`, `system-loading` and
  `system-error` change LENGTH. `shell/page`'s height IS the page's length
  (`regions.json` → `shell/page`), so those four diverge on `system/body` and `shell/page` in each
  of the two phases. Accepted
  with the reason « L20 § 4.1/4.3: the levers and the locks land on Système ».
- **phase 8** — `arr-queued`'s precondition moves (§ 3.2 point 3). The drawing does not change, so
  the expectation is ZERO divergence; **if it diverges, that is a finding and not an acceptance**,
  because a precondition change that alters a pixel means the drawing depended on the wrong fact.

**And the oracle's silence over this lot proves nothing.** L20 writes BEHAVIOUR — five verbs, five
operations, one repaired path. § 6's trap table says it in full: at L11 no divergence over 2 958
measurements while four adversarial rounds found ~40, 13, 7 and 0 defects under a permanently green
gate. **This lot is held by the rules of § 6 or by nobody.**

---

## 8. What the plan gets wrong, measured

§ 7.1 asks a wave to say so rather than execute a directive that has lost its subject. Four
findings; the steward amends the plan. Three are about what the contract SAYS; the fourth (§ 8.4)
is a mechanical block nothing in the contract mentions.

### 8.1 « relancer la veille (`POST /api/pipeline/watcher`) » names the wrong operation

`docs/reference/frontend-architecture.md` § 4's L20 entry and `product-intent-map.md`'s DOIT-3 row
both write « relancer la veille » beside `POST /api/pipeline/watcher`. Measured:

    sed -n '325,355p' personalscraper/web/routes/pipeline.py
    python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(d['components']['schemas']['WatcherRequest'],d['components']['schemas']['WatcherResponse'])"

`POST /api/pipeline/watcher` takes `{enabled: bool}`, creates or removes the `watcher.paused`
sentinel and answers `{watcher_enabled}`. **It is the DIRECTORY watcher's on/off** — production draws
it as a Switch labelled « Déclenchement automatique »
(`grep -n "Déclenchement automatique" frontend/src/components/pipeline/PipelineControls.tsx`). It
relaunches nothing and answers no figure, so it cannot serve DOIT-6.

« Relancer la veille » with DOIT-6's figures is `POST /api/acquisition/detect` — §5's episode
watcher, already `runDetection` in the maquette's contract, already mocked at
`mocks/handlers/acquisition.ts:191`, and already offered by a button that sends nothing (B-383).

**Ruled by the steward, 2026-09-12: BOTH are L20's**, and B-383's « Lancer la veille maintenant »
half moves from the mock-layer follow-up to this lot. The three other « said, not done » verbs of
B-383 stay where they are.

### 8.2 DOIT-6 is served by TWO operations, and the map's row names one

`product-intent-map.md`'s DOIT-6 row sends « the run's figures » to
`GET /api/pipeline/history/{run_uid}` and L20. That is right for the PIPELINE's figures. The
VEILLE's figures — the « X détectés, Y disponibles, Z récupérés » the clause quotes verbatim — start
at `POST /api/acquisition/detect` and are READ from `readRun`. So the row must name two operations
and the two runs they belong to. The steward relayed it to the operator as a confirmation.

### 8.3 The parallelism bound does not exist, in any configuration file

§20-1 makes it « une variable de configuration réglable » and L20's entry says « the bound is a
setting and reads through the settings feature's contract ». Measured:

    grep -rn "parallel\|concurren\|tunnel" config.example/*.json5
    ls config.example/

One hit — `indexer.json5:11 max_workers_total`, the library scanner's per-disk workers, capped at
`len(mounted_disks)`; it is not a tunnel. There is no `pipeline.json5` among the 19 files, and the
settings read the maquette draws from answers six topics
(`python3 -c "import json;print([t['id'] for t in json.load(open('frontend/maquette/design/src/mocks/seeds/settings.json'))])"`
→ `rangement`, `nommage`, `acquisition`, `identite`, `service`, `passages`), none of which carries it.

**So the bound is a DEMAND, not a read.** The design proposes: a new file `pipeline`, the key
`pipeline.tunnels.max_parallel`, type `number`, filed in the `service` topic (« Ce qui tourne »),
with the note « Combien de médias peuvent être traités en même temps. » The mock answers it in the
settings read so Système can DRAW it and its panel can edit it; the demand says the backend owes the
key. **The topic assignment is the settings feature's catalogue to confirm**, and it is named here
so nobody invents a seventh topic for one key.

### 8.4 The named-state table cannot hold this lot's states

    grep -cve '^[[:space:]]*$' frontend/maquette/design/src/engine/states.js
    sed -n '94,98p' scripts/frontend_size_ledger.py

`engine/states.js` reads **786** non-blank lines and the ledger records it at **786**, grandfathered
to « L13 — the scenario table goes with the engine it drives ».
`scripts/check-frontend-boundaries.py` **refuses the count going UP** — B-306, discharged by L19 in
#558 exactly because a grandfathered file grew 77 lines under a decision titled « dies by
subtraction » while the arm printed clean. This lot declares 26 states; Système's four take twenty
lines for four (`sed -n '580,599p' frontend/maquette/design/src/engine/states.js`), so twenty-six is
on the order of a hundred and thirty. **Even two would be refused.**

**No lot owed this**, and nothing in L20's contract mentions it. The design takes it because L20 is
the first lot that cannot proceed without it: the state table's Système slice moves to
`design/src/states/system.ts`, the engine's table SHRINKS by eighteen net lines and its record is
re-recorded downward — the direction the arm accepts. Plan phase 2, which also writes down the
alternative it refused (making `window.__recordStates` accumulate — a behaviour change to the
harness's driving seam, to save a two-line import).

**This is a mechanism the wave BUILDS, and it advances L13** rather than working around it, which is
why it is § 8's finding and not § 9's debt.

---

## 9. What this design does NOT do, and the debts it names

- **No Pipeline tab, no pipeline badge** (the operator's Q6), **no event feed** (D12), **no trigger
  legend** — the trigger is written in words (§ 4.4).
- **No redrawing of L19's per-media surfaces.** A run's detail LINKS to Arrivées; it does not draw a
  card's progress, a journey or a blocked queue.
- **No `GET /api/pipeline/stages`.** It is the Flow Board's read — eight stations of current stock —
  and a board showing THE run is precisely the surface §20 removed. It stays in the register's
  « the backend has and the interface does not use » list, and **this design says so on purpose**
  rather than leaving it looking like an oversight: the clause map sends `stages` to L20, and L20
  declines it with §20 as the reason. The steward decides whether the map's row moves or the
  operation is written off like `config/validate`.
- **No PID printed** (§ 4.3), no repair button on a lock or an orphan — those are Maintenance
  commands and stay there (B-297).
- **Debt named, not paid: the three raw `<details>` sites.** `features/acquisition/add-screen.tsx:350`,
  `features/media/season-list.tsx:247`, `features/media/panel-seasons.tsx:143` keep writing
  `<details>` raw after `ui/disclosure.tsx` exists. Converting them is a three-surface conversion,
  which « one kind of change per wave » forbids a behaviour lot from carrying. It belongs to whichever
  lot next opens those files; **if no lot does, it is B-253's species and needs an entry.**
- **Debt named: the `result` line's counts.** Until the backend carries them on `RunSummary`, the
  history's composite line is composed from what the LIST answers, which today is nothing — the
  maquette's mock composes it from the run it appended. That is honest inside the maquette and is a
  demand on the backend (§ 3.2 point 4), not a shortcut to hide.

---

## 10. The clause map, at the end

The closing phase re-reads `docs/reference/product-intent-map.md` and `BUGS.md` and reports what
moved. **It proposes; the operator amends the map** — that file says so in its own header.

| Row | From | To | Held by |
| --- | --- | --- | --- |
| **DOIT-3** | `partly` — « to draw: relancer le watcher and the global levers » | the levers' half `served` | R-L20-a, R-L20-b |
| **DOIT-4** | `partly` — « the pastille is reachable by NO path a finger can take » (B-371) | `served` | R-L20-h, with R138 unchanged |
| **DOIT-6** | `partly` — « to draw: the run's figures; the raw lines folded » | `served`, naming TWO operations (§ 8.2) | R-L20-c, R-L20-e, R-L20-f |
| **NE-DOIT-PAS-2** | `served`, with « `GET /api/maintenance/locks` is uncalled — L19 » | the locks called; who holds the lock behind « En file » stays L19's line | R-L20-g |
| **NE-DOIT-PAS-5** | `served` | unchanged, and `degraded` is a new instance of it | R-L20-e |

**DOIT-5's « progress to the library » is NOT this lot's** and the row is not touched: it is per
media, in the tunnel, and L19 owns it. L20's share of DOIT-5 is the run's detail showing a passage
reaching its end — which is a different sentence, and the map must not be made to read as if the
per-media half had landed.

**B-296 and B-297 read `fixed`; B-371 reads `fixed`; B-383's veille half reads `fixed` and the entry
says which half.** `python3 scripts/check-bug-register.py` and
`python3 scripts/check-intent-map.py` are the gate on that, and ⚠ **B-346 is live**: the closure arm
reads an entry's body up to the first paragraph OPENING with another identifier, so an entry closed
beside a `**B-NNN's …` paragraph can be misread. The closing phase reads the arm's output rather than
trusting its exit code.
