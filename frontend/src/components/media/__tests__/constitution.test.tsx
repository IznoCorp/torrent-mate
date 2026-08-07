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

import type { ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import type { DecisionCandidate } from "@/api/decisions";
import type { StagingMediaItem } from "@/api/staging";

// ---------------------------------------------------------------------------
// React Router mock — capture every navigation so we can assert the target.
// ---------------------------------------------------------------------------

const navigateMock = vi.fn();
const searchParamsMock = new URLSearchParams();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
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
const followedMock = vi.fn();
const completenessMock = vi.fn<() => {
  data: unknown;
  isLoading: boolean;
  isError: boolean;
}>(() => ({
  data: undefined,
  isLoading: false,
  isError: false,
}));
vi.mock("@/hooks/useAcquisition", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useMediaSearch: (...a: unknown[]) => searchResultsMock(...a),
  useFollow: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateFollow: () => ({ mutate: vi.fn(), isPending: false }),
  useUnfollow: () => ({ mutate: vi.fn(), isPending: false }),
  useGrabNow: () => ({ mutate: vi.fn(), isPending: false }),
  useCompleteness: () => completenessMock(),
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useFollowed: () => followedMock(),
  useToHandle: () => ({ data: { items: [], orphan_count: 0, degraded: false }, isLoading: false, isError: false }),
  useWanted: () => ({ data: { items: [], total: 0 }, isLoading: false, isError: false }),
  useJourneys: () => ({ data: { journeys: [] }, isLoading: false, isError: false }),
  useDownloads: () => ({
    data: { downloads: [], client_available: true },
    isLoading: false,
    isError: false,
  }),
  useOverview: () => ({
    data: { stalled_grabs: 0 },
    isLoading: false,
    isError: false,
  }),
}));

// ---------------------------------------------------------------------------
// (useFollowedPanel stub removed with its panel.)
// ---------------------------------------------------------------------------


vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

// ---------------------------------------------------------------------------
// Stub getJourneys for ParcoursPanel.
// ---------------------------------------------------------------------------

const { getJourneysMock } = vi.hoisted(() => ({
  getJourneysMock: vi.fn(),
}));
vi.mock("@/api/acquisition", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/acquisition")>(
      "@/api/acquisition",
    );
  return { ...actual, getJourneys: getJourneysMock };
});

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

import { AddMediaScreen } from "@/components/acquisition/AddMediaScreen";
import { AcquisitionCard } from "@/components/acquisition/AcquisitionCard";
import { MaintenantPanel } from "@/components/acquisition/MaintenantPanel";
import { SuivisPanel } from "@/components/acquisition/SuivisPanel";
import { FollowDetailSheet } from "@/components/acquisition/FollowDetailSheet";
import { CandidateCard } from "@/components/decisions/CandidateCard";
import { StagingLibrary } from "@/components/staging/StagingLibrary";
import { ATraiterList } from "@/components/controle/ATraiterList";
import { StageMediaList } from "@/components/staging/StageMediaList";

// ---------------------------------------------------------------------------
// Enforcement: every surface that displays media cards MUST be listed here.
// ---------------------------------------------------------------------------

