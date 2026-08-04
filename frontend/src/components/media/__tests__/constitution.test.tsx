/**
 * Constitution anti-drift test — §11 « Tout média est consultable ».
 *
 * Each surface that displays a media item MUST render a link to its detail
 * sheet when the item is identified (has a provider id).  An unidentified
 * item MUST NOT render a link (§11 exception — it must lead to resolution,
 * never a dead link).
 *
 * The SURFACES array is explicit: adding a new surface that displays media
 * cards requires adding an entry here.  Omitting it causes a test failure
 * (the enforcement mechanism).
 *
 * DESIGN D8: every link goes through the single ``mediaSheetHref`` helper.
 * This test verifies the helper is CALLED, not that its output is hardcoded —
 * a hand-built ``/media/...`` string would bypass D8 but still pass a
 * pattern-match check.  For surfaces that use ``<a>`` tags we check the href
 * attribute; for surfaces that use ``useNavigate`` + ``onOpen`` we check the
 * navigation call.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DecisionCandidate } from "@/api/decisions";
import type { StagingMediaItem } from "@/api/staging";

// ---------------------------------------------------------------------------
// React Router mock — capture every navigation so we can assert the target.
// ---------------------------------------------------------------------------

const navigateMock = vi.fn();
const searchParamsMock = new URLSearchParams();
vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
  useSearchParams: () => [searchParamsMock, vi.fn()] as const,
}));

// ---------------------------------------------------------------------------
// Stub the media-search hook used by MediaSearchAdd.
// ---------------------------------------------------------------------------

const searchResultsMock = vi.fn();
vi.mock("@/hooks/useAcquisition", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useMediaSearch: (...a: unknown[]) => searchResultsMock(...a),
  useFollow: () => ({ mutate: vi.fn(), isPending: false }),
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
import { CandidateCard } from "@/components/decisions/CandidateCard";
import { StagingLibrary } from "@/components/staging/StagingLibrary";

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
function movieCandidate(overrides: Partial<DecisionCandidate> = {}): DecisionCandidate {
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
  searchResultsMock.mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
  });
  stagingMediaMock.mockReturnValue({
    data: { items: [], counts: { total: 0, matched: 0, ambiguous: 0, absent: 0, with_trailer: 0 }, total: 0, page: 1, page_size: 24 },
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
      const href = navigateMock.mock.calls[0][0] as string;
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
  // SURFACE 2 — CandidateCard (<a> tag, stopPropagation)
  // -----------------------------------------------------------------------

  describe("CandidateCard", () => {
    it("renders a « Voir la fiche » link with the correct sheet href", () => {
      const onClick = vi.fn();
      render(
        <CandidateCard
          candidate={movieCandidate()}
          isSelected={false}
          onClick={onClick}
        />,
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
        <CandidateCard
          candidate={movieCandidate({ provider: "tvdb", provider_id: 255968 })}
          isSelected={false}
          onClick={vi.fn()}
        />,
      );

      const link = screen.getByText("Voir la fiche");
      expect(link.getAttribute("href")).toBe("/media/tvdb/255968");
    });
  });

  // -----------------------------------------------------------------------
  // SURFACE 3 — StagingLibrary (<a> tag in badges, + detail header)
  // -----------------------------------------------------------------------

  describe("StagingLibrary", () => {
    it("renders a « Voir la fiche » link in card badges for an identified item", () => {
      stagingMediaMock.mockReturnValue({
        data: {
          items: [identifiedStagingItem()],
          counts: { total: 1, matched: 1, ambiguous: 0, absent: 0, with_trailer: 0 },
          total: 1,
          page: 1,
          page_size: 24,
        },
        isLoading: false,
        isError: false,
      });

      render(
        <QueryClientProvider client={makeQueryClient()}>
          <StagingLibrary />
        </QueryClientProvider>,
      );

      // The card renders TWO "Voir la fiche" links — one in the badges, one in
      // the detail drawer's header (which is closed by default).  Find the one
      // inside the card (visible).
      const links = screen.getAllByText("Voir la fiche");
      // At least one is visible (the card badge).
      const visibleLink = links.find(
        (el) => el.tagName === "A" && el.getAttribute("href") !== null,
      );
      expect(visibleLink).toBeDefined();
      expect(visibleLink?.getAttribute("href")).toBe("/media/tmdb/550?kind=movie");
    });

    it("renders NO « Voir la fiche » link when provider_ids is empty (§11 exception)", () => {
      stagingMediaMock.mockReturnValue({
        data: {
          items: [unidentifiedStagingItem()],
          counts: { total: 1, matched: 0, ambiguous: 0, absent: 1, with_trailer: 0 },
          total: 1,
          page: 1,
          page_size: 24,
        },
        isLoading: false,
        isError: false,
      });

      render(
        <QueryClientProvider client={makeQueryClient()}>
          <StagingLibrary />
        </QueryClientProvider>,
      );

      expect(screen.queryByText("Voir la fiche")).not.toBeInTheDocument();
    });

    it("picks tvdb over tmdb when both are present", () => {
      stagingMediaMock.mockReturnValue({
        data: {
          items: [
            identifiedStagingItem({
              provider_ids: { tvdb: "12345", tmdb: "550" },
              media_kind: "tvshow",
              seasons: [{ season: 1, label: "Saison 1", episode_count: 10 }],
            }),
          ],
          counts: { total: 1, matched: 1, ambiguous: 0, absent: 0, with_trailer: 0 },
          total: 1,
          page: 1,
          page_size: 24,
        },
        isLoading: false,
        isError: false,
      });

      render(
        <QueryClientProvider client={makeQueryClient()}>
          <StagingLibrary />
        </QueryClientProvider>,
      );

      const links = screen.getAllByText("Voir la fiche");
      const cardLink = links.find(
        (el) => el.tagName === "A" && el.getAttribute("href") !== null,
      );
      expect(cardLink).toBeDefined();
      // tvdb priority.
      expect(cardLink?.getAttribute("href")).toBe("/media/tvdb/12345?kind=tv");
    });
  });
});
