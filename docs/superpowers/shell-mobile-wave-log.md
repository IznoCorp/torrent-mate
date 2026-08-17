# shell-mobile — the wave log

What each shell-mobile wave settled, in the words written when it landed — moved out of
IMPLEMENTATION.md so the live mission stays readable.

## SP1 — dossier servi

Branch `refactor/maquette-sp1`; prototype moved to `design/refonte.html`
(1.9 MB, images extracted as files under `design/assets/`, committed via `.gitignore` negation);
`serve.py` serves `/assets/` session-gated with `private, max-age=31536000, immutable` cache
headers; new rule R70 (`images.py`) verifies asset extraction; merged as PR #429. Post-merge
operator corrections in the same PR: result cards carry no inline action (the panel is the
single path to the act) and the screen layer stacks — back redraws the screen it covered —
both held by R71 (`ecrans.py`).

## SP2 — coquille Vite

Branch `refactor/maquette-sp2`; `design/` is also a Vite project
(`index.html` envelope + local plugin injecting `refonte.html` verbatim after Vite's HTML
pass, `dist/assets` symlinked, bundled output reserved under `dist/vite`); R72
(`coquille.py`) proves the built output renders identically to the source — DOM
serialization of the three surfaces plus region geometry per driven state, failed-response
guard on both sides — mutation-verified three ways. Merged as PR #430.

## Bascule — the host serves the build

