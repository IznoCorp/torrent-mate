# Phase 03 — Frontend SchemaForm + /config Page

## Gate

- [ ] Phase 02 merged — all 9 `/api/config/*` endpoints live, OpenAPI spec updated (Phase 4 regenerates it formally; this phase regenerates locally for typed client work)
- [ ] `make test` green on current HEAD

## Goal

Replace the `/config` `ComingSoon` stub with a full visual config editor: SchemaForm renderer, file list with dirty/restart badges, form panel, secrets tab, restart banner. No new frontend dependencies (DESIGN §6).

Reference patterns: `frontend/src/pages/Maintenance.tsx` (page layout), `frontend/src/hooks/useMaintenanceKeys.ts` (TanStack Query keys), `frontend/src/components/layout/nav.ts` (nav item enable).

## Sub-phases

### 3.1 — SchemaForm renderer (`frontend/src/components/config/SchemaForm.tsx`)

**Files**:

- Create: `frontend/src/components/config/SchemaForm.tsx`
- Create: `frontend/src/components/config/SchemaForm.test.tsx`

**Component contract**:

```tsx
interface SchemaFormProps {
  schema: Record<string, unknown>; // JSON Schema node (root or $def)
  values: Record<string, unknown>; // current values for this node
  onChange: (values: Record<string, unknown>) => void;
  errors?: Record<string, string>; // server 422 loc → field path → message
  readOnly?: boolean;
}
```

**Field kind → renderer mapping** (DESIGN §5):

| Schema `type`                        | Renderer                                                          |
| ------------------------------------ | ----------------------------------------------------------------- |
| `string`                             | `<Input>` (shadcn)                                                |
| `integer` / `number`                 | `<Input type="number">`                                           |
| `boolean`                            | `<Switch>` (shadcn)                                               |
| `string` + `enum`                    | `<Select>` (shadcn)                                               |
| `array` of primitives                | list editor (add/remove rows)                                     |
| `array` of `$ref` objects            | card list (add/remove cards)                                      |
| `object` with `properties`           | collapsible `<details>` / accordion section, recursive SchemaForm |
| `object` with `additionalProperties` | key/value row editor                                              |
| anything else                        | JSON textarea fallback with `JSON.parse` check                    |

**Commit**: `feat(config-editor): add SchemaForm renderer component`

### 3.2 — Config page (`frontend/src/pages/Config.tsx`)

**Files**:

- Create: `frontend/src/pages/Config.tsx`
- Create: `frontend/src/pages/Config.test.tsx`
- Create: `frontend/src/components/config/FileList.tsx` — sidebar file list with dirty + restart badges
- Create: `frontend/src/components/config/SecretsTab.tsx` — masked write-only inputs + `is_set` chips

**Layout** (mirrors Maintenance page shell):

```
<section className="mx-auto flex max-w-5xl flex-col gap-4">
  <h1>Configuration</h1>
  <StagingBanner /> (reused, read-only warning when role=staging)
  <RestartBanner /> (when status.restart_required)
  <FileList /> + <SchemaForm /> (two-panel desktop, stacked mobile)
  <SecretsTab />
  <RestartButton /> (confirm dialog → POST /api/config/restart-web)
</section>
```

**State machines**:

- Save flow: PUT → 200 success toast → 412 conflict dialog (offer reload) → 422 map errors to fields
- Restart: confirm dialog → POST → 202 toast "restart scheduled" → WS backoff + query retry absorb gap

**Commit**: `feat(config-editor): add Config page with file list, form, secrets, and restart`

### 3.3 — API client hooks + nav enable + router swap

**Files**:

- Create: `frontend/src/hooks/useConfigKeys.ts` — TanStack Query key constants
- Create: `frontend/src/hooks/useConfig.ts` — `useSchema()`, `useFiles()`, `useFile(name)`, `useStatus()`, `useSecrets()`, `usePutFile()`, `usePutSecrets()`, `useRestartWeb()`
- Modify: `frontend/src/api/client.ts` — add typed `apiFetch` wrappers for config endpoints (follow maintenance endpoint pattern, lines 386–485)
- Modify: `frontend/src/components/layout/nav.ts:82` — `disabled: true` → `disabled: false`, remove `wave: "S4"`
- Modify: `frontend/src/router.tsx:54` — `element: <ComingSoon .../>` → `element: <Config />`

**TanStack Query keys**:

```ts
export const configKeys = {
  schema: ["config", "schema"] as const,
  files: ["config", "files"] as const,
  file: (name: string) => ["config", "files", name] as const,
  status: ["config", "status"] as const,
  secrets: ["config", "secrets"] as const,
};
```

**Mutations** (use `useMutation` from `@tanstack/react-query`, invalidate relevant query keys on success, `X-Requested-With: TorrentMate` header on mutating endpoints):

- `usePutFile(name)` → `PUT /api/config/files/{name}` → onSuccess invalidates `configKeys.files` + `configKeys.file(name)` + `configKeys.status`
- `usePutSecrets()` → `PUT /api/config/secrets` → onSuccess invalidates `configKeys.secrets` + `configKeys.status`
- `useRestartWeb()` → `POST /api/config/restart-web`
- `useValidate()` → `POST /api/config/validate`

**Commit**: `feat(config-editor): add config API hooks, nav enable, router swap`

## Coherence gate → Phase 4

- [ ] `/config` page loads with file list populated (dev server on port 8711 or 5173)
- [ ] SchemaForm renders all field kinds correctly (dev server visual check)
- [ ] Save → 200 success toast visible
- [ ] Save with wrong hash → 412 conflict dialog
- [ ] Invalid values → 422 error mapped to fields
- [ ] "Config" nav item clickable, navigates to `/config`
- [ ] `make test` green — vitest frontend tests pass
- [ ] `make lint` green — TypeScript strict, no `any` except schema fallback paths
