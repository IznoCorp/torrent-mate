import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EventStreamProvider } from "@/components/EventStreamProvider";
import Maintenance from "@/pages/Maintenance";
import { MockWebSocket } from "@/test/mockWebSocket";

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** Resolve the request target to its URL string, across every ``fetch`` input. */
function urlOf(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

/**
 * Route every ``/api/*`` endpoint the Maintenance panels poll to a minimal
 * empty-but-valid payload — the test only asserts the relocated event panels
 * render, so the panel data can be empty.
 */
function routeFetch(input: RequestInfo | URL): Promise<Response> {
  const url = urlOf(input);
  if (url.includes("/api/maintenance/disks")) {
    return Promise.resolve(buildResponse(200, { disks: [] }));
  }
  if (url.includes("/api/maintenance/locks")) {
    return Promise.resolve(
      buildResponse(200, {
        pipeline_lock: { held: false },
        sentinels: {
          pause: false,
          watcher_paused: false,
        },
        sweep: { status: "ready", orphans: [], age_s: 0 },
      }),
    );
  }
  if (url.includes("/api/maintenance/index-health")) {
    return Promise.resolve(
      buildResponse(200, {
        items: 0,
        movies: 0,
        shows: 0,
        files: 0,
        size_gb: 0,
        nfo: { valid: 0, invalid: 0, missing: 0 },
        repair_queue_pending: 0,
        outbox_pending: 0,
        last_scan_stuck: false,
        soft_deleted: 0,
        canonical_null: 0,
        degraded: false,
      }),
    );
  }
  if (url.includes("/api/maintenance/actions")) {
    return Promise.resolve(
      buildResponse(200, { actions: [], category_counts: {} }),
    );
  }
  if (url.includes("/api/pipeline/history")) {
    return Promise.resolve(
      buildResponse(200, { runs: [], total: 0, limit: 50, offset: 0 }),
    );
  }
  return Promise.resolve(buildResponse(200, {}));
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  MockWebSocket.reset();
  fetchMock.mockReset();
  fetchMock.mockImplementation((input) => routeFetch(input));
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** Render the maintenance page behind the router, query, and stream providers. */
function renderMaintenance(): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <EventStreamProvider>
          <Maintenance />
        </EventStreamProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
  render(tree);
}

describe("Maintenance", () => {
  it("rend le flux d’événements et la table récente (relocalisés depuis le tableau de bord)", () => {
    renderMaintenance();

    expect(
      screen.getByRole("heading", { name: "Maintenance" }),
    ).toBeInTheDocument();

    // The relocated event panels (Phase 5.1) render here now.
    expect(screen.getByText("Flux d’événements")).toBeInTheDocument();
    expect(screen.getByText("Événements récents")).toBeInTheDocument();

    // A single shared WebSocket is opened by the provider — no duplicate WS.
    expect(MockWebSocket.instances).toHaveLength(1);
  });
});
