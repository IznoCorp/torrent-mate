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

## SP4d wave 3 — the Médiathèque, and E-001

Branch `feat/maquette-sp4d3`, version 0.97.20 (ONE bump for the wave). The third page wave, and
the one that changed the machinery: `viewLibrary` is 96 lines, but it is the only page whose
CONTENT the fragment wrote AFTER the page was drawn — an empty `#libitems`, an empty `#libcount`,
filled by `fillLib()` / `libFoot()` / `paintLibCount()` as the operator scrolled, `fillLib`
replacing the element outright (`box.outerHTML = …`). Two worlds writing one container is what
tore the React root down in wave 1, so the list, its footer, its sentinel and its search field all
moved WITH the page rather than leaving a seam behind.

**E-001 came first, and separately.** The operator's evolution — every sort reversible — is
maquette-first: drawn in the PROTOTYPE and measured there before any conversion touched the page.
That order is not a preference. A conversion is judged by « identical markup »; an evolution
changes the markup; doing both at once would leave neither provable. The ruling, recorded and
**open to contest**: the panel offers the six directions explicitly, each carrying its own NAME
rather than an arrow bolted onto a shared one — « Ajout récent » / « Ajout ancien », « A → Z » /
« Z → A », « Les plus incomplets » / « Les plus complets ». The alternative, tapping the
already-chosen sort to flip it, halves the rows and is INVISIBLE: nothing on a phone says that a
second tap on the row one just chose does something else. Reversing is a second PASS, never a
second comparator — « ajout récent » has no comparator at all, its order is the source's — so one
`.reverse()` says the same thing for all three. New rule **R78** (`harness/library_sort.py`, 15
holds) is the first this behaviour has ever had, and it measures the reversal on the ROWS DRAWN,
over a library narrowed until the whole set fits on one page: the list draws 24 of 260, so
reversing the order and taking the first page again gives the LAST rows of the other end — right,
and not the reverse of what was drawn.

**The PAGE HOST stopped supplying a root element**, and that is this wave's principal
arbitration. It portalled into a `<div class="body">` of its own so the legacy's write would
remove one node whole and React would only ever touch children of a node it owned. That describes
three pages emitting one root; it cannot describe a page emitting FOUR (`.viewtabs`, `.filters`,
`.countline`, `.body`), and wrapping those would be a markup change this conversion does not make.
So the shell portals straight into `#view`, and the handover is ANNOUNCED inside `render()`, the
one place that already knows which world owns the page: taking, the fragment removes the nodes IT
wrote and lets React draw; releasing, it calls `window.__releasePage()` — a `flushSync` — before
writing. Removing its own nodes rather than emptying the container is not a matter of taste: a
store write and a `render()` are not always the same task, so the shell may already have drawn,
and emptying then deletes nodes React believes it holds, leaving a blank page nothing redraws.
Measured — R77's first five holds fell before the correction existed.

**What proves the machinery moved nothing**: `fidelity.py` learned to RECORD the legacy's drawn
page and compare against the recording, because this page's markup is not what its renderer
returned. The nineteen states of the four pages migrated before this one, recorded and compared
across the host rewrite: **0 divergences**. The ten `lib-*` states, recorded from the legacy and
compared after the conversion: **0 divergences**.

**The search field's handler moved with the field.** `mountSearch` no longer binds `#libq` — the
same reason it had already let go of `.fieldinput`: binding a node React owns from outside is two
writers on one field. The caret dance the legacy needed disappeared with the rebuild that made it
necessary, and what changes the query from OUTSIDE (the clear cross) reaches the field through an
assignment made only when the two differ — measured by typing for real, character by character,
and then clearing.

**What did NOT move**: `trierLib` and `libFiltered` stay in the fragment. They touch no DOM — they
answer « which media, in which order » — so a component asks them rather than reproducing them,
and a rule reads `libFiltered()` by name. The selection bar stays the fragment's too: it lives in
`#device`, React never draws it, and the component only asks for a repaint after it renders,
exactly where `fillLib` asked for one.

R77 grew to 32 holds: `lib` joins the shell-owned list, the drawn hold stops assuming a root
count, the law hold reads the LAW rather than one spelling of it — it failed on the day the law
was made stronger — and six delegation holds cover the page that carries the most of it: lens,
category, view mode, selection, the search's cross, and `data-del`, read rather than tapped
because that control lives behind a swipe R64 drives.

