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
**The prototype:** `frontend/maquette/refonte.html` — §15 of `docs/reference/product-intent.md`
**Bug register:** `BUGS.md` at the repo root — every reported defect, one closed at a time.

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
wrapped.html` must be re-synced from `refonte.html` before every run, or the same thing happens
one level down:

```bash
/Users/izno/.pyenv/versions/3.11.9/bin/python3 - <<'EOF'
from pathlib import Path
src = Path("frontend/maquette/refonte.html").read_text()
head = ('<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,'
        'maximum-scale=1,user-scalable=no"></head><body>\n')
Path("/tmp/tm-refonte/wrapped.html").write_text(head + src)
EOF
```

`pwa.py` measures the LIVE host `tm-design.iznogoudatall.xyz`, not the local server. After
editing `serve.py`: `pm2 restart torrentmate-design`.

---

## What the v1 still owes, page by page

Read from the shipped router (`frontend/src/router.tsx`) against the prototype's named states.
Every line is a surface production really serves.

| Production route | Drawn in the prototype? | What it owes |
| --- | --- | --- |
| `/login` | yes | — |
| `/acquisition` | yes | — |
| `/medias` | yes | — |
| `/config` | yes | — |
| `/media/:provider/:id` | yes | — |
| `/controle` (Dashboard) | **no** | health at a glance, the last run's digest, what is stuck, the acquisition summary, the event feed, the schedulers |
| `/pipeline` | **no** | the flow board, the controls and their banner, a run's detail, the run history, the interpreted feed |
| `/maintenance` | **no** | the action catalogue, disks, index health, locks, the destructive log |
| `/systeme` | **partly** | the prototype says so itself: « réception seule … sa refonte mobile est différée ». That deferral is lifted |
| `*` (NotFound) | **no** | what a wrong URL says, and where it sends one |
| — | **no** | the multi-user account surfaces. The user menu draws their PLACE, disabled; the surfaces themselves are not drawn |

Nothing else in production is missing: `/scraping` and `/registry` are redirects.

---

## The third axis: what the prototype owes as an APPLICATION

The operator's judgement is on the design **and the front-end architecture**. The design is
measured by 65 rules; the architecture is not measured by anything yet, and these are its real
numbers, read from the file rather than remembered:

| Mesure | Aujourd'hui | Ce que ça veut dire pour la liaison |
| --- | --- | --- |
| lignes de code (hors jaquettes) | 39 454 | un seul fichier, aucun module |
| jeux de données en dur | **57** | 57 constantes à remplacer par autant de sources réelles |
| appels réseau | **1** | rien n'entre par le réseau : tout est inline |
| accès à `state.` | **248** | l'état n'a pas de propriétaire ; toute fonction y touche |
| `render()` | 1 défini, 43 appels | une seule fonction redessine tout |
| écouteurs | 43 | délégation par `closest()`, pas de composants |
| coutures `window.__` | 21 | les points d'accroche déjà nommés |
| `history.pushState` | 4 | la navigation existe, mais l'URL ne porte pas l'état |

Aucun de ces chiffres n'est un défaut **du prototype** : un fichier unique sans dépendance est
exactement ce qui l'a rendu vérifiable. Ce sont les **coutures** que la mission de liaison devra
ouvrir, et les nommer maintenant évite de les découvrir en les cassant.

Trois questions que la maquette doit savoir répondre avant d'être jugée :

1. **Par où entre une donnée ?** Aujourd'hui : 57 constantes. La liaison remplacera chacune par
   une source. Une constante qui n'est lue qu'à un endroit est une couture ; une constante lue
   partout est un couplage à défaire d'abord.
2. **Qui possède l'état ?** Aujourd'hui : personne — 248 accès directs. Ce n'est pas un problème
   tant que le prototype tient dans un fichier, et c'en est un dès qu'il faut le découper.
3. **Où vit une route ?** Aujourd'hui `state.page`, et l'URL ne la porte pas. La production sert
   des URL adressables ; le prototype devra le montrer avant que l'app les rebâtisse.

**Ces questions ne se tranchent pas en dessinant des pages.** Elles se tranchent en regardant le
fichier, et elles font partie de ce que l'opérateur juge.

---

**Next action:** draw the missing surfaces, in the order of the inventory above, and answer the
three questions of this section. Each surface follows the method below — real data, named states,
a rule that bites, a mutation that proves it.

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
10. **Answering a decision was a no-op on the acquisition side.** Found while drawing the screen:
   « Résoudre → » on « À traiter » opened the screen, took the choice, and left the item exactly
   where it was, because the answer only ever looked in the Arrivées list. Fixed in the prototype.
   The app's equivalent — whether resolving from one queue clears it from the other — is a
   verification step of the binding mission, on the real API, not a claim of this one.
