# Phase 03 — Content width

## Gate

- [ ] Phase 02 complete: three badge sources populate from their respective queries.
- [ ] `cd frontend && npm run lint && npm run typecheck && npx vitest run` passes clean (badge tests may fail — Phase 04 fix).

## Scope

Increase the main content container's max-width from ~1024 px to ~1280 px
(spec §1.1, finding A4). No page-content redesign — this is a CSS-only constraint
change on the `<main>` element inside `AppShell.tsx`.

**Files touched:**

- `frontend/src/components/layout/AppShell.tsx` — add `max-w-7xl` to the `<main>` wrapper

### Sub-phase 3.1 — Add `max-w-7xl` + centering to main content

**Commit:** `feat(overhaul-shell): widen main content container to max-w-7xl (~1280px)`

**Change — `frontend/src/components/layout/AppShell.tsx:88`:**

Current `<main>` element:

```tsx
<main className="flex-1 p-4 pb-[calc(env(safe-area-inset-bottom)+5rem)] md:p-6 md:pb-6">
```

Add `max-w-7xl mx-auto w-full` so the content area is capped at 1280 px and
centered on wider viewports:

```tsx
<main className="flex-1 p-4 pb-[calc(env(safe-area-inset-bottom)+5rem)] md:p-6 md:pb-6 max-w-7xl mx-auto w-full">
```

**Why `max-w-7xl` (Tailwind = 1280 px):**

- The spec calls for "max ≈ 1280 px."
- `max-w-7xl` is the closest Tailwind preset (80 rem = 1280 px at default 16 px base).
- `mx-auto` centers the container horizontally.
- `w-full` ensures it occupies 100 % of the available width below the breakpoint.

**No change to sidebar or bottom bar:** The sidebar is a sibling flex child (not
inside `<main>`), so the max-width on `<main>` does not affect it. The bottom
tab bar is `fixed` — also unaffected.

### Verification

1. **Typecheck + lint:**

   ```bash
   cd frontend && npm run typecheck && npm run lint
   ```

   Expected: zero errors. Pure className addition.

2. **Existing tests:**

   ```bash
   cd frontend && npx vitest run
   ```

   Expected: same pass/fail state as Phase 02 gate (no new failures from a className change).

3. **Chrome visual proof (manual):**
   - Open any page on a wide viewport (≥ 1440 px).
   - Content area must be centered and capped at ~1280 px.
   - Mobile (390 px iframe): no change — content already fills the viewport; `max-w-7xl` doesn't clip at narrow widths.

4. **Commit:**
   ```bash
   git add frontend/src/components/layout/AppShell.tsx
   git commit -m "feat(overhaul-shell): widen main content container to max-w-7xl (~1280px)"
   ```

## Completeness check

- [ ] `<main>` has `max-w-7xl mx-auto w-full`.
- [ ] Content centers on viewports > 1280 px.
- [ ] Content fills width on viewports < 1280 px (no premature clamping).
- [ ] Sidebar and bottom tab bar are unaffected.
- [ ] Mobile 390 px iframe: `scrollWidth - innerWidth == 0`.
- [ ] `cd frontend && npm run lint && npm run typecheck` clean.
