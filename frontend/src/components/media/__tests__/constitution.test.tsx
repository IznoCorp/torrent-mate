/**
 * Constitution anti-drift test — §11 « Tout média est consultable ».
 *
 * Each surface that displays a media item MUST render an action to its detail
 * sheet when the item is identified (has a tvdb or tmdb provider id).  An
 * unidentified item MUST NOT render a link (§11 exception — it must lead to
 * resolution, never a dead link).
 *
 * The WIRED_SURFACES array is the single source of truth.  Adding a new surface
 * that displays media cards requires adding its name here AND a describe block
 * that registers it as covered.  A name in the array without coverage is a hard
 * test failure — the enforcement mechanism.
 *
 * DESIGN D8: every link goes through the single ``mediaSheetHref`` helper
 * (or a function that calls it).  This test verifies the navigation target,
 * not that the helper itself is called.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import type { FollowedSeriesItem } from "@/api/acquisition";
import type { DecisionCandidate } from "@/api/decisions";
import type { StagingMediaItem } from "@/api/staging";

// ---------------------------------------------------------------------------
// React Router mock — capture every navigation so we can assert the target.
// ---------------------------------------------------------------------------

const navigateMock = vi.fn();
const searchParamsMock = new URLSearchParams();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    useNavigate: () => navigateMock,
    useSearchParams: () => [searchParamsMock, vi.fn()] as const,
  };
});

// ---------------------------------------------------------------------------
// Stub the media-search hook used by MediaSearchAdd.
// ---------------------------------------------------------------------------

const searchResultsMock = vi.fn();
vi.mock("@/hooks/useAcquisition", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useMediaSearch: (...a: unknown[]) => searchResultsMock(...a),
  useFollow: () => ({ mutate: vi.fn(), isPending: false }),
  useCompleteness: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }),
}));

// ---------------------------------------------------------------------------
// Stub useFollowedPanel so FollowedPanel renders without a real hook machine.
// ---------------------------------------------------------------------------

vi.mock("@/hooks/useFollowedPanel", () => ({
  useFollowedPanel: () => ({
    grabSchedule: null,
    triggerSearch: vi.fn(),
    triggerPendingId: null,
    grabNow: vi.fn(),
    grabPendingId: null,
    isGrabQueued: () => false,
    handleUnfollow: vi.fn(),
    unfollowPending: false,
    handleToggleActive: vi.fn(),
    updatePending: false,
    editTarget: null,
    setEditTarget: vi.fn(),
    editInterval: "60",
    setEditInterval: vi.fn(),
    openEditCadence: vi.fn(),
    handleSaveCadence: vi.fn(),
  }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

// ---------------------------------------------------------------------------
// Stub the staging-media hook used by StagingLibrary.
// ---------------------------------------------------------------------------

const stagingMediaMock = vi.fn();
vi.mock("@/hooks/useStagingMedia", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useStagingMedia: (...a: unknown[]) => stagingMediaMock(...a),
}));

// ---------------------------------------------------------------------------
// Imports under test (AFTER mocks — vitest hoists vi.mock calls).
// ---------------------------------------------------------------------------

import { MediaSearchAdd } from "@/components/acquisition/MediaSearchAdd";
import { FollowedPanel } from "@/components/acquisition/FollowedPanel";
import { CandidateCard } from "@/components/decisions/CandidateCard";
import { StagingLibrary } from "@/components/staging/StagingLibrary";

// ---------------------------------------------------------------------------
// Enforcement: every surface that displays media cards MUST be listed here.
// ---------------------------------------------------------------------------

const WIRED_SURFACES = [
  "MediaSearchAdd",
  "FollowedPanel",
  "CandidateCard",
  "StagingLibrary",
] as const;
type WiredSurface = (typeof WIRED_SURFACES)[number];

/** Populated by each describe block — the enforcement test verifies it matches. */
const coveredSurfaces = new Set<WiredSurface>();

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** A standard QueryClient for render wrappers that need one. */
function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
}