**And then the review found four defects of one family**, all of them a component reading its
render's SNAPSHOT where the legacy read the engine's live alias. « Réessayer » reloaded nothing:
the handler clears the error on one line and the guard below it, frozen at the value the footer
was drawn with, refused — the page arrived anyway, from the SENTINEL, which is what hid it. The
same closure froze the count, so a search or a sort during a load overwrote it with the old count
plus a page. `paintSelBar` ran on every draw where `fillLib` reached it only after the ROWS,
rebuilding a node in `#device` the legacy left alone. And `#libitems` stopped being rebuilt on
every draw, so a swipe left open survived a repaint that used to shut it. Two quieter ones came
with them: the observer stayed connected during a load the legacy disconnected it for, and
`#libq`'s value ATTRIBUTE froze at mount while the legacy re-emitted it every draw.

**The surface nobody could measure now has a name and a rule.** No named state produced a failed
NEXT page — only a long scroll reached it — so the sentence it prints and the control that
retries were asserted by nothing. `lib-erreur-suite` names it and **R79** (`library_load.py`, 8
holds) holds it, measuring the retry with the SENTINEL NEUTRALISED, because the sentinel produces
the same outcome for a different reason and that is exactly how the defect survived being
written.

**Two holds that were not holding.** R77's law hold no longer required the `#view` write to be on
the not-owned BRANCH — only that a branch and an announcement existed somewhere; it reads the
structure now, and a write hoisted out of the `else` fells it. And the two page tables — the
shell's and the fragment's flags — are compared, because an id claimed on one side and not the
other draws a page in both worlds at once, on every render, perfectly consistently, which no
drawing-shaped hold can see.

**R78 could not tell two sorts apart.** Its narrowing contained no incomplete show, so « les plus
incomplets » ranked a set where every row scores the same and answered the source order — which
is what « ajout récent » answers. The narrowing is held now; the marked entry is measured after a
REVERSED direction is chosen; « A → Z » is held alphabetical by the platform's French collation,
which breaks the tautology that a reversal assertion is true of any comparator; and the direction
is checked in the GRID, where the rows go through a different emitter.

**A rule found a defect nobody had reached.** The new state drew two pages, and R1 — the
adversarial auditor's « every tappable poster leads to a filled-in sheet » — fired at once: **87
of the library's 345 titles have a sheet with no genre and no cast**, none of them in the first
page, which is why no state had ever shown one. It is a defect of the embedded DATA, recorded as
**B-030** rather than fixed in a conversion wave. Chasing it also surfaced a real timing hole: a
state that draws a skeleton starts a load, and 620 ms later that load landed on whatever state
had replaced it. A load now remembers the store VERSION it was asked at and does nothing if
anything has happened since.

**Wave gate**: `resync.py` moved the drawer's deployed-version card to the branch's base (0.97.19,
build `aeac77cb`), committed as data; the full suite is **51 scripts, 562 holds, zero FAIL** (527 + 19 for R78, 8 for R79 and 8 for
R77); `make check` green including `check-frontend`;
`scripts/check-no-french.py` green; R59/R69/R71 byte-identical against the merge point. The
fragment went from 39 962 to 39 956 lines — nearly flat, and the number says something true: the
conversion removed about 230 lines and E-001 put back about as many, because an evolution is
written before it is moved. Pages the shell owns: `sys`, `maint`, `cfg`, `arr`, `lib`. The
fragment still draws `acq`, plus `viewIntrouvable` and `viewProfil`.

## SP4d wave 4 — Acquisition, and the last two pages

Branch `feat/maquette-sp4d4`, version 0.97.21 (ONE bump for the wave). The last page wave, and
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

**And the review found four defects, the first of which made the page inert.** Every action this
page offers mutates the world IN PLACE and signals with `toucher()`, which leaves the state's
identity unchanged — and the component subscribed to the state alone, so React bailed out and the
page kept drawing what it had drawn. Measured: « Récupérer maintenant » moved a medium from one
list to the other and left every counter on screen unchanged, 2/1/3/2/4 before and after. The two
other pages that read mutable data subscribe to the version; this one did not. `#follq` had no
handler at all — migrated as markup, its binding left to `mountSearch`, which runs inside
`render()` before React has put the field in the document: typing filtered nothing until some
other control forced a second render, the clear cross emptied the list but left the word in the
field, and the `value` attribute never followed. What the operator TYPES reached a
`dangerouslySetInnerHTML` unescaped, where the legacy escaped it — on the one call site that was
missed, in a wave that had exported `escapeHtml` for exactly this. And the deck's « Passer »
swipe had stopped animating: it writes the order to the store, so it re-renders, and the
dependency-less effect rewrote `.deckbody` on every commit — replacing the very nodes
`avancerDeck` animates, which is what that function's own comment forbids in as many words.

