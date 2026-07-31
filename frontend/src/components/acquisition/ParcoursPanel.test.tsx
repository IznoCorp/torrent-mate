/**
 * ParcoursPanel (provenance F1) — the acquisition journey view.
 *
 * Proves the panel renders each journey's stage stepper from the API, lighting up
 * the stages actually reached, and shows an empty state when nothing is tracked.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getJourneysMock, rescrapeMock, requeueMock } = vi.hoisted(() => ({
  getJourneysMock: vi.fn(),
  rescrapeMock: vi.fn(),
  requeueMock: vi.fn(),
}));

vi.mock("@/api/acquisition", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/acquisition")>(
      "@/api/acquisition",
    );
  return {
    ...actual,
    getJourneys: getJourneysMock,
    rescrapeJourney: rescrapeMock,
    requeueJourney: requeueMock,
  };
});

import { ParcoursPanel } from "./ParcoursPanel";

function renderPanel(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ParcoursPanel />
      </MemoryRouter>
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
    expect(
      await screen.findByText("Aucun parcours pour l'instant"),
    ).toBeInTheDocument();
  });

  it("shows an actionable 'awaiting' resolution chip linking to the decision deck (F2)", async () => {
    getJourneysMock.mockResolvedValue({
      journeys: [
        {
          info_hash: "abcd1234",
          kind: "movie",
          media_ref: { tvdb_id: null, tmdb_id: 27205, imdb_id: null },
          scraped_ref: null,
          followed_id: null,
          follow_title: "Inception",
          status: "ingested",
          ingest_path: "/stage/Inception",
          current_path: "/stage/Inception",
          dispatch_path: null,
          grabbed_at: 1_700_000_000,
          ingested_at: 1_700_000_100,
          scraped_at: null,
          dispatched_at: null,
          resolution_state: "awaiting",
          decision_id: 7,
          resolution_trigger: "mid_band",
        },
      ],
    });
    renderPanel();
    const chip = await screen.findByText("En attente de résolution");
    expect(chip).toBeInTheDocument();
    // The chip is a link into the resolution deck for this decision.
    expect(chip.closest("a")).toHaveAttribute("href", "/medias?decision=7");
  });

  it("deep-links a completed stage chip to the run that did it (F3)", async () => {
    getJourneysMock.mockResolvedValue({
      journeys: [
        {
          info_hash: "abcd1234",
          kind: "movie",
          media_ref: { tvdb_id: null, tmdb_id: 27205, imdb_id: null },
          scraped_ref: null,
          followed_id: null,
          follow_title: "Inception",
          status: "scraped",
          ingest_path: "/stage/Inception",
          current_path: "/stage/Inception",
          dispatch_path: null,
          grabbed_at: 1_700_000_000,
          ingested_at: 1_700_000_100,
          scraped_at: 1_700_000_200,
          dispatched_at: null,
          scrape_run_uid: "run-abc-123",
        },
      ],
    });
    renderPanel();
    const scraped = await screen.findByText(/Scrapé/);
    // The « Scrapé » chip links to the run that scraped it.
    expect(scraped.closest("a")).toHaveAttribute(
      "href",
      "/pipeline?run=run-abc-123",
    );
    // « Récupéré » has no grab_run_uid here → not a link.
    expect(screen.getByText(/Récupéré/).closest("a")).toBeNull();
  });

  it("shows a terminal 'Résolu' marker when the decision was resolved (F2)", async () => {
    getJourneysMock.mockResolvedValue({
      journeys: [
        {
          info_hash: "beef5678",
          kind: "movie",
          media_ref: { tvdb_id: null, tmdb_id: 1, imdb_id: null },
          scraped_ref: null,
          followed_id: null,
          follow_title: "Resolved Movie",
          status: "scraped",
          ingest_path: "/stage/R",
          current_path: "/stage/R",
          dispatch_path: null,
          grabbed_at: 1_700_000_000,
          ingested_at: 1_700_000_100,
          scraped_at: 1_700_000_200,
          dispatched_at: null,
          resolution_state: "resolved",
          decision_id: 9,
          resolution_trigger: "ambiguous",
        },
      ],
    });
    renderPanel();
    expect(await screen.findByText("Résolu")).toBeInTheDocument();
  });
});

describe("ParcoursPanel — F4 actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
  });

  const stuckJourney = {
    info_hash: "beef",
    kind: "movie",
    media_ref: { tvdb_id: null, tmdb_id: 1, imdb_id: null },
    scraped_ref: null,
    followed_id: null,
    follow_title: "Stuck Movie",
    status: "ingested",
    ingest_path: "/stage/S",
    current_path: "/stage/S",
    dispatch_path: null,
    grabbed_at: 1_700_000_000,
    ingested_at: 1_700_000_100,
    scraped_at: null,
    dispatched_at: null,
    stuck: true,
  };

  it("shows the Bloqué badge + action buttons on a stuck in-flight item, and triggers rescrape", async () => {
    getJourneysMock.mockResolvedValue({ journeys: [stuckJourney] });
    rescrapeMock.mockResolvedValue({ run_uid: "r1" });
    renderPanel();

    expect(await screen.findByText("Bloqué")).toBeInTheDocument();
    const rescrapeBtn = screen.getByRole("button", { name: "Re-scraper" });
    expect(rescrapeBtn).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Requeue" })).toBeInTheDocument();

    fireEvent.click(rescrapeBtn);
    await waitFor(() => {
      expect(rescrapeMock).toHaveBeenCalledWith("beef");
    });
  });

  it("hides the action buttons on a dispatched (terminal) item", async () => {
    getJourneysMock.mockResolvedValue({
      journeys: [
        {
          ...stuckJourney,
          info_hash: "done",
          status: "dispatched",
          dispatch_path: "/Volumes/D/x",
          dispatched_at: 1_700_000_300,
          stuck: false,
        },
      ],
    });
    renderPanel();
    await screen.findByText("Stuck Movie");
    expect(screen.queryByRole("button", { name: "Re-scraper" })).toBeNull();
  });
});
