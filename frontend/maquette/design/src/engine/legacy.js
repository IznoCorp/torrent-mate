/* The legacy engine, at its own address.

   THIS IS NOT NEW CODE. It is the prototype's original inline script, moved
   here byte for byte so that the fragment can stop being a program and the
   engine can start being files. Nothing in it was rewritten in the move: the
   proof that it is the same engine is a state-by-state comparison of the
   whole phone frame, taken before the move and replayed after it.

   It stays JavaScript, and that is deliberate. Typing it would mean editing
   it, and an edit hidden inside a 35 000-line move is an edit nobody can
   review. The conversion of what is left happens in the open, module by
   module, against the same oracle.

   HOW IT REACHES THE PAGE. It used to be a classic script, evaluated while
   the document parsed. It is now a module, evaluated as the shell's own
   dependency — `shell.tsx` imports it before its boot calls `installArrival`,
   so the order the engine has always relied on is the order it still gets:
   everything here runs first, the shell's boot runs second. Nothing in here
   reads `document.readyState` or waits for `DOMContentLoaded`, so being
   deferred changes no branch (measured before the move: zero occurrences).

   WHY IT PUBLISHES ITSELF AT THE END. A classic script's top-level
   declarations land in the realm's global scope, where anything evaluated in
   the page can see them — and there are two hundred and fifty-four of them,
   seen that way today by the harness, which drives this engine through
   `page.evaluate` using their bare names. A module's declarations are private, so the same
   names would simply vanish, and every rule that names one would fail with a
   ReferenceError instead of a verdict. The block at the bottom republishes
   exactly the surface that already existed — no more, no less — so that
   nothing outside can tell the difference. It is a SEAM, and it is written
   down rather than inferred; it narrows when the bridge dies, not before,
   because narrowing it means editing the instrument that measures the move.
*/
/* THE VOCABULARY THAT LEFT, READ BACK FOR THE RULES. The constants and helpers
   this file declared live with the subject that says them now; the rules still
   reach four of them under the names they always used, so they are published
   below from their homes and die with the publication. */
/* THE STORE, IMPORTED. The shell creates it and installs it before anything
   here is called; the engine reads the same object every module does. */
/* THE LADDER, THE PAGE SWITCH AND THE ADDRESSED PANELS, IMPORTED BACK. The
   handler that reads a Back, the verbs that write a navigation and the table
   that reopens an addressed panel are `app/`'s; the click delegation below
   still calls them by name. */
/* THE SETTINGS CATALOGUE, IMPORTED BACK. How a setting is identified,
   listed and read moved to the feature that owns settings when its panels did,
   and the engine reads the same answers rather than keeping its own —
   `app/icons.ts`'s arrangement and its reasoning word for word: one copy, read
   by both worlds, and the day this file goes the feature loses an importer
   rather than a subject. */
/* THE DÉCOUVRIR FEED, IMPORTED BACK. The reserve, the pile and the
   gesture that spends them are `features/acquisition/` now — the last feature
   surface this file still DREW. Its containers were already React's; what moved
   is who owns their content, and the technique is unchanged because a replaced
   node cannot animate. `render()` still calls these by name. */
/* TorrentMate — mobile-first redesign prototype
     Data: real library titles (1,861 items). */
/* THE VIEWPORT FALLBACK IS GONE (B-230), and it is deleted rather than
     corrected. It added a viewport meta carrying a maximum scale and a
     user-scalable refusal to any host that had none — the exact pair L03
     removed for WCAG 1.4.4, restored by a branch nobody reads. Dead on this
     host, which has one; live on any host that does not, which is what makes
     it a landmine rather than a defect: axe reports the violation when the
     directive is PRESENT on the served document, and it never was here.

     « A page that does not own its <head> » is not a case this prototype has:
     `index.html` IS the document and `serve.py` serves it. A fallback for a
     host nobody serves is machinery nobody can justify, which is D5's own
     shape, and `scripts/check-viewport-directives.py` now refuses the pair
     anywhere under `design/`. */
