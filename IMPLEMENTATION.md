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

**Branch:** `feat/shell-mobile`. `main`, and therefore production, is touched **once, at the
end**, after everything has been validated together. Non-negotiable.

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
Next: SP4 — emptying the catch-all surface by surface; then SP5 (visual language).

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
cd frontend/maquette && python3 -m http.server 8899
```

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

| Mesure                               | Aujourd'hui         | Avant                         |
| ------------------------------------ | ------------------- | ----------------------------- |
| lignes de code (hors jaquettes)      | 41 400              | 39 454                        |
| jeux de données en dur               | **83**              | 57                            |
| appels réseau                        | **1**               | 1                             |
| accès à `state.`                     | **265**             | 248                           |
| `render()`                           | 1 défini, 47 appels | 1 défini, 43 appels           |
| coutures `window.__` nommées         | **11**              | 21 comptées avec leurs usages |
| `history.pushState` / `replaceState` | 5 / 3               | 4 / 0                         |
| **lecture de `location`**            | **3**               | **0**                         |

Aucun de ces chiffres n'est un défaut **du prototype** : un fichier unique sans dépendance est
exactement ce qui l'a rendu vérifiable. Ce sont les **coutures** que la liaison devra ouvrir.

### Les trois questions, et ce qu'elles valent maintenant

**1. Par où entre une donnée ?** 83 constantes, contre 57. Le nombre a monté et la situation s'est
améliorée, ce qui n'est contradictoire qu'en apparence : chacune des nouvelles est lue d'une source
vivante nommée dans son commentaire — `pipeline_run`, `pm2 jlist`, `df`, `library.db`, le registre
de maintenance, `web.json5`, `ecosystem.config.js` — et **quatre règles retournent à ces sources à
l'exécution** au lieu de comparer à un chiffre écrit à côté. R66 vérifie le run par son `run_uid`,
R67 compte les processus contre `pm2 jlist` et les commandes contre le registre du moteur dans les
deux sens, R68 lit `web.json5`, R63 lit `acquire.db`.

C'est la réponse à la question, et elle est exécutable : **une constante dont la valeur est
vérifiée contre sa source est une couture nommée ; une constante que rien ne vérifie est un
couplage.** R63 l'a démontré tout seul en tombant quand le planificateur a tourné — une règle qui
échoue avec le TEMPS ne signale pas un défaut, elle désigne une couture. Il reste à faire le tri :
combien des 83 sont vérifiées, combien ne le sont pas.

**Elle est retombée le même jour**, quelques heures plus tard : le passage de 15 h 20 a poussé Silo
de 9 à 11. Deux fois en une session, sans qu'une ligne de la maquette ait été touchée. Ce n'est
plus une illustration de la question, c'en est la réponse : **ces constantes-là ne se maintiennent
pas à la main, et la liaison n'a pas le choix de les brancher.**

**2. Qui possède l'état ?** Personne — 265 accès directs, contre 248. Rien n'a bougé sur ce front
et c'est assumé : découper l'état demande de découper le fichier, et un fichier unique est
exactement ce qui a rendu ces 71 règles écrivables. **C'est la question qui reste entière**, et la
seule des trois qui ne se tranche pas sans décider d'abord comment le prototype se découpe.

Une chose a quand même été apprise en la traversant : `state.pipe` **fuyait** d'un état nommé au
suivant, si bien qu'un même id ne rendait pas la même chose selon le chemin parcouru pour y
arriver. R10 l'a trouvé. C'est le coût exact d'un état sans propriétaire, et la parade tient dans
une phrase : **tout état nommé nomme TOUS ses cadrans**, comme il nommait déjà sa page et sa phase.

**3. Où vit une route ?** Elle vivait dans `state.page`, et l'URL ne la portait pas.
**C'est réglé.** La mesure qui le disait était sans appel : `history.pushState` quatre fois,
`location` lu **zéro** fois — l'interface disait au navigateur où elle était et ne le lui demandait
jamais. Ce n'était pas une dette à transmettre, c'était une **non-conformité à DOIT-10**, et elle
se voyait : un rechargement retombait sur la page d'ouverture, et aucun écran ne pouvait être
envoyé à quelqu'un.

L'état voyage dans la REQUÊTE et non dans le chemin, et c'est une décision : ce fichier s'ouvre
depuis un serveur statique, depuis l'hôte de maquette et depuis `file://`, et une route par chemin
demande un serveur qui réécrit tout chemin inconnu vers le document — deux de ces trois-là ne le
peuvent pas. La liaison fera correspondre `?page=lib` au `/medias` de la production ; ce qui se
juge maintenant est que l'URL et l'interface ne se contredisent jamais. R69,
`harness/adresse_url.py`.

---

**Next action:** draw the missing surfaces in the order of the inventory above — Arrivées first,
because it takes the largest transfer and the arbitration hangs on it — then answer the three
questions of this section. Each surface follows the method below — real data, named states,
a rule that bites, a mutation that proves it.

Note that question 3 is not only architecture: **DOIT-10 requires every detail to have its URL**,
and the prototype's routes live in `state.page`. That is a non-conformity with the constitution,
not merely a debt to hand over.

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

**In the app** (`frontend/src`), from
`docs/analysis/2026-08-12-app-component-duplication-audit.md`:

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
