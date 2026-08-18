# Current feature: shell-mobile — the v1 redesign

## THE MISSION CHANGED. Read this before anything else.

**This is no longer a mobile restyling of the shipped app.** It is a REDESIGN — a finished v1,
a version in its own right. The prototype is not a reference the current app is brought towards
piece by piece; it is the product, and the app will be rebuilt onto it.

That reverses the order of work:

1. **Finish the prototype first — every page.** Especially the ones that exist IN PRODUCTION and
   are not yet drawn here. A surface that production has and the prototype does not is a hole in
   the v1, not a later phase. The inventory is below and it is exhaustive.
2. **Then the operator judges.** The prototype is bound to the backend only once the operator
   considers the design AND the front-end architecture solid enough. That judgement is theirs, it
   is not a checklist, and no amount of green rules substitutes for it.
3. **Then, and only then, it becomes the new version.** Binding it to the backend is a separate
   mission with its own plan.

Until step 2 is passed, **nothing here derives app code**. The phase table that used to sit in
this file described the opposite order — deriving the app surface by surface — and it is gone.

**Branches:** one per wave (`feat/maquette-sp4b`, `feat/maquette-sp4c`, …) — each wave
squash-merges onto `main` after green CI and a clean final adversarial review (standing
operator instruction). What waits until the end is not `main` but the **binding**:
production keeps running the shipped SPA untouched, the merged waves change only the
prototype track (`frontend/maquette/`, its CI gates and docs), and nothing derives app
code until the operator's judgement (step 2 above). Non-negotiable.

**Spec:** `docs/superpowers/specs/2026-08-10-refonte-mobile-quatre-pages-design.md`
**The prototype:** `frontend/maquette/design/refonte.html` — §15 of `docs/reference/product-intent.md`. It is the VISUAL reference and carries the stylesheet; since SP4-fin wave 1 it carries no program — the engine is
`frontend/maquette/design/src/engine/legacy.js`, and every migrated surface starts in its own component.
**Bug register:** `BUGS.md` at the repo root — every reported defect, one closed at a time.

---

## Current state

**SP4 is complete.** Fifteen waves have landed, each squash-merged onto `main` after green CI
and a clean final adversarial review; none of them derives app code.

The catch-all is empty. `design/refonte.html` — 39 561 lines when SP4 opened, an entire
application inside one injected fragment — is **4 217 lines: a title and a stylesheet**. It
holds no script, no element, no inline handler. What it carries is BLOCK 1 and BLOCK 2, and
that is deliberate: the CSS contract is SP5's subject, and the spec fixes it there.

| Where it lives now | What it is |
| ------------------ | ---------- |
| `design/src/engine/legacy.js` | the engine, moved byte for byte, still JavaScript on purpose |
| `design/index.html` | the application shell's markup, in the document Vite owns |
| `design/src/states.js` | the 656-line scenario table — the harness's fixture, not the product's |
| `design/src/seams.ts` | the three names the engine imports instead of reading off `window` |
| `design/src/**` | every page and every screen, as components |

Every step of it was proven the same way: a state-by-state comparison of the WHOLE phone frame,
recorded before and replayed after — **0 divergence on 82 states**, at each of the three
SP4-fin waves, with the rule suite green at unchanged hold counts.

**One item of the spec's SP4-end list was argued rather than done**, and it is open to
contest: `__go` did not move shell-side. It holds `pilotage`, a latch the engine reassigns, and
an imported binding cannot be assigned — moving it would have meant exporting a setter for a
private flag. The 656-line TABLE moved; the driving stayed. The residual behaviour debts (the
deep-entry path, the 240 ms delay on `data-suivante`) are named in the SP4-fin plan and belong
to their own work: none of these waves changed behaviour, by construction.

