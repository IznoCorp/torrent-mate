# L05 — Routing

**codename**: maquette-l05
**commit_type**: refactor
**bump**: bugfix (0.98.23 → 0.98.24)
**lot**: `docs/reference/frontend-architecture.md` § « L05 — Routing », Phase 1
**depends on**: L01 `LANDED`, L04 `LANDED` — runs alone (§ « Running two lots at once »)

**Constitution sections this wave serves**: §8 (« toute vue de détail est adressable par URL »),
§11 and DOIT-11 (the media sheet reachable by a stable link, `/media/:provider/:id`), DOIT-10
(« Chaque détail a son URL ; Retour ferme ce qu'il doit fermer »), §13 (an interface that never
displays something the data cannot justify — the reason an index is not an address), §15 (the
maquette is modified first, and it is the product).

---

## 1. What this wave delivers

D1 in force. Every page and every screen sits on a real path; the query carries how a surface is
being looked at, never which surface it is; layers are ranked in the three tiers D1 declares, and
the ranking is applied rather than merely written down.

Three consequences the lot's entry names, and they are the reason it is not deferred:

1. **Navigation leaves the engine.** This is the first subtraction of D5, performed on the
   cross-cutting part the plan says does not strangle surface by surface.
2. **The harness becomes able to drive by URL** instead of through `window.__go`, which is what
   detaches it from the 254 republished globals and makes L13 finishable.
3. **The oracle can outlive the engine.** An oracle that drives through a seam dies with the seam.

## 2. Decisions, and who took them

All eleven were arbitrated by the operator on 2026-08-22 during the brainstorm, except D-L05-9
which the operator explicitly delegated. Each records what it replaces.

### D-L05-1 — The address vocabulary is production's, and `/` redirects

`/acquisition`, `/media`, `/arrivals`, `/system`, `/maintenance`, `/settings`, `/account`; `/`
answers a `replace` redirect onto `/acquisition`, exactly as the shipped app does
(`frontend/src/router.tsx:51` — `{ index: true, element: <LegacyRedirect to="/acquisition" /> }`).

**Why English.** A route path is a NAME, not a datum — the operator's ruling of #456 — and the
shipped app's own table is already English, with the French addresses answered by redirects. The
maquette becomes production; adopting a second vocabulary would mean renaming everything twice.

**What it costs, and it is accepted.** The opening address is rewritten at boot. That is the zone
where R69 has already paid two defects (the boot's `replaceState`, then the guard entry pushed
straight after it putting the wrong address back), so the redirect is `replace` and never `push`,
and a hold measures the history depth after a cold boot.

### D-L05-2 — The media sheet takes the address the constitution names

`/media/:provider/:id`, replacing `/fiche/$titre`.

**Why.** DOIT-11 writes that address literally, and `media-screen.tsx:397` already *displays*
`/media/tvdb/<id>` in the screen bar while serving a title-keyed route — the interface showing a
stable link it does not honour. The shipped app serves `/media/:provider/:providerId` today.

**The unidentified case is not a gap**, it is §11's single exception: a media with no provider id
has no sheet and must lead to resolution. The route cannot address it, and that is the wanted
behaviour rather than a limitation to work around.

**What it needs.** A title → ids lookup: the ids exist in the fixture (`sheet.ids.tvdb` /
`.tmdb`), and the reverse direction is what the route resolves.

### D-L05-3 — The two remaining French routes become English

`/resolution/$dossier` → `/resolution/:folder`, `/releases/$titre` → `/releases/:title`.
Same ruling as D-L05-1: a route parameter is a name.

### D-L05-4 — The quality profile is renamed, because two things were called « profile »

`/profile/$title` → `/quality/:name`. `/account` is the operator's profile; `/profile/$title` was
the QUALITY profile (« 1080p Multi »). One word answering for two subjects is how a reader learns
to distrust a name.

### D-L05-5 — The panel is the only layer that gets an address, and only four of its producers

The panel takes `?panel=<kind>:<subject>`; the navigation drawer stays transient — Back closes it,
no URL.

**Why the drawer is not addressed.** D1's tier table names « an actions panel, a filter drawer » at
tier 2, and this maquette's drawer is neither: it is the navigation menu. A shareable address that
opens a navigation menu, and a reload that reopens one nobody asked for, are what tier 3 exists to
describe (« a sort menu, a confirmation »).

### D-L05-6 — `/login` is taken now rather than left to L13

