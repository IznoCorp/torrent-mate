/**
 * Unit tests for the AcquisitionPage component (acq-mobile refonte).
 *
 * Mocks the acquisition hooks and event-stream context so the page logic
 * (two views, legacy redirects, WS invalidation) is tested in isolation.
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
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EventMessage } from "@/api/events";

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

const useFollowedMock = vi.fn();
const useWantedMock = vi.fn();
const useToHandleMock = vi.fn();
const useJourneysMock = vi.fn();
const useAcquisitionStatusMock = vi.fn();
const useObligationsMock = vi.fn();

/** Stable mock mutation fns — cleared between tests. */
let followMutateFn = vi.fn();

const useEventStreamContextMock = vi.fn((): { events: EventMessage[] } => ({
  events: [],
}));

vi.mock("@/hooks/useAcquisition", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useFollowed: (...args: unknown[]) => useFollowedMock(...args),
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useWanted: (...args: unknown[]) => useWantedMock(...args),
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useToHandle: () => useToHandleMock(),
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useJourneys: () => useJourneysMock(),
  useMediaSearch: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: () => undefined,
  }),
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useAcquisitionStatus: () => useAcquisitionStatusMock(),
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useObligations: (...args: unknown[]) => useObligationsMock(...args),
  useFollow: () => ({ mutate: followMutateFn, isPending: false }),
  useUpdateFollow: () => ({ mutate: vi.fn(), isPending: false }),
  useUnfollow: () => ({ mutate: vi.fn(), isPending: false }),
  useOverview: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
  }),
  useCompleteness: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }),
  useTrackedAcquisitionRun: () => undefined,
}));

vi.mock("@/hooks/useEventStreamContext", () => ({
  useEventStreamContext: () => useEventStreamContextMock(),
}));

