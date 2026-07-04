# Phase 4 — Frontend scaffold (TorrentMateUI)

## Gate

- Phases 1–3 complete: web backend boots, auth + WS relay functional.
- Node.js 22 available (`node --version`); npm available.
- `pip install -e ".[dev]"` current (needed for OpenAPI export).

## Sub-phases

### 4.1 — Vite + React 19 + TypeScript strict

**Commit**: `feat(tm-shell): scaffold TorrentMateUI Vite + TS-strict project`

**Files** (all under `frontend/`, net-new directory at repo root):

| Action | Path                          |
| ------ | ----------------------------- |
| Create | `frontend/package.json`       |
| Create | `frontend/tsconfig.json`      |
| Create | `frontend/tsconfig.node.json` |
| Create | `frontend/vite.config.ts`     |
| Create | `frontend/eslint.config.js`   |
| Create | `frontend/index.html`         |
| Create | `frontend/src/main.tsx`       |
| Create | `frontend/src/App.tsx`        |
| Create | `frontend/src/vite-env.d.ts`  |
| Create | `frontend/.gitignore`         |

**Work**:

1. `npm create vite@latest frontend -- --template react-ts` then harden:
2. `tsconfig.json` — per DESIGN §5.1: `strict`, `noUncheckedIndexedAccess`,
   `exactOptionalPropertyTypes`, `noImplicitReturns`, `noFallthroughCasesInSwitch`.
   `paths` alias `@/` → `src/`.
3. `eslint.config.js` — `typescript-eslint` with `no-explicit-any` = error,
   `no-unsafe-*` = error, `ban-ts-comment` requires description.
4. `vite.config.ts` — resolve alias, dev server proxy `/api` + `/ws` to
   `localhost:8710`.
5. `package.json` — add `react-router-dom`, `@tanstack/react-query`,
   `@tanstack/react-table`, `@tanstack/react-form`, `@tanstack/react-virtual`,
   `zod`, `lucide-react` as deps; `vitest`, `@testing-library/react`,
   `@testing-library/jest-dom` as dev deps. Scripts: `dev`, `build`, `lint`,
   `lint:ds`, `test`, `typecheck`.

**Verification**: `cd frontend && npm ci && npx tsc --noEmit` → exit 0.

### 4.2 — shadcn/ui + Design System tokens + oxlint

**Commit**: `feat(tm-shell): integrate shadcn/ui and TorrentMate design system`

**Files**:

| Action | Path                                                          |
| ------ | ------------------------------------------------------------- |
| Create | `frontend/components.json`                                    |
| Create | `frontend/src/styles/globals.css`                             |
| Create | `frontend/src/styles/ps/` (DS token layer from zip)           |
| Create | `frontend/src/components/ds/` (StatusDot, LogLine, StatPanel) |
| Create | `frontend/src/lib/utils.ts`                                   |
| Modify | `frontend/package.json`                                       |
| Create | `frontend/oxlintrc.json`                                      |

**Work**:

1. `npx shadcn@latest init` (New York, Neutral, CSS variables).
2. Extract `docs/design/PersonalScraper Design System.zip` → copy token layer
   (`tokens.css` or equivalent) to `src/styles/ps/`, import in `globals.css`.
3. Add Geist + Geist Mono woff2 fonts to `src/assets/fonts/` (vendored for
   offline PWA; see Phase 6).
4. Port 3 DS primitives to `src/components/ds/`: **StatusDot**, **LogLine**,
   **StatPanel** — as `.tsx` references from the DS specs (DESIGN §5.1).
5. Wire oxlint with DS adherence config from the zip; add `lint:ds` script.
6. `npx shadcn@latest add` button, card, input, label, table, form, dialog,
   dropdown-menu, avatar, toast, sonner (shell plan needs these; rest per wave).

**Verification**: `cd frontend && npm run lint` → zero errors; `npm run lint:ds`
→ zero errors; `npm run build` → `dist/` output.

### 4.3 — OpenAPI export + typed API client generation

**Commit**: `feat(tm-shell): add OpenAPI export and typed frontend API client`

**Files**:

| Action | Path                           |
| ------ | ------------------------------ |
| Create | `scripts/export-openapi.py`    |
| Create | `frontend/openapi.json`        |
| Create | `frontend/src/api/schema.d.ts` |
| Create | `frontend/src/api/client.ts`   |
| Modify | `frontend/package.json`        |
| Modify | `Makefile`                     |

**Work**:

1. `scripts/export-openapi.py` — boots FastAPI app from `create_app` with a
   dummy `WebConfig`, uses `app.openapi()` to write `frontend/openapi.json`.
   Idempotent: same routes → same JSON (deterministic ordering).
2. Add `openapi-typescript` as dev dep. `npm run gen-api` → regenerates
   `src/api/schema.d.ts`. CI will `git diff --exit-code` on both files.
3. `src/api/client.ts` — typed `fetcher<Path>(path, init?)` wrapping `fetch`
   with `credentials: 'include'`; generic `queryClient` instance exported.
4. `Makefile` — add `make openapi` target (runs `export-openapi.py` +
   `npm run gen-api`).

**Verification**: `make openapi && git diff --exit-code frontend/openapi.json
frontend/src/api/schema.d.ts` → clean.

### 4.4 — CI frontend job

**Commit**: `ci(tm-shell): add frontend job to CI workflow`

**Files**:

| Action | Path                       |
| ------ | -------------------------- |
| Modify | `.github/workflows/ci.yml` |
| Modify | `frontend/package.json`    |

**Work**:

1. `.github/workflows/ci.yml` — add `frontend` job (node 22, runs-on ubuntu-latest):
   - `npm ci` → `npx tsc --noEmit` → `npm run lint` + `npm run lint:ds` →
     `npm run test -- --run` (vitest) → `npm run build`.
   - Needs: `[lint, typecheck]` (fast path: can run in parallel with Python jobs).
   - OpenAPI drift check: run `make openapi` + `git diff --exit-code` on
     `frontend/openapi.json` + `frontend/src/api/schema.d.ts`.
2. `frontend/package.json` — add `"test": "vitest"` if not already.

**Verification**: push to PR → CI `frontend` job green; OpenAPI drift gate
catches stale schema.

## Verification

```bash
make lint && make test                          # backend green
cd frontend && npx tsc --noEmit && npm run lint  # frontend green
make openapi && git diff --exit-code frontend/openapi.json  # schema fresh
```

**Manual checks**: `cd frontend && npm run dev` → Vite dev server on :5173,
proxied `/api/health` reaches backend, login page placeholder visible.