/* The 12 REAL follows, read from acquire.db with their true state: 4
     films waiting for a torrent, 8 series up to date (fractions cross-
     checked against library.db). The state is calm — it is the real one,
     and it is not dressed up. */
/* In the « réel » scenario: nothing to grab, nothing to resolve, nothing
     in flight — the four followed films are at the legitimate rest state «
     searched, found nothing ». */
/* Results of a REAL TMDB search for « star wars », cross-checked against
     the library: 3 already owned, 3 absent. 257 results found, 6 shown —
     which the interface must state. */
/* Only FILLED-IN suggestions are served: a card that opens a hollow sheet
     is a dead end, and the reserve honestly states how many it carries out
     of the 503 computed. */
/* Only suggestions whose sheet is COMPLETE (synopsis, genres, cast) are
     served: a card that opens a hollow sheet is a dead end. The reserve
     honestly states how many it carries. */
/* Categories are the REAL storage ones (categories.json5 → disk folders),
     with their counts read from library.db. « Animation » and «
     Documentaires » merge their film/series variants: storage is by nature,
     not by medium. The total is 1,861 and it adds up — a filter whose parts
     do not sum to the whole is a filter that lies. */
/* Two scenarios, and the resting one is the real one
     « réel » replays the exact state of the system: the staging area holds
     two folders only, and the 12 follows are at rest. That is what is
     needed to judge the rest states — which an always-busy prototype never
     shows.
     « charge » replays a dense state, to judge density and scrolling.
     The switch lives in the harness, not in the app. */
/* REAL contents of the staging directory. */
/* « Ça coince » holds TWO populations, and merging them would be the defect.
     A folder can be stuck because the scrape could not CHOOSE — that is a
     scrape decision, and its entry reason is a fact worth a chip — or because
     nothing in it can go through the pipeline at all, which no arbitration
     will ever fix. The first here carries a pending decision; the last two
     carry none, and say so by having no reason chip. */
/* ── Décisions de scrapage ────────────────────────────────────────────
     A decision is a FOLDER, never a medium — that is the whole reason it
     exists. The scrape could not name what is inside it, so what the operator
     is asked about is the thing on disk: `staging_path`. Everything else on
     these screens is a proposition.

     The vocabulary is the engine's, said in French rather than encoded:
     `below_threshold` is « aucun candidat n'atteignait le seuil »,
     `mid_band` « le meilleur candidat était en confiance moyenne »,
     `ambiguous` « plusieurs candidats trop proches pour trancher », and
     `manual` « envoyé à la main depuis la préparation ». A chip saying
     « zone grise » described a STATE nobody could act on; these describe the
     REASON it is here, which is actionable. */
/* Décisions RÉGLÉES — les dix vraies lignes de scrape_decision. */
/* Décisions EN ATTENTE.

     « Lucky » is a real ambiguity, arbitrated for good on 15 July; the only
     thing replayed here is its status, so the screen can be judged. Its five
     candidates, their scores and their posters are what TVDB actually
     returned that day — four of them at exactly the same score, which is the
     case this screen exists for.

     The second is the OTHER shape a decision takes, and it is just as real:
     two of the ten rows in the base came back with no candidate at all. It
     hangs on the dense scenario's folder, whose stated reason already says
     precisely that. */
/* ── LE PIPELINE ──────────────────────────────────────────────────────
     Read from `pipeline_run` in `library.db`: the last real run, its trigger,
     its duration, and what each of its NINE steps actually did.

     The steps are the engine's own, in its execution order, and each is named
     for what it DOES rather than for the command that runs it (DOIT-1). The
     engine's name is kept beside it in the mono face — it is what one needs
     when reading a log, and it is not the map.

     A step that did nothing says so with an em dash, never with « 0 ». Zero is
     a measurement; nothing to do is a state, and printing nine zeroes for a
     calm run turns a healthy pipeline into a wall of failures.

     `blockedCount` is what makes this page more than a report: the step that BLOCKS
     is the one the operator can act on, and it points at « Ça coince » just
     below rather than at a log. */
