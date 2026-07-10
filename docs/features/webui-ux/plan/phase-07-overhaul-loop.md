# Phase 7 — Full-interface UX overhaul loop (Part B)

Iterative Chrome-on-staging redesign of **every** page against the "perfect" rubric, run after
Part A. This phase is a **loop**, not a fixed edit set: each sub-phase audits one surface, redesigns
it, and re-tests on staging until it passes all 5 rubric points at mobile (~375px) + desktop
(~1280px+).

## Gate

- Every page passes the rubric at 375px + 1280px on `tm-staging.iznogoudatall.xyz` (screenshots).
- `npm run lint && typecheck && vitest run` green; `make check` green if any backend touched;
  `make openapi` committed on any route change.
- Zero console errors on any page; consistent shell/nav/card/table/badge conventions across pages.

## Rubric (per-page ACCEPTANCE — from DESIGN Part B)

1. Design system respected (shadcn, consistent tokens, no ad-hoc styles).
2. Responsive/PWA — no overflow/clip at 375px; usable ≥1280px; adequate touch targets.
3. Ergonomics — obvious primary action; guarded destructive actions; loading/error/EMPTY states;
   sensible hierarchy; no dead-ends.
4. Consistency across pages (shared header/nav; uniform card/table/badge).
5. No broken UX — inline validation, action feedback, zero console errors.

## 7.0 — Staging preview + Chrome auth harness

Push `feat/webui-ux` → `staging` branch (autodeploy), confirm health, establish the Chrome session
(forged `tm_session` cookie from `.env WEB_JWT_SECRET`, sub = `config/web.json5` username, OR the
login form). Capture a baseline screenshot set (all pages, both widths) → the audit backlog.

## 7.1 — App shell / nav

Header, sidebar/nav, responsive drawer, active-route state, footer/version. Fix consistency +
mobile drawer ergonomics. Basis for every other page.

## 7.2 — Login

Centered card, error state, loading, mobile. Simplest page — sets the visual baseline.

## 7.3 — Dashboard

Health + Version cards + Schedulers panel (post Phase 5). Grid, spacing, empty states.

## 7.4 — Pipeline

Interpreted logs + accordion + triggers legend + last-report (post Phase 2). Layout + live-update
ergonomics.

## 7.5 — Maintenance

Panels grid + StatPanels (post Phase 1) + relocated event feed/table (post Phase 5) + actions
catalog. Desktop density + mobile stacking.

## 7.6 — Registry

Provider cards + grouped sub-circuits (post Phase 1) + latency/health. Card consistency.

## 7.7 — Config

Redesigned SchemaForm (post Phase 3) + FileList + Secrets. The hardest page — deep responsive audit.

## 7.8 — Decisions / Scraping

Flat list + filters + detail (post Phase 4). List/detail responsive behaviour + inline actions.

## 7.9 — Acquisition

Suivis/Recherches/Obligations/Watcher panels (S7). Tables + empty states + mobile.

## Loop protocol (each 7.x)

1. Deploy current branch → staging → wait for health.
2. Chrome: navigate the page; screenshot 375px + 1280px; read console.
3. Assess vs rubric → concrete findings list.
4. Fix (frontend; backend only where a display gap requires it) → local gates → commit → redeploy.
5. Re-test → repeat until the page passes all 5 points.

Findings needing backend work become explicit tracked items (never silently deferred —
`feedback_nothing_out_of_scope_without_signoff`).