Branch `refactor/maquette-bascule`. The PWA head
moved into the Vite envelope (`design/index.html`, between `pwa:start`/`pwa:end` markers)
and `serve.py` EXTRACTS it for the login gate instead of restating it; `serve.py` now
serves `dist/index.html`, rebuilding under a lock when any build input is newer (0.4 s),
with a truthful 503 taxonomy (missing prototype → MANQUANT; missing build input, timeout,
failed build → the build's own last words, escaped). `TM_DESIGN_ROOT` env and `TM_DESIGN_BUILD_TIMEOUT` exist so R73 (`switchover.py`) proves
the serving contract (byte-identity, rebuild, failure-shown) against a scratch root
without touching the real source; the finer 503 taxonomy is exercised by the task evidence.
Merged as PR #431.

## SP3 — the router, by strangler

Branch `feat/maquette-sp3`. Phase A first: the harness
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

## SP4a — the machinery, paid once, on the two smallest screens

Branch `feat/maquette-sp4a`.
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

## SP4b — the fiche and the panel, migrated together

Branch `feat/maquette-sp4b`. Opens with a
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

## SP4c — resolution and releases, and M11 dies

Branch `feat/maquette-sp4c`. Two more screens
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

## clean-code / i18n — no French in the code, and no interface text in it either

Branch
`refactor/clean-code-i18n`, version 0.97.17 (ONE bump for the whole wave). The operator's binding
directive of 2026-08-16, made into something enforced rather than remembered.

Nine tasks. **T1/T2** put `react-i18next` in the shell and moved every UI string of the six
components into `design/src/i18n/fr.json` (343 leaves; the panel's three dictionaries account for
156 of them), proven byte-identical on innerText AND textContent across 81 driven states.
**T3** put `design/src`'s files, directories and ~140 declarations into English around a FROZEN
seam — the ~65 member names the legacy fragment calls, every `data-*` name and value, the `__go`
state ids, the route paths — with a 934-literal audit proving no rendered byte moved. **T9**
turned the French CSS vocabulary English across all four worlds (fragment,
components, harness selectors, extracted stylesheet): 33 classes renamed, 3 dropped as
dead, 6 frozen as data values, and 13 KEPT with the evidence for each recorded in
`regions.json`'s `$vocabulary`. The plan's « eight » was its first measurement, not the
executed set. **T4/T5** renamed 29 harness files and translated all 49
scripts' identifiers, labels and printed formats — `OK`/`ECHEC` became `PASS`/`FAIL`, « N règles
EXÉCUTÉES » became `N rules EXECUTED` — verified by AST-anonymised equality on 39 of the 49
scripts and by the hold total, 485, unchanged.

**T6** finished the two servers. `serve.py`'s identifiers, its two environment names
(`TM_DESIGN_ROOT`, `TM_DESIGN_BUILD_TIMEOUT`) and its diagnostics are English, and the French it
SERVES left the file entirely: the sign-in gate's title, the two 503 pages, the offline page and
the manifest's description are read per request from `fr.json`'s `server` namespace — the same
discipline that already made the gate EXTRACT the login screen's markup instead of restating it.
Every served page is byte-identical across the move (sign-in 108171 bytes, refused 108164,
manifest 756, offline 652, missing-prototype 576, build-failure frame 572); the one thing that
moved in the whole host is the service worker's own constant name. `build_failure` gained the
guard a constant could not need: if the copy itself is unreadable it answers an English
diagnostic page naming the copy as the defect, because the page that reports every other failure
may not fail silently. `resync.py` followed, and its two `BUGS.md` mutation recipes were re-run
and re-pointed — as was B-029's, whose quotation still named a French hold label the harness
stopped printing two tasks earlier.

**T7 is the half that outlives the wave**: `scripts/check-no-french.py`, four arms — strings,
identifiers, file names, class names — in `make check` and in its own CI job. Each arm has its
own scope, because "French" means one thing in a component and another in a rule script that
ASSERTS the French the app renders: over the harness the string arm reads only the hold LABELS.
Every exception cites its reason, and the CSS-class exceptions are READ from `regions.json`'s
`$vocabulary` so those reasons have exactly one home. Five mutations, each felling exactly its
own arm. Two of them earned their place immediately: the class arm did NOT fall at first — it
split names into words, and this vocabulary is written flat (`bandeaufiche`), so it had been
letting everything through; and the coverage guard exists because an arm whose scope silently
empties otherwise announces « no violation » while measuring nothing.

What the gate found on its first run, beyond the wave's own list: two French names still in the
PRODUCTION app (`SystemePage`, `EpisodeStateLegende` — renamed, 1364 frontend tests green), the
50th harness file (`rename.mjs`, entirely French — translated, and repaired: it read its
hand-authored name table from a vanished session scratchpad, so it threw on its first line and
could not run at all), a local `refonte` in `bridge.py`, and four literals that are data or
addresses rather than copy, now each carrying a `french-ok:` pragma with the reason already
written beside it.

The gate closed its own two blind spots before the wave ended, and what it found
there was corrected rather than allowlisted. The string arm reached `scripts/` —
the repository's own tools speak to a DEVELOPER, so they speak English; seven of
them did not. (The `personalscraper` CLI is the opposite case and no arm reads
it: it speaks to the OPERATOR, in French, and it is interface.) The identifier
arm reached `scripts/`, `personalscraper/` and `tests/`: it had been reading
2 656 declarations and now reads 124 940. The finding worth keeping is that
`personalscraper/` had NOT ONE French identifier, and that eleven of the twelve
in `tests/` are built on `saison` — the library's own folder name on disk, a
DATA value, frozen with that reason because renaming it would describe a layout
the disk does not have. `extract-maquette-css.py`, the CSS contract's own tool,
was French from end to end; renaming it is proven by the only proof that counts —
regenerating the stylesheet moves not one byte.

Two defects in the gate itself surfaced while widening it: `≠` decomposes to `=`
plus a combining slash, so a test that merely asks « does anything here combine? »
reads a mathematical sign as French; and `suite`, `refuse` and `porter` left the
lexicon, because a guardrail that flags an English word teaches its reader to
stop believing it.

Wave gate: `resync.py` reports no drift, the full 48-script suite is green with **485 holds —
the same total the wave started with**, `make check` and `make check-frontend` green. The count
is the sum of the scripts' own `N rules EXECUTED` lines (`pwa.py`'s 28 checks are tallied
separately, and six scripts print holds without a Journal tally) — recorded here because the
next wave should not have to rediscover how the number is made.