R77 gained the hold that would have caught the first: an action that moves a medium redraws the
page it moved it on. Mutation: removing the version subscription fells it, showing the counters
identical on both sides. **Three more holds were not measuring enough.** The seam hold accepted
« there are children », which a component rendering one satisfies too — it now reads what only
the FRAGMENT does: the `className` it sets and the `data-dismissable` rows no component emits.
The ownership hold read a constant declared fifty lines above it in the same file and could never
fail — it asks `PAGES_OF()` now. And the « the page is drawn » floor had been lowered for ALL
eight pages to admit the smallest; it is per page, measured, so a Médiathèque reduced to its tab
bar no longer passes. `emptyHTML`, whose last four callers left with the pages, was deleted — it
had stayed, and had been declared in the shell's type as if exported, which would have answered
« is not a function » to the first component that believed it.

**Wave gate**: `resync.py` moved the drawer's deployed-version card to the branch's base (0.97.20,
build `52f28213`), committed as data; the full suite is **51 scripts, 571 holds, zero FAIL** (562 + 9 for R77); `make check` green including `check-frontend`; `scripts/check-no-french.py` green;
R59/R69/R71 byte-identical against the merge point. The fragment went from 39 889 to 39 560
lines. Every page belongs to the shell: `sys`, `maint`, `cfg`, `arr`, `lib`, `acq`, `profil`,
`404`.

## SP4-fin wave 1 — the engine leaves the fragment

Branch `refactor/maquette-sp4fin1`, version 0.97.22. The inline script — **35 052 lines** —
becomes `design/src/engine/legacy.js`, a module the shell imports before it reads
`window.__demarrerMoteur`. The fragment goes from **39 561 to 4 507 lines**: a title, the
stylesheet, and the app shell's markup. Nothing executable.

**What the recon settled about the shape of the rest.** The script was never one thing: 30 531
lines of DATA across 118 constants (`FICHES_RAW` alone is 20 538) against 4 507 lines of code
across 135 functions. That ratio is why the engine moved whole rather than being split during
the move — 78 % of the volume is a fixture library no split makes clearer. And the order is
forced: the engine's top level calls `seedWorld()` and binds document-level listeners, so data
extracted ahead of it would not exist when the classic script ran. Everything becomes deferred
at once, or nothing can.

**Four things measured before the move, each of which would have been a defect.** It parses as
an ES module under strict mode. It reads no parse timing — zero `readyState`, zero
`DOMContentLoaded`, zero `document.write`, zero `currentScript` — so being deferred changes no
branch. The static markup carries one inline handler, `onclick="return false;"`, which needs no
global. And none of the 254 top-level names collides with a real `window` property — checked
against Chrome, because Node's `globalThis` has a different surface and would have said the
same thing for the wrong reason.

**The engine republishes its own surface, and that is a SEAM, written down rather than
inferred.** A classic script's declarations are global, and the harness drives the engine by
bare name at some forty `page.evaluate` call sites; a module's are private. So `legacy.js` ends
by republishing exactly what existed: **230 by value, 24 by getter**. The split is measured, not
chosen — a binding the engine REASSIGNS cannot be published by value, and `state` and `world`
are both reassigned and both are what the harness reads most. By value they would have answered
a world that no longer exists, silently, and every rule reading them would have measured a page
that was no longer there. The seam narrows in the wave that kills the bridge, not before:
narrowing it means editing the instrument that measures the move.

**0 divergence on 82 states, zero JS errors** — `fidelity.py --host '#device'`, so the
comparison covers the whole phone frame: screens, sheets, drawer and topbar, not `#view` alone.

### What the fidelity oracle could not see, and the suite could

`deconnecter` is an `async function`. The regex that collected the top-level names knew
`function`, `const`, `let`, `var` and `class`, and not that form — so it was the ONE name never
published. No state's markup depends on logging out, so 82 comparisons said « identical » while
`entry.py` said `ReferenceError: deconnecter is not defined`. Two gates, two blind spots, and
neither is redundant.

### Four rules went green over a file emptied of their subject

