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

const { getJourneysMock, rescrapeMock, requeueMock, toastMock } = vi.hoisted(
  () => ({
    getJourneysMock: vi.fn(),
    rescrapeMock: vi.fn(),
    requeueMock: vi.fn(),
    toastMock: {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      warning: vi.fn(),
    },
  }),
);

vi.mock("sonner", () => ({ toast: toastMock }));

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

  it("§14.3 — a rebuilt journey says 'inconnue', never 'not done'", async () => {
    // Un média rangé est FORCÉMENT passé par l'ingestion et le scraping (§14.2). Le
    // backfill §13 ne connaît pas ces instants et les laisse NULL ; sans distinction,
    // le stepper les éteint et dessine un chemin qui ne peut pas exister — « Rangé »
    // posé sur « Ingéré » et « Scrapé » éteints, ce que l'opérateur a vu.
    getJourneysMock.mockResolvedValue({
      journeys: [
        {
          info_hash: "5ea50n",
          kind: "season",
          media_ref: { tvdb_id: 73141, tmdb_id: null, imdb_id: null },
          scraped_ref: null,
          followed_id: 4,
          follow_title: "American Dad!",
          status: "dispatched",
          ingest_path: null,
          current_path: null,
          dispatch_path: "/Volumes/Disk2/series/American Dad! (2005)",
          grabbed_at: 1_700_000_000,
          ingested_at: null,
          scraped_at: null,
          dispatched_at: 1_700_000_900,
          reconstructed_at: 1_785_900_000,
        },
      ],
    });
    renderPanel();
    expect(await screen.findByText("American Dad!")).toBeInTheDocument();
    // Les étapes non datées se DISENT inconnues…
    expect(screen.getByText(/Ingéré · inconnue/)).toBeInTheDocument();
    expect(screen.getByText(/Scrapé · inconnue/)).toBeInTheDocument();
    // …et le parcours annonce qu'il a été reconstruit.
    expect(screen.getByText(/parcours reconstruit/i)).toBeInTheDocument();
  });

  it("a normal journey still shows an unreached stage as unreached", async () => {
    // Le contre-cas : sans lui, « inconnue » pourrait s'afficher partout et le stepper
    // ne dirait plus rien du tout.
    getJourneysMock.mockResolvedValue({
      journeys: [
        {
          info_hash: "abcd1234",
          kind: "episode",
          media_ref: { tvdb_id: 1, tmdb_id: null, imdb_id: null },
          scraped_ref: null,
          followed_id: 1,
          follow_title: "En cours",
          status: "ingested",
          ingest_path: "/stage/x",
          current_path: "/stage/x",
          dispatch_path: null,
          grabbed_at: 1_700_000_000,
          ingested_at: 1_700_000_100,
          scraped_at: null,
          dispatched_at: null,
          reconstructed_at: null,
        },
      ],
    });
    renderPanel();
    expect(await screen.findByText("En cours")).toBeInTheDocument();
    expect(screen.getByText("Rangé")).toBeInTheDocument();
    expect(screen.queryByText(/inconnue/)).toBeNull();
    expect(screen.queryByText(/parcours reconstruit/i)).toBeNull();
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

describe("ParcoursPanel — copie du hash (ACQUISITION-5, ticket 250)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
  });

  /** One in-flight journey whose visible title is the hash fallback. */
  function journeyFixture(): Record<string, unknown> {
    return {
      info_hash: "feedbeef00112233445566778899aabbccddeeff",
      kind: "episode",
      media_ref: { tvdb_id: null, tmdb_id: null, imdb_id: null },
      scraped_ref: null,
      followed_id: null,
      follow_title: null,
      status: "grabbed",
      ingest_path: null,
      current_path: null,
      dispatch_path: null,
      grabbed_at: 1_700_000_000,
      ingested_at: null,
      scraped_at: null,
      dispatched_at: null,
    };
  }

  it("copie l'info_hash complet dans le presse-papiers et le confirme par un toast", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    getJourneysMock.mockResolvedValue({ journeys: [journeyFixture()] });
    renderPanel();

    const btn = await screen.findByRole("button", { name: /Copier le hash/ });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(
        "feedbeef00112233445566778899aabbccddeeff",
      );
    });
    await waitFor(() => {
      expect(toastMock.success).toHaveBeenCalledWith("Hash copié.");
    });
  });

  it("donne au bouton copie le minimum tactile mobile min-h-11 (X4, ticket 250)", async () => {
    getJourneysMock.mockResolvedValue({ journeys: [journeyFixture()] });
    renderPanel();

    const btn = await screen.findByRole("button", { name: /Copier le hash/ });
    // X4: class-presence check (jsdom does not lay out — the real proof at
    // 390px happens post-deploy in Chrome, mobile-truth rule). The button
    // holds the mobile touch minimum and compacts on desktop.
    expect(btn.className).toContain("min-h-11");
    expect(btn.className).toContain("min-w-11");
    expect(btn.className).toContain("md:min-h-8");
    expect(btn.className).toContain("md:min-w-8");
    // The tiny fixed square the finding flagged must be gone.
    expect(btn.className).not.toContain("size-5");
  });

  it("toast d'erreur quand le presse-papiers refuse", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    getJourneysMock.mockResolvedValue({ journeys: [journeyFixture()] });
    renderPanel();

    const btn = await screen.findByRole("button", { name: /Copier le hash/ });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(toastMock.error).toHaveBeenCalledWith("Copie du hash impossible");
    });
    expect(toastMock.success).not.toHaveBeenCalled();
  });
});
