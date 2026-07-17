import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CompactHealth } from "@/components/controle/CompactHealth";

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** Resolve the request target to its URL string. */
function urlOf(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

/** Route fetch calls to canned payloads. */
function routeFetch(input: RequestInfo | URL): Promise<Response> {
  const url = urlOf(input);
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
  if (url.includes("/api/health")) {
    return Promise.resolve(
      buildResponse(200, { status: "ok", redis: true, db: true }),
    );
  }
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
  fetchMock.mockReset();
  fetchMock.mockImplementation((input) => routeFetch(input));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** Render CompactHealth inside the query + router providers. */
function renderCompactHealth(): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <CompactHealth />
      </MemoryRouter>
    </QueryClientProvider>
  );
  render(tree);
}

describe("CompactHealth", () => {
  it("affiche le titre Santé", () => {
    renderCompactHealth();
    expect(screen.getByText("Santé")).toBeInTheDocument();
  });

  it("affiche les disques avec nom et espace libre", async () => {
    renderCompactHealth();
    expect(await screen.findByText("Disk 1")).toBeInTheDocument();
    expect(screen.getByText(/500 Go libre/)).toBeInTheDocument();
  });

  it("affiche le nombre d'items indexés", async () => {
    renderCompactHealth();
    expect(await screen.findByText("1200 items indexés")).toBeInTheDocument();
  });

  it("affiche Redis en ligne", async () => {
    renderCompactHealth();
    expect(await screen.findByText("Redis en ligne")).toBeInTheDocument();
  });

  it("affiche le statut des fournisseurs", async () => {
    renderCompactHealth();
    expect(await screen.findByText("1/1 fournisseurs OK")).toBeInTheDocument();
  });

  it("affiche des liens vers /systeme (systeme-hub)", async () => {
    renderCompactHealth();

    // Disks row → "Détails →" links to /systeme.
    expect(
      await screen.findByRole("link", { name: "Détails →" }),
    ).toHaveAttribute("href", "/systeme");

    // Index row → "Maintenance →" links to /systeme.
    expect(screen.getByRole("link", { name: "Maintenance →" })).toHaveAttribute(
      "href",
      "/systeme",
    );

    // Providers row → "Fournisseurs →" (was "Registre →") links to /systeme.
    expect(
      screen.getByRole("link", { name: "Fournisseurs →" }),
    ).toHaveAttribute("href", "/systeme");
  });
});
