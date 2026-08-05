/**
 * ParcoursPanel — le nom de la release réellement récupérée (§13).
 *
 * Ancre de régression : le 2026-08-05, la carte de « Spider-Man : Brand New Day »
 * affichait le titre du FILM suivi au-dessus d'un stepper « Ingéré », alors que ce qui
 * se trouvait en staging était l'album `Michael Giacchino … Original Motion Picture
 * Soundtrack … FLAC`. Rien dans l'interface ne permettait de voir la différence.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getJourneysMock } = vi.hoisted(() => ({ getJourneysMock: vi.fn() }));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

vi.mock("@/api/acquisition", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/acquisition")>(
      "@/api/acquisition",
    );
  return { ...actual, getJourneys: getJourneysMock };
});

import { ParcoursPanel } from "./ParcoursPanel";

const SOUNDTRACK =
  "Michael Giacchino Spider-Man_ Brand New Day (Original Motion Picture Soundtrack).2026.WEB.FLAC";

function journey(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    info_hash: "1329fe9e",
    kind: "movie",
    media_ref: { tvdb_id: null, tmdb_id: 969681, imdb_id: null },
    scraped_ref: null,
    followed_id: 24,
    follow_title: "Spider-Man : Brand New Day",
    status: "ingested",
    ingest_path: null,
    current_path: null,
    dispatch_path: null,
    grabbed_at: 1_700_000_000,
    ingested_at: 1_700_000_100,
    scraped_at: null,
    dispatched_at: null,
    stuck: false,
    ...overrides,
  };
}

function renderPanel(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/acquisition?tab=parcours"]}>
        <ParcoursPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ParcoursPanel — nom de release", () => {
  beforeEach(() => {
    getJourneysMock.mockReset();
  });
  afterEach(cleanup);

  it("affiche la release réellement récupérée, à côté du titre du média suivi", async () => {
    getJourneysMock.mockResolvedValue({
      journeys: [journey({ release_name: SOUNDTRACK })],
    });

    renderPanel();

    // Les DEUX doivent être lisibles : le média voulu ET ce qui a été pris.
    await waitFor(() => {
      expect(screen.getByText(SOUNDTRACK)).toBeInTheDocument();
    });
    expect(screen.getByText("Spider-Man : Brand New Day")).toBeInTheDocument();
  });

  it("dit « inconnue » plutôt que d'afficher le titre du média à la place", async () => {
    getJourneysMock.mockResolvedValue({
      journeys: [journey({ release_name: null })],
    });

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("Release inconnue")).toBeInTheDocument();
    });
  });
});