`images.py`, `bridge.py`, `palette.py` and `panel.py` each read `refonte.html` from disk and
grepped it. After the move that file no longer held what they were grepping FOR — 930 image
references, five colour references, the callers of `window.__panneau.ouvrir`, and the body of
code history primitives are counted in. **None of them failed.** A hold that greps a file which
no longer holds its subject reports « no violation » about nothing at all.

The fix is the class, not the four instances: `common.py` now names `DESIGN_SOURCES` and reads
them with `design_source()`, which RAISES on a source that has been renamed away rather than
returning "". Each of the four falls under a mutation planted in the engine — a missing asset,
a `history.pushState`, an undefined custom property, a returning `panneauHTML`.

`export.py`'s classifier had the same shape of failure with the opposite symptom: it globbed
`design/src/**/*.tsx` for the class names the interface WRITES, and the engine — which writes
the great majority of them — is a `.js`. It reported that the extraction would leave CSS behind,
which read as « the stylesheet is wrong » when what had moved was the writer.

### The handover law is now held twice, and the second half carries its own control

R77's structural hold read `render()`'s shape out of `page.content()`, deliberately: the served
copy, never disk. That reason expired with this move — what the browser runs is now minified,
where `if (found.shellOwned)` reads `if(e.shellOwned)`, and a structural assertion written
against mangled names measures the minifier. It reads the engine's source instead, and it is
honest about guarding a branch that is currently DEAD: every page is shell-owned, so the `else`
never runs, and no runtime probe can reach it.

The live branch got its own hold: `#view`'s own `innerHTML` setter is wrapped for one real
redraw, which must write it zero times. **And that hold proves its own detector every run** — a
deliberate write, counted, after the measurement — because a hold asserting a count of ZERO
passes just as happily when its spy is dead.

That was not caution. It was found: the obvious mutation for it — a write on the shell-owned
branch, spelled so the structural pattern cannot see it — breaks the page so thoroughly that
thirty earlier holds fail and the script never reaches the line. « The suite went red » is not
the same as « this hold works ». And a first attempt at that mutation proved nothing at all,
because it edited the source while the harness served a build staged before it: **a runtime
hold can only be mutated THROUGH THE BUILD.**

### An oracle defect, and it was about a clock

The first comparison reported one divergence, and it was the boot hint toast — recorded with
`.show`, compared without. Its clock is identical on both trees: raised 770 ms after load,
hidden 5 775 ms after, within 5 ms across four runs. The walk simply crosses that expiry between
two adjacent states. `fidelity.py` dismissed the toast immediately after `load` — before it is
raised — so the click hit nothing. It now waits for the toast to exist and dismisses it then,
and the pre-move tree was re-recorded with the corrected oracle before any verdict was taken.

### And what the adversarial review found, which no gate had

Two, and both are the same shape: **a pattern that answers a question narrower than the one
being asked**, printing a true-sounding sentence about a scope it does not cover.

**`deroulementEnCours` was published by value, and it is rebound.** The test for « does the
engine reassign this » looked for `name =`. That binding is only ever written
`deroulementEnCours += 1` and `-= 1`, so it read as stable and went on the value side, where
`window.deroulementEnCours` would have answered 0 forever — the same silent lie the getters
exist to prevent, arrived at from the other direction. The rebinding forms that carry no bare
`=` are compound assignment, `++`/`--`, destructuring on either side, and `for (name of …)`;
all four were then searched across all 254 names, and this is the only one. The split is
**230 by value, 24 by getter**.

**R76 printed « `navigate(` appears exactly once under `design/src/` » about a scope that had
stopped containing the file most likely to break it.** Its glob reads `.ts` and `.tsx`; the
engine is a `.js`, and it navigates the router once — `window.__routeur.navigate({to: "/",
replace: true})`, inside `window.__go`. That call is not a journey: `__go` is the harness's
state DRIVER, and it resets the router before applying a named state exactly as it clears the
legacy screen stack, so a measurement never inherits the route a previous one left. The law
holds in spirit; the sentence did not. The rule now globs `.js` too and bounds both calls at
one each — the product's single door, and the driver's reset — so a third fails, which it does
under mutation.

### What stays in the fragment, and it is the spec's decision, not this wave's

The stylesheet. « The CSS contract (BLOCK 2, extraction, `regions.json`) does not move — SP4
converts structure and behaviour at IDENTICAL markup; the visual language stays SP5's
question. » `scripts/extract-maquette-css.py` reads BLOCK 2 out of that file and `make check`
fails on drift; re-pointing it is SP5's opening move.

