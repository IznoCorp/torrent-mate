/**
 * ScrapeActivityPanel — queued-state visibility (directive 2026-07-15).
 *
 * The #249 post-mortem forbids an invisible queue: a resolve waiting for the
 * pipeline lock must render an explicit « En file — pipeline en cours » pill,
 * distinct from the live-scrape pulse.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/decisions", () => ({
  decisionsKeys: { activity: ["decisions", "activity"] },
  fetchDecisionActivity: vi.fn(),
}));

import { fetchDecisionActivity } from "@/api/decisions";

import { ScrapeActivityPanel } from "./ScrapeActivityPanel";

function renderPanel(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ScrapeActivityPanel />
    </QueryClientProvider>,
  ) as unknown as ReactElement;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ScrapeActivityPanel — file de résolution visible", () => {
  it("rend la pilule « En file — pipeline en cours » pour un scrape en attente", async () => {
    vi.mocked(fetchDecisionActivity).mockResolvedValue({
      in_progress: [
        { decision_id: 1, title: "Lucky", started_at: Date.now() / 1000, queued: true },
        { decision_id: 2, title: "Backrooms", started_at: Date.now() / 1000, queued: false },
      ],
      pending_count: 2,
    });
    renderPanel();

    expect(
      await screen.findByText("En file — pipeline en cours"),
    ).toBeInTheDocument();
    expect(screen.getByText("Lucky")).toBeInTheDocument();
    // The live scrape has NO queue pill.
    expect(screen.getAllByText(/En file — pipeline en cours/)).toHaveLength(1);
    expect(screen.getByText("Backrooms")).toBeInTheDocument();
  });

  it("aucune pilule quand rien n'est en file", async () => {
    vi.mocked(fetchDecisionActivity).mockResolvedValue({
      in_progress: [
        { decision_id: 2, title: "Backrooms", started_at: Date.now() / 1000, queued: false },
      ],
      pending_count: 0,
    });
    renderPanel();

    expect(await screen.findByText("Backrooms")).toBeInTheDocument();
    expect(
      screen.queryByText("En file — pipeline en cours"),
    ).not.toBeInTheDocument();
  });
});