| Wave | Branch | PR | What it settled |
| ---- | ------ | -- | --------------- |
| **SP1 — dossier servi** | `refactor/maquette-sp1` | #429 | The prototype became a served folder — `design/refonte.html`, images extracted as real files, `/assets/` session-gated and immutably cached (R70) — plus the operator's post-merge corrections: no inline action on a result card, and a screen layer that stacks (R71). |
| **SP2 — coquille Vite** | `refactor/maquette-sp2` | #430 | `design/` became a Vite project as well, and R72 proved the built output renders identically to the source — mutation-verified three ways. |
| **Bascule — the host serves the build** | `refactor/maquette-bascule` | #431 | `serve.py` serves `dist/index.html`, rebuilds under a lock when any input is newer, and on failure shows the build's own last words instead of a generic error (R73). |
| **SP3 — the router, by strangler** | `feat/maquette-sp3` | #432 | React 19 + TanStack Router as the outer shell and the SINGLE writer of URL and history; the legacy engine speaks `window.__pont` (R74), and `design/` gained its own strict typecheck gate. |
| **SP4a — the machinery** | `feat/maquette-sp4a` | #437 | `magasin` (TanStack Store) became the owner of the engine's state, the host learned to answer ANY address (SPA fallback), and `/profil/$titre` + `/ajout` landed as the first real routes (R75, R76). |
| **SP4b — the fiche and the panel** | `feat/maquette-sp4b` | #441 | `<PanelContent>`/`<Sheet>` became the single React panel and `openSheet()` retired to a tripwire; `/fiche/$titre` landed as a real route, and scroll is now kept per HISTORY ENTRY rather than per address. |
| **SP4c — resolution and releases** | `feat/maquette-sp4c` | #442 | `/resolution/$dossier` and `/releases/$titre` landed as real routes, `Pont.reculer(n)` killed M11's double Back, and R57's probe moved off the legacy `#screen` onto the screen's own identity. |
| **clean-code / i18n** | `refactor/clean-code-i18n` | #446 | No French in the code and no interface text in it either: `react-i18next` in the shell, every UI string in `fr.json`, English names across `design/src`, the harness and the two servers — and `scripts/check-no-french.py`, four arms, in `make check` and in CI, which is the half that outlives the wave. |
| **SP4d wave 1 — the shell owns a PAGE** | `feat/maquette-sp4d1` | #447 | Système, Maintenance and Configuration became final components inside the legacy `#view` through a page host (R77); R67 stopped judging a list it had not found, R60 gained a positive control, and the nine delegation attributes gained tap-driven holds. The wave's own adversarial review found a shipped defect no rule covered: the legacy removed a node React owned, tearing the root down. |
| **SP4d wave 2 — Arrivées** | `feat/maquette-sp4d2` | #448 | The pipeline's health page became a final component, with the first migrated control that WRITES (the pilot's bar, whose three states include DOIT-4's queue). A defect of class came out of it: a harness driver mutating the engine's `state` alias in place leaves a migrated page stale, and R77 gained the source-level hold that catches it. |
| **SP4d wave 3 — the Médiathèque, and E-001** | `feat/maquette-sp4d3` | #449 | The largest data surface, its infinite scroll and its search field became a component; the page host stopped supplying a root, because a page emitting four of them cannot live in one. E-001 shipped maquette-first with its own rule (R78), and a rule found 87 library sheets with no genre and no cast (B-030). |
| **SP4d wave 4 — Acquisition, and the last two pages** | `feat/maquette-sp4d4` | #450 | The last page wave: `viewAcquisition` — three tabs, a deck and a second infinite scroll — plus `viewProfil` and `viewIntrouvable`. `PAGES_OF()` carries no `render` at all, which is SP4-fin's entry condition. The review found four real defects, the first of which left the page inert: every action mutates the world IN PLACE and signals with `toucher()`, and the component subscribed only to the state. |
| **SP4-fin wave 1 — the engine leaves the fragment** | `refactor/maquette-sp4fin1` | #451 | The 35 052-line inline script became `design/src/engine/legacy.js`; the fragment fell from 39 561 to 4 507 lines and holds nothing executable. 0 divergence on 82 states. The engine republishes its 254 top-level names — 230 by value, 24 by getter, the split measured — because the harness drives it by bare name. Four rules had gone green over a file emptied of their subject; `common.py` now owns `DESIGN_SOURCES`. |
| **SP4-fin wave 2 — the markup leaves the fragment** | `refactor/maquette-sp4fin2` | #452 | The 287 lines of application shell move to `index.html` — not into React, because the engine captures its containers at module evaluation, before React has rendered anything. **The fragment is now a title and a stylesheet.** The login gate, built from both files now, is byte-identical. Two more readers had to follow the markup; R72 needed no renegotiation, measured. |
| **SP4-fin wave 3 — the bridge dies** | `refactor/maquette-sp4fin3` | #453 | The 656-line scenario table leaves the product for `src/states.js`; the state ALIAS dies (99 reads go to the store, and a whole defect class goes with it); 61 seam call sites become imports through live `export let` bindings, so a typo fails the build. R74 renegotiated — what it called a bridge is now a driving surface for measurement; R72 needed nothing, measured. |
| **English names — no French left in the code** | `refactor/english-names` | #455 | The operator named two examples (`data-suivante`, `trierLib`) and both were real: 141 of the engine's 446 declared names were French, and nineteen `data-*` contracts. Everything moved, including the seams three frozen-with-reason entries had been protecting (`pont`/`ecrans`/`panneau` → `bridge`/`screens`/`panel`) and the `data-key` values on both sides. `scripts/code-vocabulary.txt` turns the detector's question around — « is this word one we use? » has no holes by construction. The guarantor pass before merge found five things the green gate could not see: a vocabulary SEEDED from the code had licensed the 25 French words it existed to catch (declared debt now, bounded to the dying engine by `check_french_debt`); `data-*` names had a rule and no arm; `frontend/scripts/` was outside every scope; the production app still carried a `controle/` directory and 19 French names; and the renaming tool was silently rewriting interface copy through four forms it did not know — it reads its protected spans from TypeScript's own parser now. |
| **Les valeurs, les routes et les paramètres** | `fix/design-restart` | #456 | L'opérateur lève le gel qui gardait une adresse française : une route et un paramètre sont des NOMS, pas des données. Le vocabulaire d'états passe à l'anglais du backend à la feuille de style (rien n'était persisté, donc aucune migration), les routes suivent en prototype ET en production — les trois adresses françaises répondant en redirection, parce qu'un renommage qui met en 404 l'adresse qu'il renomme est une casse déguisée. L'outil de renommage a payé trois défauts du même genre — décalage UTF-16, `regions()` qui est un scanner JavaScript, et un mode valeurs si large qu'il a réécrit 429 lignes de prose avant d'être refait sur le bon critère : la chaîne entière, jamais le mot. L'hôte design se relance désormais quand son code change, l'asymétrie qui avait verrouillé l'opérateur dehors. |

