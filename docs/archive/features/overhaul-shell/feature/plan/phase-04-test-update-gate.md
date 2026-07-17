# Phase 04 — Test update (badge helpers + count-based badges)

## Gate

- [ ] Phase 03 complete: main content has `max-w-7xl`.
- [ ] All three phases' commits are on `feat/overhaul-shell`.
- [ ] `cd frontend && npm run typecheck` passes.

## Scope

Replace the decisions-based test helpers and assertions in `AppShell.test.tsx`
with mocks for the three new badge data sources (staging, pipeline, acquisition).
This phase covers helper payloads + zero-state + count-based badge tests
(scraping and acquisition). The pipeline dot test and WS refresh test ship in
Phase 05.

**Files touched:**

- `frontend/src/components/layout/AppShell.test.tsx` — partial rewrite

### Sub-phase 4.1 — Replace badge test helpers + zero-state + scraping/acquisition badge tests

**Commit:** `test(overhaul-shell): update AppShell badge tests for staging/acquisition count badges`

**Changes in `AppShell.test.tsx`:**

**1. Remove `decisionsPayload` (lines 29-37).** Replace with three new helpers:

```ts
function stagingPayload(awaitingAction: number): Record<string, unknown> {
  return {
    items: [],
    counts: {
      total: awaitingAction,
      matched: 0,
      ambiguous: 0,
      absent: 0,
      scraped: 0,
      with_trailer: 0,
      awaiting_action: awaitingAction,
    },
    total: 0,
    page: 1,
    page_size: 1,
  };
}

function pipelineStatusPayload(state: string): Record<string, unknown> {
  return {
    state,
    run_uid: state !== "idle" ? "test-run-uid" : null,
    step: null,
    paused: false,
    watcher_enabled: false,
    pid: null,
  };
}

function wantedPayload(total: number): Record<string, unknown> {
  return { items: [], total, page: 1, page_size: 1 };
}
```

**2. Replace the `"AppShell pending-count badge"` describe block** (lines 137-267):
Begin with a `beforeEach` that stubs all three queries defaulting to zero/idle:

```ts
describe("AppShell attention badges", () => {
  beforeEach(() => {
    fetchMock.mockImplementation((input) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      if (url.includes("/api/auth/me"))
        return Promise.resolve(buildResponse(200, { username: "izno" }));
      if (url.includes("/api/staging/media") && url.includes("page_size=1"))
        return Promise.resolve(buildResponse(200, stagingPayload(0)));
      if (url.includes("/api/pipeline/status"))
        return Promise.resolve(
          buildResponse(200, pipelineStatusPayload("idle")),
        );
      if (url.includes("/api/acquisition/wanted"))
        return Promise.resolve(buildResponse(200, wantedPayload(0)));
      return Promise.resolve(buildResponse(200, {}));
    });
  });

  it("n'affiche aucun badge quand tous les compteurs sont à zéro", async () => {
    renderShell();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    expect(
      document.querySelector('[data-slot="nav-count"]'),
    ).not.toBeInTheDocument();
  });

  it("affiche un badge Scraping avec awaiting_action", async () => {
    fetchMock.mockImplementation((input) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      if (url.includes("/api/auth/me"))
        return Promise.resolve(buildResponse(200, { username: "izno" }));
      if (url.includes("/api/staging/media") && url.includes("page_size=1"))
        return Promise.resolve(buildResponse(200, stagingPayload(4)));
      if (url.includes("/api/pipeline/status"))
        return Promise.resolve(
          buildResponse(200, pipelineStatusPayload("idle")),
        );
      if (url.includes("/api/acquisition/wanted"))
        return Promise.resolve(buildResponse(200, wantedPayload(0)));
      return Promise.resolve(buildResponse(200, {}));
    });
    renderShell();
    const badges = await screen.findAllByText("4");
    const spans = badges.filter(
      (el) => el.getAttribute("data-slot") === "nav-count",
    );
    expect(spans.length).toBeGreaterThanOrEqual(1);
  });

  it("affiche un badge Acquisition avec le pending wanted", async () => {
    fetchMock.mockImplementation((input) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      if (url.includes("/api/auth/me"))
        return Promise.resolve(buildResponse(200, { username: "izno" }));
      if (url.includes("/api/staging/media") && url.includes("page_size=1"))
        return Promise.resolve(buildResponse(200, stagingPayload(0)));
      if (url.includes("/api/pipeline/status"))
        return Promise.resolve(
          buildResponse(200, pipelineStatusPayload("idle")),
        );
      if (url.includes("/api/acquisition/wanted"))
        return Promise.resolve(buildResponse(200, wantedPayload(3)));
      return Promise.resolve(buildResponse(200, {}));
    });
    renderShell();
    const badges = await screen.findAllByText("3");
    const spans = badges.filter(
      (el) => el.getAttribute("data-slot") === "nav-count",
    );
    expect(spans.length).toBeGreaterThanOrEqual(1);
  });
});
```

**3. Keep mobile nav Sheet tests (lines 91-135) unchanged.**

### Verification

1. **Lint + typecheck:**

   ```bash
   cd frontend && npm run lint && npm run typecheck
   ```

   Expected: zero errors.

2. **Run badge tests:**

   ```bash
   cd frontend && npx vitest run src/components/layout/AppShell.test.tsx
   ```

   Expected: old badge tests fail (still searching for `/api/decisions` mock), NEW
   badge tests (3 tests in the `"AppShell attention badges"` block) pass. The
   "mobile nav Sheet" tests (2) also pass. Total: 5 pass, 3 fail (the old
   decisions-based tests in the `"AppShell pending-count badge"` block).

   > Note: the old describe block is fully replaced — there should be no residual
   > decisions tests. If `vitest` still sees the old block, the replacement was
   > incomplete. Verify with `rg "pending-count badge" -g '*.tsx' frontend/src/`
   > → zero matches after the edit.

3. **Commit:**
   ```bash
   git add frontend/src/components/layout/AppShell.test.tsx
   git commit -m "test(overhaul-shell): update badge tests for staging/acquisition count badges"
   ```

## Completeness check

- [ ] `decisionsPayload` helper removed; `stagingPayload`, `pipelineStatusPayload`, `wantedPayload` added.
- [ ] Old `"AppShell pending-count badge"` describe block fully replaced.
- [ ] Three new tests: zero-count, scraping badge (awaiting_action=4), acquisition badge (pending wanted=3).
- [ ] Mobile nav Sheet tests preserved.
- [ ] `cd frontend && npm run lint && npm run typecheck` clean.