/* What really left the pipeline in the last 24 hours, read from the
     `dispatch` step of the two runs that fall inside it. « merged » and
     « moved » are two different events for the operator — an episode joining
     a series they already have is not a new title on a disk — so they are not
     flattened into one word. */
/* State */
/* THE SEED, and only the seed. This used to be `let state`, a module-level
     binding re-pointed at the store's object on every notification — a cached
     copy, correct only for as long as the subscriber that refreshed it kept
     up. Every read now goes through `currentState()` instead, so there is no
     copy to be stale: the store is the one place the state is.

     What that removes is a whole class rather than an instance. A rule could
     drive a page by mutating the cached object, and R77 had to hold that
     nobody did; with no cached object there is nothing to mutate. */
/* Rendering: building blocks */
/* The release candidate's card and the decision's card moved to the shell
     with the screen that draws them: `ReleaseCard` and `DecisionCard` in
     `src/screens/resolution.tsx`, at identical emission — `.card[data-nonmedia]`,
     no media sheet and no panel, because neither subject is a medium. Their
     rationale moved there with them; nothing here builds either shape any
     more, and a second builder kept alive next to the one being drawn is
     exactly the drift this file names below. */
/* ONE bottom panel, and its shape follows the facts it is given — and it is
     built in the shell now: `src/components/panel.tsx` is that single
     constructor, `src/components/sheet.tsx` the layer it draws into, and
     `panel.ouvrir` the verb a producer here calls, on a descriptor.

     The DESCRIPTOR crosses unchanged (facts, never markup: `title`, `meta`,
     `subtitle`, `poster`, `avatar`, `puce`, `blocs`, and the typed blocks
     `note` / `facts` / `actions` / `seasons` / `field`) — the vocabulary is
     declared with the component, and a view wanting something outside it is
     describing a fact the panel does not know about yet. The fix is still to
     add the fact.

     An ACTION's `target` remains a map of DATA ATTRIBUTES, never a handler:
     the click delegation below reads those attributes, exactly as it does for
     a card, and that is what keeps a panel opened by the shell answering to
     the engine's own acts. */
/* Active datasets, resolved by scenario. The rest of the code does not
     know which scenario is running — it reads these accessors. */
/* ── MAINTENANCE ──────────────────────────────────────────────────────
     Two levels and a panel, the shape the settings already use: the rubrics,
     a rubric's commands, then the command itself in the bottom panel.

     The panel is where the one decision of this page lives. A command that
     DELETES opens with « à blanc » on, and it cannot be turned off until the
     panel has NAMED what would be destroyed. That is not a confirmation
     dialog with another name: a dialog asks « are you sure », which one
     answers without reading, while this asks the operator to look at a list.
     A real deletion cannot be rehearsed on this machine — staging writes to
     the real disks — so what the interface owes is the look before, not a
     safety net after. */
/* One command's panel. Derived from what is TRUE about the command — does
     it delete, can it run blank, is it long — never from a list of screens. */
/* ── RÉGLAGES ────────────────────────────────────────────────────────
     The configuration, and the one decision that shapes everything else:
     ONE NAVIGATES BY WHAT ONE WANTS TO CHANGE, NEVER BY FILE.

     The engine keeps 19 JSON5 files and the shipped editor put them in a
     dropdown. That asks the operator to know that « thresholds.json5 » holds
     how much free space is needed before an ingest — which is knowledge about
     the code, not about the media library. The files are not hidden: each
     setting says which one it lives in, in the mono face, because that is what
     one needs when reading a diff or a log. They are simply not the map.

     Three levels, and the third is the panel this interface already has:
       · the rubrics — what one might want to change;
       · a rubric's settings — one row each, label left, value right;
       · one setting — the bottom panel, with its control and its explanation.

     The explanation is not written here. It is the comment the operator wrote
     above the key in the file itself, which until now nobody could read
     without opening the file. */
