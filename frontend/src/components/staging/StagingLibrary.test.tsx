/**
 * Unit tests for StagingLibrary (webui-overhaul OBJ2A staging library grid).
 *
 * Mocks useStagingMedia so the grid rendering, match-filter chips, loading /
 * error / empty branches, and the card→detail drawer are tested in isolation.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StagingMediaItem, StagingMediaResponse } from "@/api/client";

const stagingMock = vi.fn();

vi.mock("@/hooks/useStagingMedia", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useStagingMedia: () => stagingMock(),
}));

import { StagingLibrary } from "@/components/staging/StagingLibrary";

function item(overrides: Partial<StagingMediaItem> = {}): StagingMediaItem {
  return {
    id: "abc123",
    category: "001-MOVIES",
    folder: "Fight Club (1999)",
    relative_path: "001-MOVIES/Fight Club (1999)",
    media_kind: "movie",
    title: "Fight Club",
    year: 1999,
    overview: "An insomniac forms a club.",
    provider_ids: { tmdb: "550" },
    match: "matched",
    decision_id: null,
    decision_trigger: null,
    has_nfo: true,
    has_poster: true,
    has_trailer: true,
    poster_url: "/api/staging/media/abc123/poster",
    seasons: null,
    episode_count: null,
    video_count: 1,
    size_bytes: 1_600_000_000,
    modified_at: 1750000000,
    stages: [
      { key: "arrival", label: "Arrivée", state: "done" },
      { key: "scraping", label: "Scraping", state: "done" },
      { key: "dispatch", label: "Dispatch", state: "pending" },
    ],
    dispatch_target: null,
    ...overrides,
  };
}

function response(items: StagingMediaItem[]): StagingMediaResponse {
  return {
    items,
    counts: {
      total: items.length,
      matched: items.filter((i) => i.match === "matched").length,
      ambiguous: items.filter((i) => i.match === "ambiguous").length,
      absent: items.filter((i) => i.match === "absent").length,
      scraped: items.filter((i) => i.has_nfo).length,
      with_trailer: items.filter((i) => i.has_trailer).length,
      awaiting_action: 0,
    },
    total: items.length,
    page: 1,
    page_size: 24,
  };
}

/** Render StagingLibrary inside a QueryClientProvider (its detail drawer's
 *  manual-resolve action uses a mutation). */
function renderLib(): ReturnType<typeof render> {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <StagingLibrary />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  stagingMock.mockReturnValue({
    data: response([
      item(),
      item({ id: "def456", folder: "Unknown (2020)", title: "Unknown", match: "absent", has_nfo: false }),
    ]),
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("StagingLibrary", () => {
  it("renders a card per media with a match chip", () => {
    renderLib();
    expect(screen.getByText("Fight Club")).toBeInTheDocument();
    expect(screen.getByText("Unknown")).toBeInTheDocument();
    // Match verdict chips on the cards.
    expect(screen.getByText("Identifié")).toBeInTheDocument();
    expect(screen.getByText("Non identifié")).toBeInTheDocument();
  });

  it("shows match filter chips with counts", () => {
    renderLib();
    // "Identifiés (1)" filter chip built from the counts block.
    expect(screen.getByText("Identifiés")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /À résoudre/ })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("toggles a match filter chip to pressed", () => {
    renderLib();
    const chip = screen.getByRole("button", { name: /Non identifiés/ });
    fireEvent.click(chip);
    expect(chip).toHaveAttribute("aria-pressed", "true");
  });

  it("hides overviews when switched to compact density (C17)", () => {
    renderLib();
    // Comfortable by default → overviews are visible.
    expect(
      screen.getAllByText("An insomniac forms a club.").length,
    ).toBeGreaterThan(0);
    // Switching to Compact drops the overviews (denser grid).
    fireEvent.click(screen.getByRole("button", { name: "Compact" }));
    expect(
      screen.queryAllByText("An insomniac forms a club."),
    ).toHaveLength(0);
    // And back to Confortable restores them.
    fireEvent.click(screen.getByRole("button", { name: "Confortable" }));
    expect(
      screen.getAllByText("An insomniac forms a club.").length,
    ).toBeGreaterThan(0);
  });

  it("shows a loading skeleton grid", () => {
    stagingMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    const { container } = renderLib();
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
  });

  it("shows an error state with retry on failure", () => {
    const refetch = vi.fn();
    stagingMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("boom"),
      refetch,
    });
    renderLib();
    fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("shows an empty state when there are no items", () => {
    stagingMock.mockReturnValue({
      data: response([]),
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderLib();
    expect(screen.getByText("Aucun média en attente")).toBeInTheDocument();
  });

  it("opens the detail drawer with the pipeline timeline on card click", () => {
    renderLib();
    fireEvent.click(screen.getByRole("button", { name: /Fight Club/ }));
    // The drawer shows the per-media timeline section.
    expect(screen.getByText("Parcours pipeline")).toBeInTheDocument();
  });

  it("offers manual resolution on a non-identified item's detail", () => {
    renderLib();
    fireEvent.click(screen.getByRole("button", { name: /Unknown/ }));
    // An 'absent' movie has no auto-match → a manual-resolve action to the deck.
    expect(
      screen.getByRole("button", { name: /Rechercher \/ résoudre manuellement/ }),
    ).toBeInTheDocument();
  });
});
