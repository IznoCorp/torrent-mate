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

**SP1 — dossier servi**: Branch `refactor/maquette-sp1`; prototype moved to `design/refonte.html`
(1.9 MB, images extracted as files under `design/assets/`, committed via `.gitignore` negation);
`serve.py` serves `/assets/` session-gated with `private, max-age=31536000, immutable` cache
headers; new rule R70 (`images.py`) verifies asset extraction; merged as PR #429. Post-merge
operator corrections in the same PR: result cards carry no inline action (the panel is the
single path to the act) and the screen layer stacks — back redraws the screen it covered —
both held by R71 (`ecrans.py`).

**SP2 — coquille Vite**: Branch `refactor/maquette-sp2`; `design/` is also a Vite project
(`index.html` envelope + local plugin injecting `refonte.html` verbatim after Vite's HTML
pass, `dist/assets` symlinked, bundled output reserved under `dist/vite`); R72
(`coquille.py`) proves the built output renders identically to the source — DOM
serialization of the three surfaces plus region geometry per driven state, failed-response
guard on both sides — mutation-verified three ways. Merged as PR #430.

**Bascule — the host serves the build**: Branch `refactor/maquette-bascule`. The PWA head
moved into the Vite envelope (`design/index.html`, between `pwa:start`/`pwa:end` markers)
and `serve.py` EXTRACTS it for the login gate instead of restating it; `serve.py` now
serves `dist/index.html`, rebuilding under a lock when any build input is newer (0.4 s),
with a truthful 503 taxonomy (missing prototype → MANQUANT; missing build input, timeout,
failed build → the build's own last words, escaped). `TM_DESIGN_RACINE` env and `TM_DESIGN_DELAI_BUILD` exist so R73 (`bascule.py`) proves
the serving contract (byte-identity, rebuild, failure-shown) against a scratch root
without touching the real source; the finer 503 taxonomy is exercised by the task evidence.
Merged as PR #431.

**SP3 — the router, by strangler**: Branch `feat/maquette-sp3`. Phase A first: the harness
measures the BUILD (`wrapped.html` is a copy of `dist/index.html`; the copy still isolates
rule mutations). Then React 19 + TanStack Router as the outer shell (`design/src/coquille.tsx`,
bundle under `dist/vite/`, served session-gated): the router is the SINGLE writer of URL and
history; the legacy engine's 12 nav-primitive sites speak `window.__pont` (five verbs) via a
queue-and-replay pre-bridge in the envelope (the classic script runs before the deferred
module). R59/R69/R71 green with UNCHANGED rule code are the bridge's proof. R72 rescoped
(fragment verbatim ×1 + one module entry + bundle exists; the source-vs-build rendering
comparison retired — recorded in regions.json); R74 (`pont.py`) holds the bridge, its
mutation manual by design (a rule never mutates the shared copy). The shell is typed: `design/`
carries a strict `tsconfig.json` and its own `npm run typecheck`, wired into `make check-frontend`
— the build alone had no opinion on types (it exits 0 on a type error, measured). Known opens:
forward-is-not-a-return kept as legacy-faithful; a future `history.block()` would defeat the
shell's `flush()`.

**SP4a — the machinery, paid once, on the two smallest screens**: Branch `feat/maquette-sp4a`.
Two spikes decided against adoption for now: Konsta UI cannot carry R47's card geometry
without discarding its own layout defaults node by node, and Motion has no named real need —
every migrated surface's interaction is still plain CSS. The store: `magasin` (TanStack Store)
becomes the owner of the legacy engine's state, `state` kept as a synchronous read-alias so the
~70 existing readers are untouched while every WRITE moves onto the store, six batched lots.
The boot order inverts: the shell creates the store and the real `__pont` FIRST and calls
`window.__demarrerMoteur` once, so the engine's own boot writes land straight on the single
writer in the engine's own order — the queue-and-replay pre-bridge SP3 introduced is retired,
nothing left to queue. Domain hooks become the components' only door onto that state. The host
now answers ANY address, not only files it recognises: `serve.py` gained the SPA fallback, the
`<base href="/">` element, `/favicon.svg`, and the permanent `/assets/` portal rule (R73
amended, four new holds); a second harness-only server (`harness/serveur.py`, port 8917) makes
that same depth measurable locally without touching 8899 or the reverse-proxied ports. Two
pilot screens are the first drawn as real routes rather than driven through the legacy state
machine — `/profil/$titre` (Profil, the quality-profile screen — Ruling R-4 settled that this
is the per-FOLLOW screen, not a per-actor one, which does not exist in the code) and `/ajout`
(Ajout, `q`/`mode` router-owned while the address reads `/ajout`) — both through `aller()`, the
single navigator R76 holds to one call site. New rules: R75 (`adresses_ecrans.py`, cold deep
entry + `<base>` proof + address-follows-the-walk + honest wrong-address rendering) and R76
(`navigation.py`, one door, one entry per call, no merge across a synchronous double call).
Ruling R-5 (review) removed the pop dispatcher's pathname filter: ownership of a history entry
is carried by its SHAPE, not its address, and the filter would have silently stopped closing a
layer opened over a screen-route. CI gained the shell's own `npm run typecheck` gate. Known
opens for SP4b: the fiche (the most connected screen, and the biggest `openSheet` producer) and
the panel migrate together; the legacy sites that open the panel will speak to it through the
shell.
**SP4b — the fiche and the panel, migrated together**: Branch `feat/maquette-sp4b`. Opens with a
re-measure: B-024 (`data-go` settles one history entry while layers pile) is confirmed still
`latent, non atteignable` after SP4a — no code changed that walk, only the witnesses in its BUGS.md
entry were corrected. `window.__referentiel` widens so the fiche's data (cast, seasons, trailer,
artwork) is reachable from React the same way the profile's already was. `<PanneauContenu>`
(`composants/panneau.tsx`) is the single React constructor for every panel — `Descripteur`/`Bloc`/
`Action`/`Ligne`/`Segment` types, the five declared block kinds, the same refusal on an unknown
block `panneauHTML` always had. `<Feuille>` cuts the layer and its drag gesture over: every one of
the legacy panel's producers now calls `window.__panneau.ouvrir(descripteur)` /
`.fermer(pop?)` / `.ouverte()` — the shell's store owns `panneauOuvert`/`panneauDescripteur`,
`openSheet()` is retired to a tripwire (`throw` — a producer nobody converted fails loudly instead
of silently drawing nothing), `closeSheet(pop)` stays as a one-line verb the harness driver still
calls. `FicheEcran` lands as a real route, `/fiche/$titre`, transplanted from `openFiche()`
(deleted from the fragment the same commit): unknown titles render honestly (no not-found branch
existed to mirror), a fiche without a trailer shows its own `p.nofiche` rather than hiding the
section. Scroll position is now kept in the shell, keyed per HISTORY ENTRY rather than per address
(`coquille.tsx`, "LE DÉFILEMENT SUIT L'ENTRÉE D'HISTORIQUE") — the legacy layer used to restore a
covered screen's scroll itself on unwind; a router-owned screen unmounts instead, so the shell
remembers the offset and reapplies it once the port and its images have settled. `window.__ecrans`
gains `.fiche(titre)` alongside `.profil(titre)`, both NFC-normalised on write. Two rule amendments
carry the cutover: R56 (`panneau.py`) re-points its two source checks from the fragment's dead
`panneauHTML`/single-caller shape onto the component and its call sites; R71 (`ecrans.py`) trades
`#screen` for `.screen.open` wherever the target moved to a router-owned screen. R60
(`reglages.py`) gets two added holds, no rule changed. R75 (`adresses_ecrans.py`) extends with five
holds (f)-(j) for the fiche: cold deep entry, the hero/poster the fiche paints itself actually
loads, Back closes to `/`, an unknown title still renders honestly, a no-trailer real fiche shows
exactly one `p.nofiche`. B-025/026 (the screen half of the `data-go` fix had no Back rule; a silent
`catch {}` could let the URL and the UI disagree) are paid alongside B-024's re-measure — the
`data-go` handler and `noterLeChemin` now log and raise instead of swallowing. B-027/028/029
(`resynchro.py`'s first-`t:`-match and naive-brace title extraction, its silence on an unknown
title, `contenu.py`'s substring counter check matching "1" inside "11") are fixed: string-aware
extraction, a loud failure on the unmatched case, a numeric comparison. All five close as `to
confirm` in `BUGS.md`, B-024 stays `open` (latent, not reachable by a real walk — a design
decision, not a gap). A dead-code sweep in the same wave retires `saisonsHTML`, `champReglageHTML`
and `seasonHTML` from the fragment once their last legacy consumer moved to the component.
Wave gate: full 48-script harness suite green, `make check`/`make check-frontend` green, R59/R69/
R71 (`retour.py`/`adresse_url.py`/`ecrans.py`) diffed against the SP4a merge point — `retour.py`/
`adresse_url.py` byte-identical, `ecrans.py`'s only change is the Task-5 `.screen.open` amendment
above. `frontend/src/styles/ps/app-surface.css` was found drifted from the maquette by two
selectors (`--primary` vs `--primary-texte` on the active nav link, `.bottombar`/`.drawer`) —
confirmed pre-existing at the SP4a merge commit, not caused by this wave — and regenerated via
`scripts/extract-maquette-css.py`.
**SP4c — resolution and releases, and M11 dies**: Branch `feat/maquette-sp4c`. Two more screens
land as real routes: `/resolution/$dossier` (`ResolutionEcran`, transplanted from `openResolve()`)
and `/releases/$titre` (`ReleasesEcran`, transplanted from `openReleases()`), both through
`window.__ecrans` alongside `.fiche()`/`.profil()`. A fidelity walk against the deleted legacy
bodies found zero rendering divergence — 124/124, 78/78 and 80/80 boxes across the arbitration's
three shapes, all textual differences traced to inter-tag whitespace the templates left between
block boxes, never inside a run of text. The `data-resolve` collision the brief flagged as a
pre-read (candidate branch vs. a panel branch reading the same attribute for a different purpose)
turned out to be order-only: the candidate branch runs first and returns, the panel branch is
unreachable dead code (proven with a synthetic click), rewired anyway to keep saying the true
verb. `data-profil`'s three legacy producers were traced one by one; only `openReleases`' own
"Ouvrir le profil de qualité →" lived inside a `#screen`, so the two-way branch
(route-open → `__pont.retour()`; else → `__panneau.fermer()`) is complete — a third `#screen`
branch would have been dead code. **M11 (the Associer flow's double `history.back()`) dies**:
`Pont` gains `reculer(n)` — flush pending writes, announce, then `historique.go(-n)` — and the
fragment's latch counts `deroulementEnCours += 1` per **announcement**, not per entry: the
browser coalesces a multi-entry `history.go(-n)` traversal into ONE popstate, so the brief's own
`+= n` was measured wrong (mutation m2 proved it swallows the operator's next real Back) before
`ident.py`'s new history-hold caught it. R57 (`decision.py`) is amended: its `ECRAN` probe now
reads `.screen.open[data-cle^="resolution:"]` instead of rooting on the legacy `#screen`, which
the arbitration screen no longer renders into — the same identity-read shift `panneau.py` and
`galerie.py` made for the fiche in SP4b, one line, mutation-proven (24/24 both ways). The
per-identity ladder pair (`fiche:`/`ajout:`) that four harnesses (`audit.py`, `audit2.py`,
`dest.py`, `states.py`) carried collapses to ONE generic, ladder-last rung —
`.screen.open[data-cle]` — covering `resolution:`/`releases:` and closing the pre-existing
`profil:` coverage hole in the same edit; wiring it surfaced a latent, pre-existing R10 defect in
`audit.py`'s own `couche()` helper (it tested `#sheet`/`#screen`/`#dlg` but no route, so a click
opening `/resolution/…` read as "changed nothing" — confirmed pre-existing via `git stash`, fixed
alongside). `harness/serveur.py`'s SPA fallback mis-read any route param carrying its own dots
(`Backrooms.2026.MULTi.2160p.WEB-DL`, a real staging folder name) as a missing file extension and
404ed; fixed to fold to the document for any path that is not a real file, except under the two
directories the served root actually holds files in (`/assets/`, `/vite/`). The live host
(`serve.py`, R73) never carried this defect — verified with a new `bascule.py` hold, not assumed.
R75 (`adresses_ecrans.py`) gains six holds (k)-(p): both screens open cold at a dotted deep
address, one Back lands on `/`, an unknown subject renders the arbitration's own honest empty
case rather than raising — 35 → 49 holds, all green, mutation-proven (a severed route falls 14).
`releaseCardHTML`/`decisionCardHTML` — the legacy builders the two screens were transplanted
from — are deleted with zero remaining callers once the components took over; `CarteRelease` and
`CarteDecision` (`design/src/ecrans/resolution.tsx`) are their replacements. Wave gate: full
48-script suite green, `make check`/`make check-frontend` green, R59/R69/R71
(`retour.py`/`adresse_url.py`/`ecrans.py`) byte-identical against the SP4b merge point
(`9842e44d`) — `ecrans.py` included, since this wave's two screens are not ones it traverses.
Carried open: the 240 ms dead delay on `data-suivante` (a frozen quarter-second, was a legacy
screen-close cover — kept identical under the binding-parity constraint; flagged for the operator
in `BUGS.md`'s evolutions register, not fixed here); a deep `/releases/$titre` entry with no
`__ecrans` call leaves `relTitre` null for `data-prendre` (mirrors the accepted `/ajout`
addQ/addMode debt, dies with the legacy dispatcher), and a deep `/resolution/$dossier` entry the
same way leaves `resolveTarget` stale for `data-resolve`/`data-laisser` (same settlement, same
door, dies with the legacy dispatcher too); `ident.py`'s only remaining `#screen` read is `ou()`'s
`ecran` field — deliberately left, recorded under R57 — since its two early informational probes
(the arbitration screen's `.h2`, the add screen's banner/field/id-block) already moved to
`.screen.open[data-cle^="resolution:"]` / `[data-cle^="ajout:"]` and no longer print `None`.
Next: the rest of the catch-all surface by surface; then SP5 (visual language).

---

## Where to start

**`BUGS.md` at the repo root is the bug register.** Every defect the operator reports is written
there when it is reported, one is closed at a time, and a fix closes only with a mutation-tested
rule that covers the path the operator actually walks. Read it before starting anything.

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
  [ "$s" = commun.py ] && continue   # the shared plumbing, not a rule
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
| **Arrivées**                                                           | **drawn** — the pilot's bar, the nine steps of the last real run, its digest, and « arrivé dans les 24 h »                       | R66, `harness/arrivees.py` |
| **Système**                                                            | **drawn** — the deferral is lifted. PM2 services, schedulers, the pipeline's executions, disks, index, dependencies, code errors | R67, `harness/machine.py`  |
| **Maintenance**                                                        | **drawn** — six rubrics over the engine's 26 real `library-*` commands, plus the destructive journal                             | R67                        |
| **Configuration**                                                      | **extended** — a seventh rubric, « Les passages programmés », over the six real cron schedules                                   | R60 extended               |
| `*` (NotFound)                                                         | **drawn** — and it closed a crash: an unknown id used to stop the whole frame on a TypeError                                     | R68, `harness/adresse.py`  |
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
and the interface never contradict each other. R69, `harness/adresse_url.py`.

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

## What is already done, ahead of the phase plan

The prototype and its harness carry the design; some app-side work was pulled forward because
the audit that motivated it was done. Neither replaces a phase.

**In the prototype.**

- The **startup screen** (`demarrage`) covers the wait between signing in and an interface being
  there, and the **gate** shows the same screen — extracted, never retyped — from the submit
  onwards. R53, `harness/demarrage.py`.
- **Signing out** ends the session on the server and lands on the entry screen, instead of
  answering with a message over an interface that had not moved. R54,
  `harness/deconnexion.py`.
- **Every gesture answers a real finger.** The pull to refresh and the swipe between views had
  both been lost to the compositor and worked only under synthetic events. R55,
  `harness/doigt.py`.
- **One bottom panel**, taking a descriptor of facts and ordered blocks of declared kinds. The
  fallback builder that answered for « whatever the first does not recognise » is gone. R56,
  `harness/panneau.py`.
- The prototype **installs as its own application** — « TorrentMate Design », with an explicit
  manifest `id`, and its own icons: a yellow ring where the app has none and staging has a cyan
  one, generated by `frontend/scripts/make-design-icons.py`. R52 extended.
- **The install offer is actually offered.** The banner existed and nothing ever showed it:
  `beforeinstallprompt` was never captured, so on Android the browser kept the offer and on iOS
  Safari — which fires no event at all — the banner was the guide nobody saw. R51,
  `harness/installation.py`.
- **The back gesture follows the path actually walked**, tabs and lenses included, closes a layer
  first, and at the root warns instead of leaving — closing only on a second back within five
  seconds. R59, `harness/retour.py`.
- **The list poster reaches the card's edges**, 84px wide with the card's height as its floor,
  so a card at that floor gives an exact 2:3 and its artwork is untouched. Full height AND the
  ratio cannot both hold on a taller card — measured, a grid sizes the column before the row's
  height is known — so cropping is bounded rather than forbidden. The episode popover carries the
  brand outline, so its limits can be found on a dark surface. R47 rewritten, R58.
- **The brand colour is painted where the design puts it.** `--accent` was referenced eleven
  times and defined nowhere: the wordmark, the sign-in button, the install button and the startup
  bar were all unlit, and the host hid it by retyping the palette. R61, `harness/palette.py`.
- **One sign-in screen**, wherever one meets it: the host extracts everything the screen
  inherits — palette, box model, typography — instead of restating it. R62, `harness/entree.py`.
- **A card says what the engine knows.** A follow carries its identity, what is happening and
  when, and what tells a healthy follow from a stalled one, all read from `acquire.db`; a library
  row carries the synopsis, clamped to the largest number of lines that fits. R63,
  `harness/contenu.py`.
- **A row's drawer opens either way, one row at a time**, without firing the tap — and it renders
  identically on WebKit, where it used to spill past the rounded card. R64, `harness/glisse.py`.
- **The startup screen covers one wait and plays once**, across the two pages that wait spans.
  R53 corrected. Its history is in `BUGS.md`: the rule was wrong in both directions.
- **The settings are navigated by what one wants to change**, never by file: five rubrics plus
  secrets and ranking, over the 153 settings the engine really keeps. Each row is identified by
  its label alone — its subject, then what it does, in French — because the leaf key drew
  « Activé » seven times in one list; the key is in the mono face under it, the file on the group
  header. Nothing is written until the save bar — which exists only
  when there is something to save — NAMES the files it will write; a secret says whether it is
  set and never what it is worth. R60, `harness/reglages.py`.
- **The arbitration screen is drawn** — a decision is a FOLDER, not a medium; the score is shown
  only when it separates; a candidate wears only its own poster; three ways out, the third of
  which (« Laisser tel quel ») existed in the engine and nowhere in the interface. R57,
  `harness/decision.py`.

**In the app** (`frontend/src`), from the 2026-08-12 component-duplication
audit (the audit document itself was never committed; its outcomes are):

- `ds/Panel` extracted; eleven files stopped writing the surface string by hand, and a test
  fails naming any file that starts again.
- `AcquisitionCard` → `ds/MediaRow`, with `facts: MediaFact[]` in place of `meta: ReactNode`,
  `journey` in place of `strip` and `action` in place of `footer`.
- `ds/MediaCard` → `ds/MediaTile`, and `Chip` moved out of `acquisition/`.
- `EmptyState` adopted on nine surfaces.
- `ds/DecisionRow` — the interface's THIRD card shape, derived from the drawing: a
  decision is a folder, so it promises neither sheet nor panel. `RecentResolutions` and
  `DecisionList` take it; `decisionFacts()` derives the facts once for both.
- The arbitration surfaces follow the drawing: the folder is the subject everywhere, the
  score is printed only when it separates (`tie.ts`), a candidate no longer sends the
  operator off-screen to decide, and « Ignorer » became « Laisser tel quel ».
- `src/components/decisions/__tests__/contract.test.tsx` carries R57 app-side, mirroring
  `harness/decision.py`, so the drawing and the code cannot drift apart in silence.

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
   from a list of keys. R60 extended, `harness/reglages.py` — 42 checks, eight named states, one
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