/* THE SETTINGS SCREEN'S WORKING STATE IS NOT THIS FILE'S ANY MORE: it is
     `features/settings/state.ts`'s, and its reset is the harness driver's. The
     rules still read `SETTINGS_STATE` and `settingId` under those names, so
     they are published below from their homes. */
/* One setting, in the panel — the same panel as everywhere else, taking the
     same descriptor of facts. What it says: where the value comes from, what
     the file's own comment explains, and what it is now. */
/* THE FLOATING ACTION BUTTON IS NOT THIS FILE'S ANY MORE.
     It was static markup this engine showed and hid, from two flags kept in
     step by hand — a page's own answer and whether a message was on screen.
     Both are store state now and the button reads them itself
     (`app/action-button.tsx`), which is the whole of what « one decision point »
     asked for: written in two places, the second writer erases the first. */
/* Loading
     Two regimes, and the difference is not ergonomic — it is ethical.

     · LIBRARY   → infinite scroll. The source is `library.db`, locally: one
     more page costs neither provider quota nor external network. Scrolling
     is the phone's natural gesture, so it is served. The shown/total count
     stays visible so one always knows where one stands within 1,861 items.

     · DÉCOUVRIR → explicit batches. Each batch costs TMDB calls. Infinite
     scroll would turn a distracted thumb into a burst against a dependency.
     The next batch is asked for.

     In both cases a loading failure SAYS SO and offers a retry: a list that
     stops in silence reads as « there is nothing left », which is a lie. */
/* Release candidates — INVENTED, and the only invented data in this
     prototype: no tracker is queried here. The vocabulary (source,
     resolution, language, seeders) is the real ranking's. */
/* The REAL profile, as defined in acquire/desired.py
     `QualityProfile` has only FOUR fields, and that is everything a follow
     can set. Anything else (accepted sources, CAM/TS exclusions) does not
     exist per follow.

     What is global and lives in `ranking.json5` (already editable under
     /config ?tab=classement): the ranking WEIGHTS — resolution, codec,
     container, audio, language, source, seeders, size, provider. A follow
     does not redefine them; it only sets FLOORS and requirements.

     A distinction never to lose: the profile FILTERS (it eliminates), the
     ranking ORDERS (it separates what remains). */
/* EVERY SORT GOES BOTH WAYS, and each way has its own NAME rather than an
     arrow bolted onto a shared one: « Ajout récent » reversed is « Ajout
     ancien », which is what one would say out loud, and « Les plus incomplets »
     reversed is « Les plus complets », not « incomplets, à l'envers ».

     The panel lists the six, and the one in force is marked. The alternative —
     tapping the sort one has already chosen to flip it — costs half the rows
     and is invisible: nothing on a phone says that a second tap on the row one
     just chose does something else. A row that reads « A → Z » and answers
     Z → A is the opposite of showing what the machine will do. */
/* The name of the sort in force, which is what the control on the count line
     reads. `sortReversed` is a store field like any other and, like `sortKey`, it
     stays OUT of the address: the sort is a preference, not a place (A7). */
/* THE PAGE'S OWN DERIVATION, and it stays HERE while the drawing leaves.
     WHAT LEFT AT L09. `sortLibrary` and `libFiltered` answered « which media,
     in which order » over this fixture; the layer answers it now, and it
     answers it where the paging is — a page of an unsorted set, sorted
     afterwards, is a page of the wrong rows. `libraryLoaded` went with them:
     how many titles the source holds is a field of the listing's own answer. */
/* Deleting from the poster view
     The problem: offer deletion inside a poster grid without spoiling the
     grid. Two paths, neither costing a pixel at rest:

     · LONG-PRESS on a poster → the same action sheet as everywhere else
     (Voir la fiche · Supprimer). Fast, but invisible.
     · « Sélectionner » in the count line — which already exists — switches
     the grid into selection mode: checkboxes on posters, action bar at the
     bottom, and deletion becomes MULTIPLE. That is what makes long-press
     discoverable, and the only path that allows real housekeeping.

     A simple tap still opens the sheet: the most frequent path is never
     sacrificed to a rare action. */