---

## SP4d wave 1 — Système, Maintenance, Configuration: the shell owns a PAGE

Branch `feat/maquette-sp4d1`, version 0.97.18 (ONE bump for the whole wave). The first of
SP4d's four page waves: the three surfaces the legacy engine drew with `viewSystem`,
`viewMaintenance` and `viewReglages` leave the fragment and become final React components.
They went first not because they are small — Réglages is the largest data surface in the
prototype — but because they **write almost nothing**, which is what makes them the place to
pay for the PAGE machinery, exactly as SP4a paid for the SCREEN machinery on the two smallest
screens.

**A PAGE is not a screen, and that is the whole of the machinery.** Every surface migrated
before this wave is an overlay screen with its own path, drawn inside the React root. A page
has no address of its own: `/` stays the pages' route with its legacy query, the LEGACY parser
keeps owning it, and a page's markup has to land inside `#view`, where the stylesheet, the
harness selectors and the document-level click delegation all expect it. So the shell PORTALS
into `#view`: a `PAGES_OF()` entry gains `shellOwned`, `render()` skips its `innerHTML` write
for such a page and does everything else it always did (the bar, the nav and the save bar are
shared furniture), and `src/pages/host.tsx` holds the ONE table a later wave adds a page to.

Four rulings, all contestable, all recorded in `regions.json`: **the host element IS the page's
root** (`div.body`, which all three pages emit) rather than a wrapper, and it lives inside
`#view` rather than in a container of the shell's own — the alternative moves the markup out of
`.stage`'s layout context, forces a CSS amendment the spec reserves for SP5, and would move
every harness selector reading `#view …` with it. **The shell empties `#view` when it takes
ownership**, once, on the transition — not on every render, and not in the legacy, which cannot
know when React is ready to draw; handing back needs nothing, because the legacy's own write
removes what React left. **A host element rather than a portal straight into `#view`**, because
leaving a migrated page the legacy's write runs FIRST, synchronously, and React would then be
removing children that are already detached. And **a migrated page's entry loses its
`render`**, so clearing `shellOwned` without restoring a renderer CRASHES rather than silently
drawing a page nobody maintains.

**`REG_ETAT` stays the fragment's**, read by the component through the store's `version` bump:
R60 reads `REG_ETAT.modifs` in five holds, and making the settings state React-owned would
leave them reading nothing. The shared emitters are reused VERBATIM and SPLIT rather than
re-derived — `listeFaitsHTML` gained `lignesFaitsHTML`, `skelCards` gained `skelCardsInner`,
`surfErr` gained `surfErrInner`, `emptyHTML` gained `emptyInner` — each outer function emitting
exactly what it always did, the inner one existing because React cannot set the outer markup of
a node it also draws. The save bar is the settings page's SECOND portal, into `#device`, because
`#savebar` never lived inside `#view`.

**Every deletion was preceded by its own fidelity proof.** `frontend/maquette/fidelity.py` — run
by hand, against the legacy renderer, BEFORE deleting it — compares `#view`'s markup with the
legacy function's own output in the same document, through ONE serialiser: 0 divergences over
the four `systeme-*` states, 0 over the four `maintenance-*`, 0 over all sixteen `reglages-*`
(the eight field types included). It normalises the three things that are the WRITER and not the
markup — inline-style serialisation, attribute ORDER, whitespace runs — and each of those cost a
full measuring cycle to understand; it deliberately does NOT normalise a whitespace text node
between TEXT and a tag, because that one renders. Two such nodes were restored in this wave.

