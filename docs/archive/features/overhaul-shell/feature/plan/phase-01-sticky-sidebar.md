# Phase 01 — Sticky sidebar

## Gate

- [ ] Branch `feat/overhaul-shell` exists and is checked out.
- [ ] `cd frontend && npm run lint && npm run typecheck && npx vitest run` passes clean on HEAD.

## Scope

Make the desktop `Sidebar` `<aside>` sticky so it stays fully visible/scrollable
independently of the page content. Today it is a plain flex child of the
`min-h-screen` wrapper (`Sidebar.tsx:68-72`), so on tall pages (e.g. 7 276 px
`/maintenance`) the nav scrolls out of view (finding A1).

**Files touched:**

- `frontend/src/components/layout/Sidebar.tsx` — add `sticky top-0 h-screen overflow-y-auto`
- `frontend/src/components/layout/AppShell.tsx` — ensure the flex shell accommodates a sticky child

**Preserved invariants (must not regress):**

- Collapse rail: `md:w-16` / `md:w-56` toggles still work.
- `tm-sidebar-collapsed` localStorage persistence round-trips.
- `NavSections` reused in the mobile Sheet (unchanged).
- `env(safe-area-inset-*)` behavior on mobile (unchanged).

### Sub-phase 1.1 — Add `sticky` + `overflow-y-auto` to Sidebar aside

**Commit:** `feat(overhaul-shell): make sidebar sticky with independent scroll`

**Change — `frontend/src/components/layout/Sidebar.tsx:68-72`:**

The current `<aside>` className:

```tsx
<aside
  className={cn(
    "hidden shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex",
    collapsed ? "md:w-16" : "md:w-56",
  )}
>
```

Add `sticky top-0 h-screen overflow-y-auto` so the sidebar sticks to the viewport
top and scrolls its own nav independently:

```tsx
<aside
  className={cn(
    "hidden shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex sticky top-0 h-screen overflow-y-auto",
    collapsed ? "md:w-16" : "md:w-56",
  )}
>
```

The `h-screen` + `overflow-y-auto` makes the sidebar fill the viewport height and
scroll its inner `NavSections` (flex child with `flex-1`) when it overflows. The
`sticky top-0` pins it to the top inside the `AppShell` flex wrapper.

**No change needed in AppShell.tsx** — the existing `<div className="flex min-h-screen ...">` wrapper already accommodates a sticky child. The sidebar's `shrink-0` prevents flex compression.

### Verification

1. **Typecheck + lint:**

   ```bash
   cd frontend && npm run typecheck && npm run lint
   ```

   Expected: zero errors. The change is a className string only.

2. **Existing Sidebar tests:**

   ```bash
   cd frontend && npx vitest run src/components/layout/Sidebar.test.tsx
   ```

   Expected: all tests pass (4 tests). The className change doesn't affect the DOM assertions.

3. **Chrome visual proof (manual, post-commit):**
   - Open `/maintenance` (tallest page) on prod or staging.
   - Scroll to page bottom. Sidebar must remain fully visible — nav entries not off-screen.
   - Toggle collapse: `md:w-16` rail still shrinks, `PanelLeftOpen`/`PanelLeftClose` icons work.
   - Mobile (390px iframe): no regression — `scrollWidth - innerWidth == 0`, collapse behavior N/A on mobile (sidebar is `hidden` below `md`).

4. **Commit:**
   ```bash
   git add frontend/src/components/layout/Sidebar.tsx
   git commit -m "feat(overhaul-shell): make sidebar sticky with independent scroll"
   ```

### Sidebar test (no changes needed)

The `Sidebar.test.tsx` tests render the component in isolation (`MemoryRouter`) and
assert DOM structure. Since the change is purely CSS (className), no test updates
are needed — the existing assertions on link presence, active state, and section
labels remain unchanged. The test does not assert scroll behavior (a visual
concern, verified manually via Chrome).

## Completeness check

- [ ] Sidebar `<aside>` has `sticky top-0 h-screen overflow-y-auto`.
- [ ] `NavSections` inside sidebar scrolls independently (nav overscroll is contained).
- [ ] Collapse rail toggle still works, persistence round-trips.
- [ ] Mobile Sheet nav is unchanged (no sticky on the Sheet's `NavSections` — it's a different render path).
- [ ] `cd frontend && npm run lint && npm run typecheck && npx vitest run` green.
