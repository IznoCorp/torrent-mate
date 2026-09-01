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

import { StalledGrabsAlert } from "./StalledGrabsAlert";

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

function renderAlert(count: number): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <StalledGrabsAlert count={count} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("StalledGrabsAlert — the parked-acquisitions alert", () => {
  beforeEach(() => {
    getOverviewMock.mockReset();
    getStalledGrabsMock.mockReset();
    getStalledGrabsMock.mockResolvedValue(STALLED);
  });
  afterEach(cleanup);

  it("alerte, avec la raison ET la release réellement récupérée", async () => {
    renderAlert(1);

    // Le détail arrive par une requête distincte : on attend qu'il soit peint, sinon on
    // n'éprouve que le compteur — précisément ce que §8 juge insuffisant.
    await waitFor(() => {
      expect(
        screen.getByText(/un run s'est terminé depuis l'ingestion sans la ranger/),
      ).toBeInTheDocument();
    });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(
      "1 acquisition récupérée n'est jamais allée au bout",
    );
    // §13 — la release réellement prise, celle qui trahit la bande originale.
    expect(alert).toHaveTextContent(/Original Motion Picture Soundtrack/);
  });

  it("ne montre rien quand rien n'est parqué (une alerte permanente n'alerte plus)", () => {
    renderAlert(0);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    // The detail list is not even fetched for a zero count.
    expect(getStalledGrabsMock).not.toHaveBeenCalled();
  });

  it("dit quand la liste derrière le compteur n'a pas pu être chargée", async () => {
    // A wanted row can outlive its journey: the count can be non-zero while
    // the LIST read fails. Silence there would render a bare count — §8 wants
    // the failure named.
    getStalledGrabsMock.mockRejectedValue(new Error("boom"));
    renderAlert(2);

    await waitFor(() => {
      expect(
        screen.getByText(/La liste des acquisitions concernées n'a pas pu être chargée/),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