**The rule ladders gained the identity these three pages never had, in the same wave that moved
them.** New rule **R77** (`harness/page_host.py`) holds the ownership law: a migrated page is
drawn once, a legacy page still draws, and a page draws the SAME whichever world it was reached
from — the residue hold measures constancy across predecessors rather than a root count, because
pages emit different numbers of roots. **R67** stopped judging a list it had not found: its five
Système lists are located by the FRENCH text of their `<h2>`, which now comes from `fr.json`, and
`rows or []` turned a lookup miss into an empty list that « no row is wrong » is true of; the
heading, the reading key, the verdict's word and the declared source are now named once, in one
table the reading is generated from, and every list must be FOUND with rows to judge first.
**R60** gained a POSITIVE CONTROL, and it is the wave's most durable lesson: its « every setting
subject carries a written name » hold reads a set filled as a SIDE EFFECT of naming a subject —
delete the side effect and the hold stays GREEN. And the DELEGATION, which no rule touched at
all: R67 reaches Maintenance through `applyState` and R60 reaches every settings state through
`__go`, never through a tap, so the nine `data-*` attributes the document-level handler acts on
were unmeasured. Each now has a hold driven by a REAL tap, with the control looked up before it
is tapped — a click on a selector that matches nothing times out and CRASHES the script, which
reads as a broken rule instead of a named defect.

**A setting is no longer named in two places.** The fragment's four literal tables
(`LIBELLES_REGLAGES`, `CONTENANTS_REGLAGES`, `NOMS_SUJETS`, `UNITES`) and the panel component's
copy reading `fr.json` were two implementations of one naming — a label curated on one side and
not the other renames a row on the page and leaves the panel above it saying something else. The
naming moved to `settings-labels.ts`, read by the page, by the panel and by the fragment's own
panel title through `window.__settingLabels`; the fragment gave up 247 lines. The ORDER was the
substance: the detector came back to the React side FIRST (`panel.tsx` had dropped
`window.__sujetsSansNom.add(s)` as « an unrelated diagnostic », which is exactly what makes a
hold go quiet), then the page pointed at it, then R60's four call sites followed, and only then
the fragment lost its tables. Proven both ways: the two implementations compared over all 159 rows the prototype
declares (the 153 JSON5 settings plus the six PM2 schedules) — labels, subjects, units — 0
divergence; and a mutation dropping the recording line
fells the control ALONE while the hold below it stays green on the empty set.

**And then the wave's own adversarial review found what the whole suite had walked past.** The
settings page's save bar is a React portal into `#device`; the legacy still removed that node by
hand when the page changed, and the guard written for it read the ARRIVING page — so on the way
OUT of Réglages it did not hold. React unmounted the portal a microtask later and removed a node
that was no longer its container's child: `NotFoundError` on the CONSOLE, never a page error,
the React root torn down, and every migrated page and screen dead until a reload. Measured
rather than argued: coming back to Réglages drew the LIBRARY's four roots and zero settings
rows. The legacy's mounter is deleted — no page draws a bar from there any more, so what was
left could only ever remove someone else's node — and R77 gained the hold that would have caught
it, mutation-proven by re-injecting the removal into the served copy alone. Two more divergences
came out of the same reading, both invisible to the fidelity oracle because it could only ever
see `#view` and the bar lives in `#device`: the restart banner named its files through
`nomDeFichier` where the legacy printed them raw, and the save bar had lost the whitespace text
node the legacy's own line break put between « en attente » and « Écrira » — the SP4b trap, one
instance not restored. `fidelity.py` now takes the host to compare, so a page's second host
cannot ship unproven again. The rules gained the rest: two more emptiness holds got the
denominator the rung had just given the five block lists, the runs and code-errors lists (whose
tone is derived where they are drawn, so no declared field can judge them) got the half that
needs no data, three delegation taps that accepted « something happened » now compare the row's
own value against what opened, and the ownership law reads the document the BROWSER ran instead
of the source on disk — under this wave's own mutation method, a source read could have stayed
green over a page that had lost the guard.

