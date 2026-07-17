# Phase 02 — /systeme hub (4 tabs, routes, redirects)

**Goal**: Create the new `SystemePage` with 4 URL-addressable tabs mirroring the AcquisitionPage
pattern. Redistribute every existing maintenance/registry panel into the new tabs. Remove
`/maintenance` + `/registry` routes, add `/systeme`, wire redirects, collapse sidebar entries.
Zero panel rewrites — only the page shell, routing, and redirects are new code.

**Constitution served**: §3.2, §7 (journal home), DOIT-10 (URL-addressable), F1 (second history table renamed).

## Surface

| File                                                          | Action                                                                         |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `frontend/src/pages/SystemePage.tsx`                          | **NEW** — 4-tab shell (AcquisitionPage pattern)                                |
| `frontend/src/pages/SystemePage.test.tsx`                     | **NEW** — migrated Maintenance.test.tsx + RegistryPage suite                   |
| `frontend/src/router.tsx`                                     | Add `/systeme` route; remove `/maintenance` + `/registry`                      |
| `frontend/src/components/layout/nav.ts`                       | Replace Maintenance + Registre entries with one "Système"                      |
| `frontend/src/components/pipeline/MaintenanceRunRedirect.tsx` | Remove — its logic folds into SystemePage (tab "maintenance" runs on /systeme) |

## Sub-phases

### 2.1 — Create SystemePage with 4 tabs

**Commit**: `feat(systeme-hub): add SystemePage with 4 URL-addressable tabs`

**Page shape** (mirrors `AcquisitionPage.tsx`):

```
/systeme?tab=etat|actions|maintenance|journal  (default etat)
```

**Tab model**:

| Tab id        | Label                     | Content                                                                                                  |
| ------------- | ------------------------- | -------------------------------------------------------------------------------------------------------- |
| `etat`        | État                      | DisksPanel + LocksPanel + IndexHealthPanel + providers (ex-RegistryPage) + EventFeed + RecentEventsTable |
| `actions`     | Actions                   | ActionCatalog (ex-Maintenance, kept as-is)                                                               |
| `maintenance` | Exécutions de maintenance | RunHistoryTable (kind="maintenance") + TriggerLegend + `&run=` RunDetail drawer                          |
| `journal`     | Journal                   | DestructiveLogPanel (§7 home)                                                                            |

**Key patterns borrowed from AcquisitionPage.tsx**:

- `useSearchParams` → `rawTab` → validated `activeTab: TabId`
- Tabs array with `{ id, label }` shape
- `setActiveTab` pushes/clears `?tab=` in URL (replace: false, except default = clean URL)
- Tablist: `role="tablist"`, `flex-nowrap overflow-x-auto`, same segmented-control styling
- `<Card><CardContent>` wrapping the active panel

**State tab (état) redistribution**:

- `DisksPanel` — uses `/api/maintenance/disks` (already mocked in router.test.tsx)
- `LocksPanel` — uses `/api/maintenance/locks` (sized to content, H4)
- `IndexHealthPanel` — uses `/api/maintenance/index-health` (already mocked)
- Provider cards (from `RegistryPage.tsx`) — uses `useRegistryStatus()` (existing hook, no change)
- `EventFeed` + `RecentEventsTable` — use `useEventStreamContext()` (already in shell)

**Actions tab**: `ActionCatalog` (no change to component internals).

**Maintenance tab**: `RunHistoryTable` with `kind="maintenance"` + `TriggerLegend`.
When `&run=<uid>` is present, open a RunDetail drawer (exact same RunDetail component
as on `/pipeline` — it already accepts any uid). The `MaintenanceRunRedirect` logic
(teleport `/maintenance?run=` → `/pipeline?run=`) stays intact as a LegacyRedirect
on the route, NOT in the page component.

**Journal tab**: `DestructiveLogPanel` — its canonical home per §7.

**Gates**:

```bash
cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run -- src/pages/SystemePage.test.tsx
```

### 2.2 — Migrate tests + delete old pages

**Commit**: `refactor(systeme-hub): migrate Maintenance + Registry test suites to SystemePage`

**Test migration plan**:

1. Copy `Maintenance.test.tsx` → `SystemePage.test.tsx`; adapt:
   - Route: `/maintenance` → `/systeme` (headings will differ)
   - Assert the "Système" h1 (not "Maintenance")
   - Verify all 4 tabs render their content
   - Verify `?tab=etat` renders disks + locks + index + providers
   - Verify `?tab=actions` renders ActionCatalog
   - Verify `?tab=maintenance` renders RunHistoryTable (kind=maintenance)
   - Verify `?tab=journal` renders DestructiveLogPanel
   - Verify default (no ?tab=) renders état tab
   - Verify `?tab=inconnu` falls back to état

2. Copy `RegistryPage.test.tsx` provider-card assertions into `SystemePage.test.tsx`:
   - Provider cards visible in état tab
   - Circuit breaker badges render
   - Loading/empty states work

3. Delete `Maintenance.test.tsx` + `RegistryPage.test.tsx` + `Maintenance.tsx` + `RegistryPage.tsx`.

**Gates**:

```bash
cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run
```

Verify no residual imports of `Maintenance` or `RegistryPage` in any file:

```bash
rg "from.*Maintenance|from.*RegistryPage" frontend/src/ -g '*.ts' -g '*.tsx'
```

### 2.3 — Routing + sidebar + redirects

**Commit**: `feat(systeme-hub): add /systeme route, remove /maintenance + /registry, redirects + sidebar`

**Router changes** (`frontend/src/router.tsx`):

```typescript
// ADD import
import SystemePage from "@/pages/SystemePage";

// REMOVE entries:
//   { path: "maintenance", element: <MaintenanceRunRedirect /> },
//   { path: "registry", element: <RegistryPage /> },

// ADD entry (in the AppShell children, after /acquisition):
{ path: "systeme", element: <SystemePage /> },

// CHANGE /maintenance entry to LegacyRedirect (keeps ?run= teleport):
{
  path: "maintenance",
  element: <LegacyRedirect to="/pipeline" />,
},

// CHANGE /registry entry to LegacyRedirect:
{
  path: "registry",
  element: <LegacyRedirect to="/systeme?tab=etat" />,
},
```

**CRITICAL**: The V3 contract — `/maintenance?run=<uid>` MUST still land on `/pipeline?run=<uid>`.
With the `LegacyRedirect` pattern, `/maintenance?run=abc` forwards `?run=abc` to `/pipeline?run=abc`.
This preserves the existing `MaintenanceRunRedirect` behavior exactly — just via the shared
LegacyRedirect component instead of a dedicated wrapper. The `Navigateto` with `replace` handles
the history correctly.

**Sidebar changes** (`frontend/src/components/layout/nav.ts`):

```typescript
// CHANGE "Système" section:
{
  title: "Système",
  items: [{ to: "/systeme", label: "Système", icon: Wrench }],
},

// CHANGE "Configuration" section — remove Registre entry:
{
  title: "Configuration",
  items: [{ to: "/config", label: "Config", icon: Settings }],
},
```

Note: The nav grouping "Système" / "Configuration" was already established. Now:

- "Système" section has ONE entry: "Système" (to `/systeme`) — the section label and the
  entry label are the same, the group-label → entry-name collision is acceptable per the
  DESIGN.md's flat-nav arbitration (no group micro-labels in 6-entry nav).
- "Configuration" section has ONE entry: "Config" (the `Plug` icon for Registre is gone).

**Remove `MaintenanceRunRedirect.tsx`**: Delete the file — its logic is replaced by
`LegacyRedirect to="/pipeline"` on the `/maintenance` route.

**Remove `Maintenance.tsx` + `RegistryPage.tsx`**: Delete both page files (tests already migrated in 2.2).

**Redirect verification tests** (add to `router.test.tsx`):

```typescript
it("redirige /registry vers /systeme?tab=etat", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: ["/registry"] });
  render(<QueryClientProvider client={client}><AuthProvider><RouterProvider router={router} /></AuthProvider></QueryClientProvider>);
  await waitFor(() => {
    expect(router.state.location.pathname).toBe("/systeme");
    expect(router.state.location.search).toBe("?tab=etat");
  });
});

it("redirige /maintenance vers /pipeline (V3 contract: ?run= teleport via LegacyRedirect)", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: ["/maintenance"] });
  render(<QueryClientProvider client={client}><AuthProvider><RouterProvider router={router} /></AuthProvider></QueryClientProvider>);
  await waitFor(() => {
    expect(router.state.location.pathname).toBe("/pipeline");
  });
});

it("transmet /maintenance?run=<uid> vers /pipeline?run=<uid> (V3 contract)", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: ["/maintenance?run=abc123def456"] });
  render(<QueryClientProvider client={client}><AuthProvider><RouterProvider router={router} /></AuthProvider></QueryClientProvider>);
  await waitFor(() => {
    expect(router.state.location.pathname).toBe("/pipeline");
    expect(router.state.location.search).toBe("?run=abc123def456");
  });
});

it("redirige /maintenance?run= (paramètre vide) vers /pipeline (même comportement qu'avant — LegacyRedirect)", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: ["/maintenance?run="] });
  render(<QueryClientProvider client={client}><AuthProvider><RouterProvider router={router} /></AuthProvider></QueryClientProvider>);
  await waitFor(() => {
    expect(router.state.location.pathname).toBe("/pipeline");
    expect(router.state.location.search).toBe("?run=");
  });
});
```

**Gates**:

```bash
cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run
```

Verify no residual imports:

```bash
rg "MaintenanceRunRedirect|from.*pages/Maintenance|from.*pages/RegistryPage" frontend/src/ -g '*.ts' -g '*.tsx' && echo "FAIL: residual import" || echo "OK"
```

Cross-check router import removals — `router.tsx` must no longer import `MaintenanceRunRedirect`, `Maintenance`, or `RegistryPage`.

### Files-in-scope summary

| Phase | Files touched | New files | Deleted files |
| ----- | ------------- | --------- | ------------- |
| 2.1   | 0             | 2         | 0             |
| 2.2   | 0             | 0         | 4             |
| 2.3   | 3             | 0         | 1             |

**Total**: 10 files (2 new, 3 modified, 5 deleted). All frontend-only, zero backend.
