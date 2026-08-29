# L10-ter — the survey: what the dying engine still draws, and what the shell is

**Measured on `main` at `faee1192`, 2026-08-29.** Every figure below carries the command that
produces it; re-run the command rather than trust the figure. The brief this survey answers cited
« twelve `innerHTML` writes, two identified, ten not » — the count below is different, and the
difference is § 1.1.

---

## 1. The inventory, and the command that re-derives it

### 1.1 The command

The brief's command was `grep -n "\.innerHTML = " …`. **It reads twelve of thirteen**: it demands a
space after the `=`, and `legacy.js:8943` writes `select("#toastmsg").innerHTML =` with the value
on the next line. A count that depends on where a line breaks is a count that changes when a
formatter runs — the exact shape B-085 records. The command that re-derives the inventory reads
every way a script can put markup into the document, not one spelling of one of them:

```bash
grep -nE '\.(innerHTML|outerHTML)\s*=|insertAdjacentHTML\(|\.(appendChild|append|prepend|replaceChildren)\(' \
  frontend/maquette/design/src/engine/legacy.js
```

**19 sites** on 2026-08-29 — 13 `innerHTML` writes, 2 `insertAdjacentHTML`, 4 `appendChild`.
`--count` gives the number; the listing gives the surfaces, and it is the listing that matters,
because 19 sites draw **nine surfaces** and one of the sites draws nothing at all.

**What this command does NOT read, said before the table so nobody reads the table as complete.**
It reads markup WRITES. Two other things make the engine the owner of a surface, and neither
writes markup:

- **A descriptor.** The bottom panel is React (`ui/sheet.tsx`); its CONTENT is a descriptor of
  facts a producer hands to `window.__panel.open`. Every producer is still in the engine —
  `grep -c "panel\.open(" frontend/maquette/design/src/engine/legacy.js` → **10**, against
  `grep -rn "panel.open(" frontend/maquette/design/src/{features,app,lib,ui}` → **0**. So every
  sheet the operator opens — the follow sheet, the journey, the « ⋮ », the account menu, a
  setting, the seasons — is produced by the engine, drawn by React, and invisible to a grep for
  `innerHTML`.
- **A toggle.** Twelve nodes are static markup in `index.html` that the engine shows, hides or
  animates without ever writing them: the splash, the login gate, the install banner, the FAB,
  the pull-to-refresh indicator. § 2 lists them.

### 1.2 The nineteen sites, by surface

| Surface                     | Sites (`legacy.js`)                                                                                         | Container                                                                                | Who owns the container                             | Class                                                                                        |
| --------------------------- | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| **The tab bar**             | `7802` `nav.innerHTML` in `renderNav()`                                                                     | `<nav id="nav">`, **empty** in `index.html:441`                                          | static markup                                      | **frame chrome**                                                                             |
| **The drawer**              | `10000` in `openDrawer()`                                                                                   | `<aside id="drawer">`, **empty** in `index.html:454`                                     | static markup                                      | **frame chrome** — and the NAVIGATION table it draws from is the engine's (`legacy.js:9975`) |
| **The confirmation dialog** | `9064` `openDlg(html)`                                                                                      | `<div id="dlg">`                                                                         | static markup                                      | **frame layer** — 3 producers hand it HTML strings                                           |
| **The toast**               | `8943` (undo variant) + `8933` `textContent` (plain)                                                        | `#toastmsg` inside `#toast`                                                              | static markup                                      | **frame chrome** — 30 `toast(…)` and 6 `toastUndo(…)` callers                                |
| **The selection bar**       | `8236` + `8239` (appended to `#device`)                                                                     | `.selbar`, created per open                                                              | engine creates the node                            | **frame slot, feature content** — the library's selection mode                               |
| **The episode popover**     | `32060` + `32061` (appended to `#device`)                                                                   | `.eppop`, created per open                                                               | engine creates the node                            | **transient layer, feature content** — the media/follow sheets                               |
| **Découvrir — the feed**    | `8653` `.deckbody` · `8677`, `8684` `#sugitems` · `8620`, `8634` deck card swap · `8842`, `8845` `#sugload` | drawn by `features/acquisition/page.tsx:574` (« drawn here and filled by the fragment ») | **React draws the container, the engine fills it** | **feature content** — Acquisition's third tab                                                |
| **The page view**           | `7862` `view.innerHTML = found.render()`                                                                    | `#view`                                                                                  | React portal (`app/page-host.tsx`)                 | **DEAD** — see § 1.3                                                                         |
| **The harness panel**       | `10074` + `10098`                                                                                           | `.hpanel`, created per open                                                              | engine                                             | **scaffolding** — ships nowhere, dies at switchover                                          |
| **A viewport meta**         | `49` `document.head.appendChild`                                                                            | `<head>`                                                                                 | the document                                       | **scaffolding, and a landmine** — see § 5, finding 3                                         |

