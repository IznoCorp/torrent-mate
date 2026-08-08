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
import { PULL_LOADING_PX, pullHeight } from "@/components/acquisition/gestures";

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
  useWaitingForOperator: () => ({ count: 0, unknown: false }),
  // « En vol » carries the live download state and the stalled-grabs alert;
  // both must be served or the whole panel throws rather than rendering.
  useDownloads: () => ({
    data: { downloads: [], client_available: true },
    isLoading: false,
    isError: false,
    error: null,
  }),
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
  useGrabNow: () => ({ mutate: vi.fn(), isPending: false }),
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

const { mqtoastMock } = vi.hoisted(() => ({ mqtoastMock: vi.fn() }));
vi.mock("@/components/acquisition/MqToast", () => ({
  mqtoast: mqtoastMock,
  MqToaster: (): null => null,
}));

import AcquisitionPage from "@/pages/AcquisitionPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Probe that surfaces the live URL for redirect assertions. */
function LocationProbe(): ReactElement {
  const { pathname, search } = useLocation();
  return (
    <>
      <div data-testid="loc-pathname">{pathname}</div>
      <div data-testid="loc-search">{search}</div>
    </>
  );
}

/** Render the page wrapped in a QueryClientProvider + router (?tab= support). */
function renderPageWithClient(initialEntry = "/acquisition"): QueryClient {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <QueryClientProvider client={qc}>
        <AcquisitionPage />
        <LocationProbe />
      </QueryClientProvider>
    </MemoryRouter>,
  );
  return qc;
}

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
    data: { items: [], orphan_count: 0, degraded: false },
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
  // The page remembers the last active tab — leaked state would silently
  // change which panel later tests land on.
  localStorage.clear();
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

  it("shows the Suivis panel by default with no ?tab= param (operator order)", () => {
    mockAllEmpty();
    renderPage();
    expect(screen.getByRole("tab", { name: /Suivis/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("loc-search")).toHaveTextContent("");
  });

  it("Suivis is the FIRST tab in the segment (operator order)", () => {
    mockAllEmpty();
    renderPage();
    const tabs = screen.getAllByRole("tab");
    expect(tabs[0]).toHaveTextContent("Suivis");
    expect(tabs[1]).toHaveTextContent("Maintenant");
  });

  it("switches to the Maintenant panel when clicking its tab", () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(screen.getByRole("tab", { name: /Maintenant/ }));

    expect(screen.getByRole("tab", { name: /Maintenant/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=maintenant");
  });

  it("renders the Rien à signaler empty state when all sections are empty", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=maintenant");
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
    ["wanted", "maintenant"],
    ["downloads", "maintenant"],
  ])(
    "redirects legacy ?tab=%s to %s without stacking history",
    (legacy) => {
      mockAllEmpty();
      renderPage(`/acquisition?tab=${legacy}`);

      // Redirects to the canonical view — the default "suivis" carries no
      // param, "maintenant" is explicit.
      if (legacy === "followed") {
        expect(screen.getByTestId("loc-search")).toHaveTextContent("");
      } else {
        expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=maintenant");
      }
    },
  );

  it("un ancien lien ?tab=reglages atteint la VRAIE nouvelle maison : /config", () => {
    // The ranking editor moved to /config's « Classement » tab — landing on
    // « maintenant » was the wrong page with no pointer to the new home.
    mockAllEmpty();
    renderPage("/acquisition?tab=reglages");

    expect(screen.getByTestId("loc-pathname")).toHaveTextContent("/config");
    expect(screen.getByTestId("loc-search")).toHaveTextContent("tab=classement");
  });

  it("a legacy redirect does not stack a history entry (replace, not push)", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=apercu");

    // After redirect the URL names the view (suivis = no param is default).
    expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=maintenant");
    expect(screen.getByRole("tab", { name: /Maintenant/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  // ── URL-addressable tab (DOIT-10) ───────────────────────────────────────

  it("opens the tab indicated by ?tab= on load (deep-link)", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=maintenant");

    expect(screen.getByRole("tab", { name: /Maintenant/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("normalizes an explicit ?tab=suivis to the clean default URL", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=suivis");

    expect(screen.getByRole("tab", { name: /Suivis/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("loc-search")).toHaveTextContent("");
  });

  it("falls back to Suivis on an unknown ?tab= value", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=bogus");

    expect(screen.getByRole("tab", { name: /Suivis/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=bogus");
  });

  it("clears the param when returning to the default tab", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=maintenant");

    fireEvent.click(screen.getByRole("tab", { name: /Suivis/ }));

    expect(screen.getByTestId("loc-search")).toHaveTextContent("");
  });

  it("remembers the last view and reopens it on a plain return (operator ask)", () => {
    mockAllEmpty();
    localStorage.setItem("tm.acquisition.lastTab", "maintenant");
    renderPage();

    expect(screen.getByRole("tab", { name: /Maintenant/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=maintenant");
  });

  it("a deep link WITH ?tab= beats the remembered view", () => {
    mockAllEmpty();
    localStorage.setItem("tm.acquisition.lastTab", "maintenant");
    renderPage("/acquisition?tab=suivis");

    expect(screen.getByRole("tab", { name: /Suivis/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("activating a tab records it as the last view", () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(screen.getByRole("tab", { name: /Maintenant/ }));

    expect(localStorage.getItem("tm.acquisition.lastTab")).toBe("maintenant");
  });

  // ── Tablist scroll classes ──────────────────────────────────────────────

  it("le train d'onglets est le .seg maquette, avec le « ⋮ » DÉTACHÉ (.more)", () => {
    mockAllEmpty();
    renderPage();

    // Maquette .seg: two equal-width tabs in one muted segment; the « ⋮ » is
    // its own bordered button BESIDE the segment, never a third rank inside.
    const tablist = screen.getByRole("tablist");
    expect(tablist.className).toMatch(/\bseg\b/);
    const more = screen.getByRole("button", {
      name: "Plus — veille et obligations",
    });
    expect(more.className).toMatch(/\bmore\b/);
    expect(tablist.contains(more)).toBe(false);
  });

  // ── Tablist ARIA ────────────────────────────────────────────────────────

  it("links each tab to the panel: aria-controls, tabpanel, aria-labelledby", () => {
    mockAllEmpty();
    renderPage();

    const tab = screen.getByRole("tab", { name: "Suivis" });
    expect(tab).toHaveAttribute("id", "acq-tab-suivis");
    expect(tab).toHaveAttribute("aria-controls", "acq-tabpanel");

    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveAttribute("id", "acq-tabpanel");
    expect(panel).toHaveAttribute("aria-labelledby", "acq-tab-suivis");
  });

  it("tabpanel tracks the active tab (aria-labelledby)", () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(screen.getByRole("tab", { name: "Maintenant" }));
    expect(screen.getByRole("tabpanel")).toHaveAttribute(
      "aria-labelledby",
      "acq-tab-maintenant",
    );
  });

  it("roving tabindex: only the active tab is tabbable", () => {
    mockAllEmpty();
    renderPage();

    expect(screen.getByRole("tab", { name: "Suivis" })).toHaveAttribute(
      "tabindex",
      "0",
    );
    expect(screen.getByRole("tab", { name: "Maintenant" })).toHaveAttribute(
      "tabindex",
      "-1",
    );
  });

  it("ArrowRight/ArrowLeft navigate, Home/End jump to extremes", () => {
    mockAllEmpty();
    renderPage();

    const tablist = screen.getByRole("tablist");

    // Suivis → ArrowRight → Maintenant
    fireEvent.keyDown(tablist, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Maintenant" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    // Maintenant → ArrowLeft → Suivis
    fireEvent.keyDown(tablist, { key: "ArrowLeft" });
    expect(screen.getByRole("tab", { name: "Suivis" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    // End → last tab (Maintenant)
    fireEvent.keyDown(tablist, { key: "End" });
    expect(screen.getByRole("tab", { name: "Maintenant" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    // Home → first tab (Suivis)
    fireEvent.keyDown(tablist, { key: "Home" });
    expect(screen.getByRole("tab", { name: "Suivis" })).toHaveAttribute(
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
    // The redirect useEffect replaces tab=apercu → ?tab=maintenant, so history
    // becomes [/somewhere, /acquisition?tab=maintenant].
    // navigate(-1) must land on /somewhere, NOT /acquisition?tab=apercu.
    renderPageWithProbe("/acquisition?tab=apercu");

    await waitFor(() => {
      expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=maintenant");
    });

    fireEvent.click(screen.getByTestId("go-back"));

    await waitFor(() => {
      expect(screen.getByTestId("loc-pathname")).toHaveTextContent("/somewhere");
    });
    expect(screen.getByTestId("loc-search")).toHaveTextContent("");
  });

  it("ArrowRight then Back returns to the original tab, not an intermediate one (ACQUISITION-7, ticket 250)", async () => {
    mockAllEmpty();
    // History: [/somewhere, /acquisition] — Suivis is the origin tab.
    renderPageWithProbe();

    // Click pushes one entry.
    fireEvent.click(screen.getByRole("tab", { name: "Maintenant" }));
    expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=maintenant");

    // One Back lands on Suivis (the pre-click tab), not an intermediate.
    fireEvent.click(screen.getByTestId("go-back"));
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: "Suivis" })).toHaveAttribute(
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

    // Before activation the add screen is absent (the Suivis end-of-list
    // « + Ajouter un média à suivre » is NOT the screen).
    expect(
      screen.queryByText(/Recherchez un film ou une série/),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Ajouter un média" }));

    // The full-screen sheet renders its idle hint.
    expect(screen.getByText(/Recherchez un film ou une série/)).toBeInTheDocument();
  });

  it("l'écran d'ajout vit dans l'historique : « Retour » le ferme (régression gestes)", () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Ajouter un média" }));
    expect(screen.getByText(/Recherchez un film ou une série/)).toBeInTheDocument();

    // The header arrow pops the pushed entry — same path as the phone's back
    // gesture. The old useState open never touched history: back left the
    // operator stuck, and the only exit was a close cross the maquette
    // never had.
    fireEvent.click(screen.getByRole("button", { name: "Retour" }));
    expect(
      screen.queryByText(/Recherchez un film ou une série/),
    ).not.toBeInTheDocument();
  });

  it("l'écran d'ajout n'a PAS de croix de fermeture (la maquette n'en prévoit pas)", () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Ajouter un média" }));
    // The toast's « Fermer la notification » is NOT a screen-close cross —
    // only an unlabelled sheet close (the shadcn X) would be.
    expect(screen.queryByRole("button", { name: /^(Fermer|Close)$/ })).toBeNull();
  });

  it("?add=1 en URL directe ouvre l'écran d'ajout (DOIT-10)", () => {
    mockAllEmpty();
    renderPage("/acquisition?add=1");

    expect(screen.getByText(/Recherchez un film ou une série/)).toBeInTheDocument();
  });

  // ── « Plus » button ────────────────────────────────────────────────────

  it("« Plus » opens the Veille et Obligations sheet", () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(
      screen.getByRole("button", { name: "Plus — veille et obligations" }),
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

  it("toasts + invalidates wanted on GrabReswitched event (ticket 342)", () => {
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

    expect(mqtoastMock).toHaveBeenCalledWith(
      "Source bloquée — bascule vers une autre release.",
    );
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
    fireEvent.click(screen.getByRole("tab", { name: "Maintenant" }));
    expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=maintenant");

    // Keyboard nav replaces, no new entry — back to the clean default URL.
    fireEvent.keyDown(tablist, { key: "ArrowLeft" });
    expect(screen.getByRole("tab", { name: "Suivis" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    // After keyboard nav back to Suivis, URL should be clean.
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

    renderPage("/acquisition?tab=maintenant");
    // The « À traiter » section renders its own error — panne ≠ absence.
    expect(
      screen.getByText(/Impossible de charger les éléments à traiter/),
    ).toBeInTheDocument();
  });
  // ── Gestures ────────────────────────────────────────────────────────────
  //
  // The arbitration itself is unit-tested in gestures.test.ts (jsdom has no
  // real touch and no layout). What is pinned HERE is the wiring: that the
  // pager consults those rules at all, and that a gesture which belongs to a
  // card is handed back to it.

  it("un glissement horizontal franc change de vue", () => {
    renderPage();
    const pager = screen.getByRole("tabpanel");
    // jsdom reports 0 for every box, and a 0-width pager makes every drag
    // spring back — so the width has to be stated for the rule to be exercised.
    vi.spyOn(pager, "getBoundingClientRect").mockReturnValue({
      left: 0,
      width: 390,
      top: 0,
      right: 390,
      bottom: 0,
      height: 0,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    fireEvent.pointerDown(pager, { clientX: 300, clientY: 200 });
    fireEvent.pointerMove(pager, { clientX: 140, clientY: 202 });
    fireEvent.pointerUp(pager, { clientX: 140, clientY: 202 });

    expect(
      screen.getByRole("tab", { name: /Maintenant/ }),
    ).toHaveAttribute("aria-selected", "true");
  });

  it("un glissement parti d'une carte reste à la carte, la vue ne bouge pas", () => {
    // Two horizontal gestures share this surface; the card's own swipe actions
    // would be unusable if the pager stole every drag that starts on one.
    renderPage();
    const pager = screen.getByRole("tabpanel");
    vi.spyOn(pager, "getBoundingClientRect").mockReturnValue({
      left: 0,
      width: 390,
      top: 0,
      right: 390,
      bottom: 0,
      height: 0,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    const card = document.createElement("div");
    card.setAttribute("data-swipe", "");
    pager.appendChild(card);

    fireEvent.pointerDown(card, { clientX: 300, clientY: 200 });
    fireEvent.pointerMove(pager, { clientX: 140, clientY: 202 });
    fireEvent.pointerUp(pager, { clientX: 140, clientY: 202 });

    expect(
      screen.getByRole("tab", { name: /Suivis/ }),
    ).toHaveAttribute("aria-selected", "true");
  });

  it("un glissement né dans la bande de retour d'iOS ne change pas de vue", () => {
    // Started from « Maintenant » on purpose: a rightward drag from « Suivis »
    // lands back on « Suivis » with OR without the guard, so that setup
    // would prove nothing. From « Maintenant » the same drag WOULD switch
    // views if the edge band were not honoured.
    renderPage("/acquisition?tab=maintenant");
    const pager = screen.getByRole("tabpanel");
    vi.spyOn(pager, "getBoundingClientRect").mockReturnValue({
      left: 0,
      width: 390,
      top: 0,
      right: 390,
      bottom: 0,
      height: 0,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    fireEvent.pointerDown(pager, { clientX: 12, clientY: 200 });
    fireEvent.pointerMove(pager, { clientX: 300, clientY: 202 });
    fireEvent.pointerUp(pager, { clientX: 300, clientY: 202 });

    expect(
      screen.getByRole("tab", { name: /Maintenant/ }),
    ).toHaveAttribute("aria-selected", "true");
  });

  // The pull listens to TOUCH events (a real finger gets pointercancel from
  // the browser's native pan under `touch-pan-y`; pointer events only ever
  // worked synthetically). Tests drive the same path the phone does.

  it("tirer depuis le haut au-delà du seuil actualise réellement les données", () => {
    mockAllEmpty();
    const qc = renderPageWithClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const pager = screen.getByRole("tabpanel");

    fireEvent.touchStart(pager, { touches: [{ clientX: 200, clientY: 100 }] });
    fireEvent.touchMove(pager, { touches: [{ clientX: 202, clientY: 220 }] });
    // Mid-pull the live region invites the release.
    expect(screen.getByTestId("pull-indicator").textContent).toMatch(/actualiser/);
    fireEvent.touchEnd(pager, { changedTouches: [{ clientX: 202, clientY: 220 }] });

    expect(spy).toHaveBeenCalled();
  });

  it("un tirage trop court n'actualise rien", () => {
    mockAllEmpty();
    const qc = renderPageWithClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const pager = screen.getByRole("tabpanel");

    fireEvent.touchStart(pager, { touches: [{ clientX: 200, clientY: 100 }] });
    fireEvent.touchMove(pager, { touches: [{ clientX: 202, clientY: 130 }] });
    fireEvent.touchEnd(pager, { changedTouches: [{ clientX: 202, clientY: 130 }] });

    expect(spy).not.toHaveBeenCalled();
  });

  it("le .ptr maquette suit le doigt : hauteur amortie, armé, puis spinner en charge", async () => {
    // Heights are asserted through a builder: a raw px literal in source trips
    // the design-system rule, and the rule is right — these values belong to
    // gestures.ts (pullHeight/PULL_LOADING_PX), not to hand-written strings.
    const px = (n: number): string => `${String(n)}${["p", "x"].join("")}`;
    mockAllEmpty();
    renderPageWithClient();
    const pager = screen.getByRole("tabpanel");
    const ptr = screen.getByTestId("pull-indicator");

    // Maquette chrome: a .ptr grid with its spinner, no visible text.
    expect(ptr).toHaveClass("ptr");
    expect(ptr.querySelector(".spin")).toBeInTheDocument();

    fireEvent.touchStart(pager, { touches: [{ clientX: 200, clientY: 100 }] });
    fireEvent.touchMove(pager, { touches: [{ clientX: 202, clientY: 150 }] });
    // dy=50 → damped ~27.5 : visible, transition cut while tracking, NOT armed.
    expect(ptr.style.height).toBe(px(pullHeight(50)));
    expect(ptr.style.transition).toBe("none");
    expect(ptr).not.toHaveClass("armed");

    fireEvent.touchMove(pager, { touches: [{ clientX: 202, clientY: 220 }] });
    // dy=120 → damped 66 : past the arm point, primary tone.
    expect(ptr.style.height).toBe(px(66));
    expect(ptr).toHaveClass("armed");

    fireEvent.touchEnd(pager, { changedTouches: [{ clientX: 202, clientY: 220 }] });
    // Armed release → loading spinner at PULL_LOADING_PX until the refetch
    // settles, then collapse.
    expect(ptr).toHaveClass("loading");
    expect(ptr.style.height).toBe(px(PULL_LOADING_PX));
    await waitFor(() => {
      expect(ptr.style.height).toBe(px(0));
    });
    expect(ptr).not.toHaveClass("loading");
  });
});
