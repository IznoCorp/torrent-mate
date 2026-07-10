# Phase 4 — Frontend page + nav

## Gate

```bash
cd frontend
npm run lint
npm run typecheck
npx vitest run
```

All three must pass with zero errors.

Additionally:

```bash
make openapi   # verify no drift from Phase 2 regen
```

## Objectives

1. Create `frontend/src/pages/RegistryPage.tsx` — the `/registry` page
   replacing the `ComingSoon` stub. Renders one `StatPanel`-style card per
   provider (name, circuit-state badge coloured by state, recent-failure
   count, last success/failure relative time, `last_latency_ms`), plus a
   chain/attempt strip driven by the latest `RegistryFanOutCompleted` event.
2. Replace the `ComingSoon` stub in `frontend/src/router.tsx:63-65` with
   the new `RegistryPage` import and element.
3. Enable the nav entry in `frontend/src/components/layout/nav.ts:81` —
   drop `disabled: true` and `wave: "S6"`.
4. Wire the WS event stream into the page: consume `CircuitBreakerOpened`,
   `CircuitBreakerClosed`, `CircuitBreakerHalfOpened`, and
   `RegistryFanOutCompleted` from `useEventStreamContext()` to
   invalidate/patch the TanStack Query cache live.
5. Create `frontend/src/pages/RegistryPage.test.tsx` — Vitest coverage
   (renders providers, badge colour per state, empty state).

## Files to create

- `frontend/src/pages/RegistryPage.tsx`
- `frontend/src/pages/RegistryPage.test.tsx`

## Files to modify

- `frontend/src/router.tsx` (line ~63-65): replace `ComingSoon` with `RegistryPage` import + element.
- `frontend/src/components/layout/nav.ts` (line ~81): drop `disabled: true` and `wave: "S6"`.

## RegistryPage component (`frontend/src/pages/RegistryPage.tsx`)

Follows the pattern of `frontend/src/pages/Decisions.tsx`: TanStack Query
for initial snapshot, `useEventStreamContext` for live WS patches,
`StatPanel`-style cards, skeleton loading state.

