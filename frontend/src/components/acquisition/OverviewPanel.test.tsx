/**
 * OverviewPanel (provenance F5) — the « état de la machine » rollup.
 *
 * Proves the panel renders the aggregate tiles from GET /overview, deep-links the
 * actionable ones, and shows an empty state when the spine is empty.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getOverviewMock } = vi.hoisted(() => ({ getOverviewMock: vi.fn() }));

vi.mock("@/api/acquisition", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/acquisition")>(
      "@/api/acquisition",
    );
  return { ...actual, getOverview: getOverviewMock };
});

import { OverviewPanel } from "./OverviewPanel";

function renderPanel(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <OverviewPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OverviewPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
  });

  it("renders the rollup tiles and deep-links the actionable ones", async () => {
    getOverviewMock.mockResolvedValue({
      by_status: { grabbed: 2, ingested: 1, scraped: 0, dispatched: 5 },
      in_flight: 3,
      stuck: 1,
      awaiting_resolution: 2,
      watcher_enabled: true,
      last_successful_run_at: 1_700_000_000,
    });
    renderPanel();

    expect(await screen.findByText("En vol")).toBeInTheDocument();
    expect(screen.getByText("Bloqués")).toBeInTheDocument();
    expect(screen.getByText("En attente de résolution")).toBeInTheDocument();
    expect(screen.getByText("Dispatchés")).toBeInTheDocument();

    // The « Bloqués » tile deep-links to the Parcours detail.
    expect(
      screen.getByLabelText("Voir les items bloqués").closest("a"),
    ).toHaveAttribute("href", "/acquisition?tab=parcours");
    // « En attente de résolution » deep-links to the decisions deck.
    expect(
      screen.getByLabelText("Voir les décisions en attente").closest("a"),
    ).toHaveAttribute("href", "/medias");
    expect(screen.getByText(/Veille active/)).toBeInTheDocument();
  });

  it("still renders tiles when the spine is empty but decisions are pending (no under-count)", async () => {
    getOverviewMock.mockResolvedValue({
      by_status: {},
      in_flight: 0,
      stuck: 0,
      awaiting_resolution: 3, // manual-drop decisions, NO spine row
      watcher_enabled: true,
      last_successful_run_at: null,
    });
    renderPanel();
    // Must NOT show the empty state — the 3 pending decisions need attention.
    expect(
      await screen.findByText("En attente de résolution"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Rien en vol")).toBeNull();
  });

  it("shows an empty state when EVERY pillar is zero", async () => {
    getOverviewMock.mockResolvedValue({
      by_status: {},
      in_flight: 0,
      stuck: 0,
      awaiting_resolution: 0,
      watcher_enabled: true,
      last_successful_run_at: null,
    });
    renderPanel();
    expect(await screen.findByText("Rien en vol")).toBeInTheDocument();
  });
});
