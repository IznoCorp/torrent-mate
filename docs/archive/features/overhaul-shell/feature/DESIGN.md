# DESIGN — overhaul-shell (Design overhaul V1: shell)

**Wave 1 of 5** of the design overhaul — epic #304, ticket #305.
**Binding shared spec:** `docs/superpowers/specs/2026-07-16-design-overhaul-design.md` — this wave implements
**§1.1 (sidebar sticky · attention badges · width)** under the **§6 sequencing invariant**. On any conflict, the
shared spec wins; on conflict with `docs/reference/product-intent.md`, the constitution wins.
**Constitution served:** §8 (badges = « rien en silence » depuis n'importe quel écran), DOIT-3 (agir là où l'on
observe), DOIT-9 (mobile poste principal), DOIT-10 (aucune URL cassée — cette vague n'en touche aucune).

## Scope (exhaustive — nothing else ships in this wave)

1. **Sticky sidebar** — `Sidebar.tsx` `<aside>` becomes `sticky top-0 h-screen overflow-y-auto` (or equivalent)
   inside the existing `AppShell.tsx` flex shell (`AppShell.tsx:80`). MUST preserve: collapse rail
   (`md:w-16`/`md:w-56`), `tm-sidebar-collapsed` localStorage persistence, `NavSections` reuse in the mobile
   Sheet, `env(safe-area-inset-*)` behavior. Evidence of the defect: `Sidebar.tsx:68-72` (plain flex child, nav
   scrolls away on 4 800–7 276 px pages — findings doc A1).
2. **Attention badges** — extend the existing `badges: Record<path, ReactNode>` mechanism
   (`AppShellInner`, `AppShell.tsx:32-92`, rendered by Sidebar/BottomTabBar/NavSections):
   - `/scraping` badge changes source: **`counts.awaiting_action` alone** (from `GET /api/staging/media`) —
     the field already covers ambiguous + absent + unknown-kind + verify-blocked (`stages.py:118-131`,
     `routes/staging.py:137-138`); do NOT sum pending decisions on top (double count).
   - `/pipeline` badge: running dot when a run is active (from the polled `GET /api/pipeline/status`).
   - `/acquisition` badge: pending wanted count (existing `useWanted` count query pattern).
   - **Refresh:** extend the existing WS listener (currently ItemProgressed `queued_for_decision` only,
     `AppShell.tsx:51-67`) to invalidate the staging-counts query on ItemProgressed status changes and
     run-finished events; fallback poll 60 s. If measurement shows the staging scan is too chatty for badge
     polling, the aggregate `GET /api/attention/counts` (spec §5.3) may ship in this wave — otherwise defer to V2.
   - `NavCountBadge` stays the renderer (hidden at zero).
3. **Width** — main content container max ≈1280 px (from ~1024 px); introduce 2-col grids only where a surface
   already justifies it without redesigning it (this wave does NOT rebuild any page content — that is V2–V5).

## Hard non-goals (sequencing invariant, spec §6)

- **NO route additions/removals/renames**, no redirects, no nav-entry changes (labels, order, grouping stay).
- No page-content redesign (Dashboard/Médias/etc. are V2+).
- No new backend endpoint unless the badge-chattiness measurement forces `GET /api/attention/counts`
  (read-only, typed, `make openapi` if added).

## Acceptance (executable — ACCEPTANCE.md will carry the exact commands)

- Sidebar stays fully visible/scrollable at scroll-bottom of `/maintenance` (tallest page) — Chrome proof.
- `scrollWidth - innerWidth == 0` at 390 px on all routes (iframe harness) — no regression.
- Badges: seeded states (≥1 blocked media, run active, ≥1 pending wanted) each surface their badge from any
  screen; zero states render no badge.
- Collapse rail + persistence still work (`tm-sidebar-collapsed` round-trip).
- Existing suites green: AppShell/nav/router/BottomTabBar tests updated only where badge sources changed.
- Version 0.50.0 served by `/api/version` after deploy (⚠ solidify also targets 0.50.0 on its worktree —
  whichever PR merges second re-bumps; flagged to the operator).

## Proof protocol (per spec §6)

Executed prod déroulé with dated captures + 390 px iframe harness + SW cache-bust
(unregister + `caches.delete`, compare loaded chunk vs no-store `/index.html`).