**Wave gate**: `resync.py` reports 0 corrections; the full suite is **49 scripts, 521 holds,
zero FAIL** (494 at the wave's mid-point, +15 for R67 and +12 for R77 — the count
is the sum of the scripts' own `N rules EXECUTED` lines; four scripts print verdicts without a
Journal tally and contribute none); `make check` green including `check-frontend` (10 566
backend tests, 1 364 frontend tests); `scripts/check-no-french.py` green on four arms;
R59/R69/R71 byte-identical against the merge point. The fragment went from 40 465 to 40 071
lines. Pages the shell now owns: `sys`, `maint`, `cfg`. Pages the fragment still draws:
`acq`, `arr`, `lib`, plus `viewIntrouvable` and `viewProfil`. The DRAWER stays where it was —
this wave was not its last consumer: the topbar burger and `viewIntrouvable` still open it.

## SP4d wave 2 — Arrivées, and the first migrated control that writes

Branch `feat/maquette-sp4d2`, version 0.97.19 (ONE bump for the wave). The second page wave,
on the machinery wave 1 paid for: `viewArrivals` — 43 lines — becomes `pages/arrivals.tsx`, and
with it the two emitters whose ONLY caller it was, `barrePipelineHTML` (29 lines) and
`dernierPassageHTML` (26). That is the difference from wave 1: there, every emitter had other
callers and was reused verbatim through the référentiel; here two of them had none, so they
became real JSX rather than published helpers. `secHTML`, which nine call sites share, stayed in
the fragment and gained its `secInner` — the same split as `emptyInner`, `skelCardsInner` and
`surfErrInner`, and the component reproduces the outer function's EMPTY case by drawing no
section at all.

**Arrivées is the first migrated page carrying a control that WRITES.** The pilot's bar writes
nothing itself: it emits `data-pipe="lancer"` / `"arreter"` and the document-level delegation
does the writing, exactly as before. Its three states include the one DOIT-4 exists for — a pass
asked DURING a run is QUEUED, visibly, never refused with « busy, try again ».

Fidelity proven before any deletion: **0 divergences over all six `arr-*` states** (repos,
running, queued, loaded, loading, error).

**And a defect of CLASS, measured on the way.** R66 drove the page by writing `state.page = "arr"`
— the engine's alias — and calling `render()`. That alias points at the store's CURRENT object,
so mutating it in place leaves the object's identity unchanged: nothing React subscribes to
moves, and the page keeps drawing whatever was there before. Measured, not argued: the store said
« arr » while `#view` held the ACQUISITION page's roots, and the rule reported a missing button
rather than a stale page. The fragment itself no longer writes the alias anywhere — SP4a
converted its ~70 write sites — but six harness scripts still did. All six now go through the
store, and R77 gained the source-level hold that catches the class: no rule drives a page by
mutating the alias. Mutation: putting a single driver back fells it, naming the file and the
line. It matters beyond this wave — the same write would have silently broken the Médiathèque and
Acquisition waves, on rules that look green.

R77 took Arrivées in (25 holds): the residue walk crosses both worlds on it, and the bar's three
taps plus the `data-go` crossref each have a hold driven by a REAL tap. Mutation: `data-pipe`
disabled in the served bundle alone fells the three taps, each naming the attribute that went
missing.

**The wave's own adversarial review** found the new alias-drive hold matched only ONE shape —
`state.x =` on a single physical line — and would have been walked past by
`Object.assign(state, …)`, which the engine itself uses, by `state["page"] =`, and by a write
split across two source lines, which is this directory's own house style. It now flattens the
text and looks for three shapes; three mutations, one run each, fell it. The engine's single
`Object.assign(state, etatDeLURL())` earned a hold of its own in the process: a COLD deep address
must land on the page it names, drawn by the shell. It holds for a sturdier reason than the boot
order — starting the engine after React's first paint does NOT fell it, because the address write
that follows re-renders the shell — so the mutation that proves it is the URL parser ceasing to
read `page`. The review also caught a tap that read only the store where its two siblings read
the drawing, a block inheriting a scenario it did not name, and three fresh comments repeating a
call-site count that was wrong at the source (`rg -c` counts the definition line).