The full record of each wave, in the words written when it landed, is in
`docs/superpowers/shell-mobile-wave-log.md`; the per-wave plans are in `docs/superpowers/plans/`.

### The latest wave, in full

**SP4-fin wave 3 — the bridge dies, and the fixture leaves the product**: Branch `refactor/maquette-sp4fin3`, version 0.97.24. Four things the spec named for SP4-end,
each proven at **0 divergence on 82 states**.

### The scenario table was never the engine's

`STATES` — **656 lines of FIXTURE** — was carried by the product so that something outside it
could measure the product. It is `src/states.js` now, importing by name the eighteen engine
names its entries call, which the engine EXPORTS explicitly rather than being reached through a
global.

**What did not move is the driving, and that is an arbitrage rather than an oversight.** `__go`
closes the harness panel, unmasks three overlays, resets the world unless asked not to, and
holds `pilotage` — a latch the engine REASSIGNS. An imported binding cannot be assigned, so
moving `__go` out would have meant exporting a setter for a private flag: one indirection
traded for a worse one. The engine keeps the mechanics and looks the state up in the table this
module REGISTERS with it — in that direction, so the engine never depends on the module that
measures it. An empty table is a legitimate state (a document with no driver cannot be driven)
and `__go` says so by name.

### The state alias is gone, and with it a whole class

`let state` was re-pointed at the store's object on every notification: a CACHED COPY, correct
only for as long as the subscriber refreshing it kept up. All 99 reads go through
`currentState()`, which reads the store. The seed became `INITIAL_STATE`, used once at boot; the
subscriber — whose entire body was the refresh — is deleted; `window.state` became a live read.

What that removes is a class, not an instance: a rule could drive a page by mutating the cached
object, and R77 had to hold that none did. With no cached object there is nothing to mutate.

### The seam is an import, and what that buys is narrower than it sounds