/* WHICH PANEL AN ELEMENT ADDRESSES, AND WHAT OPENING IT MEANS, ARE THE
     FRAME'S — `app/frame-verbs.ts` answers `data-panel` and fills the door this
     file's press reads. Only the press stays here, and it goes with the
     gesture. */
/* THE LONG PRESS — arbitrated in `lib/press-arbitration.ts`.

     The arbitration MOVED to that module: the timer, the 12px tolerance, the
     pointer listeners, the click swallowed by its POINT and the refusal of the
     browser's own menu are vocabulary, and vocabulary is not the engine's
     (invariant 10). What stays here is what only this surface knows — WHICH
     element a press addresses, and what opening it means. That is the whole of
     the two callbacks below.

     Nothing was added to the engine to do it: the block left and an import
     took its place, which is the only shape D5 allows. Its behaviour is
     unchanged and R55 proves that against a real thumb, before the move and
     after it. */
/* User menu.
     One entry today — signing out — and the shape that will hold the rest: this
     interface is single-user for now, and a multi-user one with per-user rights
     is what the profile entry will open onto. The entry is drawn disabled and
     says why, rather than being absent: a menu that grows an item later teaches
     its shape twice. */
/* Découvrir: one card, one tappable body
     · poster            → the media sheet, never a dead link
     · rest of the card   → bottom panel, same grammar as Suivis
     · swipe left OR right → dismissed, with « Annuler » in the toast
     The verb follows the nature: one FOLLOWS a series, one ADDS a film. */
/* THE DÉCOUVRIR FEED HAS LEFT — the reserve, the three card shapes, the
     pile and the gesture that spends them are
     `features/acquisition/discover-feed.ts` and `discover-cards.ts` now, and
     this file imports them back. Its own `resize` listener went with
     `mountDeck`: two listeners on one window would measure the deck twice. */
/* A search result is not one of your media yet, so it has a panel of its own
     rather than a follow's: what it offers is the act that WOULD make it one,
     and the sheet to judge it by. This panel is the ONLY place that carries
     the act — the card wears no inline button, so the row stays the size of
  /* Typing filters as you go (the source is LOCAL, therefore free) — unlike
     the provider search on the add screen, which runs on submit. */
/* Interactions */
/* WHETHER A MESSAGE IS ON SCREEN IS WRITTEN IN ONE PLACE. Six call sites
     flipped the class and the attribute by hand — across two functions and a
     handler bound beside them — which was already two ends kept in step by
     hand. The moment a THIRD end appeared (the action button, which must not
     sit under the message's close target) all of them would have had to move
     together or the interface would half-work in a way no single one reveals.

     THERE WAS A SEVENTH, and counting six is how it was missed: the boot hint
     is also dismissed from a capture-phase `pointerdown`, which wrote the class
     alone and left the state saying a message was up. It goes through here now,
     and R86 drives that path. */
/* THE MESSAGE IS NOT DRAWN HERE ANY MORE. `setMessageShown` toggled a class
     and an attribute on static markup, and `toast`/`toastUndo` wrote
     `#toastmsg` — one of them with `innerHTML`, to inject an undo control as a
     string. The layer is `ui/toast.tsx` and its verbs are
     `app/toast-host.ts`'s, behind a DESCRIPTOR: what happened, and what undoes
     it. `app/panel-host.ts` is the precedent — facts cross, markup is the
     component's.

     THE THIRTY-FOUR CALLERS BELOW KEEP SAYING `toast(…)` and `toastUndo(…)`,
     because they are PRODUCERS and a producer moves to its feature at L19.
     These two lines die with them. */
/* A page restored the way a named state starts: the layers hidden without
     touching history, the store written, the port back at the top when the
     patch names a new place, and the page drawn. The ladder's handler restores
     a page through it, and the harness drives its named states through it. */