The sign-in screen is a screen, D1 says every screen has a real path, and `serve.py` already serves
`/login`. L13 keeps the splash, the document-level delegation, the boot handshake and the
republished `window` surface.

### D-L05-7 — `openScreen()` goes with the navigation it belonged to

It has zero callers — every screen migrated to a route — and it is navigation machinery, so it
leaves with the rest of what this lot subtracts from the engine (D5). Machinery nobody can justify
is machinery nobody dares delete; the moment it loses its subject is the moment to remove it.

### D-L05-8 — CLAUDE.md's stale sentence is corrected in this wave's pull request

§ Language states that « `/deconnexion` on the design host is still French ». It is not:
`serve.py:753` serves `/logout` and `serve.py:757` `/login`, and `harness/logout.py` holds them —
which is why that rule sits in the `--contracts` tier. A sentence that lost its subject is
corrected in the move that notices it.

### D-L05-9 — An index is not an address (delegated to the implementer, decided here)

Of the engine's eight distinct panel producers, four carry a stable, nameable subject and four do
not:

| Producer | Subject | Tier |
| --- | --- | --- |
| `openFollowSheet(title)` (and its alias `openDetailSheet`) | a title | 2 — `?panel=follow:<title>` |
| `openJourneySheet(title)` | a title | 2 — `?panel=journey:<title>` |
| `openSetting(id)` | a setting id | 2 — `?panel=setting:<id>` |
| `openActionMaintenance(id)` | a command id | 2 — `?panel=action:<id>` |
| `openUserSheet()` | none — a menu | 3 |
| `openMoreSheet()` | none — a menu | 3 |
| `openSugSheet(index)` | a POSITION in `SUGGESTIONS` | 3 |
| `openAddSheet(index)` | a POSITION in `SEARCH.results` | 3 |

**The reasoning, because the delegation makes it mine to defend.** An address that carries a
position designates something else once the list has moved — the interface then reopens a panel
about a media the operator never asked for, which is §13's « aucun état affiché n'est une
constante » read from its other end. Addressing those two by title instead is available and is
deliberately refused here: the same title can appear in the suggestions and in the add results, so
choosing which panel opens is a behaviour decision, and it belongs to L09 where the real data
arrives. A menu is tier 3 by D1's own example.

### D-L05-10 — The harness's ground moves from `/wrapped.html` to `/`

`harness/common.py` pins `http://127.0.0.1:8899/wrapped.html`, served by a plain `http.server`
that answers a file for a file's own path and 404 for everything else. Under D1 that pathname
matches no route, so the router would render the not-found page and **every** measurement would
collapse — the oracle's 83 × 33 included. The host becomes `harness/server.py`, which already
folds any unresolved address onto the document, and the three instruments read `/`.

This is a hard dependency, not a convenience: it is step one of the plan.

### D-L05-11 — R69 is renegotiated, not deleted

Its text justifies the query by the impossibility of path routing from `file://` and from a static
host. D1 accepts that cost explicitly and names the lost use (opening the file by double-click).
R69 keeps its five holds, gains a sixth, and its reason in `regions.json` is rewritten naming D1 as
what replaces it — never quietly edited to pretend it always said this.

## 3. The address table

| Address | Carries | State in the query |
| --- | --- | --- |
| `/` | `replace` redirect → `/acquisition` | — |
| `/acquisition` | Acquisition | `tab` (default `now`) |
| `/media` | Médiathèque | `lens` `mode` `cat` (defaults `cat` `grid` `all`) |
| `/arrivals` | Arrivées | — |
| `/system` | Système | — |
| `/maintenance` | Maintenance | `topic` (today `rub`) |
| `/settings` | Réglages | — |
| `/account` | Profil et préférences | — |
| `/login` | The sign-in screen | — |
| `/media/:provider/:id` | The media sheet | — |
| `/resolution/:folder` | The arbitration screen | — |
| `/releases/:title` | The release-choice screen | — |
| `/quality/:name` | The quality profile | — |
| `/add` | The add screen (unchanged) | `q` `mode` |
| anything else | the 404 page | address left exactly as typed |

Every page may additionally carry `panel` (D-L05-9). `/media` and `/media/:provider/:id` do not
compete: they are two routes.

**Only what DIFFERS from the opening state is written** — R69's hold 1, kept as it is. A dial at
its default is absent from the address.

