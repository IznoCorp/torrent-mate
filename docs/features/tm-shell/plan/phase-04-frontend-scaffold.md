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
| Create | `frontend/tsconfig.app.json`  |
| Create | `frontend/tsconfig.node.json` |
| Create | `frontend/vite.config.ts`     |
| Create | `frontend/eslint.config.js`   |
| Create | `frontend/index.html`         |
| Create | `frontend/src/main.tsx`       |
| Create | `frontend/src/App.tsx`        |
| Create | `frontend/src/index.css`      |
| Create | `frontend/src/vite-env.d.ts`  |
| Create | `frontend/src/test/setup.ts`  |
| Create | `frontend/src/App.test.tsx`   |
| Create | `frontend/package-lock.json`  |
| Create | `frontend/.gitignore`         |

> **Delivered nuances (2026-07-04, actual scaffold)**
>
> - Split `tsconfig` follows the current Vite convention: root `tsconfig.json` is a
>   solution file referencing `tsconfig.app.json` (src, strict) + `tsconfig.node.json`
>   (`vite.config.ts`). Because the solution config carries `references` (not `include`),
>   `typecheck` uses **`tsc -b --noEmit`** (build mode follows references); bare
>   `tsc --noEmit` on a solution config type-checks nothing.
> - `baseUrl` is **omitted** (TypeScript 6 deprecates it, TS5101); `paths` `@/*` resolves
>   relative to `tsconfig.app.json`.
> - `lint:ds` script is **deferred to 4.2** (it wires the DS-adherence oxlint config from
>   the design-system zip, which does not exist until 4.2). 4.1 ships `lint`/`typecheck`/
>   `test`/`dev`/`build`/`preview` only.
> - Extra required deps beyond the phase draft's list (all standard, non-optional):
>   `@types/react`, `@types/react-dom`, `@types/node`, and `@testing-library/dom` (a
>   required peer of `@testing-library/react` v16). A minimal `src/index.css`,
>   `src/test/setup.ts` (jest-dom matcher registration) and a `src/App.test.tsx` vitest
>   smoke test are added so `npm run test` is meaningful. `package-lock.json` is committed
>   (`npm ci` in later CI/deploy needs it).
> - Pinned to the registry `latest` majors on the dev box: Vite 8, React 19, TypeScript 6,
>   ESLint 10, typescript-eslint 8, Zod 4, Vitest 4 (all peer-compatible).

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

**Verification**: `cd frontend && npm ci && npm run typecheck` (i.e. `tsc -b --noEmit`)
→ exit 0; `npm run lint` → 0 errors; `npm run test -- --run` → pass; `npm run build`
→ `dist/` produced.

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

> **Delivered nuances (2026-07-04, actual 4.2 scaffold)**
>
> - **shadcn hand-authored, not CLI.** Given the 4.1 bleeding-edge stack (Vite 8,
>   TS 6, React 19, Tailwind **v4.3.2**), `npx shadcn@latest init` would re-detect
>   the framework and overwrite the hand-crafted `globals.css` / edit `vite.config.ts`.
>   Components were hand-copied from the registry (current "new-york" `data-slot`
>   function-component pattern, React-19-native, no `forwardRef`) into
>   `src/components/ui/`. Deterministic and lint-clean.
> - **Tailwind v4 via `@tailwindcss/vite`** (no `tailwind.config`). `globals.css`
>   = `@import "tailwindcss"` → `@import "./ps/styles.css"` (DS token layer) →
>   `@theme inline { … }` mapping the DS custom properties into Tailwind's
>   `--color-*` / `--radius-*` / `--font-*` namespaces (per INTEGRATION.md §B.2 note).
>   `main.tsx` now imports `./styles/globals.css`; `src/index.css` removed.
> - **Components delivered:** button, card, input, label, table, dialog,
>   dropdown-menu, avatar, **sonner**. `form` and the deprecated `toast` block are
>   **not** shipped: `toast` is superseded by `sonner`, and shadcn `form` wraps
>   `react-hook-form` while the app uses **TanStack Form** (DESIGN §5.3) — the
>   login form will be built on TanStack Form in phase 5, not shadcn `form`.
> - **`sonner` patched:** upstream reads the theme from `next-themes` (not a dep);
>   pinned `theme="dark"` (DS is dark-first) + DS-var toast surface. `<button>`
>   `destructive` variant maps `text-destructive-foreground` (DS token) rather than
>   upstream's raw `text-white`. Zero `any`; one non-blocking `react-refresh`
>   warning on `button.tsx` (`buttonVariants` co-export — canonical shadcn).
> - **Fonts vendored.** Geist + Geist Mono **variable** woff2 pulled from the
>   `geist` npm package v1.7.2 (jsDelivr) into `src/assets/fonts/`; `tokens/fonts.css`
>   remote Google-Fonts `@import` replaced with local `@font-face` (weight range
>   `100 900`). Two files cover every weight; bundled by Vite into `dist/assets/`.
> - **DS primitives** (`StatusDot`, `LogLine`, `StatPanel`) ported to
>   `src/components/ds/*.tsx` (typed from the `.d.ts` contracts) with a **co-located
>   `.css`** each — the reference `.jsx` injected CSS strings were moved verbatim to
>   real stylesheets (token `var(--…)` refs preserved) so styling stays out of
>   lint-scanned JS and is Vite-bundled on first use. One vitest render test each (3).
> - **oxlint adaptation.** `_adherence.oxlintrc.json` is ESLint-flavoured; oxlint
>   1.72 rejects two things: the `x-omelette` DS-metadata key (unknown field) and
>   the esquery selector rule **`no-restricted-syntax`** (`Rule not found in plugin
>   'eslint'` — oxlint has no esquery engine). Both removed; the supported
>   adherence rules (`no-restricted-imports` internal-import guard,
>   `react/forbid-elements`) + `overrides` are kept, plus `ignorePatterns`
>   (`dist`, `node_modules`). `lint:ds` = `oxlint -c oxlintrc.json src` exits 0.
> - **Adherence fully enforced (same commit, Jul 4).** The token/prop-contract
>   selectors from `_adherence.oxlintrc.json` (`no-restricted-syntax`: raw-hex,
>   raw-px, non-system font-family guards + per-component prop-whitelist and
>   enum-valued-prop constraints — 27 selectors total) were ported to a new
>   ESLint config block (`files: ["src/**/*.{ts,tsx}"]`) in `eslint.config.js`.
>   ESLint's core `no-restricted-syntax` supports esquery natively, so all
>   selectors run under `npm run lint`. **Px adaptation:** the raw-px selector
>   uses `(?<!\[)\b` — negative lookbehind for `[` — to avoid false-positives
>   on Tailwind v4 arbitrary values (`ring-[3px]`, `translate-y-[2px]`). The
>   raw-hex and font-family selectors are ported verbatim. Negative probe
>   confirmed: `style={{color:'#ff0000'}}` → `no-restricted-syntax` error. All
>   gates green (`lint`, `typecheck`, `lint:ds`, `test`).

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
