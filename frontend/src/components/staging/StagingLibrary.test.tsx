/**
 * Unit tests for StagingLibrary (webui-overhaul OBJ2A staging library grid).
 *
 * Mocks useStagingMedia so the grid rendering, match-filter chips, loading /
 * error / empty branches, and the card→detail drawer are tested in isolation.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StagingMediaItem, StagingMediaResponse } from "@/api/staging";

const stagingMock = vi.fn();

vi.mock("@/hooks/useStagingMedia", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useStagingMedia: (params: unknown) => stagingMock(params),
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
    position_stage: "dispatch",
    position_state: "pending",
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
function renderLib(
  initialEntries: string[] = ["/scraping"],
): ReturnType<typeof render> {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <QueryClientProvider client={qc}>
        <StagingLibrary />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  stagingMock.mockReturnValue({
    data: response([
      item(),
      item({
        id: "def456",
        folder: "Unknown (2020)",
        title: "Unknown",
        match: "absent",
        has_nfo: false,
      }),
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

  it("always requests the dispatch preview (A2) and toggles the trailer filter (A1)", () => {
    renderLib();

    // A2: with_dispatch is always on so the detail drawer's dispatch preview renders.
    const initial = stagingMock.mock.calls.at(-1)?.[0] as Record<
      string,
      unknown
    >;
    expect(initial.with_dispatch).toBe(true);
    expect(initial.missing_trailer).toBeUndefined();

    // A1: clicking "Sans bande-annonce" adds missing_trailer=true to the query.
    fireEvent.click(screen.getByText("Sans bande-annonce"));
    const after = stagingMock.mock.calls.at(-1)?.[0] as Record<string, unknown>;
    expect(after.missing_trailer).toBe(true);
    expect(after.with_dispatch).toBe(true);
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

  it("gives the 'À résoudre' chip a warning tone when ambiguities are pending (C18)", () => {
    stagingMock.mockReturnValue({
      data: response([
        item({ id: "amb1", title: "Ambiguous One", match: "ambiguous" }),
      ]),
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderLib();
    // Both the filter chip and the ambiguous card carry "À résoudre"; the chip
    // is the one with aria-pressed.
    const chip = screen
      .getAllByRole("button", { name: /À résoudre/ })
      .find((b) => b.hasAttribute("aria-pressed"));
    // The Badge wears the warning tone (its DS class references --warning).
    expect(chip?.querySelector("span")?.className).toMatch(/--warning/);
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
    expect(screen.queryAllByText("An insomniac forms a club.")).toHaveLength(0);
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

  it("opens the detail directly from a ?media= URL param — it is a route (#20)", () => {
    // Deep-linking the media id opens the detail with no click, so the browser
    // Back button (which drops the param) closes it like any route.
    renderLib(["/scraping?media=abc123"]);
    expect(screen.getByText("Parcours pipeline")).toBeInTheDocument();
  });

  it("offers manual resolution on a non-identified item's detail", () => {
    renderLib();
    fireEvent.click(screen.getByRole("button", { name: /Unknown/ }));
    // An 'absent' movie has no auto-match → a manual-resolve action to the deck.
    expect(
      screen.getByRole("button", {
        name: /Rechercher \/ résoudre manuellement/,
      }),
    ).toBeInTheDocument();
  });

  it("shows the D3 not-found notice for an absent ?media=, then clears it when a card is clicked", () => {
    // Start with a ?media= param pointing to an id not in the current data.
    renderLib(["/scraping?media=nonexistent"]);

    // The honest "not found" notice is shown so the operator knows the param
    // was not silently ignored.
    expect(
      screen.getByText(/Média introuvable sur cette page/),
    ).toBeInTheDocument();

    // Clicking a visible card clears the notice (the find succeeds now) and
    // opens the detail sheet.
    fireEvent.click(screen.getByRole("button", { name: /Fight Club/ }));
    expect(
      screen.queryByText(/Média introuvable sur cette page/),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Parcours pipeline")).toBeInTheDocument();
  });
});