**The three renames** (`$titre` → `:title`, `$dossier` → `:folder`, `rub` → `topic`) go through
`scripts/rename-identifiers.py`. The tool is not the proof: the diff is re-read line by line and
the rule suite re-run, because two corruptions in this repository were found by reading the diff
after the tool reported success.

## 4. Mechanism

**The engine stops fabricating addresses.** `recordPath()` calls a shell seam that turns
*(page, dials, panel)* into `go({ to, search })` — the one function R76 already holds to a single
call site. `urlFromState()`, `stateFromUrl()` and `URL_DEFAULTS` leave `legacy.js`.
`navigationState()` and `onEngineBack()` stay: unwinding layers is logic, not addressing.

**The router stays the single writer of the URL and the history.** Nothing about that changes —
what changes is that the pages now go through it too, as the five screens already do.

**The page host keeps portalling into `#view`.** A page route's component stays `null`; the route
match writes `state.page` into the store and `render()` draws as it always has. Converting pages
into route components is L07/L09's business — it changes who DRAWS, and this wave changes only who
ADDRESSES.

**Boot order is unchanged.** The shell creates the store and the real bridge first, then calls
`window.__startEngine`. The engine's `base` computation (`shell.tsx:561`) loses its purpose once
every pathname is router territory, and goes with the address derivation.

## 5. The rules that bite

Every one lands mutation-tested: break the behaviour on purpose, confirm the rule falls **and
names the right defect**, restore.

| Guard | Where | What falls when it is broken |
| --- | --- | --- |
| R69, renegotiated | `harness/url_state.py` | the six holds of § 6 below |
| addressing (9th arm) | `scripts/check-frontend-boundaries.py` | a page id declared as a query param, or a dial declared in a path — offline, in `make check` |
| R75 extended | `harness/screen_addresses.py` | the renamed screen addresses, cold, at depth |
| R76 | `harness/navigation.py` | more than one `navigate()` call site |
| R59 / R71 / R74 | `back.py` `screens.py` `bridge.py` | the back journey, the screen stack, the bridge — at UNCHANGED rule code, which is the point |

The 9th arm **extends the existing guard rather than sitting beside it** — L02's lesson, paid for
once already.

## 6. Done when

The lot's contract, line by line, plus what this design adds.

1. **No page identity survives in a query and no state in a path, both checked** — the 9th arm
   offline, R69 at runtime.
2. **A deep address lands on its state cold** — every page and every screen, from a fresh
   navigation, not from inside an already-loaded document.
3. **Back and Forward behave on every tier** — a page, an addressed panel, a transient layer.
4. **R69 is renegotiated with its reason recorded** — in `regions.json` and in the rule's own
   docstring, naming D1 as what replaces its premise.
5. **The oracle is green** — 83 states × 33 regions, 0 divergence, or each divergence accepted with
   a written reason. This wave moves navigation, so a divergence is justified one by one, never in
   a block.
6. The full rule suite is green **at unchanged hold counts**
   (`scripts/harness-hold-counts.py --compare`) — except where a rule deliberately gains holds,
   which is recorded.
7. `make lint`, `make test` (no failure and **no error**), `make check`.
8. The « In flight » row of `IMPLEMENTATION.md` § « Where the frontend work stands » is written
   **when the pull request opens**, not after the merge.

## 7. Risks, each with what answers it

| Risk | Answer |
| --- | --- |
| The boot rewrite (D-L05-1) reintroduces R69's two historical defects | the redirect is `replace`; a hold measures history depth after a cold boot, and the guard entry's own shape is unchanged |
| 31 files name `wrapped.html`; missing one leaves it measuring a 404 page | the host swap is step one and the whole suite runs immediately after it, before any behaviour changes |
| A rename corrupts silently | `rename-identifiers.py`, then the diff re-read by hand, then the suite — the tool's read-back is skipped for `--values` and for Python |
| The oracle goes red for a real reason and is waved through | divergences are accepted one by one with reasons; a block acceptance is refused |
| The suite is green while holding LESS | `--compare` on the hold counts is part of the gate, not a courtesy |

## 8. Out of scope, named so absence is not read as arbitration

The 116 `__go(` call sites across 32 rule files (intact — converting them is a second kind of
change, and L02 paid to learn that); the backend (the interface is not frozen); bundle splitting
(L12); the 42 contrast findings and the 13 px search field (L06); B-036 and B-040; the harness's
53 flat `.py` files (recorded and deliberately unscheduled).
