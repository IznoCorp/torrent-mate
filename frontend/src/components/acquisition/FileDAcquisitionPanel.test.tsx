/**
 * Unit tests for the FileDAcquisitionPanel component (Phase 03).
 *
 * Tests the merged "File d'acquisition" panel: grouped wanted searches
 * (status filter + accordion per series/season, DOIT-2 FR status labels) followed
 * by live downloads with the fail-soft « client torrent injoignable » notice
 * (NE-DOIT-PAS-1/5).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

// jsdom polyfill — Radix Select calls scrollIntoView which jsdom doesn't implement.
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

// ---------------------------------------------------------------------------
// Mock hooks + API
// ---------------------------------------------------------------------------

const getWantedMock = vi.fn();
const useDownloadsMock = vi.fn();

vi.mock("@/api/acquisition", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/acquisition")>(
      "@/api/acquisition",
    );
  return {
    ...actual,
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return
    getWanted: (...args: unknown[]) => getWantedMock(...args),
  };
});

vi.mock("@/hooks/useAcquisition", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useDownloads: () => useDownloadsMock(),
  useFollowed: () => ({
    isLoading: false,
    isError: false,
    data: { items: [] },
    error: null,
  }),
  useObligations: () => ({
    isLoading: false,
    isError: false,
    data: { items: [] },
    error: null,
  }),
  useAcquisitionStatus: () => ({
    isLoading: false,
    isError: false,
    data: {
      watcher_enabled: true,
      last_successful_run_at: null,
      recent_runs: [],
      deferred: [],
    },
    error: null,
  }),
  useMediaSearch: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: () => undefined,
  }),
  useFollow: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateFollow: () => ({ mutate: vi.fn(), isPending: false }),
  useUnfollow: () => ({ mutate: vi.fn(), isPending: false }),
  useCompleteness: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }),
  useTrackedAcquisitionRun: () => undefined,
}));

import { FileDAcquisitionPanel } from "@/components/acquisition/FileDAcquisitionPanel";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/** A single wanted item matching WantedItem shape. */
function makeWanted(overrides: Record<string, unknown> = {}) {
  return {
    id: 10,
    title: "Top Chef",
    kind: "episode",
    season: 16,
    episode: 5,
    status: "pending",
    attempts: 0,
    enqueued_at: 1_719_792_000,
    last_search_at: null,
    ...overrides,
  };
}