61 call sites — `panneau` 40, `ecrans` 14, `pont` 7 — stop going through `window` and import
from `src/seams.ts`. The exports are `let`, deliberately: the implementations need the store,
which the shell creates in its BODY, after its imports, and the engine is one of them. An ES
export is a LIVE BINDING, so the shell fills them at boot and the engine reads them at call
time, which is the only time it calls.

**Stated plainly, because it is easy to oversell**: the engine is JavaScript `tsc` does not
check, so this is not type safety at the call sites. What it is — a declared dependency, and a
name the BUNDLER resolves. Exercised: renaming one import to `pnot` fails the build.

**And the globals do not disappear**, for a measured reason rather than a tidy one: this harness
drives through them — `__ecrans` nine times, `__panneau` seven, `__pont` twice. They are the
same objects the shell fills the imports with, so the two ways cannot disagree.

### R74 renegotiated, R72 not — and both by measurement

R74's subject changed meaning: what it called « the bridge » was three globals bridging a
classic script to a module world, and that world is gone. It now describes a DRIVING SURFACE for
measurement. Recorded in `regions.json`. R72 needed nothing at all, measured rather than assumed:
the fragment is still injected verbatim, exactly once.

### Two errors of mine, and one of them killed the page

The blanket rewrite of `state.` landed in PROSE in four comments. Found with a scanner that
tracks comment / string / template-interpolation context properly — which also showed that the
six occurrences it flagged « in strings » were `${…}` interpolations, i.e. code.

Worse: the edit to the publication block **never ran**. Its command was issued in a shell whose
`cd` had failed, and I read the un-edited line in a later grep without registering it. The result
was `state: { get: () => state }` with the binding removed — so the name resolved to
`window.state`, i.e. to that getter, and the page died at load with « Maximum call stack size
exceeded ». **A failed command is not a no-op; it is an edit that did not happen, and the next
read must be treated as evidence rather than scenery.** The reason is written at the exact line.

---

## Where to start

**`BUGS.md` at the repo root is the bug register.** Every defect the operator reports is written
there when it is reported, one is closed at a time, and a fix closes only with a mutation-tested
rule that covers the path the operator actually walks. Read it before starting anything. Closed
entries keep their full history in `BUGS-CLOSED.md`, indexed from `BUGS.md`.

Read, in this order:

1. `frontend/maquette/README.md` — the prototype's contract, its named states, the rule set,
   and the traps already paid for. It is short and it saves days.
2. `docs/superpowers/specs/2026-08-10-refonte-mobile-quatre-pages-design.md` — §7 carries the
   method. Its §8 phases describe deriving the app surface by surface, which is the order the
   mission reversed: read them as history, not as instructions.
3. `BUGS.md` — what is reported and not yet confirmed.

Then draw the missing surfaces, in the order of the inventory below.

**Serve the prototype locally** (never on 8710 or 8711, which the reverse proxy routes to
production and staging):

```bash
cd frontend/maquette && python3 serve.py 8899
```

`serve.py` serves the BUILD (`design/dist/`), rebuilding under lock when sources
change — a plain `http.server` would serve the sources and measure nothing real.

The prototype needs a wrapper supplying a viewport meta; the harness scripts build one. Without
it Chrome falls back to the legacy 980px layout viewport and every measurement is wrong.

**Run the harness** with the Python that carries Playwright — it is the only one that has it:

```bash
cd frontend/maquette/harness
for s in *.py; do
  [ "$s" = common.py ] && continue   # the shared plumbing, not a rule
  /Users/izno/.pyenv/versions/3.11.9/bin/python3 "$s" > /dev/null || echo "FAILED: $s"
done
```

Every script fails through its exit code, not through its output. A script that only prints
cannot fail, and a script that cannot fail is a report nobody is obliged to read.

**Two traps, each already paid for twice.** A stale copy of the scripts lives in
`/tmp/tm-refonte`; running from there measures the previous version. And `/tmp/tm-refonte/
wrapped.html` — the harness's copy of the BUILD, the same document the host serves — must be
rebuilt and re-copied before every run, or the same thing happens one level down:

```bash
cd frontend/maquette/design
npm run build
cp dist/index.html /tmp/tm-refonte/wrapped.html
rm -rf /tmp/tm-refonte/vite && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
ln -sfn "$(git rev-parse --show-toplevel)/frontend/maquette/design/assets" /tmp/tm-refonte/assets
```

