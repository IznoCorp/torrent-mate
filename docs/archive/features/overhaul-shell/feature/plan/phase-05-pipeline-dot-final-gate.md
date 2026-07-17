# Phase 05 — Pipeline dot test + WS refresh test + final gate

## Gate

- [ ] Phase 04 complete: badge test helpers + zero-state + count-based badge tests written.
- [ ] `cd frontend && npm run typecheck` passes.
- [ ] Phase 04's three new badge tests pass; old decisions-based tests are gone.

## Scope

Add the pipeline running-dot badge test and the WS-refresh test to
`AppShell.test.tsx`, then run the full project gate (lint + test + check).

**Files touched:**

- `frontend/src/components/layout/AppShell.test.tsx` — add two tests

### Sub-phase 5.1 — Pipeline dot + WS refresh tests

**Commit:** `test(overhaul-shell): add pipeline running-dot and WS-refresh badge tests`

**Add to the `"AppShell attention badges"` describe block** (after the acquisition
badge test from Phase 04):

```ts
it("affiche un dot Pipeline quand le pipeline est en cours", async () => {
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
        buildResponse(200, pipelineStatusPayload("running")),
      );
    if (url.includes("/api/acquisition/wanted"))
      return Promise.resolve(buildResponse(200, wantedPayload(0)));
    return Promise.resolve(buildResponse(200, {}));
  });
  renderShell();
  const dots = await screen.findAllByLabelText(/Pipeline en cours d/i);
  expect(dots.length).toBeGreaterThanOrEqual(1);
});
```

**Add a WS-refresh test** (replaces the old `queued_for_decision` WS test — the
new listener invalidates staging counts on any `ItemProgressed`):

```ts
it("rafraîchit le badge Scraping sur ItemProgressed WS", async () => {
  let sendCount = 0;
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
      return Promise.resolve(buildResponse(200, stagingPayload(sendCount)));
    if (url.includes("/api/pipeline/status"))
      return Promise.resolve(buildResponse(200, pipelineStatusPayload("idle")));
    if (url.includes("/api/acquisition/wanted"))
      return Promise.resolve(buildResponse(200, wantedPayload(0)));
    return Promise.resolve(buildResponse(200, {}));
  });
  renderShell();
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalled();
  });
  // No badge initially (count = 0).
  expect(
    document.querySelector('[data-slot="nav-count"]'),
  ).not.toBeInTheDocument();

  // Complete WS handshake.
  act(() => {
    latestSocket().emitOpen();
    latestSocket().emitMessage({
      type: "ws.hello",
      data: { build_commit: "test-sha" },
    });
  });

  sendCount = 7;
  // Emit ItemProgressed (any status — new listener catches all).
  act(() => {
    latestSocket().emitMessage({
      id: "1680000000000-1",
      type: "ItemProgressed",
      data: {
        step: "verify",
        status: "blocked",
        staging_path: "/staging/001-MOVIES/Foo (2025)",
      },
    });
  });

  const badges = await screen.findAllByText("7");
  const spans = badges.filter(
    (el) => el.getAttribute("data-slot") === "nav-count",
  );
  expect(spans.length).toBeGreaterThanOrEqual(1);
});
```

### Verification

1. **Lint + typecheck:**

   ```bash
   cd frontend && npm run lint && npm run typecheck
   ```

   Expected: zero errors.

2. **All badge tests pass:**

   ```bash
   cd frontend && npx vitest run src/components/layout/AppShell.test.tsx
   ```

   Expected: 7 tests pass (2 mobile nav Sheet + 5 badge tests).

3. **Commit:**
   ```bash
   git add frontend/src/components/layout/AppShell.test.tsx
   git commit -m "test(overhaul-shell): add pipeline running-dot and WS-refresh badge tests"
   ```

### Sub-phase 5.2 — Final gate (no new commit)

```bash
cd frontend && npm run lint && npm run typecheck && npx vitest run
make lint        # ruff + mypy
make test        # all Python tests (expect ~6000+ passed, 0 failed)
python -c "import personalscraper"  # smoke test
```

All must pass with zero errors. The `make check` gate is the definitive signal.

**Residual import sweep:**

```bash
rg "useDecisions|decisionsKeys" -g '*.tsx' -g '*.ts' frontend/src/components/layout/
```

Expected: zero matches.

## Completeness check

- [ ] Pipeline running-dot test: `StatusDot` visible when `state === "running"`.
- [ ] WS-refresh test: `ItemProgressed` invalidates staging counts → badge updates.
- [ ] `cd frontend && npm run lint && npm run typecheck && npx vitest run` all green.
- [ ] `make lint && make test` green.
- [ ] `python -c "import personalscraper"` succeeds.
- [ ] Zero residual `useDecisions`/`decisionsKeys` references in layout components.
- [ ] Phase gate ready for PR (operator runs Chrome proof per ACCEPTANCE).