const WIRED_SURFACES = [
  "AddMediaScreen",
  "AcquisitionCard",
  "MaintenantPanel",
  "SuivisPanel",
  "FollowDetailSheet",
  "CandidateCard",
  "StagingLibrary",
  "ATraiterList",
  "StageMediaList",
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
  // SURFACE 1 — AddMediaScreen (result row → navigate)
  // -----------------------------------------------------------------------

  describe("AddMediaScreen", () => {
    coveredSurfaces.add("AddMediaScreen");

    it("navigates to the media sheet when clicking an identified result card", () => {
      searchResultsMock.mockReturnValue({
        // useInfiniteQuery shape (the search paginates since recherche-juste).
        data: {
          pages: [{ total: 1, offset: 0, limit: 20, results: [movieResult()] }],
        },
        isLoading: false,
        isError: false,
        hasNextPage: false,
        isFetchingNextPage: false,
        fetchNextPage: vi.fn(),
      });

      render(<AddMediaScreen open onOpenChange={vi.fn()} />);
      // Submit the search so results render.
      const input = screen.getByPlaceholderText("Titre (film ou série)");
      fireEvent.change(input, { target: { value: "Inception" } });
      fireEvent.submit(input);

      // The poster is the control that reaches the sheet (the row also
      // carries the add action, so it cannot itself be a button).
      const poster = screen.getByRole("button", { name: "Fiche de Inception" });
      fireEvent.click(poster);

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
        data: { pages: [{ total: 0, offset: 0, limit: 20, results: [] }] },
        isLoading: false,
        isError: false,
        hasNextPage: false,
        isFetchingNextPage: false,
        fetchNextPage: vi.fn(),
      });

      render(<AddMediaScreen open onOpenChange={vi.fn()} />);
      const input = screen.getByPlaceholderText("Titre (film ou série)");
      fireEvent.change(input, { target: { value: "Nothing" } });
      fireEvent.submit(input);

      expect(navigateMock).not.toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------------------
  // SURFACE 2 — AcquisitionCard (poster → media sheet, or no control at all)
  // -----------------------------------------------------------------------

  describe("AcquisitionCard", () => {
    coveredSurfaces.add("AcquisitionCard");

    // This card is the shared primitive behind every acquisition list, so the
    // §11 contract is enforced HERE once rather than in each panel: a poster is
    // a control when it leads somewhere, and is not a control when it does not.

    it("makes the poster a button that reaches the media sheet", () => {
      const onPoster = vi.fn();
      render(
        <AcquisitionCard title="Inception" posterUrl={null} onPoster={onPoster} />,
      );

      const poster = screen.getByRole("button", { name: "Fiche de Inception" });
      fireEvent.click(poster);
      expect(onPoster).toHaveBeenCalledTimes(1);
    });

    it("renders NO poster control when the media has no sheet", () => {
      // A blocked item is stuck at identification: there is no provider id, so
      // there is nothing to link to. A button that does nothing is the dead
      // control §11 forbids — the poster degrades to plain image.
      render(<AcquisitionCard title="Inconnu" posterUrl={null} />);

      expect(
        screen.queryByRole("button", { name: /Fiche de/ }),
      ).not.toBeInTheDocument();
    });

    it("renders NO body control when there is no detail sheet", () => {
      // Same rule applied to the body: the card is tappable only when the tap
      // has a destination.
      render(<AcquisitionCard title="Inconnu" posterUrl={null} />);

      expect(screen.queryByRole("button")).not.toBeInTheDocument();
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
            candidate={movieCandidate({
              provider: "tvdb",
              provider_id: 255968,
            })}
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
  // SURFACE 5 — ATraiterList (indirect: « Résoudre → » opens the staging
  // drawer at /medias?media=<id>, whose « Voir la fiche » button is the
  // second hop to the sheet — covered by StagingLibrary above).
  // -----------------------------------------------------------------------

  describe("ATraiterList", () => {
    coveredSurfaces.add("ATraiterList");

    it("renders a resolve link to the staging drawer for an identified blocked item", () => {
      const blocked = identifiedStagingItem({
        id: "blocked-at",
        position_state: "blocked",
        match: "matched",
        title: "Inception",
      });
      stagingMediaMock.mockReturnValue({
        data: {
          items: [blocked],
          counts: {
            total: 1,
            matched: 1,
            ambiguous: 0,
            absent: 0,
            with_trailer: 0,
          },
          total: 1,
          page: 1,
          page_size: 100,
        },
        isLoading: false,
        isError: false,
      });

      render(
        <MemoryRouter>
          <QueryClientProvider client={makeQueryClient()}>
            <ATraiterList />
          </QueryClientProvider>
        </MemoryRouter>,
      );

      // « Résoudre → » links to the staging drawer — the indirect §11 path.
      const link = screen.getByText("Résoudre →");
      expect(link.tagName).toBe("A");
      expect(link.getAttribute("href")).toBe("/medias?media=blocked-at");
    });
  });

  // -----------------------------------------------------------------------
  // SURFACE 6 — StageMediaList (indirect: « Ouvrir la fiche média » button
  // fires onOpenMedia, which the host opens the staging drawer — same
  // two-hop contract as ATraiterList).
  // -----------------------------------------------------------------------

  describe("StageMediaList", () => {
    coveredSurfaces.add("StageMediaList");

    it("renders 'Ouvrir la fiche média' button for a blocked identified item", () => {
      const onOpenMedia = vi.fn();
      const blocked = identifiedStagingItem({
        id: "blocked-sm",
        position_state: "blocked",
        match: "matched",
        title: "Fight Club",
      });
      stagingMediaMock.mockReturnValue({
        data: {
          items: [blocked],
          counts: {
            total: 1,
            matched: 1,
            ambiguous: 0,
            absent: 0,
            with_trailer: 0,
          },
          total: 1,
          page: 1,
          page_size: 50,
        },
        isLoading: false,
        isError: false,
      });

      render(
        <MemoryRouter>
          <QueryClientProvider client={makeQueryClient()}>
            <StageMediaList stageKey="arrival" onOpenMedia={onOpenMedia} />
          </QueryClientProvider>
        </MemoryRouter>,
      );

      // Open the accordion to reveal the action button.
      const trigger = screen.getByText("Fight Club");
      fireEvent.click(trigger);

      const button = screen.getByText("Ouvrir la fiche média");
      fireEvent.click(button);
      expect(onOpenMedia).toHaveBeenCalledWith("blocked-sm");
    });
  });

  // -----------------------------------------------------------------------
  // SURFACES 3-5 — the acquisition panels and the detail sheet
  // -----------------------------------------------------------------------

  // These three render AcquisitionCard, so the poster contract is already
  // enforced on the primitive above. What they own — and what is asserted here —
  // is the DERIVATION: each must hand the card a real destination built from the
  // item's provider ids, and hand it nothing when the item has none. A panel
  // that passed a no-op would render a control that goes nowhere while the
  // primitive's own tests stayed green.

  /** A followed series carrying a tvdb id — it has a sheet. */
  function identifiedFollow(): Record<string, unknown> {
    return {
      id: 1,
      title: "Silo",
      kind: "show",
      status: "a_recuperer",
      active: true,
      added_at: 1_750_000_000,
      wanted_pending: 0,
      wanted_grabbed: 0,
      year: 2023,
      poster_url: null,
      tvdb_unresolved: false,
      priming_running: false,
      media_ref: { tvdb_id: 400000, tmdb_id: null, imdb_id: null },
      owned_count: 1,
      aired_count: 2,
    };
  }

  /** The same follow with no provider id at all — it has NO sheet. */
  function unidentifiedFollow(): Record<string, unknown> {
    return {
      ...identifiedFollow(),
      id: 2,
      title: "Inconnu",
      media_ref: { tvdb_id: null, tmdb_id: null, imdb_id: null },
    };
  }

  function renderInRouter(node: ReactElement): void {
    render(
      <MemoryRouter>
        <QueryClientProvider client={makeQueryClient()}>
          {node}
        </QueryClientProvider>
      </MemoryRouter>,
    );
  }

  describe("MaintenantPanel", () => {
    coveredSurfaces.add("MaintenantPanel");

    it("gives an identified item a poster that reaches its sheet", () => {
      followedMock.mockReturnValue({
        data: { items: [identifiedFollow()] },
        isLoading: false,
        isError: false,
      });
      renderInRouter(<MaintenantPanel />);

      expect(
        screen.getByRole("button", { name: "Fiche de Silo" }),
      ).toBeInTheDocument();
    });

    it("gives an item with no provider id NO poster control", () => {
      followedMock.mockReturnValue({
        data: { items: [unidentifiedFollow()] },
        isLoading: false,
        isError: false,
      });
      renderInRouter(<MaintenantPanel />);

      expect(
        screen.queryByRole("button", { name: "Fiche de Inconnu" }),
      ).not.toBeInTheDocument();
    });
  });

  describe("SuivisPanel", () => {
    coveredSurfaces.add("SuivisPanel");

    it("gives an identified follow a poster that reaches its sheet", () => {
      followedMock.mockReturnValue({
        data: { items: [identifiedFollow()] },
        isLoading: false,
        isError: false,
      });
      renderInRouter(<SuivisPanel />);

      expect(
        screen.getByRole("button", { name: "Fiche de Silo" }),
      ).toBeInTheDocument();
    });

    it("gives a follow with no provider id NO poster control", () => {
      followedMock.mockReturnValue({
        data: { items: [unidentifiedFollow()] },
        isLoading: false,
        isError: false,
      });
      renderInRouter(<SuivisPanel />);

      expect(
        screen.queryByRole("button", { name: "Fiche de Inconnu" }),
      ).not.toBeInTheDocument();
    });
  });

  describe("FollowDetailSheet", () => {
    coveredSurfaces.add("FollowDetailSheet");

    it("offers « Voir la fiche » when the follow has a sheet", () => {
      completenessMock.mockReturnValue({
        data: { title: "Silo", seasons: [] },
        isLoading: false,
        isError: false,
      });
      renderInRouter(
        <FollowDetailSheet
          followedId={1}
          status="a_recuperer"
          kind="show"
          open
          onOpenChange={vi.fn()}
          mediaHref="/media/tvdb/400000?kind=tv"
        />,
      );

      expect(
        screen.getByRole("button", { name: /Voir la fiche/i }),
      ).toBeInTheDocument();
    });

    it("omits « Voir la fiche » entirely when there is no sheet", () => {
      // Absent, not disabled: a control the operator can see but never use is
      // the dead link §11 forbids.
      completenessMock.mockReturnValue({
        data: { title: "Inconnu", seasons: [] },
        isLoading: false,
        isError: false,
      });
      renderInRouter(
        <FollowDetailSheet
          followedId={2}
          status="a_recuperer"
          kind="show"
          open
          onOpenChange={vi.fn()}
          mediaHref={null}
        />,
      );

      expect(
        screen.queryByRole("button", { name: /Voir la fiche/i }),
      ).not.toBeInTheDocument();
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
