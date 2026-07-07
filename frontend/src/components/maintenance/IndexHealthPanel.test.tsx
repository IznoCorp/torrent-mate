import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { IndexHealthPanel } from "@/components/maintenance/IndexHealthPanel";

import type { IndexHealthResponse } from "@/api/client";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

function makeHealth(
  overrides: Partial<IndexHealthResponse> = {},
): IndexHealthResponse {
  return {
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
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Mock the client module
// ---------------------------------------------------------------------------

vi.mock("@/api/client", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    getIndexHealth: vi.fn(),
  };
});

async function mockGetIndexHealth() {
  const mod = await import("@/api/client");
  return mod.getIndexHealth as ReturnType<typeof vi.fn>;
}

function renderPanel(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <IndexHealthPanel />
    </QueryClientProvider>
  );
  render(tree);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(cleanup);

describe("IndexHealthPanel", () => {
  it("affiche les compteurs sans bandeau dégradé quand l'index est sain", async () => {
    const fn = await mockGetIndexHealth();
    fn.mockResolvedValue(makeHealth());
    renderPanel();

    expect(await screen.findByText("1200")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("affiche un bandeau dégradé quand la lecture de l'index a échoué", async () => {
    const fn = await mockGetIndexHealth();
    // A degraded response: the DB file exists but a query failed → zeroed counts
    // plus degraded=true. The panel must NOT present this as a healthy library.
    fn.mockResolvedValue(
      makeHealth({
        items: 0,
        movies: 0,
        shows: 0,
        files: 0,
        size_gb: 0,
        degraded: true,
        error: "no such table: media_item",
      }),
    );
    renderPanel();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/dégradée/i);
    expect(alert).toHaveTextContent("no such table: media_item");
  });
});
