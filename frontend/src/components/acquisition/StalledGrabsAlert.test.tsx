/**
 * OverviewPanel — l'alerte « récupéré mais jamais rangé » (§14.1 / §8).
 *
 * Ancre de régression : le wanted #95 est resté parqué à `grabbed` sans que rien ne le
 * signale, jusqu'à ce que l'opérateur pose la question deux heures plus tard.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getOverviewMock, getStalledGrabsMock } = vi.hoisted(() => ({
  getOverviewMock: vi.fn(),
  getStalledGrabsMock: vi.fn(),
}));

vi.mock("@/api/acquisition", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/acquisition")>(
      "@/api/acquisition",
    );
  return {
    ...actual,
    getOverview: getOverviewMock,
    getStalledGrabs: getStalledGrabsMock,
  };
});

import { OverviewPanel } from "./OverviewPanel";

const OVERVIEW = {
  by_status: { dispatched: 3 },
  in_flight: 0,
  stuck: 0,
  stalled_grabs: 0,
  awaiting_resolution: 0,
  watcher_enabled: true,
  last_successful_run_at: 1_700_000_000,
  pending_run: null,
};

const STALLED = {
  items: [
    {
      wanted_id: 95,
      title: "Spider-Man : Brand New Day",
      kind: "movie",
      season: null,
      episode: null,
      info_hash: "1329fe9e",
      release_name:
        "Michael Giacchino Spider-Man_ Brand New Day (Original Motion Picture Soundtrack).2026.WEB.FLAC",
      since: 1_700_000_100,
      reason: "un run s'est terminé depuis l'ingestion sans la ranger",
    },
  ],
};

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

describe("OverviewPanel — alerte grabs en souffrance", () => {
  beforeEach(() => {
    getOverviewMock.mockReset();
    getStalledGrabsMock.mockReset();
    getStalledGrabsMock.mockResolvedValue(STALLED);
  });
  afterEach(cleanup);

  it("alerte, avec la raison ET la release réellement récupérée", async () => {
    getOverviewMock.mockResolvedValue({ ...OVERVIEW, stalled_grabs: 1 });

    renderPanel();

    // Le détail arrive par une requête distincte : on attend qu'il soit peint, sinon on
    // n'éprouve que le compteur — précisément ce que §8 juge insuffisant.
    await waitFor(() => {
      expect(
        screen.getByText(/un run s'est terminé depuis l'ingestion sans la ranger/),
      ).toBeInTheDocument();
    });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(
      "1 acquisition récupérée n'est jamais arrivée en médiathèque",
    );
    // §13 — la release réellement prise, celle qui trahit la bande originale.
    expect(alert).toHaveTextContent(/Original Motion Picture Soundtrack/);
  });

  it("ne montre rien quand rien n'est parqué (une alerte permanente n'alerte plus)", async () => {
    getOverviewMock.mockResolvedValue(OVERVIEW);

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("Dispatchés")).toBeInTheDocument();
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(getStalledGrabsMock).not.toHaveBeenCalled();
  });

  it("n'est jamais masquée par « Rien en vol » quand elle est seule", async () => {
    // Une ligne wanted survit à la disparition de son parcours : le spine peut être vide
    // alors qu'une acquisition est bel et bien parquée.
    getOverviewMock.mockResolvedValue({
      ...OVERVIEW,
      by_status: {},
      stalled_grabs: 1,
    });

    renderPanel();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.queryByText("Rien en vol")).not.toBeInTheDocument();
  });
});
