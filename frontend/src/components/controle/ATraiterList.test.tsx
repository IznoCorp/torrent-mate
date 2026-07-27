/**
 * Unit tests for ATraiterList (control-medias phase 5.2).
 *
 * Mocks useStagingMedia so the blocked-items list, empty state, FR reason
 * display, and resolve links are tested in isolation.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StagingMediaItem, StagingMediaResponse } from "@/api/staging";

const stagingMock = vi.fn();

vi.mock("@/hooks/useStagingMedia", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useStagingMedia: (params: unknown) => stagingMock(params),
}));

import { ATraiterList } from "@/components/controle/ATraiterList";

/** Build a minimal StagingMediaItem with defaults sensible for blocked items. */
function item(overrides: Partial<StagingMediaItem> = {}): StagingMediaItem {
  return {
    id: "abc123",
    category: "001-MOVIES",
    folder: "Fight Club (1999)",
    relative_path: "001-MOVIES/Fight Club (1999)",
    media_kind: "movie",
    title: "Fight Club",
    year: 1999,
    overview: null,
    provider_ids: {},
    match: "matched",
    decision_id: null,
    decision_trigger: null,
    has_nfo: true,
    has_poster: true,
    has_trailer: false,
    poster_url: "/api/staging/media/abc123/poster",
    seasons: null,
    episode_count: null,
    video_count: 1,
    size_bytes: 1_600_000_000,
    modified_at: 1750000000,
    position_stage: "verify",
    position_state: "blocked",
    stages: [
      { key: "arrival", label: "Arrivée", state: "done" },
      { key: "sorting", label: "Tri", state: "done" },
      { key: "cleaning", label: "Nettoyage", state: "done" },
      { key: "matching", label: "Identification", state: "done" },
      { key: "scraping", label: "Scraping", state: "done" },
      { key: "trailers", label: "Bandes-annonces", state: "done" },
      { key: "verify", label: "Vérification", state: "blocked" },
      { key: "dispatch", label: "Dispatch", state: "pending" },
    ],
    blocked_reason: "Bloqué : aucun poster trouvé",
    dispatch_target: null,
    ...overrides,
  };
}

/** Build a StagingMediaResponse with the given items. */
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
      awaiting_action: items.filter((i) => i.position_state === "blocked")
        .length,
    },
    total: items.length,
    page: 1,
    page_size: 100,
  };
}

/** Wrap ATraiterList in required providers. */
function renderList(
  initialEntries: string[] = ["/"],
): ReturnType<typeof render> {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <QueryClientProvider client={qc}>
        <ATraiterList />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  stagingMock.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("ATraiterList", () => {
  it("renders the empty state when no items are blocked", () => {
    stagingMock.mockReturnValue({
      data: response([]),
      isLoading: false,
      isError: false,
    });

    renderList();
    expect(screen.getByText("Rien à traiter")).toBeDefined();
    expect(screen.getByText("À traiter")).toBeDefined();
  });

  it("renders empty state when items exist but none are blocked", () => {
    stagingMock.mockReturnValue({
      data: response([
        item({ position_state: "pending", blocked_reason: null }),
      ]),
      isLoading: false,
      isError: false,
    });

    renderList();
    expect(screen.getByText("Rien à traiter")).toBeDefined();
  });

  it("renders a blocked item with its blocked_reason and media link", () => {
    stagingMock.mockReturnValue({
      data: response([
        item({
          id: "abc123",
          title: "Fight Club",
          match: "matched",
          blocked_reason: "Bloqué : aucun poster trouvé",
          position_state: "blocked",
        }),
      ]),
      isLoading: false,
      isError: false,
    });

    renderList();
    expect(screen.getByText("Fight Club")).toBeDefined();
    // The blocked_reason takes priority over the match-state label.
    expect(screen.getByText("Bloqué : aucun poster trouvé")).toBeDefined();
    const link = screen.getByText("Résoudre →");
    expect(link).toBeDefined();
    expect(link.getAttribute("href")).toBe("/medias?media=abc123");
  });

  it("falls back to match-state label when blocked_reason is absent", () => {
    stagingMock.mockReturnValue({
      data: response([
        item({
          id: "def456",
          title: "Inconnu",
          match: "absent",
          blocked_reason: null,
          position_state: "blocked",
        }),
      ]),
      isLoading: false,
      isError: false,
    });

    renderList();
    expect(screen.getByText("Inconnu")).toBeDefined();
    // matchBadge("absent") → "Non identifié"
    expect(screen.getByText("Non identifié")).toBeDefined();
  });

  it("links ambiguous items to the resolution deck via decision_id", () => {
    stagingMock.mockReturnValue({
      data: response([
        item({
          id: "xyz789",
          title: "Ambigu Movie",
          match: "ambiguous",
          decision_id: 42,
          blocked_reason: null,
          position_state: "blocked",
        }),
      ]),
      isLoading: false,
      isError: false,
    });

    renderList();
    expect(screen.getByText("Ambigu Movie")).toBeDefined();
    // matchBadge("ambiguous") → "À résoudre"
    expect(screen.getByText("À résoudre")).toBeDefined();
    const link = screen.getByText("Résoudre →");
    expect(link).toBeDefined();
    expect(link.getAttribute("href")).toBe("/medias?decision=42");
  });

  it("renders multiple blocked items", () => {
    stagingMock.mockReturnValue({
      data: response([
        item({
          id: "a1",
          title: "Film A",
          blocked_reason: "Bloqué : pas de NFO",
          position_state: "blocked",
        }),
        item({
          id: "a2",
          title: "Film B",
          match: "ambiguous",
          decision_id: 7,
          blocked_reason: null,
          position_state: "blocked",
        }),
      ]),
      isLoading: false,
      isError: false,
    });

    renderList();
    expect(screen.getByText("Film A")).toBeDefined();
    expect(screen.getByText("Film B")).toBeDefined();
    // Two resolve links
    const links = screen.getAllByText("Résoudre →");
    expect(links).toHaveLength(2);
    expect(links[0]?.getAttribute("href")).toBe("/medias?media=a1");
    expect(links[1]?.getAttribute("href")).toBe("/medias?decision=7");
  });

  it("shows the count badge", () => {
    stagingMock.mockReturnValue({
      data: response([
        item({ id: "b1", position_state: "blocked" }),
        item({ id: "b2", position_state: "blocked" }),
      ]),
      isLoading: false,
      isError: false,
    });

    renderList();
    expect(screen.getByText("2")).toBeDefined();
  });

  it("renders loading skeletons", () => {
    stagingMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    renderList();
    const container = screen.getByRole("generic", { busy: true });
    // The aria-busy container should be present (the outer div)
    expect(container).toBeDefined();
  });

  it("renders error state with retry", () => {
    stagingMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("fetch failed"),
    });

    renderList();
    expect(
      screen.getByText("Impossible de charger les éléments à traiter."),
    ).toBeDefined();
    expect(screen.getByText("fetch failed")).toBeDefined();
    expect(screen.getByText("Réessayer")).toBeDefined();
  });
});