`pwa.py` measures the LIVE host `tm-design.iznogoudatall.xyz`, not the local server. After
editing `serve.py`: `pm2 restart torrentmate-design`.

---

## What the v1 still owes, page by page

Read from the shipped router (`frontend/src/router.tsx`) and the shipped nav model
(`frontend/src/components/layout/nav.ts`) against the prototype's named states.

Two of production's routes are already redirects and owe nothing: `/scraping` → `/medias`,
`/registry` → `/systeme`. A third, `/maintenance`, is **also** a redirect — `MaintenanceRunRedirect`
sends it to `/systeme?tab=journal`, or to `/pipeline?run=…` when it carries a run. The page it
names has not existed for some time; its panels live on `/systeme`.

### The v1's structure, and it is settled

The prototype's four tabs and production's four do not agree: production's bar is
`Acquisition · Médias · Pipeline · Contrôle`, the prototype's is
`Acquisition · Médiathèque · Arrivées · Système`. The disagreement was arbitrated by the
operator rather than split down the middle, and the arbitration replaced the question:

> **The cut is by the NATURE OF THE TROUBLE.** A medium in trouble is Arrivées. A machine in
> trouble is Système. A setting is Configuration. A command run against the library is
> Maintenance.

That axis is the reason the panels can be placed at all. Production's `/controle` has no axis —
it stacks blocked media (`ATraiterList`) on top of disk and provider health (`CompactHealth`)
with nothing saying why they share a page. **So `Contrôle` does not survive as a destination**:
its seven panels each have a home under the rule, and none of those homes is a new page.

|         |                                                                           |
| ------- | ------------------------------------------------------------------------- |
| Bar     | `Acquisition · Médiathèque · Arrivées · Système` — unchanged              |
| Off-bar | `Maintenance` · `Configuration`, reached from Système and from the drawer |
| Gone    | `Contrôle` — the binding mission redirects `/controle` to Arrivées        |

Where every shipped panel lands. The first block places itself; the second was arbitrated;
the third is derived from the rule rather than asked again.