Nine surfaces the engine draws: **six are the frame's** (tab bar, drawer, dialog, toast, the
selection slot, the popover layer), **one is a feature's** (the Découvrir feed), **two are
scaffolding**. The tenth site draws nothing.

### 1.3 What the engine does NOT draw any more — and the plan still says it does

**The engine draws no page.** `PAGES_OF()` (`legacy.js:7655–7745`) has eight entries and every
one carries `shellOwned: true` and no `render`:

```bash
sed -n 7655,7745p frontend/maquette/design/src/engine/legacy.js | grep -c "shellOwned: true"   # 8
sed -n 7655,7745p frontend/maquette/design/src/engine/legacy.js | grep -c "render:"            # 0
```

So the `else` branch of `render()` at `legacy.js:7856–7863` — the one that writes `#view` — is
unreachable, and if it were reached it would throw (`found.render` is undefined on every entry).
The page host's own comment (`app/page-host.tsx:463`: « An id absent from this table is a page
the legacy still draws ») describes a case with zero members.

**The legacy screen layer is dead too.** `#screen` (`index.html:455`) is opened by nothing:
`openScreen` left with L05, and the stack that `closeScreen` pops is declared at `legacy.js:9101`
and **never pushed** — `grep -n "screenStack.push" legacy.js` → nothing. Three live code paths
still test it (`onEngineBack`, `hideLayers`, `window.__close`) and `app/shell.tsx:288–291`
re-parents the React mount node relative to it. It is the shape D5 forbids — machinery nobody
can justify, kept because nobody measured it — and it is L13's to remove (`frontend-architecture.md` § 4, L13, as amended by this phase).

**Why the plan says otherwise.** `frontend-architecture.md` § 4 L13 carries « the sixty fixture
families … belong to surfaces the ENGINE still draws — their literals cannot leave before their
markup does ». The markup left. What still reads those families is the ten panel producers, the
Découvrir feed and the delegation's verbs — descriptors and handlers, not markup. The sentence is
corrected in the plan amendment.

---

## 2. What the shell IS — every node of the frame, and who owns it

The frame is the markup of `index.html` inside `.device`, plus what React mounts into `#shell`.
**Nothing about it is written down anywhere as a whole**; this table is that. « Drawn » is who
writes the node's children; « driven » is who toggles its state.

