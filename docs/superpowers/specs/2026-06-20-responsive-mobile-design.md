# mobile — responsive mobile UI — DESIGN

> **Codename**: `mobile` · **Branch**: `feat/mobile` · **Type / SemVer**: minor (additive UI,
> frontend-only) · **Builds on**: bridge + monitoring (web/ SPA, merged to `main`, v0.10.0).
>
> Make the whole KanbanMate web UI usable on phones. **Frontend-only** — no backend/endpoint/daemon
> change. Desktop layout is unchanged; a mobile layout branches in at a breakpoint.

---

## §1 — Problem & motivation

The SPA (bridge config + monitoring) is desktop-only: a fixed 256 px sidebar, master-detail grids
with fixed columns (`320px 1fr` / `360px 1fr`), wide panels. On a phone the sidebar eats the
screen, the two-column grids overflow, and dialogs are oversized. The operator wants to drive
KanbanMate from a phone (it's exposed at `km.iznogoudatall.xyz`). This adds a responsive mobile
layout to the existing SPA without disturbing the desktop experience.

## §2 — Goals / non-goals

### Goals

1. Every surface usable on a phone: login, the shell (board switcher + 8 nav items), and all tabs
   (Columns, Transitions, Defaults, Validation, YAML, Monitoring, Daemon, Profiles), plus the
   dialogs (Sync board, File picker) and the rich editors (CodeMirror prompt, terminal tail).
2. **Hamburger-drawer nav** on mobile: a top app-bar with ☰ that slides in the existing sidebar
   (board switcher + Board/Daemon groups) as an overlay; content takes full width.
3. **List → full-screen detail + back** for master-detail panels on mobile; side-by-side grid stays
   on desktop.
4. Touch-friendly sizing (tap targets ≥ ~40 px), fluid widths, dialogs as near-full-screen sheets.
5. **Desktop unchanged** — the mobile layout is purely additive, gated by a breakpoint.

### Non-goals

- No backend/endpoint/daemon change; no new dependency.
- No native app, PWA/offline, or gesture navigation.
- No desktop redesign; no new feature behaviour (same data, same actions, same i18n).

## §3 — Mechanism

- A reactive **`useIsMobile()`** hook: `window.matchMedia("(max-width: 768px)")` with a change
  listener (returns a boolean, re-renders on viewport cross). Lives in `web/src/useIsMobile.js`.
  768 px = phones + small tablets portrait.
- Components read `useIsMobile()` and branch the layout where structure must change (drawer vs
  sidebar; list↔detail). Where only sizing changes, prefer fluid CSS (max-width, %, `flex-wrap`,
  `minWidth: 0`) so it also degrades on window resize without JS.
- `<meta name="viewport" content="width=device-width, initial-scale=1">` is already present
  (`web/index.html`).

## §4 — Components

### §4.1 Shell (`components/AppShell.jsx`)

- **Desktop** (`!isMobile`): unchanged — 256 px sidebar + header.
- **Mobile**: render a **top app-bar** instead of the sidebar — `[☰] <tab title>  … [Save]` — and a
  slide-in **drawer** holding the _existing_ sidebar content (board switcher + `BOARD_NAV` +
  `DAEMON_NAV` groups). Drawer = fixed overlay panel (~280 px) + a dim backdrop; opens on ☰,
  closes on backdrop tap or nav selection (`onNav` wrapped to also close). The header's secondary
  actions (Validate, `LangSwitcher`, logout) move into the **drawer footer** on mobile; **Save**
  stays in the app-bar (primary, compact) when `boardScope`. New local state `drawerOpen`.
- Reuse the existing `Wordmark`, `NavItem`, `GroupLabel`, `Select` switcher; no duplication — the
  drawer renders the same nav markup the desktop sidebar does (extract the sidebar body into a
  small `SidebarNav` sub-component shared by both).

### §4.2 Master-detail panels

Affected: `TransitionsPanel`, `MonitoringPanel`, `DaemonPanel`, `ProfilesPanel` (expand list).
Each already holds a selection state (`sel` / `pick` / `open`). Add an `isMobile` branch:

- **Mobile + nothing selected** → render the LIST full-width.
- **Mobile + selected** → render the DETAIL full-width, preceded by a back header (`← <title>`)
  that clears the selection.
- **Desktop** → the existing two-column grid (unchanged).

Encapsulate the shared chrome in a tiny `components/MobileMasterDetail.jsx`:
`<MobileMasterDetail isMobile selected list={<…>} detail={<…>} onBack={…} backLabel={…}>` — renders
`list` or (`back header` + `detail`) on mobile, and `{list}{detail}` side-by-side wrapper on
desktop is left to the panel (the helper only owns the mobile switch). Panels pass their existing
list/detail JSX.

`ColumnsPanel` is a single list (rows with inline controls) — no detail view; make the row controls
`flex-wrap` and the action bar stack on mobile. `Defaults` / `Validation` / `YAML` are already
single-column — only fluid widths needed.

### §4.3 Dialogs (`SyncBoardDialog`, `FilePicker`)

The design-system `Dialog` is fixed-width (`width=…`). On mobile, constrain to the viewport: a
wrapper style `width: min(<width>, 100vw - 24px)` and allow it to grow tall (near-full-screen
sheet). If the DS `Dialog` doesn't accept a responsive width, wrap its content so it never exceeds
the viewport (no horizontal page scroll). Buttons stay reachable (sticky footer if needed).

### §4.4 Editors

- CodeMirror prompt editor + terminal-tail `<pre>` + YAML preview: cap width to the container,
  allow internal horizontal scroll (`overflow:auto`), never force page-width overflow (`minWidth:0`
  on flex parents). The two/three-column field grids in the transition editor collapse to one column
  on mobile (`grid-template-columns: 1fr`).

### §4.5 Login (`components/LoginScreen.jsx`)

Card `width: min(360px, 100vw - 32px)`, padding preserved. Already centered — only the width cap.

## §5 — i18n

Add `shell.menu` ("Menu" / «Menu») and `common.back` ("Back" / «Retour») for the ☰ aria-label and
the master-detail back header. All other strings reuse existing keys. EN default + FR.

## §6 — Error handling / testing

- No new failure modes (frontend layout only); existing error banners unchanged.
- Testing: manual in a narrow viewport (responsive devtools / a real phone via
  `km.iznogoudatall.xyz`) across every tab + login + a dialog; plus the existing `npm run build`.
  No backend tests (no backend change). Verify desktop is visually unchanged at ≥ 769 px.

## §7 — Out of scope

Native app, PWA/offline, gestures, desktop redesign, any backend/daemon change, new dependency.