| Shipped panel                                         | Home            | Why                                                                                                                                                                               |
| ----------------------------------------------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ATraiterList` — blocked staged media                 | **Arrivées**    | a medium in trouble                                                                                                                                                               |
| `ScrapeActivityPanel`                                 | **Arrivées**    | a medium being identified                                                                                                                                                         |
| `RecentResolutions`                                   | **Arrivées**    | a medium just unblocked                                                                                                                                                           |
| `FlowBoard` — the eight stages                        | **Arrivées**    | the pipeline's health is where its media are                                                                                                                                      |
| `CompactHealth` — disks, index, Redis, providers      | **Système**     | a machine in trouble                                                                                                                                                              |
| `ActionCatalog`, index repairs, `DestructiveLogPanel` | **Maintenance** | commands run against the library                                                                                                                                                  |
| `PipelineControls` + `PipelineActionBanner`           | **Arrivées**    | DOIT-3 — act where one observes. The blocked stage and the button to relaunch it are one glance                                                                                   |
| `RunHistoryTable` · `RunDetail` · `RunLogFeed`        | **Système**     | « succès d'exécution » and « logs ». Arrivées keeps the PRESENT — what is stuck, what arrived in 24 h — and never becomes an archive                                              |
| `AcquisitionSummaryCard`                              | **Acquisition** | the tab already shows it in full; it does not owe a second, shorter copy                                                                                                          |
| `SchedulersPanel`                                     | **Système**     | did it fire, did it succeed. Its HOUR is a setting and lives in Configuration — the schedule and its health are two objects that share a name                                     |
| `LastRunDigest` — « X détectés, Y récupérés »         | **Arrivées**    | a count of media, not of executions. The run's _history_ is Système's; the last run's _result_ is the story of what arrived                                                       |
| `StalledPanel` — per-step reasons                     | **split**       | a torrent deferred for ratio is a medium (Arrivées); a step that raised is code (Système). The operator's rule is explicit: no blocked medium in Système, but its code errors yes |

### What is therefore still owed — nothing, as far as the SURFACES go

| Surface                                                                | State                                                                                                                            | Rule                       |
| ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| `/login`, `/acquisition`, `/medias`, `/config`, `/media/:provider/:id` | drawn before this                                                                                                                | R49–R63                    |
| **Arrivées**                                                           | **drawn** — the pilot's bar, the nine steps of the last real run, its digest, and « arrivé dans les 24 h »                       | R66, `harness/arrivals.py` |
| **Système**                                                            | **drawn** — the deferral is lifted. PM2 services, schedulers, the pipeline's executions, disks, index, dependencies, code errors | R67, `harness/machine.py`  |
| **Maintenance**                                                        | **drawn** — six rubrics over the engine's 26 real `library-*` commands, plus the destructive journal                             | R67                        |
| **Configuration**                                                      | **extended** — a seventh rubric, « Les passages programmés », over the six real cron schedules                                   | R60 extended               |
| `*` (NotFound)                                                         | **drawn** — and it closed a crash: an unknown id used to stop the whole frame on a TypeError                                     | R68, `harness/address.py`  |
| multi-user account                                                     | **drawn** — the one real account, its session read from `web.json5`, and the place of the others marked EMPTY                    | R68                        |

Every figure on these surfaces is read from the live system — `pipeline_run`, `pm2 jlist`, `df`,
`library.db`, the maintenance registry, `web.json5`, `ecosystem.config.js`. Four of the rules go
back to those sources AT RUN TIME rather than comparing against a number written beside them: R66
against `pipeline_run` by run_uid, R67 against `pm2 jlist` and the maintenance registry in both
directions, R68 against `web.json5`.

---

## The third axis: what the prototype owes as an APPLICATION

The operator's judgement is on the design **and** the front-end architecture. The design is
measured by 71 rules; the architecture was measured by nothing. These are its numbers, read from
the file rather than remembered — the column on the right is what changed while the missing
surfaces were being drawn.

| Measure                              | Today               | Before                        |
| ------------------------------------ | ------------------- | ----------------------------- |
| lines of code (poster data excluded) | 41,400              | 39,454                        |
| hardcoded data sets                  | **83**              | 57                            |
| network calls                        | **1**               | 1                             |
| direct `state.` accesses             | **265**             | 248                           |
| `render()`                           | 1 defined, 47 calls | 1 defined, 43 calls           |
| named `window.__` seams              | **11**              | 21 counted with their usages  |
| `history.pushState` / `replaceState` | 5 / 3               | 4 / 0                         |
| **reads of `location`**              | **3**               | **0**                         |

None of these numbers is a defect **of the prototype**: a single dependency-free file is
exactly what made it verifiable. They are the **seams** the binding will have to open.

### The three questions, and what they are worth now

**1. Where does a piece of data come in?** 83 constants, up from 57. The number rose and the
situation improved, which is only apparently contradictory: every new constant is read from a
living source named in its comment — `pipeline_run`, `pm2 jlist`, `df`, `library.db`, the
maintenance registry, `web.json5`, `ecosystem.config.js` — and **four rules go back to those
sources at run time** instead of comparing against a number written beside them. R66 checks the
run by its `run_uid`, R67 counts processes against `pm2 jlist` and commands against the engine's
registry in both directions, R68 reads `web.json5`, R63 reads `acquire.db`.

That is the answer to the question, and it is executable: **a constant whose value is verified
against its source is a named seam; a constant nothing verifies is a coupling.** R63 demonstrated
it on its own by failing when the scheduler ran — a rule that fails with TIME does not signal a
defect, it points at a seam. The triage remains to be done: how many of the 83 are verified, and
how many are not.

**It fell again the same day**, a few hours later: the 15:20 run pushed Silo from 9 to 11. Twice
in one session, without a single line of the prototype being touched. That is no longer an
illustration of the question, it is its answer: **those constants cannot be maintained by hand,
and the binding has no choice but to wire them.**

**2. Who owns the state?** Nobody — 265 direct accesses, up from 248. Nothing moved on this
front and that is deliberate: splitting the state requires splitting the file, and a single file
is exactly what made those 71 rules writable. **This is the question that remains whole**, and
the only one of the three that cannot be settled without first deciding how the prototype gets
split.

One thing was still learned crossing it: `state.pipe` **leaked** from one named state to the
next, so the same id did not render the same thing depending on the path taken to reach it. R10
found it. That is the exact cost of ownerless state, and the counter-measure fits in one
sentence: **every named state names ALL of its dials**, as it already named its page and its
phase.

**3. Where does a route live?** It used to live in `state.page`, and the URL did not carry it.
**That is settled.** The measurement that said so was final: `history.pushState` four times,
`location` read **zero** times — the interface told the browser where it was and never asked it.
That was not a debt to hand over, it was a **non-conformity with DOIT-10**, and it showed: a
reload fell back onto the opening page, and no screen could be sent to anyone.

The state travels in the QUERY, not in the path, and that is a decision: this document opens
from a static server, from the prototype host, and from `file://`, and path-based routing
requires a server that rewrites every unknown path to the document — two of those three cannot.
The binding will map `?page=lib` onto production's `/medias`; what is judged now is that the URL
and the interface never contradict each other. R69, `harness/url_state.py`.