/* Kept as a VERB the driver can still say: `touch.py`, `drag.py` and
     `machine.py` call `closeSheet()` from inside the page, and moving a layer
     to the shell must not take away the vocabulary that drives it. The layer
     state, the per-layer guard and the unwind all live in
     `panel.fermer` now — this is one line pointing there, not a
     second implementation. */
/* THE ENTRY IS NOT THIS FILE'S ANY MORE — the splash, the sign-in gate and
     the install proposal are `app/entry.ts`'s (`MODEL.md` § 2 Part 9). It was
     LOGIC over static markup, and it is the logic that had to move: §17
     redraws the gate for Plex SSO and cannot do so while the gate is engine
     code, because D5 allows no addition here.

     The MARKUP stays in `index.html`, for two reasons that are not the same
     one: the splash is on screen from the first painted frame, which a
     component cannot be; and the gate is EXTRACTED by `serve.py` and served as
     the design host's own password page, so a component would leave that host
     a second copy to keep in step.

     What is left below is the vocabulary the drivers still say, one line each,
     pointing at the seam. They go with the boot handshake at L13. */
/* THE DRIVEN FLAG CROSSES AS AN ARGUMENT. `__go` drives a named state
     without touching history (R74 holds it), and `walk.driven` is how the page
     switch knows. It used to be read from INSIDE `showSignIn`, which is a
     private flag read by a function that is no longer here — so it is passed.
     Left out, driving the `signin` state replaced the address with `/login`
     and every state measured after it inherited that route: caught by the
     oracle as a divergence in `relay-refused`, eighty states later, which is
     what a leaked address looks like from the outside. */
/* THE DRAWER IS NOT DRAWN HERE ANY MORE. It was an empty `<aside>` this
     engine filled on every open — the brand, the three titled groups from a
     table of its own, the appearance control and the served identity. It is
     `app/drawer.tsx` now, over `ui/drawer.tsx`, reading the ONE navigation
     table; and it REGISTERS with the ladder rather than being found by it, so
     the ladder's handler asks a registration instead of testing a class.

     The verbs are verbs, and they are NOT this file's any more: opening the
     drawer and closing it belong to the frame that answers the taps
     (`app/frame-verbs.ts`, `app/layers.ts`). */
/* THE APPEARANCE IS NOT THIS FILE'S ANY MORE. The three states, the stored
     choice, the live media listener and the attribute they write are
     `app/appearance.ts`'s — the frame's entry (`MODEL.md` § 2 Part 9), because
     §17 redraws the sign-in gate beside them and cannot do so while the entry
     is engine code. The drawer offers the control and calls that module
     directly; the `data-apparence` branch of the delegation went with it, and
     with it the last French `data-*` name this file wrote. */
/* The media sheet moved to the shell with the rest of the screens:
     `src/screens/media.tsx` renders it as the route `/mediasheet/$title`. The
     verb a call site says is `screens.mediaSheet(title)`; the template,
     the seasons and the actions live there, at identical markup — the
     click delegation below still reads their data attributes. */
/* Journey sheet
     A journey has no hole. A step not reached is stated « à venir », never
     « pas faite »; a step without a date is stated « inconnue », never
     given an invented date. */
/* Gestures — pointer events, so one path serves finger, mouse and pen.
     Two differences a touch-only implementation never meets:
     · a touch is captured implicitly by the element that received the start; a
       mouse is not, so the END of a drag is listened for on the window — a
       release outside the frame would otherwise never arrive;
     · dragging a picture is a browser default that swallows the pointer stream
       outright, which is why images inside a draggable surface disable it. */
/* WHERE A GESTURE LISTENS, and it is not a matter of taste.

     A gesture that belongs to the SCROLLPORT — the pull to refresh — listens
     on the scrollport, because that is the thing it acts on. Every other
     gesture belongs to an OBJECT: a row, a suggestion, a deck card. Objects
     are drawn in layers ABOVE the scrollport too — the sheet, the screen, the
     drawer — so an object gesture listens on the FRAME. Bound to the
     scrollport it answers only where the object happens to be drawn today, and
     four states already drew a poster no press could reach.

     The guard is the same in every one of them: `closest(...)` decides whether
     the press concerns this gesture, so listening wider costs nothing and
     stops a surface from silently losing its gesture the day it moves. */
