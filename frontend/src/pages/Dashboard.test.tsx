import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EventStreamProvider } from "@/components/EventStreamProvider";
import Dashboard from "@/pages/Dashboard";
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
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.href;
  }
  return input.url;
}

/** A minimal schedulers payload (watcher + one cron). */
const SCHEDULERS = {
  schedulers: [
    {
      name: "personalscraper-watch",
      kind: "watcher",
      display_name: "Surveillance des téléchargements",
      schedule: null,
      enabled: true,
      last_run_at: null,
      last_outcome: null,
    },
    {
      name: "personalscraper-grab",
      kind: "cron",
      display_name: "Récupération (grab)",
      schedule: "Tous les jours à 03:20 et 15:20",
      enabled: null,
      last_run_at: null,
      last_outcome: null,
    },
  ],
};

/** Route ``/api/*`` to their canned payloads. */
function routeFetch(input: RequestInfo | URL): Promise<Response> {
  const url = urlOf(input);
  if (url.includes("/api/version")) {
    return Promise.resolve(
      buildResponse(200, { version: "0.40.0", build_commit: "abcdef1234567" }),
    );
  }
  if (url.includes("/api/maintenance/schedulers")) {
    return Promise.resolve(buildResponse(200, SCHEDULERS));
  }
  return Promise.resolve(
    buildResponse(200, { status: "ok", redis: true, db: true }),
  );
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

/** Render the dashboard behind the router, query, and event-stream providers. */
function renderDashboard(): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <EventStreamProvider>
          <Dashboard />
        </EventStreamProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
  render(tree);
}

describe("Dashboard", () => {
  it("monte les cartes et le panneau planificateurs, sans flux d’événements", async () => {
    renderDashboard();

    // Structure: heading + scheduler overview.
    expect(
      screen.getByRole("heading", { name: "Tableau de bord" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Planificateurs")).toBeInTheDocument();

    // The event feed + recent-events table moved to Maintenance (Phase 5.1) —
    // they must NOT render on the Dashboard anymore.
    expect(screen.queryByText("Flux d’événements")).not.toBeInTheDocument();
    expect(screen.queryByText("Événements récents")).not.toBeInTheDocument();

    // Cards resolve from their queries (Redis online, version rendered).
    expect(await screen.findByText("Redis en ligne")).toBeInTheDocument();
    expect(await screen.findByText("0.40.0")).toBeInTheDocument();

    // Scheduler rows resolve from the mocked payload.
    expect(
      await screen.findByText("Surveillance des téléchargements"),
    ).toBeInTheDocument();
    expect(await screen.findByText("Récupération (grab)")).toBeInTheDocument();
  });
});