/** A fully-typed identified search result (movie). */
function movieResult() {
  return {
    provider: "tmdb",
    provider_id: 27205,
    title: "Inception",
    year: 2010,
    kind: "movie",
    score: 0.95,
    poster_url: null,
    overview: null,
    already_owned: false,
  };
}

/** A fully-typed DecisionCandidate. */
function movieCandidate(
  overrides: Partial<DecisionCandidate> = {},
): DecisionCandidate {
  return {
    provider: "tmdb",
    provider_id: 123,
    title: "Inception",
    year: 2010,
    score: 0.85,
    poster_url: null,
    overview: null,
    ...overrides,
  };
}

/** A minimal StagingMediaItem (matched + identified). */
function identifiedStagingItem(
  overrides: Partial<StagingMediaItem> = {},
): StagingMediaItem {
  return {
    id: "abc123",
    title: "Fight Club",
    year: 1999,
    poster_url: null,
    overview: null,
    category: "001-MOVIES",
    folder: "Fight Club (1999)",
    relative_path: "001-MOVIES/Fight Club (1999)",
    media_kind: "movie",
    provider_ids: { tmdb: "550" },
    match: "matched",
    position_stage: "done",
    position_state: "pending",
    has_nfo: true,
    has_poster: true,
    has_trailer: false,
    video_count: 1,
    size_bytes: 0,
    stages: [],
    ...overrides,
  };
}

/** A StagingMediaItem with NO provider ids (unidentified — no link). */
function unidentifiedStagingItem(
  overrides: Partial<StagingMediaItem> = {},
): StagingMediaItem {
  return identifiedStagingItem({
    provider_ids: {},
    match: "absent",
    title: "Unknown File",
    year: null,
    ...overrides,
  });
}

/** A minimal FollowedSeriesItem (identified, tvdb). */
function followedItem(
  overrides: Partial<FollowedSeriesItem> = {},
): FollowedSeriesItem {
  return {
    id: 1,
    title: "House of the Dragon",
    kind: "show",
    active: true,
    added_at: 0,
    cadence: { interval_minutes: 60 },
    cadence_tier: null,
    next_search_at: null,
    quality_profile: null,
    wanted_pending: 0,
    wanted_grabbed: 0,
    season_count: 2,
    year: 2022,
    overview: null,
    poster_url: null,
    media_ref: { tvdb_id: 371572, tmdb_id: null, imdb_id: null },
    status: "a_jour",
    priming_running: false,
    tvdb_unresolved: false,
    aired_count: null,
    owned_count: null,
    a_recuperer_count: null,
    en_acquisition_count: null,
    en_attente_count: null,
    non_verifie_count: null,
    movie_facts: null,
    ...overrides,
  };
}

/** Render FollowedPanel with the given items. */
function renderPanel(items: readonly FollowedSeriesItem[]): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <FollowedPanel
        data={items}
        isLoading={false}
        isError={false}
        error={null}
      />
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  navigateMock.mockReset();
  // Reset the shared search-params mock so no test leaks ?media= into the next.
  searchParamsMock.delete("media");
  searchResultsMock.mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
  });
  stagingMediaMock.mockReturnValue({
    data: {
      items: [],
      counts: {
        total: 0,
        matched: 0,
        ambiguous: 0,
        absent: 0,
        with_trailer: 0,
      },
      total: 0,
      page: 1,
      page_size: 24,
    },
    isLoading: false,
    isError: false,
  });
});

afterEach(cleanup);