`resync.py` did move with its subject: both things it rewrites — the `FOLLOWS` counters and the
drawer's « Version déployée » footer — are the engine's, not the fragment's.

## English names — the operator saw what four waves had not

Branch `refactor/english-names`, versions 0.97.26 → 0.97.31. The operator's whole message was
« data-suivante, trierLib, …. encore beaucoup d'éléments utilise des noms français », and both
examples were real: **141 of the engine's 446 declared names (31 %) were French**, and so were
nineteen `data-*` contracts.

**And the guard said « no violation » throughout.** Its French detection was a hand-written
list of 156 words with holes in it — `suivante`, `trier`, `fermer`, `afficher`, `masquer`,
`chargement`, `compte`, `monde` were all invisible — so its verdict meant « none among the
words we thought of ». That is this session's recurring defect, arrived at one last time: a
pattern answering a narrower question than the one being asked.

### What moved

| | |
| --- | --- |
| pure identifiers | 106 |
| names that are also properties | 29 |
| `etat` and the store API (`lire`, `ecrire`, `adopterEtat`, `adopterMonde`, `toucher`, `monde`) | 7 |
| `data-*` contracts | 19 |
| the login form's fields | 2, across seven sites |
| the last names the vocabulary surfaced | 27 |

Every batch proven the same way: **0 divergence on 82 states**, or — where the markup changes
on purpose — the rename map applied to the RECORDING and exact equality required, which says
« every difference is a rename and nothing else ». The rule suite green at 568 holds, unchanged
from `main`, at every step.

### The detector now asks the opposite question

`scripts/code-vocabulary.txt` holds **522 words** — the ones this codebase's names are built
from. « Is this word one we use? » has no holes by construction: a name built from a word
nobody wrote down is refused, whatever language it comes from. The arm reads `.js` too, which
is what finally puts the legacy engine under a guard.

It justified itself immediately. Seeded from the code, it contained **thirteen French words** —
meaning twenty-seven more French names, `trierLib` among them, that a dictionary sweep had
missed because *trier*, *carte*, *sortie* and *note* are English as well.

### Nine shapes that look like an identifier and are not

Each one cost a red gate, and each is now in `scripts/rename-identifiers.py` with its reason:

| Shape | What it really is |
| --- | --- |
| `"un compte, un identifiant."` | interface copy |
| `mode === "clair"` inside `${…}` | a string NESTED IN an interpolation — an interpolation is code, and code contains strings |
| `reglages-modifie` | a hyphen-composed state id |
| `"ajout:suivi"` | a colon-composed data key — renaming it rewrote a rule's own EXPECTED value |
| `f"/profil/{titre}"` | a route path; a slash delimits an address |
| `[data-go=profil]` | a bracketed selector — an attribute AND the value it must carry |
| `liste:` in `t("…", {…})` | an i18n placeholder named in `fr.json` |
| `PAGES = { profil: … }` | a key that IS a page id |
| `"PLANIFICATEURS"` | …but this one IS an identifier, told apart by CASE |

The tool carries its own proof: **an empty map must round-trip every file byte-identically**.
That is what caught two bisect errors of mine — one measuring a single state out of the
recorded order, one comparing slices instead of growing prefixes.

### An inventory that could not see what it was inventorying

Listing `data-*` names by searching for the literal text `data-x` misses every attribute the
engine GENERATES: it writes `data-${nom}` where `nom` is a key of a data object, so
`{ profil: "American Dad!" }` becomes `data-profil`. Renaming the reader without the data left
forty states with a half-moved contract, and two names — `completer`, `retirer` — existed only
in that generated form, where no inventory of literals could ever have found them. A third
form again: a ternary, `{ settri: cle }`, inside no `target: { … }` block at all.

### The mistake that merged two contracts

Renaming `fiche` → `sheet` looked like the other 140. It was not: `data-fiche` is the media
sheet, and **`data-sheet` already existed** as the sheet-opener (`utilisateur`, `plus`). After
the merge the user menu answered with the media sheet's actions — seven rules said so. Measured,
reverted, and `fiche` is now a NAMED DEBT in the frozen list: the obvious English name is taken,
so it needs one of its own and its own step.

The check this adds, and it belongs before any property-mode rename: **does the target name
already exist as a contract?** Target collisions had been checked for bindings and for `data-*`
names — not for a binding whose rename lands on an existing attribute.

## SP4-fin wave 3 — the bridge dies, and the fixture leaves the product

Branch `refactor/maquette-sp4fin3`, version 0.97.24. Four things the spec named for SP4-end,
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

