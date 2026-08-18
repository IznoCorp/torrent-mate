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
**The prototype:** `frontend/maquette/design/refonte.html` — §15 of `docs/reference/product-intent.md`
**Bug register:** `BUGS.md` at the repo root — every reported defect, one closed at a time.

---

## Current state

Twelve waves have landed. Each squash-merged onto `main` after green CI and a clean final
adversarial review; none of them derives app code.

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

The full record of each wave, in the words written when it landed, is in
`docs/superpowers/shell-mobile-wave-log.md`; the per-wave plans are in `docs/superpowers/plans/`.

### The latest wave, in full

**SP4d wave 4 — Acquisition, and the last two pages**: Branch `feat/maquette-sp4d4`, version 0.97.21 (ONE bump for the wave). The last page wave, and
the one that empties the page table: `viewAcquisition` — 290 lines, three tabs, a deck and a
second infinite scroll — becomes `pages/acquisition.tsx`, and the two small pages nobody had
counted go with it: `viewProfil` (48 lines, « Profil et préférences », off-bar) and
`viewIntrouvable` (10, the unknown address). **`PAGES_OF()` now carries no `render` at all**,
which is the condition SP4-end starts from.

**What does NOT move, and why it was measured before deciding.** `avancerDeck` mutates the deck's
own DOM in place — it inserts a card at the back, decrements every `data-depth`, writes an inline
transform on the outgoing one and removes it 440 ms later — and its own comment says why: a
replaced node cannot animate. React owning that markup would restore the string it last rendered
on the next repaint and undo the gesture FOUR rules measure (R55, R64, `deck.py`, `mouse.py`). So
the component draws `#sugitems`, `#sugload` and `.deckbody` and fills them only with what the FRAGMENT emits — the rows come from `fillSug` / `sugFoot`, and the deck's pile from `deckHTML`, written once when the container has none rather than on every commit: rewriting it on each render replaces the very nodes `avancerDeck` is animating, and « Passer » does write the store, so it re-renders. React manages no children there. React manages zero children there, so neither world removes the
other's nodes — the arrangement `paintSelBar` already had, one level down. What SP4-end owes that
machinery is a new HOME (`src/`, as an imperative module) rather than a rewrite: an imperative
gesture engine is final code; what must die is the fragment as an editing source.

**Two things the wholesale `innerHTML` rewrite did for free**, which had to be said out loud
here. The fragment fills those containers DURING `render()`, before React has put them in the
document, so a migrated page asks again from an effect — the same way it asks for the selection
bar to be repainted. And the deck at rest, written into the body by that effect, is a node React
does not know: a re-render leaves it in place, so the pile stayed at the top of every other
state until the component learned to clear it.

Fidelity by RECORDING, taken before any deletion: **0 divergences over all EIGHTEEN states** —
the four of « En cours », the six of « Suivis », the six of « Découvrir », plus Profil and
Introuvable.

**A deletion that blanked the page, and the lesson under it.** `sugCardHTML` was deleted as dead
code because counting `name(` found zero callers. It is used as a VALUE — `fillSug` chooses
between it and `sugTileHTML` and calls whichever it chose — and the suggestions went blank at the
first measurement. Restored, with the reason it looked dead written above it. The same faulty
count is what made the recon miscount `secHTML`'s call sites a wave earlier: a symbol referenced
without parentheses is invisible to it.

R77 grew to 42 holds: the eight pages are all shell-owned, `LEGACY_OWNED` is EMPTY and the rule
says so out loud rather than passing over an empty list, the « the page is drawn » floor stopped
encoding the size of the pages that happened to exist when it was written (the unknown-address
page is seven elements, by design), Acquisition's delegation gained four tap-driven holds — tab,
pill, display mode, suggestion mode — and the seam itself gained one: the containers survive a
round trip, still filled. Four mutations, one run each.

**The drawer stays**, and this wave was not its last consumer: it still has two — the topbar
burger, which is static app shell, and the « Voir toutes les pages » crossref of the
unknown-address page, which is React now and emits the same `data-drawer`.

**Wave gate**: `resync.py` moved the drawer's deployed-version card to the branch's base (0.97.20,
build `52f28213`), committed as data; the full suite is **51 scripts, 570 holds, zero FAIL** (562
+ 8 for R77); `make check` green including `check-frontend`; `scripts/check-no-french.py` green;
R59/R69/R71 byte-identical against the merge point. The fragment went from 39 889 to 39 560
lines. Every page belongs to the shell: `sys`, `maint`, `cfg`, `arr`, `lib`, `acq`, `profil`,
`404`.

### The wave order from here (operator ruling, 2026-08-16)

1. **clean-code / i18n — DONE** (branch `refactor/clean-code-i18n`, recorded above). The
   rule now has a gate, and it is written where it is enforced: root `CLAUDE.md`
   (§Code Conventions, §Language) and `frontend/maquette/README.md` (§Language of the
   source, §Where the interface's French lives). Every wave below is born under it:
   English names on the day a thing is written, interface text in `fr.json` from the
   first line.
2. **SP4d — four waves**, in this order: sys + maint + config → arrivées → médiathèque
   (with E-001) → acquisition. **Waves 1, 2 and 3 DONE** (`feat/maquette-sp4d1` #447,
   `feat/maquette-sp4d2` #448, `feat/maquette-sp4d3`): the PAGE machinery is paid for and
   has since been simplified — the shell portals straight into `#view` and the handover is
   announced, which is what a page emitting several roots needs; `src/pages/host.tsx`'s
   table is the ONE place the next wave adds its page; every harness driver writes through
   the store; and E-001 is drawn, held by R78. **SP4d is DONE**: wave 4
   (`feat/maquette-sp4d4`) took Acquisition and the two small pages nobody had counted, so
   `PAGES_OF()` carries no renderer at all. The drawer stays — it still has two consumers,
   one of them React's.
3. **SP4-fin** — the engine's death: empty fragment, `refonte.html` retired as a source,
   bridge and aliases removed, `openScreen` swept, the deep-entry `relTitre` /
   `resolveTarget` debt settled.

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
