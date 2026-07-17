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

/** Empty staging media response — no blocked items (ATraiterList). */
const EMPTY_STAGING = {
  items: [],
  total: 0,
  page: 1,
  page_size: 100,
};

/** Minimal pipeline history response — no runs yet. */
const EMPTY_HISTORY = { runs: [], total: 0 };

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
  // Control-station panels (A3): each self-contained card fetches its own
  // endpoint — serve minimal well-shaped payloads.
  if (url.includes("/api/pipeline/status")) {
    return Promise.resolve(
      buildResponse(200, {
        state: "idle",
        paused: false,
        watcher_enabled: true,
      }),
    );
  }
  if (url.includes("/api/pipeline/stages")) {
    return Promise.resolve(
      buildResponse(200, { stages: [], run_processed: null }),
    );
  }
  if (url.includes("/api/pipeline/history")) {
    return Promise.resolve(buildResponse(200, EMPTY_HISTORY));
  }
  if (url.includes("/api/acquisition/wanted")) {
    return Promise.resolve(
      buildResponse(200, { items: [], total: 4, page: 1, page_size: 1 }),
    );
  }
  if (url.includes("/api/acquisition/downloads")) {
    return Promise.resolve(
      buildResponse(200, {
        downloads: [
          { name: "A", state: "downloading", progress: 0.4 },
          { name: "B", state: "uploading", progress: 1 },
        ],
        client_available: true,
      }),
    );
  }
  if (url.includes("/api/acquisition/status")) {
    return Promise.resolve(
      buildResponse(200, {
        watcher_enabled: true,
        last_successful_run_at: null,
        recent_runs: [],
        deferred: [{ name: "C", reason: "ratio_below_threshold" }],
      }),
    );
  }
  if (url.includes("/api/maintenance/disks")) {
    return Promise.resolve(
      buildResponse(200, {
        disks: [
          {
            id: "disk_1",
            label: "Disk 1",
            mounted: true,
            free_gb: 500.0,
            total_gb: 1000.0,
            used_pct: 50.0,
          },
        ],
      }),
    );
  }
  if (url.includes("/api/maintenance/index-health")) {
    return Promise.resolve(
      buildResponse(200, {
        items: 1200,
        movies: 800,
        shows: 400,
        files: 3400,
        size_gb: 4200.5,
        nfo: { valid: 1150, invalid: 30, missing: 20 },
        repair_queue_pending: 0,
        repair_queue_oldest_age_s: null,
        outbox_pending: 0,
        outbox_oldest_age_s: null,
        last_scan_id: 42,
        last_scan_mode: "full",
        last_scan_status: "ok",
        last_scan_started_at: null,
        last_scan_finished_at: null,
        last_scan_stuck: false,
        soft_deleted: 0,
        canonical_null: 0,
        degraded: false,
        error: null,
      }),
    );
  }
  // ATraiterList → GET /api/staging/media
  if (url.includes("/api/staging/media")) {
    return Promise.resolve(buildResponse(200, EMPTY_STAGING));
  }
  // ScrapeActivityPanel → GET /api/decisions/activity
  if (url.includes("/api/decisions/activity")) {
    return Promise.resolve(buildResponse(200, { active: [], queue_size: 0 }));
  }
  // CompactHealth → GET /api/registry/status
  if (url.includes("/api/registry/status")) {
    return Promise.resolve(
      buildResponse(200, {
        providers: [
          {
            provider_name: "tmdb",
            circuit_state: "closed",
            failure_count_recent: 0,
            last_failure_at: null,
            last_latency_ms: 45.2,
            last_success_at: Date.now() / 1000,
            live: true,
          },
        ],
      }),
    );
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

describe("Contrôle", () => {
  it("affiche le titre Contrôle et le panneau planificateurs", async () => {
    renderDashboard();

    expect(
      screen.getByRole("heading", { name: "Contrôle" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Acquisitions & planificateurs"),
    ).toBeInTheDocument();

    // The event feed + recent-events table moved to Maintenance (Phase 5.1) —
    // they must NOT render on the Dashboard anymore.
    expect(screen.queryByText("Flux d'événements")).not.toBeInTheDocument();
    expect(screen.queryByText("Événements récents")).not.toBeInTheDocument();

    // CompactHealth renders health rows (Redis, index, disks, providers).
    expect(await screen.findByText("Redis en ligne")).toBeInTheDocument();
    expect(screen.getByText("Santé")).toBeInTheDocument();

    // LastRunDigest shows the empty state (no history yet).
    expect(
      screen.getByText("Aucun run enregistré pour le moment."),
    ).toBeInTheDocument();

    // Scheduler rows resolve from the mocked payload.
    expect(
      await screen.findByText("Surveillance des téléchargements"),
    ).toBeInTheDocument();
    expect(await screen.findByText("Récupération (grab)")).toBeInTheDocument();
  });

  it("est un poste de contrôle : contrôles pipeline + acquisitions + santé + disques (A3)", async () => {
    renderDashboard();

    // Pipeline controls are usable from home (idle status → « Démarrer »).
    expect(await screen.findByText("Démarrer")).toBeInTheDocument();

    // Acquisitions glance: pending (total=4), in-progress downloads (1 of the
    // 2 canned rows has progress < 1), deferred torrent surfaced.
    expect(
      await screen.findByText(/4 épisodes en attente/),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 téléchargement en cours/)).toBeInTheDocument();
    expect(screen.getByText(/1 torrent différé/)).toBeInTheDocument();

    // CompactHealth resolves disks + index from their endpoints.
    expect(await screen.findByText("Santé")).toBeInTheDocument();
    expect(screen.getByText("Disk 1")).toBeInTheDocument();
    expect(screen.getByText("1200 items indexés")).toBeInTheDocument();
  });

  it("affiche la liste À traiter (vide par défaut)", async () => {
    renderDashboard();

    // Even when empty, ATraiterList renders a calm row.
    expect(await screen.findByText("Rien à traiter")).toBeInTheDocument();
  });
});