describe("§11 constitution — « Tout média est consultable »", () => {
  // -----------------------------------------------------------------------
  // SURFACE 1 — MediaSearchAdd (onOpen → navigate)
  // -----------------------------------------------------------------------

  describe("MediaSearchAdd", () => {
    coveredSurfaces.add("MediaSearchAdd");

    it("navigates to the media sheet when clicking an identified result card", () => {
      searchResultsMock.mockReturnValue({
        data: { results: [movieResult()] },
        isLoading: false,
        isError: false,
      });

      render(<MediaSearchAdd />);
      // Submit the search so results render.
      const input = screen.getByPlaceholderText("Titre (film ou série)");
      fireEvent.change(input, { target: { value: "Inception" } });
      fireEvent.submit(input);

      // The card is a <button> (MediaCard with onOpen).  Click it.
      const card = screen.getByRole("button", { name: /Inception/ });
      fireEvent.click(card);

      expect(navigateMock).toHaveBeenCalledTimes(1);
      const firstCall = navigateMock.mock.calls[0];
      if (!firstCall) throw new Error("unreachable: navigate was not called");
      const href = firstCall[0] as string;
      expect(href).toMatch(/^\/media\/tmdb\/27205/);
      // The kind hint avoids a wasted provider round-trip (phase-2 call contract).
      expect(href).toContain("kind=movie");
    });

    it("does not navigate when there are no search results (no card rendered)", () => {
      searchResultsMock.mockReturnValue({
        data: { results: [] },
        isLoading: false,
        isError: false,
      });

      render(<MediaSearchAdd />);
      const input = screen.getByPlaceholderText("Titre (film ou série)");
      fireEvent.change(input, { target: { value: "Nothing" } });
      fireEvent.submit(input);

      expect(navigateMock).not.toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------------------
  // SURFACE 2 — FollowedPanel (DropdownMenuItem → useNavigate)
  // -----------------------------------------------------------------------

  describe("FollowedPanel", () => {
    coveredSurfaces.add("FollowedPanel");

    it("navigates to the media sheet from the dropdown's « Voir la fiche »", () => {
      renderPanel([followedItem()]);

      // Open the row's ⋯ dropdown so the menu items are visible.
      fireEvent.pointerDown(
        screen.getByRole("button", {
          name: "Actions pour House of the Dragon",
        }),
      );

      // Click « Voir la fiche » — it fires navigate(sheetHref).
      const menuItem = screen.getByText("Voir la fiche");
      fireEvent.click(menuItem);

      expect(navigateMock).toHaveBeenCalledTimes(1);
      const firstCall = navigateMock.mock.calls[0];
      if (!firstCall) throw new Error("unreachable: navigate was not called");
      const href = firstCall[0] as string;
      expect(href).toMatch(/^\/media\/tvdb\/371572/);
      expect(href).toContain("kind=tv");
    });

    it("renders NO « Voir la fiche » for an imdb-only item (§11 exception)", () => {
      renderPanel([
        followedItem({
          media_ref: { tvdb_id: null, tmdb_id: null, imdb_id: "tt0903747" },
        }),
      ]);

      // Open the row's ⋯ dropdown.
      fireEvent.pointerDown(
        screen.getByRole("button", {
          name: "Actions pour House of the Dragon",
        }),
      );

      // The « Voir la fiche » menuitem must NOT appear — imdb-only items have
      // no backend sheet route, and §11 forbids a dead link.
      expect(screen.queryByText("Voir la fiche")).not.toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // SURFACE 3 — CandidateCard (Link, stopPropagation)
  // -----------------------------------------------------------------------

  describe("CandidateCard", () => {
    coveredSurfaces.add("CandidateCard");

    it("renders a « Voir la fiche » link with the correct sheet href", () => {
      const onClick = vi.fn();
      render(
        <MemoryRouter>
          <CandidateCard
            candidate={movieCandidate()}
            isSelected={false}
            onClick={onClick}
          />
        </MemoryRouter>,
      );

      const link = screen.getByText("Voir la fiche");
      expect(link).toBeInTheDocument();
      expect(link.tagName).toBe("A");
      expect(link.getAttribute("href")).toBe("/media/tmdb/123");

      // Clicking the link must NOT trigger the card's onClick (selection).
      fireEvent.click(link);
      expect(onClick).not.toHaveBeenCalled();
    });

    it("renders a sheet link for TVDB candidates too", () => {
      render(
        <MemoryRouter>
          <CandidateCard
            candidate={movieCandidate({ provider: "tvdb", provider_id: 255968 })}
            isSelected={false}
            onClick={vi.fn()}
          />
        </MemoryRouter>,
      );

      const link = screen.getByText("Voir la fiche");
      expect(link.getAttribute("href")).toBe("/media/tvdb/255968");
    });
  });

  // -----------------------------------------------------------------------
  // SURFACE 4 — StagingLibrary (detail drawer button, not card badge)
  //
  // The staging card opens a detail drawer on click; the « Voir la fiche »
  // button lives INSIDE that drawer (operator arbitration 2026-08-04).
  // The test must open the drawer to see it.
  // -----------------------------------------------------------------------

  describe("StagingLibrary", () => {
    coveredSurfaces.add("StagingLibrary");

    it("renders « Voir la fiche » in the detail drawer for an identified item", () => {
      // Open the drawer on the identified item so the detail (and its button)
      // renders.
      searchParamsMock.set("media", "abc123");
      stagingMediaMock.mockReturnValue({
        data: {
          items: [identifiedStagingItem()],
          counts: {
            total: 1,
            matched: 1,
            ambiguous: 0,
            absent: 0,
            with_trailer: 0,
          },
          total: 1,
          page: 1,
          page_size: 24,
        },
        isLoading: false,
        isError: false,
      });

      render(
        <MemoryRouter>
          <QueryClientProvider client={makeQueryClient()}>
            <StagingLibrary />
          </QueryClientProvider>
        </MemoryRouter>,
      );

      // The drawer is open — one « Voir la fiche » button inside it.
      const link = screen.getByText("Voir la fiche");
      expect(link.tagName).toBe("A");
      expect(link.getAttribute("href")).toBe("/media/tmdb/550?kind=movie");
    });

    it("renders NO « Voir la fiche » when provider_ids is empty (§11 exception)", () => {
      stagingMediaMock.mockReturnValue({
        data: {
          items: [unidentifiedStagingItem()],
          counts: {
            total: 1,
            matched: 0,
            ambiguous: 0,
            absent: 1,
            with_trailer: 0,
          },
          total: 1,
          page: 1,
          page_size: 24,
        },
        isLoading: false,
        isError: false,
      });

      render(
        <MemoryRouter>
          <QueryClientProvider client={makeQueryClient()}>
            <StagingLibrary />
          </QueryClientProvider>
        </MemoryRouter>,
      );

      // Neither the card badge nor the drawer (closed) shows the link.
      expect(screen.queryByText("Voir la fiche")).not.toBeInTheDocument();
    });

    it("picks tvdb over tmdb when both are present (drawer button)", () => {
      // Open the drawer so the drawer's button is visible.
      searchParamsMock.set("media", "abc123");
      stagingMediaMock.mockReturnValue({
        data: {
          items: [
            identifiedStagingItem({
              provider_ids: { tvdb: "12345", tmdb: "550" },
              media_kind: "tvshow",
              seasons: [{ season: 1, label: "Saison 1", episode_count: 10 }],
            }),
          ],
          counts: {
            total: 1,
            matched: 1,
            ambiguous: 0,
            absent: 0,
            with_trailer: 0,
          },
          total: 1,
          page: 1,
          page_size: 24,
        },
        isLoading: false,
        isError: false,
      });

      render(
        <MemoryRouter>
          <QueryClientProvider client={makeQueryClient()}>
            <StagingLibrary />
          </QueryClientProvider>
        </MemoryRouter>,
      );

      const link = screen.getByText("Voir la fiche");
      expect(link.getAttribute("href")).toBe("/media/tvdb/12345?kind=tv");
    });
  });

  // -----------------------------------------------------------------------
  // Enforcement — a surface added to WIRED_SURFACES without a corresponding
  // describe block that registers coverage is a hard failure.
  // -----------------------------------------------------------------------

  it("covers every wired surface (enforcement mechanism)", () => {
    const missing = WIRED_SURFACES.filter((s) => !coveredSurfaces.has(s));
    expect(missing).toEqual([]);
  });
});
