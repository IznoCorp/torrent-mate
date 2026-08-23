# Phase 11 — The navigation path: Back pops deliberate arrivals, the parent is the floor

**Authority**: `docs/reference/product-intent.md` § 16 « Le chemin de navigation (règle gravée) »
and `docs/reference/frontend-architecture.md` D1b — both in PR #485 (`docs/steward-adjustment-7`)
at the time of writing; read them THERE (`git show origin/docs/steward-adjustment-7:<path>`) until
it merges. D1b assigns rules 1 to 3 to this wave, because it owns the address model while it is
open. Rule 4 (Up, a drawn gesture) is NOT this wave's: nothing here implements it.

**What it reverses.** D-8.1 (phase 8) resolved every screen address to the HOME page underneath.
§ 16 rule 3 puts the REAL PARENT there, rendered. D-8.1 is struck in `phase-08-pr-fixes-cycle-1.md`
by this phase, naming § 16.

**What it does NOT simplify, measured before this phase opened.** The parent being right does not
remove 9.3: a panel's entry composed over the parent (`/media?panel=…`) still stops the router
matching `/media/$provider/$id` and unmounts the sheet. The panel hangs off the screen's own path
whatever page sits beneath. 9.3 stays as landed.

The running directives of phase 8 (« How this phase runs ») apply: reproduce, fix, hold,
mutation; build+copy WITH the `rm -rf`; every `legacy.js`/`.md` edit through a Python write;
`ruff check` only on harness/scripts; English; no phase/session/bug/wave id in a source comment.

## The model, decided

**The hierarchy.** `/acquisition` is the root. Every top-level page sits on it. Every screen sits
on the page it is opened FROM — read off the emitter of its opener, not guessed:

| Screen                 | Parent page | Why                                                   |
| ---------------------- | ----------- | ----------------------------------------------------- |
| `/media/$provider/$id` | `lib`       | the sheet is the library's object (§ 16 names it)     |
| `/resolution/$folder`  | `arr`       | a resolution is an arrival's (§ 16 names it)          |
| `/releases/$title`     | `acq`       | opened from the follow panel on the acquisition page  |
| `/quality/$name`       | `acq`       | `data-profile` is emitted inside the releases surface |
| `/add`                 | `acq`       | the add screen is the acquisition page's own verb     |

`SCREEN_PATHS` becomes `SCREEN_PARENTS: Readonly<Record<string, string>>` (path → page id);
`destinationOf` resolves a screen address to `{ page: parent }`; the boundaries arm holds the
table's keys against the routes exactly as it held the list. The sign-in screen keeps `HOME_PAGE`.

**The stack, by construction.** Under any top-level page the stack is `[guard, /acquisition]`;
under a non-home page `[guard, /acquisition, /page]`; under a screen its parent's stack plus
the screen's entry; a panel's layer entry on top of whatever it opened over. Exactly these
shapes, and a hold counts them (rule (e) below).

**The verbs.** Opening a surface — a screen (the router's `go()`), a panel (`pushLayer`) —
PUSHES. A setting — `acqTab`, `libLens`/`libMode`/`libCat`, `maintTopic`, the settings search
— REPLACES (`__bridge.replace(navigationState(), compose)`, which the layer sites already use).
Switching a top-level page: from `/acquisition` to another page PUSHES (the floor stays
beneath); from a non-home page to another non-home page REPLACES the top; to `/acquisition`
from any other page goes BACK one entry (the floor is already there — pushing or replacing would
leave two acquisition entries, and a silent Back). The exit guard's own re-push stays.

**The cold link.** The boot synthesises the stack from the hierarchy: replace the guard onto the
opening entry, record `/acquisition`, record the parent page when it is not `/acquisition`,
then — for a screen — re-record the screen's own address on top (the router renders by URL, so
the screen is drawn from the address the document opened at; the intermediate pushes happen
before the first paint and under `pilotage`). The parent page is RENDERED beneath the screen:
`state.page` is the parent, and closing the screen reveals a page already in place. A cold
not-found address keeps `[guard, /typo]`; a cold `/login` keeps `[guard, /acquisition]` plus the
gate. A cold `?panel=` reopens on top as today (9.3, 9.4, 10.1 unchanged).