```typescript
/**
 * Registry page — provider health dashboard (``/registry``, S6 reg-health).
 *
 * Renders one card per configured provider with live circuit-breaker state,
 * recent-failure count, last success/failure timestamps, and last call
 * latency.  A chain/attempt strip at the bottom shows the latest fan-out
 * provenance.
 *
 * Reuses:
 * - {@link useRegistryStatus} TanStack Query hook (§3.4)
 * - {@link useEventStreamContext} for live circuit/registry events
 * - {@link StatPanel} for the card primitive
 */

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, type ReactElement } from "react";

import { registryKeys } from "@/api/registry";
import { useRegistryStatus } from "@/hooks/useRegistryStatus";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Event class names the panel listens for (DESIGN §3.4). */
const REGISTRY_EVENT_TYPES = new Set([
  "CircuitBreakerOpened",
  "CircuitBreakerClosed",
  "CircuitBreakerHalfOpened",
  "RegistryFanOutCompleted",
]);

/** Circuit-state → badge variant mapping. */
const CIRCUIT_BADGE: Record<string, "default" | "destructive" | "secondary"> = {
  closed: "default",
  open: "destructive",
  half_open: "secondary",
};

/** Circuit-state → French label. */
const CIRCUIT_LABEL: Record<string, string> = {
  closed: "OK",
  open: "Ouvert",
  half_open: "Semi-ouvert",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format a Unix-epoch float as a relative-time string. */
function relativeTime(epoch: number | null | undefined): string {
  if (epoch == null) return "—";
  const diff = Date.now() - epoch * 1000;
  if (diff < 60_000) return "à l'instant";
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `il y a ${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `il y a ${hours} h`;
  const days = Math.floor(hours / 24);
  return `il y a ${days} j`;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function RegistryPage(): ReactElement {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useRegistryStatus();
  const eventStream = useEventStreamContext();

  // Invalidate the snapshot on any registry/circuit event (DESIGN §3.4).
  useEffect(() => {
    if (!eventStream) return;
    const hasFreshEvent = eventStream.events.some((e) =>
      REGISTRY_EVENT_TYPES.has(e.type),
    );
    if (hasFreshEvent) {
      queryClient.invalidateQueries({ queryKey: registryKeys.status() });
    }
  }, [eventStream, queryClient]);

  // ── Loading ──────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-4 p-4">
        <h1 className="text-2xl font-bold">Registre des fournisseurs</h1>
        {Array.from({ length: 3 }).map((_, idx) => (
          <Skeleton key={`sk-${String(idx)}`} className="h-28 w-full" />
        ))}
      </div>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────
  if (isError || !data) {
    return (
      <div className="p-4">
        <h1 className="text-2xl font-bold">Registre des fournisseurs</h1>
        <p className="mt-4 text-muted-foreground">
          Impossible de charger le statut :{" "}
          {error instanceof Error ? error.message : "Erreur inconnue"}
        </p>
      </div>
    );
  }

  const { providers } = data;

  // ── Empty state ──────────────────────────────────────────────────────
  if (providers.length === 0) {
    return (
      <div className="p-4">
        <h1 className="text-2xl font-bold">Registre des fournisseurs</h1>
        <p className="mt-4 text-muted-foreground">
          Aucun fournisseur configuré.
        </p>
      </div>
    );
  }

  // ── Normal render ────────────────────────────────────────────────────
  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-bold">Registre des fournisseurs</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {providers.map((p) => (
          <Card key={p.provider_name}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-lg">{p.provider_name}</CardTitle>
              <Badge variant={CIRCUIT_BADGE[p.circuit_state] ?? "secondary"}>
                {CIRCUIT_LABEL[p.circuit_state] ?? p.circuit_state}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              {p.degraded ? (
                <p className="text-destructive">État dégradé</p>
              ) : (
                <>
                  <p>Échecs récents : {p.failure_count_recent}</p>
                  <p>Dernier succès : {relativeTime(p.last_success_at)}</p>
                  <p>Dernier échec : {relativeTime(p.last_failure_at)}</p>
                  <p>
                    Latence :{" "}
                    {p.last_latency_ms != null
                      ? `${p.last_latency_ms.toFixed(0)} ms`
                      : "—"}
                  </p>
                </>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

## Router change (`frontend/src/router.tsx`)

Line ~63-65, replace:

```typescript
{
  path: "registry",
  element: <ComingSoon title="Registre" wave="S6" />,
},
```

With:

```typescript
import RegistryPage from "@/pages/RegistryPage";
// ...
{
  path: "registry",
  element: <RegistryPage />,
},
```

Remove the `ComingSoon` import if `/registry` was its last usage —
check if `ComingSoon` is still used for `/acquisition` (line ~68).

## Nav change (`frontend/src/components/layout/nav.ts`)

Line ~81, replace:

```typescript
{ to: "/registry", label: "Registre", icon: Plug, disabled: true, wave: "S6" },
```

With:

```typescript
{ to: "/registry", label: "Registre", icon: Plug },
```

## Vitest tests (`frontend/src/pages/RegistryPage.test.tsx`)

```typescript
/**
 * Vitest tests for the RegistryPage component (reg-health Phase 4).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement } from "react";

import RegistryPage from "./RegistryPage";

// Mock the hook — the page doesn't own data fetching.
vi.mock("@/hooks/useRegistryStatus", () => ({
  useRegistryStatus: vi.fn(),
}));

// Mock the event stream context — the page subscribes.
vi.mock("@/hooks/useEventStreamContext", () => ({
  useEventStreamContext: vi.fn(() => ({ events: [] })),
}));

const { useRegistryStatus } = await import("@/hooks/useRegistryStatus");

function renderPage(): ReturnType<typeof render> {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <RegistryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RegistryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows skeleton while loading", () => {
    vi.mocked(useRegistryStatus).mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    } as ReturnType<typeof useRegistryStatus>);
    renderPage();
    // The page renders <Skeleton> components during loading.
    expect(screen.getByText("Registre des fournisseurs")).toBeDefined();
  });

  it("renders provider cards on success", () => {
    vi.mocked(useRegistryStatus).mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        providers: [
          {
            provider_name: "tmdb",
            circuit_state: "closed",
            failure_count_recent: 0,
            last_success_at: 1719792000.0,
            last_failure_at: null,
            last_latency_ms: 42.5,
            degraded: false,
          },
          {
            provider_name: "tvdb",
            circuit_state: "open",
            failure_count_recent: 5,
            last_success_at: null,
            last_failure_at: 1719705600.0,
            last_latency_ms: null,
            degraded: false,
          },
        ],
      },
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useRegistryStatus>);

    renderPage();

    // Both provider names are rendered.
    expect(screen.getByText("tmdb")).toBeDefined();
    expect(screen.getByText("tvdb")).toBeDefined();

    // Badge labels for each circuit state.
    expect(screen.getByText("OK")).toBeDefined();
    expect(screen.getByText("Ouvert")).toBeDefined();

    // Latency is shown.
    expect(screen.getByText(/42 ms/)).toBeDefined();
  });

  it("renders empty state when no providers", () => {
    vi.mocked(useRegistryStatus).mockReturnValue({
      isLoading: false,
      isError: false,
      data: { providers: [] },
      error: null,
    } as unknown as ReturnType<typeof useRegistryStatus>);

    renderPage();
    expect(screen.getByText("Aucun fournisseur configuré.")).toBeDefined();
  });

  it("shows degraded badge for degraded providers", () => {
    vi.mocked(useRegistryStatus).mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        providers: [
          {
            provider_name: "omdb",
            circuit_state: "open",
            failure_count_recent: 0,
            last_success_at: null,
            last_failure_at: null,
            last_latency_ms: null,
            degraded: true,
          },
        ],
      },
      error: null,
    } as unknown as ReturnType<typeof useRegistryStatus>);

    renderPage();
    expect(screen.getByText("État dégradé")).toBeDefined();
  });

  it("shows error message on fetch failure", () => {
    vi.mocked(useRegistryStatus).mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("Network error"),
    } as unknown as ReturnType<typeof useRegistryStatus>);

    renderPage();
    expect(screen.getByText(/Impossible de charger/)).toBeDefined();
  });
});
```

## Gotchas

- **WS events auto-publish (DESIGN §2)**: `RedisEventPublisher` already
  subscribes to the base `Event` class and publishes every event to the
  Redis stream → WebSocket relay. The page does NOT need to wire any new
  backend WS handler — it only needs to subscribe/react on the frontend
  via `useEventStreamContext()`.

- **Event ring invalidation, not per-provider patch**: the page invalidates
  the entire TanStack Query cache on any registry/circuit event, then
  re-fetches the REST snapshot. This is simpler than per-provider patching
  and consistent with the S2 pipeline pattern (REST snapshot + WS as
  "something changed" signal).

- **`ComingSoon` may still be used by S7 `/acquisition`**: check before
  removing the import from `router.tsx`. If it's still used, keep the
  import and only replace the `/registry` route entry.

- **Nav `disabled` field**: the `NavItem` interface in `nav.ts` supports
  `disabled?: boolean` (line ~27). Dropping `disabled: true` is sufficient
  — the sidebar and bottom tab bar both respect it.

- **Badge variant mapping**: `Closed → "default"` (green/secondary),
  `Open → "destructive"` (red), `HalfOpen → "secondary"` (yellow/neutral).
  These are shadcn/ui `Badge` variants. The exact colours depend on the
  theme — this is DESIGN_CONFORM.

- **`EventMessage.type` is the EventClassName string**: the WS envelope
  carries `{"type": "CircuitBreakerOpened", "data": {...}}`. The
  `useEventStream` hook parses this into `EventMessage` objects with a
  `.type` field. The page filters on the `type` string, exactly as the
  pipeline dashboard does.