---

**Next action:** draw the missing surfaces in the order of the inventory above — Arrivées first,
because it takes the largest transfer and the arbitration hangs on it — then answer the three
questions of this section. Each surface follows the method below — real data, named states,
a rule that bites, a mutation that proves it.

Note that question 3 was not only architecture: **DOIT-10 requires every detail to have its
URL**, and the prototype's routes used to live in `state.page` alone. That non-conformity is
closed — the URL carries the state in its query, held by R69; what the binding still owes is the
mapping onto production's paths.

---

## What the prototype already settles

These were argued, measured and recorded. Re-opening one costs a day; the reasons are in
`frontend/maquette/regions.json` → `$adversarialReview` (65 rules) and `$methodLessons` (37).

- **The prototype is the reference.** A divergence between the app and it is a defect in the app,
  unless the prototype was amended first with the reason written down.
- **CSS is extracted, never retyped.** A hand edit to the generated stylesheet is reverted by the
  drift guard.
- **Every gesture answers a pointer** — and a finger is read from the stream the compositor does
  not cancel. A gesture living inside the scrollport reads touch events; one that can claim its
  axis in `touch-action` keeps the pointer path.
- **Episode presence is read, never inferred.** A `number <= owned count` threshold assumes the
  hole is at the end of a season; it is false for 35 series in this library.
- **A trailer always opens YouTube**, never in-app playback, wherever one arrives from.
- **One back control**, in the flow, on every screen that has one.
- **One card, one behaviour.** The poster opens the media sheet, the card body opens the bottom
  panel, a gallery tile answers a long press. The panel carries EVERY action for that medium;
  an inline button is a shortcut, never the only way in. The panel is derived from what is true
  about the medium, so the one reached from a gallery equals the one reached from a card.
- **One builder per shape, not per screen** — and none of them takes markup. `cardHTML` for every
  list, `tileHTML` for every gallery, `panneauHTML` for every bottom panel, a separate builder
  for a release candidate (not a medium: no sheet, no panel). Each takes a descriptor of FACTS;
  a view wanting something outside it adds the fact rather than passing markup.
- **One season rendering**, within a sheet and across sheets.
- **Identify is not follow.** Resolving a stuck folder associates a medium so the pipeline
  finishes; it never creates a follow.

## Method lessons that cost the most

- **A screenshot fingerprint is not an oracle.** Two captures of the same unmodified file diverge
  on 8 to 15 of the states. Use bounding rects plus a computed-style subset.
- **A synthetic event is not a finger.** It is never cancelled, so it cannot tell whether a
  gesture survives the compositor. Two gestures were lost that way and no script noticed.
- **A rule that never bit proves nothing.** Every rule added is mutation-tested: break the
  behaviour on purpose, confirm the rule falls and names the right defect, restore.
- **A derivation must not read back its own output.** The list poster was sized against the
  median card and now sets it, so the computation returns its own answer.
- **A rule can assert the DEFECT.** R53 did, twice, in both directions: it first certified a
  startup screen that flashed for one frame, then demanded a floor that made the bar play twice.
  Writing down the behaviour that exists is not the same as writing down the one that is wanted.