## 11.1 — The parent under a screen, and the floor under a page

`lib/addresses.ts`: `SCREEN_PARENTS`; `destinationOf` → `{ page: parent }`; `isScreenPath` reads
the keys; `scripts/check-frontend-boundaries.py` holds the keys against the routes and each
value against `PAGE_PATHS` (a parent that is not a page is a violation); the pytest cases adapt.
The engine boot synthesises the stack (the model above). R69: hold 9's five cold entries assert
the PARENT page beneath (derived from the model, as the screens list already is), and the Retour
walk asserts the page revealed is the parent and the address is the parent's own path; R75
(h)/(l)/(n): a Retour from a cold sheet lands on `/media`, from a cold resolution on
`/arrivals`, from cold releases on `/acquisition` — page rendered, screen gone, `armedExit`
NOT set (the guard is two entries down). A cold `/media`: Back → `/acquisition`, page `acq`,
rendered. Mutation: resolve screens to HOME again → R69's parent holds fall; drop the floor
synthesis → the cold `/media` Back hold falls (it reaches the guard).

## 11.2 — Settings replace; page switches stack nothing

`legacy.js`: a `replacePath()` beside `recordPath()` (same catch convention: log and raise the
flag); the six setting sites (`11684` settings search, `11814` acqTab, `11826` lens/libCount,
`12076` maintTopic, and the two `else recordPath()` in the layer-aware sites when they are a
setting) call it; the three page-switch sites (`11766` `data-page`, the `data-go` at `11803`,
the drawer's at `12123`) call a `switchPage(page)` that implements the verbs above (push from
home, replace elsewhere, back to home). `hideLayers()` before a switch stays. `navigationState()`
unchanged. Holds in R69 — each SEPARATE, each reading `history.length` deltas and `armedExit`,
never only the address: (a) in-app walk: `/media?lens=inc` → open the sheet (tap a poster or
`window.__screens.mediaSheet(title)`) → Back → `/media?lens=inc`, page `lib`, lens `inc` — the
real origin with its setting; and from the add screen's search back to `/add?q=…`; (c) page
switches: acq → lib → sys → arr: `history.length` grows by exactly 1 over the walk, Back from
`arr` lands on `/acquisition` with page `acq` rendered, `armedExit` falsy; the same from `lib`
and `sys`; switching back to acq from lib leaves `[guard, acq]` (a Back then arms the guard);
(d) the guard arms ONLY on `/acquisition`: Back from `/media` does not arm it, Back from
`/acquisition` does; (e) settings leave NO entry: tap a lens, an acqTab, a maintenance topic —
`history.length` unchanged and one Back leaves the page (lands on `/acquisition`), never undoes
the setting. Mutations: one site back to `recordPath()` → (e) falls naming the delta; page
switch pushing again → (c) falls on the length; the floor not kept → (d)/(c) fall.

## 11.3 — What the rest of the suite says

R59 `back.py`, R74 `bridge.py` (history primitives count in the design sources — it will move:
name the movement), `navigation.py`, `screens.py`, `panel.py` (the tab-bar walk of 10.1 now
leaves `[guard, acq, page]`; its holds adapt: after the tap the panel's entry is replaced, not
buried — re-measure and hold what IS), `screen_addresses.py`, `logout.py` — every rule green at
understood hold counts; every movement named in the commit body. The oracle: `__go`-driven
states do not walk history, but a screen state may now render its parent beneath — run
`make maquette-oracle`; a divergence is reviewed and accepted with its reason, never waved.
`phase-08-pr-fixes-cycle-1.md`: D-8.1 struck, naming § 16 and this phase.

## Ignored, with reason

- Rule 4 (Up): a surface, drawn first, no lot carries it — not this wave (D1b).
- Per-page stacks: § 16's explicit choice — not built.
- The stale `panelDescriptor.title` after a close (10.1 noted it): pre-existing, harmless.