**Wave gate**: `resync.py` moved the drawer's deployed-version card to the branch's base
(0.97.18, build `21c54a98`), committed as data; the full suite is **49 scripts, 527 holds, zero
FAIL** (521 + 6 for R77: Arrivées' four delegation holds, the alias-drive law and the cold
deep address); `make check` green including `check-frontend`;
`scripts/check-no-french.py` green; R59/R69/R71 byte-identical against the merge point. The
fragment went from 40 047 to 39 961 lines. Pages the shell owns: `sys`, `maint`, `cfg`, `arr`.
Pages the fragment still draws: `lib`, `acq`, plus `viewIntrouvable` and `viewProfil`.

## What is already done, ahead of the phase plan

The prototype and its harness carry the design; some app-side work was pulled forward because
the audit that motivated it was done. Neither replaces a phase.

**In the prototype.**

- The **startup screen** (`demarrage`) covers the wait between signing in and an interface being
  there, and the **gate** shows the same screen — extracted, never retyped — from the submit
  onwards. R53, `harness/startup.py`.
- **Signing out** ends the session on the server and lands on the entry screen, instead of
  answering with a message over an interface that had not moved. R54,
  `harness/logout.py`.
- **Every gesture answers a real finger.** The pull to refresh and the swipe between views had
  both been lost to the compositor and worked only under synthetic events. R55,
  `harness/touch.py`.
- **One bottom panel**, taking a descriptor of facts and ordered blocks of declared kinds. The
  fallback builder that answered for « whatever the first does not recognise » is gone. R56,
  `harness/panel.py`.
- The prototype **installs as its own application** — « TorrentMate Design », with an explicit
  manifest `id`, and its own icons: a yellow ring where the app has none and staging has a cyan
  one, generated by `frontend/scripts/make-design-icons.py`. R52 extended.
- **The install offer is actually offered.** The banner existed and nothing ever showed it:
  `beforeinstallprompt` was never captured, so on Android the browser kept the offer and on iOS
  Safari — which fires no event at all — the banner was the guide nobody saw. R51,
  `harness/install.py`.
- **The back gesture follows the path actually walked**, tabs and lenses included, closes a layer
  first, and at the root warns instead of leaving — closing only on a second back within five
  seconds. R59, `harness/back.py`.
- **The list poster reaches the card's edges**, 84px wide with the card's height as its floor,
  so a card at that floor gives an exact 2:3 and its artwork is untouched. Full height AND the
  ratio cannot both hold on a taller card — measured, a grid sizes the column before the row's
  height is known — so cropping is bounded rather than forbidden. The episode popover carries the
  brand outline, so its limits can be found on a dark surface. R47 rewritten, R58.
- **The brand colour is painted where the design puts it.** `--accent` was referenced eleven
  times and defined nowhere: the wordmark, the sign-in button, the install button and the startup
  bar were all unlit, and the host hid it by retyping the palette. R61, `harness/palette.py`.
- **One sign-in screen**, wherever one meets it: the host extracts everything the screen
  inherits — palette, box model, typography — instead of restating it. R62, `harness/entry.py`.
- **A card says what the engine knows.** A follow carries its identity, what is happening and
  when, and what tells a healthy follow from a stalled one, all read from `acquire.db`; a library
  row carries the synopsis, clamped to the largest number of lines that fits. R63,
  `harness/content.py`.
- **A row's drawer opens either way, one row at a time**, without firing the tap — and it renders
  identically on WebKit, where it used to spill past the rounded card. R64, `harness/drag.py`.
- **The startup screen covers one wait and plays once**, across the two pages that wait spans.
  R53 corrected. Its history is in `BUGS.md`: the rule was wrong in both directions.
- **The settings are navigated by what one wants to change**, never by file: five rubrics plus
  secrets and ranking, over the 153 settings the engine really keeps. Each row is identified by
  its label alone — its subject, then what it does, in French — because the leaf key drew
  « Activé » seven times in one list; the key is in the mono face under it, the file on the group
  header. Nothing is written until the save bar — which exists only
  when there is something to save — NAMES the files it will write; a secret says whether it is
  set and never what it is worth. R60, `harness/settings.py`.
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