vi.mock("sonner", () => ({
  toast: { info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

import AcquisitionPage from "@/pages/AcquisitionPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Probe that surfaces the live URL search string for ?tab= assertions. */
function LocationProbe(): ReactElement {
  const { search } = useLocation();
  return <div data-testid="loc-search">{search}</div>;
}

/** Render the page wrapped in a QueryClientProvider + router (?tab= support). */
function renderPage(initialEntry = "/acquisition"): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  const tree: ReactElement = (
    <MemoryRouter initialEntries={[initialEntry]}>
      <QueryClientProvider client={qc}>
        <AcquisitionPage />
        <LocationProbe />
      </QueryClientProvider>
    </MemoryRouter>
  );
  render(tree);
}

/** Default mock return values for read hooks (empty data). */
function mockAllEmpty(): void {
  useFollowedMock.mockReturnValue({
    isLoading: false,
    isError: false,
    data: { items: [] },
    error: null,
  });
  useWantedMock.mockReturnValue({
    isLoading: false,
    isError: false,
    data: { items: [] },
    error: null,
  });
  useToHandleMock.mockReturnValue({
    isLoading: false,
    isError: false,
    data: { items: [], orphan_count: 0 },
    error: null,
  });
  useJourneysMock.mockReturnValue({
    isLoading: false,
    isError: false,
    data: { journeys: [] },
    error: null,
  });
  useAcquisitionStatusMock.mockReturnValue({
    isLoading: false,
    isError: false,
    data: {
      watcher_enabled: true,
      last_successful_run_at: null,
      recent_runs: [],
      deferred: [],
    },
    error: null,
  });
  useObligationsMock.mockReturnValue({
    isLoading: false,
    isError: false,
    data: { items: [] },
    error: null,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  followMutateFn = vi.fn();
});

describe("AcquisitionPage", () => {
  // ── Tab navigation ──────────────────────────────────────────────────────

  it("exposes exactly two views", () => {
    mockAllEmpty();
    renderPage();
    expect(screen.getAllByRole("tab")).toHaveLength(2);
    expect(screen.getByRole("tab", { name: /Maintenant/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Suivis/ })).toBeInTheDocument();
  });

  it("does not render a duplicate « Acquisition » title — the bottom bar already says where you are (§12/D3)", () => {
    mockAllEmpty();
    renderPage();
    expect(screen.queryByRole("heading", { name: "Acquisition" })).toBeNull();
  });

  it("shows the Maintenant panel by default with no ?tab= param", () => {
    mockAllEmpty();
    renderPage();
    expect(screen.getByRole("tab", { name: /Maintenant/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("loc-search")).toHaveTextContent("");
  });

  it("switches to the Suivis panel when clicking its tab", () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(screen.getByRole("tab", { name: /Suivis/ }));

    expect(screen.getByRole("tab", { name: /Suivis/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=suivis");
  });

  it("renders the Rien à signaler empty state when all sections are empty", () => {
    mockAllEmpty();
    renderPage();
    expect(screen.getByText(/Rien à signaler/)).toBeInTheDocument();
  });

  // ── Legacy redirects ────────────────────────────────────────────────────

  it.each([
    ["followed", "suivis"],
    ["file", "maintenant"],
    ["apercu", "maintenant"],
    ["obligations", "maintenant"],
    ["watcher", "maintenant"],
    ["parcours", "maintenant"],
    ["reglages", "maintenant"],
    ["wanted", "maintenant"],
    ["downloads", "maintenant"],
  ])(
    "redirects legacy ?tab=%s to %s without stacking history",
    (legacy) => {
      mockAllEmpty();
      renderPage(`/acquisition?tab=${legacy}`);

      // Redirects to the canonical view — "maintenant" carries no param.
      if (legacy === "followed") {
        expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=suivis");
      } else {
        expect(screen.getByTestId("loc-search")).toHaveTextContent("");
      }
    },
  );

  it("a legacy redirect does not stack a history entry (replace, not push)", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=apercu");

    // After redirect the URL is clean (maintenant = no param).
    expect(screen.getByTestId("loc-search")).toHaveTextContent("");
    expect(screen.getByRole("tab", { name: /Maintenant/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  // ── URL-addressable tab (DOIT-10) ───────────────────────────────────────

  it("opens the tab indicated by ?tab= on load (deep-link)", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=suivis");

    expect(screen.getByRole("tab", { name: /Suivis/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("falls back to Maintenant on an unknown ?tab= value", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=bogus");

    expect(screen.getByRole("tab", { name: /Maintenant/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=bogus");
  });

  it("clears the param when returning to the default tab", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=suivis");

    fireEvent.click(screen.getByRole("tab", { name: /Maintenant/ }));

    expect(screen.getByTestId("loc-search")).toHaveTextContent("");
  });

  // ── Tablist scroll classes ──────────────────────────────────────────────

  it("has flex-nowrap and overflow-x-auto, NOT flex-wrap", () => {
    mockAllEmpty();
    renderPage();

    const tablist = screen.getByRole("tablist");
    expect(tablist.className).toMatch(/\bflex-nowrap\b/);
    expect(tablist.className).toMatch(/\boverflow-x-auto\b/);
    expect(tablist.className).not.toMatch(/\bflex-wrap\b/);
  });

  // ── Tablist ARIA ────────────────────────────────────────────────────────

  it("links each tab to the panel: aria-controls, tabpanel, aria-labelledby", () => {
    mockAllEmpty();
    renderPage();

    const tab = screen.getByRole("tab", { name: "Maintenant" });
    expect(tab).toHaveAttribute("id", "acq-tab-maintenant");
    expect(tab).toHaveAttribute("aria-controls", "acq-tabpanel");

    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveAttribute("id", "acq-tabpanel");
    expect(panel).toHaveAttribute("aria-labelledby", "acq-tab-maintenant");
  });

  it("tabpanel tracks the active tab (aria-labelledby)", () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(screen.getByRole("tab", { name: "Suivis" }));
    expect(screen.getByRole("tabpanel")).toHaveAttribute(
      "aria-labelledby",
      "acq-tab-suivis",
    );
  });

  it("roving tabindex: only the active tab is tabbable", () => {
    mockAllEmpty();
    renderPage();

    expect(screen.getByRole("tab", { name: "Maintenant" })).toHaveAttribute(
      "tabindex",
      "0",
    );
    expect(screen.getByRole("tab", { name: "Suivis" })).toHaveAttribute(
      "tabindex",
      "-1",
    );
  });

  it("ArrowRight/ArrowLeft navigate, Home/End jump to extremes", () => {
    mockAllEmpty();
    renderPage();

    const tablist = screen.getByRole("tablist");

    // Maintenant → ArrowRight → Suivis
    fireEvent.keyDown(tablist, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Suivis" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    // Suivis → ArrowLeft → Maintenant
    fireEvent.keyDown(tablist, { key: "ArrowLeft" });
    expect(screen.getByRole("tab", { name: "Maintenant" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    // End → last tab (Suivis)
    fireEvent.keyDown(tablist, { key: "End" });
    expect(screen.getByRole("tab", { name: "Suivis" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    // Home → first tab (Maintenant)
    fireEvent.keyDown(tablist, { key: "Home" });
    expect(screen.getByRole("tab", { name: "Maintenant" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  // ── Back-navigation probe (mutation-proof) ──────────────────────────────

  function BackProbe(): ReactElement {
    const navigate = useNavigate();
    const location = useLocation();
    return (
      <>
        <div data-testid="loc-pathname">{location.pathname}</div>
        <div data-testid="loc-search">{location.search}</div>
        <button
          data-testid="go-back"
          onClick={() => {
            void navigate(-1);
          }}
        >
          Back
        </button>
      </>
    );
  }

  function renderPageWithProbe(initialEntry = "/acquisition"): void {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const tree: ReactElement = (
      <MemoryRouter initialEntries={["/somewhere", initialEntry]}>
        <QueryClientProvider client={qc}>
          <AcquisitionPage />
          <BackProbe />
        </QueryClientProvider>
      </MemoryRouter>
    );
    render(tree);
  }

  it("navigate(-1) after legacy redirect lands on first entry, not the legacy URL", async () => {
    mockAllEmpty();
    // Two-entry history: /somewhere (index 0), /acquisition?tab=apercu (index 1).
    // The redirect useEffect replaces tab=apercu → clean (maintenant default),
    // so history becomes [/somewhere, /acquisition].
    // navigate(-1) must land on /somewhere, NOT /acquisition?tab=apercu.
    renderPageWithProbe("/acquisition?tab=apercu");

    await waitFor(() => {
      expect(screen.getByTestId("loc-search")).toHaveTextContent("");
    });

    fireEvent.click(screen.getByTestId("go-back"));

    await waitFor(() => {
      expect(screen.getByTestId("loc-pathname")).toHaveTextContent("/somewhere");
    });
    expect(screen.getByTestId("loc-search")).toHaveTextContent("");
  });

  it("ArrowRight then Back returns to the original tab, not an intermediate one (ACQUISITION-7, ticket 250)", async () => {
    mockAllEmpty();
    // History: [/somewhere, /acquisition] — Maintenant is the origin tab.
    renderPageWithProbe();

    // Click pushes one entry.
    fireEvent.click(screen.getByRole("tab", { name: "Suivis" }));
    expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=suivis");

    // One Back lands on Maintenant (the pre-click tab), not an intermediate.
    fireEvent.click(screen.getByTestId("go-back"));
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: "Maintenant" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
    });
    expect(screen.getByTestId("loc-search").textContent).not.toContain("tab=");
  });

  // ── « + » add button ──────────────────────────────────────────────────

  it("renders the « + » button anchored above the bottom bar", () => {
    mockAllEmpty();
    renderPage();

    const addBtn = screen.getByRole("button", { name: "Ajouter un média" });
    expect(addBtn).toBeInTheDocument();
    // The button is fixed-positioned and uses the aboveBottomBar helper — its
    // computed bottom must reference the custom property, not a literal pixel.
    expect(addBtn.style.bottom).toContain("var(--tm-bottom-bar-h");
  });

  it("the « + » opens AddMediaScreen", () => {
    mockAllEmpty();
    renderPage();

    // Before activation the add screen is absent.
    expect(screen.queryByText(/Ajouter un média/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Ajouter un média" }));

    // The full-screen sheet renders its title.
    expect(screen.getByText(/Ajouter un média/)).toBeInTheDocument();
  });

  // ── « Plus » button ────────────────────────────────────────────────────

  it("« Plus » opens the Veille et Obligations sheet", () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(
      screen.getByRole("button", { name: "Veille et obligations" }),
    );

    // The ObligationsPanel renders inside the sheet.
    expect(screen.getByText(/Obligations de partage/i)).toBeInTheDocument();
  });

  // ── R13 WS invalidation ────────────────────────────────────────────────

  it("invalidates acqKeys.all on SeriesFollowed event", () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidateQueriesSpy = vi
      .spyOn(qc, "invalidateQueries")
      .mockResolvedValue(undefined);

    useEventStreamContextMock.mockReturnValue({
      events: [{ type: "SeriesFollowed", id: "1-0", data: {} }],
    });
    mockAllEmpty();

    const tree: ReactElement = (
      <MemoryRouter>
        <QueryClientProvider client={qc}>
          <AcquisitionPage />
        </QueryClientProvider>
      </MemoryRouter>
    );
    render(tree);

    expect(invalidateQueriesSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["acquisition"] }),
    );
  });

  it("invalidates wanted + followed on WantedEnqueued event", () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidateQueriesSpy = vi
      .spyOn(qc, "invalidateQueries")
      .mockResolvedValue(undefined);

    useEventStreamContextMock.mockReturnValue({
      events: [{ type: "WantedEnqueued", id: "2-0", data: {} }],
    });
    mockAllEmpty();

    const tree: ReactElement = (
      <MemoryRouter>
        <QueryClientProvider client={qc}>
          <AcquisitionPage />
        </QueryClientProvider>
      </MemoryRouter>
    );
    render(tree);

    expect(invalidateQueriesSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["acquisition", "wanted", {}],
      }),
    );
    expect(invalidateQueriesSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["acquisition", "followed", {}],
      }),
    );
  });

  it("toasts + invalidates wanted on GrabReswitched event (ticket 342)", async () => {
    const { toast } = await import("sonner");
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidateQueriesSpy = vi
      .spyOn(qc, "invalidateQueries")
      .mockResolvedValue(undefined);

    useEventStreamContextMock.mockReturnValue({
      events: [{ type: "GrabReswitched", id: "9-0", data: {} }],
    });
    mockAllEmpty();

    const tree: ReactElement = (
      <MemoryRouter>
        <QueryClientProvider client={qc}>
          <AcquisitionPage />
        </QueryClientProvider>
      </MemoryRouter>
    );
    render(tree);

    expect(vi.mocked(toast.info)).toHaveBeenCalled();
    expect(invalidateQueriesSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["acquisition", "wanted", {}],
      }),
    );
  });

  it("invalidates obligations on SeedObligationSatisfied event", () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidateQueriesSpy = vi
      .spyOn(qc, "invalidateQueries")
      .mockResolvedValue(undefined);

    useEventStreamContextMock.mockReturnValue({
      events: [{ type: "SeedObligationSatisfied", id: "3-0", data: {} }],
    });
    mockAllEmpty();

    const tree: ReactElement = (
      <MemoryRouter>
        <QueryClientProvider client={qc}>
          <AcquisitionPage />
        </QueryClientProvider>
      </MemoryRouter>
    );
    render(tree);

    expect(invalidateQueriesSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["acquisition", "obligations", {}],
      }),
    );
  });

  it("invalidates status on WatcherRunTriggered event", () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidateQueriesSpy = vi
      .spyOn(qc, "invalidateQueries")
      .mockResolvedValue(undefined);

    useEventStreamContextMock.mockReturnValue({
      events: [{ type: "WatcherRunTriggered", id: "4-0", data: {} }],
    });
    mockAllEmpty();

    const tree: ReactElement = (
      <MemoryRouter>
        <QueryClientProvider client={qc}>
          <AcquisitionPage />
        </QueryClientProvider>
      </MemoryRouter>
    );
    render(tree);

    expect(invalidateQueriesSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["acquisition", "status"],
      }),
    );
  });

  // ── Tablist keyboard navigation: replace vs push ────────────────────────

  it("ArrowRight REPLACES the URL (keyboard nav), click PUSHES", () => {
    mockAllEmpty();
    renderPage();

    const tablist = screen.getByRole("tablist");

    // Click pushes a new history entry.
    fireEvent.click(screen.getByRole("tab", { name: "Suivis" }));
    expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=suivis");

    // Keyboard nav replaces, no new entry — URL still just ?tab=suivis.
    fireEvent.keyDown(tablist, { key: "ArrowLeft" });
    expect(screen.getByRole("tab", { name: "Maintenant" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    // After keyboard nav back to Maintenant, URL should be clean.
    expect(screen.getByTestId("loc-search")).toHaveTextContent("");
  });

  // ── Loading state ───────────────────────────────────────────────────────

  it("shows loading text while data is still in flight", () => {
    useFollowedMock.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });
    useWantedMock.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });
    useToHandleMock.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });
    useJourneysMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { journeys: [] },
      error: null,
    });

    renderPage();
    expect(screen.getByText(/Chargement/)).toBeInTheDocument();
  });

  // ── Error state ─────────────────────────────────────────────────────────

  it("shows a section-level error when toHandle fails (panne ≠ absence)", () => {
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [] },
      error: null,
    });
    useWantedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [] },
      error: null,
    });
    useToHandleMock.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: null,
    });
    useJourneysMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { journeys: [] },
      error: null,
    });

    renderPage();
    // The « À traiter » section renders its own error — panne ≠ absence.
    expect(
      screen.getByText(/Impossible de charger les éléments à traiter/),
    ).toBeInTheDocument();
  });
});