| Node                      | Markup                     | Drawn by                                                                                              | Driven by                                                                                                                                          | Read by React without being drawn by it                                                       |
| ------------------------- | -------------------------- | ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `.stage > .device#device` | static                     | —                                                                                                     | `harness.css` (the phone frame; ships nowhere)                                                                                                     | positioned ancestor of every layer; `shell.tsx` re-parents `#shell` into it                   |
| `#shell`                  | static mount               | **React root**: `ConnectionMark`, `ConnectionNotice`, the router (5 screens), the sheet and the scrim | —                                                                                                                                                  | —                                                                                             |
| `#splash`                 | static                     | —                                                                                                     | engine: `coverLoading` / `__loadingDone` (`9774`)                                                                                                  | —                                                                                             |
| `.skip-link`              | static                     | —                                                                                                     | `app/focus.ts` (focus lands on `#port`)                                                                                                            | —                                                                                             |
| `header#topbar`           | static                     | `#connection` is React (`ConnectionMark`); burger and avatar are static                               | burger → `data-drawer` (engine delegation); avatar → `data-sheet="utilisateur"` (engine producer)                                                  | —                                                                                             |
| `main#port`               | static                     | —                                                                                                     | scroll: `app/scroll-restoration.ts` (history), `app/focus.ts` (skip link), engine `applyState` (`scrollTop = 0`), engine pull-to-refresh on `#ptr` | `aria-busy` by `app/page-host.tsx`; `@container/port`                                         |
| `#view`                   | static                     | **React portal** for all 8 pages                                                                      | engine `render()` announces the handover                                                                                                           | —                                                                                             |
| `#installbar`             | static                     | —                                                                                                     | engine: `beforeinstallprompt`, iOS detection, `hidden` toggles (`9816–9915`)                                                                       | —                                                                                             |
| `#login`                  | static                     | —                                                                                                     | engine: `showSignIn` / `hideSignIn` / submit (`9678–9800`); address through `__bridge.replace`                                                     | `lib/addresses.ts` names `/login`                                                             |
| `.hbtn`                   | static                     | —                                                                                                     | engine (design notes, harness panel) — scaffolding                                                                                                 | —                                                                                             |
| `#fab`                    | static                     | —                                                                                                     | engine: `refreshActionButton`, `pageWantsActionButton`                                                                                             | —                                                                                             |
| `nav#nav`                 | static, **empty**          | **engine** `renderNav()`, **on every `render()`**                                                     | —                                                                                                                                                  | `app/bar-height.ts` measures it                                                               |
| `aside#drawer`            | static, **empty**          | **engine** `openDrawer()`                                                                             | engine `closeDrawer`, `hideLayers`, `onEngineBack`                                                                                                 | `app/focus.ts` watches `data-open`; `app/drawer-gesture.ts` closes it through `__closeLayers` |
| `#screen`                 | static, empty              | nothing (dead)                                                                                        | engine tests it in three places                                                                                                                    | `shell.tsx` positions the mount node before it                                                |
| `#scrim` + `#sheet`       | **React** (`ui/sheet.tsx`) | React from a descriptor                                                                               | verbs: `app/panel-host.ts`; **the engine raises `#scrim` itself** for the drawer and the dialog (`setOpen(select("#scrim"))`)                      | —                                                                                             |
| `#dlg`                    | static, empty              | **engine** `openDlg(html)`                                                                            | engine `closeDlg`; no history entry (§ 5, finding 2)                                                                                               | `app/focus.ts` watches it                                                                     |
| `#toast` / `#toastmsg`    | static                     | **engine**                                                                                            | engine `setMessageShown`, 5–6 s timers                                                                                                             | —                                                                                             |
| `[data-part="screen"]` ×5 | —                          | **React routes** into `#shell`                                                                        | the router; `app/history-bridge.ts`                                                                                                                | `app/focus.ts`, `app/scroll-restoration.ts` select them by part                               |

<sub>`grep -n 'id="' frontend/maquette/design/index.html` lists the static nodes; the owners are
read from `frontend/maquette/design/src/app/*.ts*` and `engine/legacy.js` at the lines cited.</sub>

**The reading of this table, in one sentence.** React owns the URL, the history, the pages, the
screens, the sheet, the scrim, focus, scroll memory and liveness; **the engine owns the chrome
(tab bar, drawer, dialog, toast, FAB), the entry (splash, login, install), the ladder's logic, and
every verb** — and the two worlds meet on `data-open`, on `#scrim`, and on twelve `window.__`
seams (`grep -on "window\.__[a-zA-Z]*" … | sort -u | wc -l` → 41 distinct names across engine
and shell).

---

## 3. The layer ladder — what Back walks, and what it does not

The engine's back handler (`onEngineBack`, `legacy.js:9461–9478`) walks the layers in this order,
and it is the whole of the ladder:

1. **drawer** — `#drawer.open` → `closeDrawer(true)`. Pushes its own entry (`pushLayer("drawer")`,
   the only `pushLayer` call left in the engine).