- **« It cannot affect production » is a measurement, not an argument.** The prototype was proved
  harmless by building the bundle on both sides and comparing — and the first comparison said no:
  Tailwind v4 scans from the project root, took six words out of `refonte.html` for utilities, and
  shipped 936 bytes of them to production. The design host's icons, sitting in `frontend/public/`,
  shipped another 56 kB the same way.

---

## Carried, not hidden

1. **Plex deletion.** `api/plex.py` only refreshes. Which route removes an entry on this server is
   a verification step of the binding mission, not a claim of this one.
2. **A real deletion cannot be validated before production.** Staging writes to the real disks and
   the real databases, and fabricating a medium for the proof is forbidden. Protocol: dry-run only
   on staging; the first real deletion happens after the production merge, on a medium the
   operator names, after a genuine `sqlite3 .backup` — a file copy of a WAL database is not a
   backup.
3. **The multi-user account system** is a later mission. The user menu draws its place — profile
   and preferences, disabled, saying why — so the shape is settled before the feature lands.
4. **`?tab=maintenant`.** The label became « En cours »; whether the URL param migrates with a
   legacy redirect or stays is decided when the prototype is bound to the backend. The deep link
   must keep working either way, and the prototype has to DRAW what a legacy link lands on.
5. ~~**The list poster cannot be enlarged by its own derivation.**~~ **Closed**, and the question
   was replaced rather than answered: the poster is no longer a fraction of anything, it reaches
   the card's edges. 84px wide, with the card's height as its floor, so a card at that floor
   gives an exact 2:3 and its artwork is untouched. What remains named in R47 is the limit —
   full height and the 2:3 ratio cannot both hold on a taller card, so cropping is bounded.
6. ~~**The design host and the app share their icons.**~~ **Closed.** The design host carries a
   yellow-ringed set of its own, generated from staging's shape by
   `frontend/scripts/make-design-icons.py`.
7. **The arbitration SCREEN itself is drawn but not built.** `ds/DecisionRow` and the vocabulary
   are derived; the screen's own shape — one folder at a time, the three ways out side by side,
   the progression replacing the desktop deck's keyboard shortcuts — belongs to the Arrivées
   screen the prototype already draws — what is missing is the app, and the app comes after the
   operator's judgement.
8. **The synopsis is not in the read-model.** The library's rows carry it in the prototype, read
   from the `<plot>` of each medium's own NFO — real data, but `library.db` has neither a column
   of `media_item` nor a key of `item_attribute` for it. The app cannot render this surface until
   the read-model grows the field, and the scan that fills it. Nine of 349 titles have no plot at
   all, and those must show nothing rather than a filler.
9. ~~**Editing a setting is drawn only as far as the panel.**~~ **Closed.** Five fields, one
   refusal and one state that crosses them, each derived from the setting's VALUE rather than
   from a list of keys. R60 extended, `harness/settings.py` — 42 checks, eight named states, one
   per field.
10. **Five tokens the app will owe.** The design-system lint found nine hardcoded colours in the
    prototype — a real C19 violation, and one of them (`var(--warning, #d97706)`) was the B-014
    shape again: a fallback onto a token that IS defined, which is a landmine that has not gone
    off. They are tokens now: `--mq-shadow-toast`, `--mq-shadow-pop`, `--mq-shadow-carte`,
    `--mq-shadow-badge`, `--mq-scrim-doux`, `--mq-tile-overlay`. Their VALUES live in the
    prototype's own palette, which sits in BLOCK 1 and is therefore not exported — so the
    generated stylesheet names them and defines none of them, exactly as it already does for
    `--border` and `--card`. **When the app adopts that stylesheet, `frontend/src/styles/ps/
   tokens/maquette.css` must gain the five it does not yet carry.** Measured, because « it
    cannot affect production » is a measurement: adding them now costs 170 bytes of unused
    custom properties in the shipped CSS, and leaving them out keeps `frontend/dist`
    byte-identical.

11. **Answering a decision was a no-op on the acquisition side.** Found while drawing the screen:
    « Résoudre → » on « À traiter » opened the screen, took the choice, and left the item exactly
    where it was, because the answer only ever looked in the Arrivées list. Fixed in the prototype.
    The app's equivalent — whether resolving from one queue clears it from the other — is a
    verification step of the binding mission, on the real API, not a claim of this one.