/** A single download item matching AcquisitionDownload shape. */
function makeDownload(overrides: Record<string, unknown> = {}) {
  return {
    name: "Top.Chef.S16E05.FRENCH.1080p",
    info_hash: "abc123def456",
    state: "downloading",
    progress: 0.45,
    size_bytes: 2_500_000_000,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Render the panel wrapped in a QueryClientProvider. */
function renderPanel(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <FileDAcquisitionPanel />
    </QueryClientProvider>
  );
  render(tree);
}

/** Build a WantedResponse-shaped page. */
function wantedPage(
  items: ReturnType<typeof makeWanted>[],
  total?: number,
): {
  items: ReturnType<typeof makeWanted>[];
  total: number;
  page: number;
  page_size: number;
} {
  return {
    items,
    total: total ?? items.length,
    page: 1,
    page_size: 200,
  };
}

/** Default mock return values: empty wanted + no downloads. */
function mockEmpty(): void {
  getWantedMock.mockResolvedValue(wantedPage([], 0));
  useDownloadsMock.mockReturnValue({
    isLoading: false,
    isError: false,
    data: { downloads: [], client_available: true },
    error: null,
  });
}

/** Mock getWanted to return a single page of wanted items. */
function mockWantedItems(
  items: ReturnType<typeof makeWanted>[],
  total?: number,
): void {
  getWantedMock.mockResolvedValue(wantedPage(items, total));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("FileDAcquisitionPanel", () => {
  // ── Layout: both sections render together ───────────────────────────────

  it("renders both Recherches and Téléchargements sections together (no internal toggle)", () => {
    mockEmpty();
    renderPanel();

    expect(screen.getByText("Recherches")).toBeInTheDocument();
    expect(screen.getByText("Téléchargements")).toBeInTheDocument();
  });

  // ── Recherches section — status filter ──────────────────────────────────

  it("renders the status filter Select with default « Tous »", () => {
    mockEmpty();
    renderPanel();

    // The Select trigger renders the current value label.
    expect(screen.getByText("Statut :")).toBeInTheDocument();
    // The SelectValue shows "Tous" by default (all status).
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("calls getWanted with new status when filter changes", async () => {
    mockEmpty();
    renderPanel();

    // Open the Select dropdown.
    const trigger = screen.getByRole("combobox");
    fireEvent.click(trigger);

    // Select "Abandonné" from the dropdown.
    const abandonedOption = await screen.findByRole("option", {
      name: "Abandonné",
    });
    fireEvent.click(abandonedOption);

    // getWanted should have been called with the new status filter.
    await waitFor(() => {
      expect(getWantedMock).toHaveBeenCalledWith(
        expect.objectContaining({
          status: "abandoned",
          page: 1,
          page_size: 200,
        }),
      );
    });
  });

  // ── Recherches section — grouped accordion ──────────────────────────────

  it("groups wanted items by title → season in expandable accordion", async () => {
    mockEmpty();
    mockWantedItems(
      [
        makeWanted({
          id: 1,
          title: "Top Chef",
          season: 16,
          episode: 1,
          status: "pending",
        }),
        makeWanted({
          id: 2,
          title: "Top Chef",
          season: 16,
          episode: 2,
          status: "pending",
        }),
        makeWanted({
          id: 3,
          title: "Top Chef",
          season: 15,
          episode: 10,
          status: "grabbed",
        }),
        makeWanted({
          id: 4,
          title: "Koh-Lanta",
          season: 30,
          episode: 1,
          status: "pending",
        }),
      ],
      4,
    );
    renderPanel();

    // Series titles appear as accordion triggers (async fetch-all).
    expect(await screen.findByText("Top Chef")).toBeInTheDocument();
    expect(screen.getByText("Koh-Lanta")).toBeInTheDocument();

    // Season + episode counts in the trigger caption.
    expect(screen.getByText(/2 saisons, 3 épisodes/)).toBeInTheDocument();
    expect(screen.getByText(/1 saison, 1 épisode/)).toBeInTheDocument();
  });

  it("expands a series accordion to reveal season sub-groups", async () => {
    mockEmpty();
    mockWantedItems(
      [
        makeWanted({
          id: 1,
          title: "Top Chef",
          season: 16,
          episode: 1,
          status: "pending",
        }),
        makeWanted({
          id: 2,
          title: "Top Chef",
          season: 15,
          episode: 10,
          status: "grabbed",
        }),
      ],
      2,
    );
    renderPanel();

    // Click the accordion trigger to expand (await the async fetch-all).
    const trigger = await screen.findByRole("button", { name: /Top Chef/ });
    fireEvent.click(trigger);

    // Season sub-headings should now be visible.
    expect(screen.getByText(/Saison 16/)).toBeInTheDocument();
    expect(screen.getByText(/Saison 15/)).toBeInTheDocument();

    // Episode rows should be visible.
    expect(screen.getByText("S16E01")).toBeInTheDocument();
    expect(screen.getByText("S15E10")).toBeInTheDocument();
  });

  // ── Episode row: abandoned badge + FR label ─────────────────────────────

  it("renders an abandoned episode row with danger badge + FR label « Abandonné »", async () => {
    mockEmpty();
    mockWantedItems(
      [
        makeWanted({
          id: 99,
          title: "Top Chef",
          season: 16,
          episode: 5,
          status: "abandoned",
          attempts: 0,
        }),
      ],
      1,
    );
    renderPanel();

    // Expand the accordion to see the episodes (await the async fetch-all).
    const trigger = await screen.findByRole("button", { name: /Top Chef/ });
    fireEvent.click(trigger);

    // The "Abandonné" badge must be visible.
    const badge = screen.getByText("Abandonné");
    expect(badge).toBeInTheDocument();
    // The episode row is rendered.
    expect(screen.getByText("S16E05")).toBeInTheDocument();
  });

  // ── Recherches section — empty states ───────────────────────────────────

  it('shows empty text when no wanted items exist (status "all")', async () => {
    mockEmpty();
    renderPanel();

    expect(await screen.findByText(/Aucune recherche en file/)).toBeInTheDocument();
  });

  it("shows filter-specific empty text when a non-all status is selected", async () => {
    mockEmpty();
    renderPanel();

    // Change status to "abandoned". After the filter change the component
    // re-renders with status="abandoned" and the mock still returns empty
    // items → the empty text should be filter-specific (STATUS_LABEL).
    const trigger = screen.getByRole("combobox");
    fireEvent.click(trigger);
    const abandonedOption = await screen.findByRole("option", {
      name: "Abandonné",
    });
    fireEvent.click(abandonedOption);

    // The filter-specific empty text must appear, not the generic one.
    await waitFor(() => {
      expect(
        screen.getByText(/Aucune recherche avec le statut « Abandonné »/),
      ).toBeInTheDocument();
    });
    // The generic empty text must NOT be shown.
    expect(
      screen.queryByText(/Aucune recherche en file/),
    ).not.toBeInTheDocument();
  });

  // ── Recherches section — error states ───────────────────────────────────

  it("shows error message when wanted fetch fails", async () => {
    getWantedMock.mockRejectedValue(new Error("Timeout"));
    useDownloadsMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { downloads: [], client_available: true },
      error: null,
    });
    renderPanel();

    expect(await screen.findByText(/Erreur de chargement/)).toBeInTheDocument();
    expect(screen.getByText(/Timeout/)).toBeInTheDocument();
  });

  // ── Recherches section — loading state ──────────────────────────────────

  it("shows loading skeletons while wanted data loads", () => {
    // Never-resolving promise keeps useQuery in loading state.
    getWantedMock.mockImplementation(() => new Promise(() => undefined));
    useDownloadsMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { downloads: [], client_available: true },
      error: null,
    });
    renderPanel();

    // Skeletons have aria-busy="true".
    const busy = document.querySelector('[aria-busy="true"]');
    expect(busy).toBeInTheDocument();
  });

  // ── Téléchargements section — download rows ─────────────────────────────

  it("renders download rows when downloads are active", () => {
    mockEmpty();
    useDownloadsMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        downloads: [
          makeDownload({
            name: "Top.Chef.S16E05.FRENCH.1080p",
            info_hash: "aaa111",
            state: "downloading",
            progress: 0.45,
          }),
          makeDownload({
            name: "Koh-Lanta.S30E01.FRENCH.720p",
            info_hash: "bbb222",
            state: "uploading",
            progress: 1,
          }),
        ],
        client_available: true,
      },
      error: null,
    });
    renderPanel();

    // Both download names should be visible.
    expect(screen.getByText(/Top\.Chef\.S16E05/)).toBeInTheDocument();
    expect(screen.getByText(/Koh-Lanta\.S30E01/)).toBeInTheDocument();

    // The « client torrent injoignable » notice must NOT appear.
    expect(
      screen.queryByText(/Client torrent injoignable/),
    ).not.toBeInTheDocument();
  });

  // ── Téléchargements — client_available=false notice ─────────────────────

  it("shows « client torrent injoignable » notice when client is down, still lists download rows", () => {
    mockEmpty();
    useDownloadsMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        downloads: [
          makeDownload({
            name: "Top.Chef.S16E05.FRENCH.1080p",
            info_hash: "aaa111",
            state: "downloading",
            progress: 0.45,
          }),
        ],
        client_available: false,
      },
      error: null,
    });
    renderPanel();

    // The fail-soft notice must be visible.
    expect(screen.getByText(/Client torrent injoignable/)).toBeInTheDocument();
    // The download row must STILL be listed (NE-DOIT-PAS-1/5).
    expect(screen.getByText(/Top\.Chef\.S16E05/)).toBeInTheDocument();
  });

  it("does NOT show the notice when client_available is true and downloads exist", () => {
    mockEmpty();
    useDownloadsMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        downloads: [
          makeDownload({
            name: "Top.Chef.S16E05.FRENCH.1080p",
            info_hash: "aaa111",
          }),
        ],
        client_available: true,
      },
      error: null,
    });
    renderPanel();

    expect(
      screen.queryByText(/Client torrent injoignable/),
    ).not.toBeInTheDocument();
  });

  // ── Téléchargements — empty state ───────────────────────────────────────

  it("shows empty state when no downloads are active", () => {
    mockEmpty();
    renderPanel();

    expect(
      screen.getByText(/Aucun téléchargement en cours/),
    ).toBeInTheDocument();
  });

  // ── Téléchargements — loading state ─────────────────────────────────────

  it("shows loading skeletons while downloads load", () => {
    getWantedMock.mockResolvedValue(wantedPage([], 0));
    useDownloadsMock.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });
    renderPanel();

    // Downloads section should show skeletons.
    const sections = screen.getAllByText("Téléchargements");
    expect(sections.length).toBeGreaterThanOrEqual(1);
    const busy = document.querySelectorAll('[aria-busy="true"]');
    expect(busy.length).toBeGreaterThan(0);
  });

  // ── Full-set grouping (pages loop) ──────────────────────────────────────

  it("groups items across multiple pages (fetch-all loop)", async () => {
    // Page 1 returns 200 items of "Top Chef", total=250.
    const page1Items = Array.from({ length: 200 }, (_, i) =>
      makeWanted({
        id: i + 1,
        title: "Top Chef",
        season: 16,
        episode: i + 1,
        status: "pending",
      }),
    );
    getWantedMock
      .mockResolvedValueOnce(wantedPage(page1Items, 250))
      // Page 2 returns 50 items of "Koh-Lanta".
      .mockResolvedValueOnce(
        wantedPage(
          Array.from({ length: 50 }, (_, i) =>
            makeWanted({
              id: 200 + i + 1,
              title: "Koh-Lanta",
              season: 30,
              episode: i + 1,
              status: "pending",
            }),
          ),
          250,
        ),
      );

    renderPanel();

    // Both series should appear (from different pages).
    expect(await screen.findByText("Top Chef")).toBeInTheDocument();
    expect(screen.getByText("Koh-Lanta")).toBeInTheDocument();

    // Two pages were fetched.
    expect(getWantedMock).toHaveBeenCalledTimes(2);
    expect(getWantedMock).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 200 }),
    );
    expect(getWantedMock).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2, page_size: 200 }),
    );

    // Pagination controls are absent (the grouped view has none).
    expect(
      screen.queryByRole("button", { name: /Précédent/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Suivant/ }),
    ).not.toBeInTheDocument();
  });

  // ── Cap notice ───────────────────────────────────────────────────────────

  it("shows cap notice when total exceeds HARD_CAP (1000)", async () => {
    // total=1500, page 1 returns 200 items.
    getWantedMock.mockResolvedValueOnce(
      wantedPage(
        [
          makeWanted({ id: 1, title: "Top Chef", season: 16, episode: 1 }),
          makeWanted({ id: 2, title: "Koh-Lanta", season: 30, episode: 1 }),
        ],
        1500,
      ),
    );

    renderPanel();

    expect(
      await screen.findByText(/Affichage limité aux 1000 premières recherches/),
    ).toBeInTheDocument();
    expect(screen.getByText(/1500 au total/)).toBeInTheDocument();
  });

  it("does NOT show cap notice when total is ≤ 1000", async () => {
    mockWantedItems([makeWanted({ id: 1 })], 500);
    renderPanel();

    await screen.findByText("Top Chef");
    expect(screen.queryByText(/Affichage limité/)).not.toBeInTheDocument();
  });

  // ── Pagination controls absent ───────────────────────────────────────────

  it("does not render any pagination controls in the grouped view", async () => {
    mockWantedItems([makeWanted({ id: 1 })], 1);
    renderPanel();

    await screen.findByText("Top Chef");
    // No Précédent / Suivant buttons.
    expect(
      screen.queryByRole("button", { name: /Précédent/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Suivant/ }),
    ).not.toBeInTheDocument();
  });

  // ── Mutation-proof invariants (sub-phase 5.2) ─────────────────────────────

  it("shows error message for downloads when useDownloads isError, hides calm empty state", () => {
    mockEmpty();
    useDownloadsMock.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("Connexion refusée"),
    });
    renderPanel();

    // FR error message is present.
    expect(screen.getByText(/Erreur de chargement/)).toBeInTheDocument();
    expect(screen.getByText(/Connexion refusée/)).toBeInTheDocument();
    // Calm empty state « Aucun téléchargement en cours » must NOT appear.
    expect(
      screen.queryByText(/Aucun téléchargement en cours/),
    ).not.toBeInTheDocument();
  });

  it("shows « client torrent injoignable » notice when downloads empty and client is down (post-hoist)", () => {
    mockEmpty();
    // downloads=[], client_available=false — notice must still render because
    // it was hoisted above the length>0 guard (F3).
    useDownloadsMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { downloads: [], client_available: false },
      error: null,
    });
    renderPanel();

    // The fail-soft notice is visible even with zero downloads.
    expect(screen.getByText(/Client torrent injoignable/)).toBeInTheDocument();
    // The empty state is also shown (downloads.length === 0).
    expect(
      screen.getByText(/Aucun téléchargement en cours/),
    ).toBeInTheDocument();
  });

  it("renders an abandoned badge with danger tone (not just the FR label)", async () => {
    mockEmpty();
    mockWantedItems(
      [
        makeWanted({
          id: 99,
          title: "Top Chef",
          season: 16,
          episode: 5,
          status: "abandoned",
          attempts: 0,
        }),
      ],
      1,
    );
    renderPanel();

    // Expand the accordion.
    fireEvent.click(await screen.findByRole("button", { name: /Top Chef/ }));

    const badgeEl = screen.getByText("Abandonné");
    expect(badgeEl).toBeInTheDocument();
    // The badge element carries the data-slot and the danger tone class.
    const badgeWrapper = badgeEl.closest('[data-slot="badge"]');
    expect(badgeWrapper).not.toBeNull();
    expect(badgeWrapper?.className).toContain("var(--danger)");
  });

  it("renders « Film » label for kind:movie wanted rows, no « Saison ?? »", async () => {
    mockEmpty();
    mockWantedItems(
      [
        makeWanted({
          id: 50,
          title: "Le Robot sauvage",
          kind: "movie",
          season: null,
          episode: null,
          status: "pending",
        }),
      ],
      1,
    );
    renderPanel();

    // Expand the accordion.
    fireEvent.click(await screen.findByRole("button", { name: /Le Robot sauvage/ }));

    // Group heading reads « Film (1) » (not « Saison ?? »).
    expect(screen.getByText(/Film \(1\)/)).toBeInTheDocument();
    expect(screen.queryByText(/Saison \?/)).not.toBeInTheDocument();
    // Row label uses FOLLOW_KIND_LABEL["movie"] → "Film", never raw "movie".
    expect(screen.getByText("Film")).toBeInTheDocument();
    // The raw enum value must not leak.
    const rawMovie = screen.queryByText((content) => content === "movie");
    expect(rawMovie).not.toBeInTheDocument();
  });
});