/* THE THREE CARD GESTURES ARE GONE FROM HERE.

     The SWIPE's shape — the axis decision, the two drawers' travel, where a
     released row rests, and the click a drag must not let through — is
     vocabulary, and vocabulary is not the engine's (invariant 10):
     `lib/swipe-arbitration.ts`. What a suggestion's swipe and a deck card's
     swipe MEAN is Découvrir's, so both went to the feature that draws them
     (`features/acquisition/card-gestures.ts`), where `dismissSug`, `passerSug`
     and `advanceDeck` already live.

     Nothing took their place here: the boot installs them on the same frame
     element this file listened on, BEFORE the tap registry, because the swipe's
     guard now says `stopImmediatePropagation` and only a listener registered
     first can stop the registry beside it. */
/* THE PULL IS GONE FROM HERE TOO, both halves of it.

     The GESTURE was already `lib/pull-gesture.ts`'s. What stayed was the
     indicator — its height under the finger, its spinner, the message a
     finished refresh says — and that is the FRAME's affordance, so it went to
     `app/pull-indicator.ts` with the reset the harness drives through
     (`window.__reposPTR`, published from there now).

     The reset no longer writes `className = "ptr"`: it removes the two state
     classes it added. That one assignment erased every utility the markup
     paints on the indicator, which is why its states had to be read on the
     spinner inside it (ruling 59). */
/* 4) Sheet: dragging the handle to close moved to the shell with the layer
     itself — `src/components/sheet.tsx` owns the handle, the pointer capture
     and the dismissal threshold. Nothing binds here anymore: `#sheetgrab` does
     not exist when this script runs. */
/* ── what the scenario table needs, exported by name ────────────────────────

   The harness module (`src/harness/`) holds the named states and their
   driver, and they call back into it. They could have gone through the `window` surface below
   like the harness does — but the table is SOURCE, not a probe typed into a
   browser, and a source file that reaches its neighbour through a global says
   nothing about what it actually depends on. The names are listed, so the
   dependency is readable and a deletion breaks the build instead of a run. */
/* ── the published surface ───────────────────────────────────────────────────

   Two lists, and the split is measured rather than chosen: a binding the
   engine REASSIGNS cannot be published by value, because the copy taken here
   would keep pointing at the object that was current when this line ran.
   `state` and `world` are both reassigned, and both are what the harness
   reads most — published by value they would answer a stale world, silently,
   and every rule reading them would measure a page that no longer exists.

   The rest never change identity (a `const` cannot, and no `function` here is
   reassigned — checked, not assumed), so a plain value is exactly as live as
   a getter and reads better.

   230 by value, 24 by getter, 254 in all — and BOTH numbers were wrong once,
   for the same reason twice: a pattern that answers a question narrower than
   the one being asked.

   The first count said 253, because the regex collecting the names knew
   `function`, `const`, `let`, `var` and `class`, and `signOut` is an
   `async function`. No state's markup depends on logging out, so a
   state-by-state comparison of the whole frame said « identical » while the
   rule suite said `ReferenceError`.

   The first SPLIT put `unwindInProgress` on the by-value side, because the
   test for « does the engine rebind this » looked for `name =` — and this one
   is only ever written `unwindInProgress += 1` and `-= 1`. Published by
   value it would have answered 0 forever, which is the same class of silent
   lie the getters exist to prevent, arrived at from the other direction. The
   forms that rebind without a bare `=` are compound assignment, `++`/`--`,
   destructuring on either side, and `for (name of …)`; all four were searched
   across all 254 names, and this is the only one. */
// The rules' names for three moved helpers, published from their homes.
// Read live, because the engine reassigns each of these.