### A positive control earned its keep, on the day it was supposed to

`panel.py` went red on « there really are callers — 0 calls ». That check exists for one reason:
its neighbour asserts that NO caller hands markup to the panel, and an assertion about an empty
set is true of nothing. The engine's 40 call sites had just stopped spelling the verb
`window.__panneau.ouvrir(` and started spelling it `panneau.ouvrir(` — so the count fell to
zero, and the pair said so instead of quietly passing.

It counts both spellings now, because there are two and they are the same object. Both halves
fall under mutation, separately: a caller handing a string fails the first, every caller renamed
away fails the second.

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

## SP4-fin wave 2 — the markup leaves the fragment

Branch `refactor/maquette-sp4fin2`, version 0.97.23. The 287 lines of application shell —
`.stage`, `.device`, the splash, the sign-in card, the topbar and its burger, the drawer,
`#view`, `#screen`, the sheet and dialog hosts, the toast — move to `index.html`. **The fragment
is now a title and a stylesheet: zero `<script>`, zero top-level element, zero inline handler.**
4 507 → 4 217 lines.

**It went to `index.html`, not into React, and the reason is the engine's boot.** The engine
captures its containers at module evaluation — `view = F('#view')` and its siblings — and a
module evaluates before React has rendered anything. Markup drawn by a component would not exist
when the engine looks for it, and the shell would have to stop starting the engine before its
first render to fix that: a change to the boot contract, in order to move static markup.
`index.html` is the document Vite owns, it is real source rather than a fragment injected
verbatim, and its body is parsed before any module runs — exactly the order the markup already
had. It sits AFTER the injection marker so the order inside `<body>` is unchanged too: mount
node, stylesheet, shell.

**0 divergence on 82 states, zero JS errors.**

### The login gate, proven byte for byte rather than eyeballed

`serve.py` builds the sign-in page out of the prototype's own screen — it clones the MARKUP and
inherits the STYLE — and those two halves now live in different files. It reads each block where
it lives: `login:markup` and `login:splash` from `index.html`, `login:font` / `palette` / `socle`
/ `style` / `splashstyle` from the fragment. Pointing one at the wrong file raises, because
`extract` raises on a missing marker.

The gate was then built on both sides of the change and compared: **byte-identical, in both its
normal and its refused state** (108 171 and 108 164 bytes).

### The same failure shape, a third and fourth time — and one of them was loud

`startup.py` (R53) reads the markup for the startup screen's declaration ORDER, and it did not go
quietly green: it raised `min() iterable argument is empty`, because all three landmarks it looks
for returned -1. Loud is better than silent, but « the harness is broken » is the wrong sentence
for « the document moved ». Each landmark is now looked up by name and the misses are NAMED, in
a hold that falls under mutation instead of raising.

`export.py` sliced the fragment at `</style>` to keep « markup + JS without the CSS ». The
fragment now ENDS at `</style>`, so that slice is two characters long — and this classifier would
have called every class the application writes « dead », i.e. reported that the stylesheet was
wrong. It reads `index.html` plus the `src/` sources, and classifies exactly as before: 267 app,
22 written-only, 4 harness, **0 dead**.

`common.py`'s `DESIGN_SOURCES` gained `index.html`. It contributes nothing to the four counts
that list serves TODAY — zero asset references, zero `var(--…)`, zero history primitives, zero
panel callers. That is not a reason to leave it out: the list names where the design is WRITTEN,
so the next one added to the shell is covered on the day it is typed.

### Two rules went red on a PROCESS, not on the code

`pwa.py` and `entry.py` are the only rules that measure the LIVE host, because installability
and the sign-in gate are things only a real server hands out. `serve.py` is read once, at boot —
so the edit above was not live, the running process still looked for `login:markup` in the
fragment, and the host answered its own build-failure page. The two rules then reported « the
login gate declares no manifest » and `Cannot read properties of null`: eight symptoms, none of
them about the change under test.

`pm2 restart torrentmate-design`, and both are green — the gate it now serves is 108 171 bytes,
the same count proven byte-identical against `main`. Written into the README, because it recurs
every time `serve.py` changes.

### R72 needed no renegotiation, and that was measured rather than assumed

The plan reserved the right to renegotiate « the fragment appears verbatim exactly once », since
a fragment that is only a stylesheet is a different object. It did not need it: the fragment is
still injected verbatim, exactly once, and `shell.py` is green untouched.

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