2. **screen** — `#screen.open` → `closeScreen(true)`. **Dead** (§ 1.3). The five real screens are
   routes: a Back from one is a history pop the router handles, not a ladder step.
3. **sheet** — `panel.isOpen()` → `panel.close(true)`. The panel host pushes `"sheet"`; an
   addressed panel travels in the query (D1, second tier).
4. **the page** — a top-level page REPLACES (D1b), and Back from `/acquisition` arms the exit guard.

**What is NOT on the ladder, and D1 says it should be.** D1's third tier reads « Transient: no URL,
but Back still closes it », and names a confirmation as the example. `openDlg` pushes no entry and
`onEngineBack` has no `#dlg` branch, so a hardware Back with a dialog open pops the entry UNDER the
dialog — a page or the exit guard — with the dialog still up. Derived from the code, not exercised
(the office's first limit); it is § 5, finding 2, and it belongs to the frame lot. The toast and
the episode popover are transient too and are closed by their own timer or tap, which is right for
them — a Back that dismissed a toast would be a Back stolen from the page.

`window.__closeLayers` (`9614`) is a different verb: what a SCRIM TAP closes — dialog, sheet,
drawer, in that order — and it is what `app/drawer-gesture.ts` also calls, so a swipe and a tap
share one closing path.

`window.__closeLayers` walks three layers where the ladder walks two live ones; the scrim is
raised by three different writers (the engine for the drawer and the dialog, React for the sheet)
on one shared element. That asymmetry is the frame's, and the model (`MODEL.md` § 2, part 6)
names one owner for it.

---

## 4. What production does with the same surfaces

Not to draw from it — `frontend/src` is archived at switchover and never harvested (§15). **An
unexplained difference is a decision nobody took**, and this is the first document able to name
them. Read from `frontend/src/components/layout/*.tsx`, `hooks/usePwa.ts`,
`lib/use-back-closes.ts`, `router.tsx`.

| Surface                 | Production (`frontend/src`)                                                                                                                               | Maquette                                                                                                            | Verdict                                                                                                                                                                                                          |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| The frame               | `AppShell.tsx`: one viewport tall, `h-svh overflow-clip`, one scrollport `main[data-scroll-root]` — chosen to stop iOS's URL bar shivering the fixed zone | `.device` + `main#port`, one scrollport, `100dvh` in the base layer                                                 | **same model**, independently reached; nothing to decide                                                                                                                                                         |
| Bottom tab bar          | `BottomTabBar.tsx`, `< md` only, 4 tabs: Acquisition · Médias · Pipeline · Contrôle                                                                       | `#nav`, `md:hidden`, 4 tabs: Acquisition · Médiathèque · Arrivées · Système                                         | the SET differs because `/pipeline` and `/control` are undrawn (plan § 1, item 1) and Arrivées has no production page. Known; the operator's open UX question in `IMPLEMENTATION.md`                             |
| Desktop navigation      | `Sidebar.tsx`, `hidden md:flex` — a persistent rail at `≥ md`                                                                                             | **none.** The tab bar hides at `md` and no rail exists: at desktop width the burger's drawer is the only navigation | **a decision nobody took** — `product-intent.md` §12 says the desktop « doit rester pleinement fonctionnel ». It is functional through the drawer; whether a rail is drawn is the operator's (`QUESTIONS.md` Q1) |
| The drawer              | a shadcn `Sheet side="left"` with the same `NavSections` as the rail, plus `VersionCard`                                                                  | engine-drawn `<aside>` from `NAVIGATION`, plus the served identity block                                            | same content, two owners; **the maquette's is the one that has to move** (frame lot)                                                                                                                             |
| Top bar                 | brand, connection `StatusDot` from the event stream, `UserMenu`                                                                                           | brand, `ConnectionMark` (React, L10), avatar opening the « utilisateur » sheet                                      | same                                                                                                                                                                                                             |
| Nav badges              | `/media` awaiting count, `/pipeline` running/paused dot, `/acquisition` waiting count, `?` when a query errors                                            | `acq` (to grab + to resolve), `arr` (stuck)                                                                         | the maquette shows **no pipeline-running indicator in its chrome** — the page that would carry it is undrawn. Recorded, not decided here                                                                         |
| Back closes a layer     | `useBackCloses`: a same-URL history entry per open sheet, per component                                                                                   | one ladder, one history bridge, addressed panels in the query (D1b)                                                 | the maquette's is settled and better; nothing to take                                                                                                                                                            |
| Service worker          | Workbox precache of the shell, `registerType: 'prompt'`, update check on load / visibility / 15 min, `/api/version` poll, toast + one reload              | `serve.py` serves a worker that **caches nothing** (README: a caching worker would serve yesterday's prototype)     | **L11's whole subject**; the production discipline is the reference for what « all installs converge » means, and it is `web-ui.md` § PWA                                                                        |
| Install proposal        | `usePwa` + `InstallBanner`: `beforeinstallprompt`, iOS detection, dismissal in `localStorage`                                                             | engine `9816–9915`: the same two paths, dismissal per session only                                                  | same design; the maquette's logic is in the engine and moves with the frame lot                                                                                                                                  |
| Route guard             | `ProtectedRoute` → `/login` page                                                                                                                          | `/login` is a layer over a built frame (`lib/addresses.ts`)                                                         | the maquette's is the designed one (D1)                                                                                                                                                                          |
| Legacy French routes    | `medias`, `systeme`, `controle` redirected by `router.tsx`                                                                                                | `serve.py` answers them with redirects (#456)                                                                       | same                                                                                                                                                                                                             |
| Frame heights published | `--topbar-h` AND the bottom bar (`bottom-bar-metrics.ts`)                                                                                                 | `--tm-bottom-bar-h` only (`app/bar-height.ts`, R84)                                                                 | the top bar's height is read by nothing in the maquette today; if a surface ever needs it, R84's « exactly one publisher » applies                                                                               |

---

## 5. Findings, written into the register during the phase

Each is a `BUGS.md` entry; the number is the one `check-bug-register.py --next` gave on this
branch at the moment of writing.

1. **B-228** — the brief's inventory command reads twelve of thirteen writes; the count moved
   three times in a day because the instrument was a spelling. (B-085's species — the phase's
   own figure for the « guards green » table is **1**.)
2. **B-229** — the confirmation dialog is not on the ladder: no history entry, no Back branch,
   against D1's third tier.
3. **B-230** — `legacy.js:44–50` re-adds `maximum-scale=1,user-scalable=no` to any host without a
   viewport meta. Dead on the maquette's host, which has one; live on any host that does not —
   the exact directive L03 removed for WCAG 1.4.4.
4. **B-231** — the tab bar is rebuilt from scratch on every `render()`: `renderNav()` is called
   unconditionally at `legacy.js:7868`, so the chrome's buttons are new nodes on every page
   switch and every store bump. A persistent chrome is the first property of `MODEL.md` § 3 and
   it is false today.
5. **B-232** — two dead layers: the page-render branch of `render()` and the `#screen` layer,
   with three live tests and one React positioning decision resting on the second.
6. **B-233** — `theme-color` is a constant `#0b0b0d` while the document paints light under
   `data-theme="light"`; the status bar of an installed light-theme app is dark.
7. **B-234** — the viewport meta declares no `interactive-widget`, so the virtual keyboard
   resizes the layout viewport (the platform default) — the property L12 names (« the virtual
   keyboard resizing content rather than the viewport ») has no declaration behind it.
8. **B-235** — no desktop navigation exists beyond the drawer (§ 4). Filed as `open` because the
   answer is the operator's, not because it is known to be wrong.
9. **B-236** — every bottom-panel producer is still the engine's — ten of ten — and no lot of the
   plan owes their conversion, which is B-220's class over the product's whole sheet layer.

<sub>the commands: § 1.1 for the writes · `grep -n "screenStack" legacy.js` for the dead layer ·
`grep -n "theme-color" index.html` · `grep -c "interactive-widget" index.html` → 0 ·
`grep -n "md:hidden" index.html` and `grep -rln "sidebar\|Sidebar" design/src/{app,features,ui,lib}` → none</sub>
