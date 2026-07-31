/**
 * ParcoursPanel (provenance F1) — the acquisition journey view.
 *
 * Proves the panel renders each journey's stage stepper from the API, lighting up
 * the stages actually reached, and shows an empty state when nothing is tracked.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getJourneysMock } = vi.hoisted(() => ({ getJourneysMock: vi.fn() }));

vi.mock("@/api/acquisition", async () => {
  const actual = await vi.importActual<typeof import("@/api/acquisition")>("@/api/acquisition");
  return { ...actual, getJourneys: getJourneysMock };
});

import { ParcoursPanel } from "./ParcoursPanel";

function renderPanel(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ParcoursPanel />
    </QueryClientProvider>,
  );
}

describe("ParcoursPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
  });

  it("renders a journey with its title and reached stages", async () => {
    getJourneysMock.mockResolvedValue({
      journeys: [
        {
          info_hash: "abcd1234",
          kind: "episode",
          media_ref: { tvdb_id: 382389, tmdb_id: null, imdb_id: null },
          scraped_ref: null,
          followed_id: 12,
          follow_title: "Star Trek: SNW",
          status: "ingested",
          ingest_path: "/stage/Star Trek",
          current_path: "/stage/Star Trek",
          dispatch_path: null,
          grabbed_at: 1_700_000_000,
          ingested_at: 1_700_000_100,
          scraped_at: null,
          dispatched_at: null,
        },
      ],
    });
    renderPanel();
    expect(await screen.findByText("Star Trek: SNW")).toBeInTheDocument();
    // Reached stages present; unreached stage still labelled.
    expect(screen.getByText(/Récupéré/)).toBeInTheDocument();
    expect(screen.getByText(/Ingéré/)).toBeInTheDocument();
    expect(screen.getByText("Rangé")).toBeInTheDocument(); // not reached → bare label, no timestamp
  });

  it("shows an empty state when there are no journeys", async () => {
    getJourneysMock.mockResolvedValue({ journeys: [] });
    renderPanel();
    expect(await screen.findByText("Aucun parcours pour l'instant")).toBeInTheDocument();
  });
});
