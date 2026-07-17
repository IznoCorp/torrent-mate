/**
 * Unit tests for the AcquisitionPage component (acq-watch Phase 4).
 *
 * Mocks the acquisition hooks and event-stream context so the page logic
 * (four panels, empty states, CRUD flows, status badges, pagination,
 * WS invalidation) is tested in isolation.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EventMessage } from "@/api/events";

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

const useFollowedMock = vi.fn();
const useWantedMock = vi.fn();
const useObligationsMock = vi.fn();
const useAcquisitionStatusMock = vi.fn();
const useDownloadsMock = vi.fn();

/** Stable mock mutation fns — cleared between tests, set per-test. */
let followMutateFn = vi.fn();
let updateFollowMutateFn = vi.fn();
let unfollowMutateFn = vi.fn();

const useEventStreamContextMock = vi.fn((): { events: EventMessage[] } => ({
  events: [],
}));

const useSchedulersMock = vi.fn();

const setWatcherMock = vi.fn();

vi.mock("@/hooks/useAcquisition", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useFollowed: (...args: unknown[]) => useFollowedMock(...args),
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useWanted: (...args: unknown[]) => useWantedMock(...args),
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useObligations: (...args: unknown[]) => useObligationsMock(...args),
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useAcquisitionStatus: () => useAcquisitionStatusMock(),
  // Arrival badge on the downloads tab (A4 limite avouée).
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useDownloads: () => useDownloadsMock(),
  useMediaSearch: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: () => undefined,
  }),
  useFollow: () => ({ mutate: followMutateFn, isPending: false }),
  useUpdateFollow: () => ({ mutate: updateFollowMutateFn, isPending: false }),
  useUnfollow: () => ({ mutate: unfollowMutateFn, isPending: false }),
  // §5 additions: the completeness accordion + the run-tracking hook. Stubbed
  // to inert values so the page/panel render is unaffected by them.
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

vi.mock("@/hooks/useSchedulers", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useSchedulers: () => useSchedulersMock(),
}));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual("@/api/client");
  return {
    ...(actual as object),
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return
    setWatcher: (...args: unknown[]) => setWatcherMock(...args),
  };
});

import AcquisitionPage from "@/pages/AcquisitionPage";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/** A single followed-series item matching FollowedSeriesItem shape. */
function makeFollowed(overrides: Record<string, unknown> = {}) {
  const merged = {
    id: 1,
    title: "Top Chef",
    active: true,
    added_at: 1_719_792_000,
    cadence: { interval_minutes: 60 },
    quality_profile: null,
    wanted_pending: 2,
    media_ref: { tvdb_id: 255968, tmdb_id: null, imdb_id: null },
    ...overrides,
  };
  // Mirror the backend-derived status (C14) so the fixture matches the real
  // response shape; an explicit `status` override still wins.
  const status = !merged.active
    ? "disabled"
    : merged.wanted_pending > 0
      ? "pending"
      : "up_to_date";
  return { status, ...merged };
}

/** A single wanted item matching WantedItemResponse shape. */
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

/** A single obligation item matching ObligationItem shape. */
function makeObligation(overrides: Record<string, unknown> = {}) {
  return {
    info_hash: "abcdef1234567890abcdef1234567890abcdef12",
    source_tracker: "lacale",
    dispatched_path: "/movies/Top Chef",
    min_seed_time_s: 86400,
    min_ratio: 1.0,
    observed_ratio: 0.8,
    hnr_count: 0,
    added_at: 1_719_792_000,
    released_at: null,
    breached_at: null,
    satisfied_at: null,
    accumulated_seed_time_s: 43200,
    ...overrides,
  };
}

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
    data: { items: [], total: 0, page: 1, page_size: 50 },
    error: null,
  });
  useObligationsMock.mockReturnValue({
    isLoading: false,
    isError: false,
    data: { items: [] },
    error: null,
  });
  useAcquisitionStatusMock.mockReturnValue({
    isLoading: false,
    isError: false,
    data: {
      watcher_enabled: true,
      last_successful_run_at: 1_719_792_000,
      recent_runs: [],
      deferred: [],
    },
    error: null,
  });
  useDownloadsMock.mockReturnValue({
    isLoading: false,
    isError: false,
    data: { downloads: [], client_available: true },
    error: null,
  });
  // Default: the grab scheduler is present with its live schedule (C15).
  useSchedulersMock.mockReturnValue({
    data: {
      schedulers: [
        {
          name: "personalscraper-grab",
          display_name: "Récupération (grab)",
          kind: "cron",
          schedule: "Tous les jours à 03:20 et 15:20",
          enabled: true,
          last_run_at: null,
          last_outcome: null,
        },
      ],
    },
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  followMutateFn = vi.fn();
  updateFollowMutateFn = vi.fn();
  unfollowMutateFn = vi.fn();
});

describe("AcquisitionPage", () => {
  // ── Tab navigation ──────────────────────────────────────────────────────

  it("renders the tab bar with all four panels", () => {
    mockAllEmpty();
    renderPage();

    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Suivis" })).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "File d'acquisition" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Obligations" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Watcher" })).toBeInTheDocument();
  });

  it('shows the Followed panel by default with "Suivis" tab selected', () => {
    mockAllEmpty();
    renderPage();

    expect(screen.getByRole("tab", { name: "Suivis" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByText(/aucune série suivie/i)).toBeInTheDocument();
  });

  it("switches to the File d'acquisition panel when clicking its tab", async () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(
      screen.getByRole("tab", { name: "File d'acquisition" }),
    );

    expect(
      screen.getByRole("tab", { name: "File d'acquisition" }),
    ).toHaveAttribute("aria-selected", "true");
    expect(
      await screen.findByText(/File d'acquisition — merged panel/),
    ).toBeInTheDocument();
  });

  it("switches to the Obligations panel when clicking its tab", async () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(screen.getByRole("tab", { name: "Obligations" }));

    expect(screen.getByRole("tab", { name: "Obligations" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(
      await screen.findByText(/aucune obligation de seed/i),
    ).toBeInTheDocument();
  });

  it("switches to the Watcher panel when clicking its tab", async () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(screen.getByRole("tab", { name: "Watcher" }));

    expect(screen.getByRole("tab", { name: "Watcher" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(await screen.findByText(/état du watcher/i)).toBeInTheDocument();
  });

  // ── Followed panel — table ──────────────────────────────────────────────

  it("renders followed series in a table with distinct IDs", () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          makeFollowed({
            id: 1,
            title: "Top Chef",
            wanted_pending: 3,
            media_ref: { tvdb_id: 255968, tmdb_id: null, imdb_id: null },
          }),
          makeFollowed({
            id: 2,
            title: "Koh-Lanta",
            active: false,
            wanted_pending: 0,
            media_ref: { tvdb_id: 12345, tmdb_id: null, imdb_id: null },
          }),
        ],
      },
      error: null,
    });
    renderPage();

    expect(screen.getByText("Top Chef")).toBeInTheDocument();
    // Derived état badge: Top Chef (active + 3 pending) → "En attente".
    expect(screen.getByText("En attente")).toBeInTheDocument();
    // The inactive follow leaves the grid (revue mobile 2026-07-15): it lives
    // in the collapsed « Suivis retirés » section, reactivatable.
    expect(screen.getByText("Suivis retirés (1)")).toBeInTheDocument();
    expect(screen.getByText(/Koh-Lanta/)).toBeInTheDocument();
    expect(screen.queryByText("12345")).not.toBeInTheDocument();
  });

  it("maps the backend-derived status verbatim without re-deriving it (C14)", () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          // Contradictory flags on purpose: the raw active/pending would read
          // as "En cours", but the backend-derived status says up_to_date. The
          // UI must trust `status` (no JSX derivation) → "À jour".
          makeFollowed({
            id: 1,
            title: "Top Chef",
            active: true,
            wanted_pending: 4,
            status: "up_to_date",
          }),
        ],
      },
      error: null,
    });
    renderPage();

    expect(screen.getByText("À jour")).toBeInTheDocument();
    expect(screen.queryByText("En cours")).not.toBeInTheDocument();
  });

  it("builds the automatic-search caption from the live grab scheduler (C15)", () => {
    mockAllEmpty();
    useSchedulersMock.mockReturnValue({
      data: {
        schedulers: [
          {
            name: "personalscraper-grab",
            display_name: "Récupération (grab)",
            kind: "cron",
            schedule: "Le lundi à 09:00",
            enabled: true,
            last_run_at: null,
            last_outcome: null,
          },
        ],
      },
    });
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [makeFollowed({ id: 1 })] },
      error: null,
    });
    renderPage();

    // The caption reflects the scheduler's live schedule, not a hardcoded one.
    expect(
      screen.getByText(/Recherche automatique : Le lundi à 09:00\./),
    ).toBeInTheDocument();
  });

  it("omits the automatic-search caption when the grab scheduler is absent (C15)", () => {
    mockAllEmpty();
    useSchedulersMock.mockReturnValue({ data: { schedulers: [] } });
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [makeFollowed({ id: 1 })] },
      error: null,
    });
    renderPage();

    expect(screen.queryByText(/Recherche automatique/)).not.toBeInTheDocument();
  });

  it("shows a per-series 'Rechercher maintenant' action for active series only", async () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          makeFollowed({ id: 1, title: "Top Chef", active: true }),
          makeFollowed({ id: 2, title: "Koh-Lanta", active: false }),
        ],
      },
      error: null,
    });
    renderPage();

    // Inactive follows left the grid (revue mobile 2026-07-15) and the
    // compact-row actions live in a DropdownMenu. Open the active row's menu.
    const trigger = screen.getByRole("button", {
      name: "Actions pour Top Chef",
    });
    fireEvent.pointerDown(trigger);
    // Rechercher maintenant is a menuitem in the dropdown.
    const searchItem = await screen.findByRole("menuitem", {
      name: "Rechercher maintenant",
    });
    expect(searchItem).not.toHaveAttribute("aria-disabled", "true");
  });

  it("toggles a followed series active/paused in place via updateFollow (C16)", async () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [makeFollowed({ id: 7, title: "Top Chef", active: true })],
      },
      error: null,
    });
    renderPage();

    // The active toggle moved to the DropdownMenu — open it first.
    const trigger = screen.getByRole("button", {
      name: "Actions pour Top Chef",
    });
    fireEvent.pointerDown(trigger);
    const deactivateItem = await screen.findByRole("menuitem", {
      name: "Désactiver",
    });
    fireEvent.click(deactivateItem);
    expect(updateFollowMutateFn).toHaveBeenCalledWith({
      id: 7,
      body: { active: false },
    });
  });

  it("surfaces a followed-query error instead of the empty state", () => {
    // Adversarial-review regression: on a failed followed query (e.g. 401) the
    // panel must show an error, NOT "aucune série suivie" (data illusion).
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("Session expirée"),
    });
    renderPage();

    expect(
      screen.getByText(/erreur de chargement des séries suivies/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/session expirée/i)).toBeInTheDocument();
    // The empty-state text must NOT be shown.
    expect(screen.queryByText(/aucune série suivie/i)).not.toBeInTheDocument();
  });

  it("shows wanted_pending badge when count is above zero", () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [makeFollowed({ wanted_pending: 3 })] },
      error: null,
    });
    renderPage();

    // The follow card shows the pending count as a "N en attente" badge.
    expect(screen.getByText("3 en attente")).toBeInTheDocument();
  });

  it("shows a next-search caption coloured by cadence tier (OBJ3)", () => {
    mockAllEmpty();
    const soon = Math.floor(Date.now() / 1000) + 3 * 3600; // ~3h out
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          makeFollowed({
            active: true,
            next_search_at: soon,
            cadence_tier: "warm",
          }),
        ],
      },
      error: null,
    });
    renderPage();

    // Next-search caption in the compact row shows a relative estimate.
    expect(screen.getByText(/dans ~3\s?h/)).toBeInTheDocument();
  });

  it('does not render the "Personnalisé" badge in compact row (removed per E1)', () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          makeFollowed({
            quality_profile: { preferred_words: ["MULTi"] },
          }),
        ],
      },
      error: null,
    });
    renderPage();

    // The quality_profile badge was removed from compact rows (Phase 02).
    expect(screen.queryByText("Personnalisé")).not.toBeInTheDocument();
  });

  it("shows loading skeletons while followed data loads", () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });
    renderPage();

    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  // ── Followed panel — add form ──────────────────────────────────────────

  it("renders the add form with TVDB ID and title inputs", () => {
    mockAllEmpty();
    renderPage();
    // The manual add-by-ID form is a collapsed accordion (secondary to the
    // primary title search) — expand it before asserting its inputs.
    fireEvent.click(
      screen.getByRole("button", { name: /Ajouter par ID TVDB/ }),
    );

    expect(screen.getByLabelText("ID TVDB")).toBeInTheDocument();
    expect(screen.getByLabelText(/titre/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Suivre" })).toBeInTheDocument();
  });

  it("calls useFollow().mutate on form submit", () => {
    mockAllEmpty();
    renderPage();
    fireEvent.click(
      screen.getByRole("button", { name: /Ajouter par ID TVDB/ }),
    );

    fireEvent.change(screen.getByLabelText("ID TVDB"), {
      target: { value: "255968" },
    });
    fireEvent.change(screen.getByLabelText(/titre/i), {
      target: { value: "Top Chef" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Suivre" }));

    expect(followMutateFn).toHaveBeenCalledWith(
      expect.objectContaining({
        tvdb_id: 255968,
        title: "Top Chef",
      }),
      expect.any(Object),
    );
  });

  it("disables the Follow button when tvdb_id is empty", () => {
    mockAllEmpty();
    renderPage();
    fireEvent.click(
      screen.getByRole("button", { name: /Ajouter par ID TVDB/ }),
    );

    expect(screen.getByRole("button", { name: "Suivre" })).toBeDisabled();
  });

  // ── Followed panel — unfollow ──────────────────────────────────────────

  it("calls useUnfollow().mutate on unfollow via dropdown", async () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [makeFollowed({ id: 42 })] },
      error: null,
    });
    renderPage();

    // Open the actions dropdown.
    const trigger = screen.getByRole("button", {
      name: "Actions pour Top Chef",
    });
    fireEvent.pointerDown(trigger);
    const retirerItem = await screen.findByRole("menuitem", {
      name: "Retirer",
    });
    fireEvent.click(retirerItem);
    expect(unfollowMutateFn).toHaveBeenCalledWith(42);
  });

  // ── Followed panel — edit-cadence dialog ────────────────────────────────

  it("opens the edit-cadence dialog from the dropdown", async () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          makeFollowed({
            title: "Top Chef",
            cadence: { interval_minutes: 120 },
          }),
        ],
      },
      error: null,
    });
    renderPage();

    // Open the actions dropdown, click Cadence.
    const trigger = screen.getByRole("button", {
      name: "Actions pour Top Chef",
    });
    fireEvent.pointerDown(trigger);
    const cadenceItem = await screen.findByRole("menuitem", {
      name: "Cadence",
    });
    fireEvent.click(cadenceItem);

    expect(
      await screen.findByRole("dialog", { name: /modifier la cadence/i }),
    ).toBeInTheDocument();
    // Pre-filled with existing interval.
    const intervalInput = screen.getByLabelText(/intervalle/i);
    expect(intervalInput).toHaveValue(120);
  });

  it("calls useUpdateFollow().mutate when saving the cadence dialog", async () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [makeFollowed({ id: 7, cadence: null })],
      },
      error: null,
    });
    renderPage();

    // Open dropdown, click Cadence.
    fireEvent.pointerDown(
      screen.getByRole("button", { name: "Actions pour Top Chef" }),
    );
    fireEvent.click(await screen.findByRole("menuitem", { name: "Cadence" }));
    await screen.findByRole("dialog", { name: /modifier la cadence/i });

    fireEvent.change(screen.getByLabelText(/intervalle/i), {
      target: { value: "90" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(updateFollowMutateFn).toHaveBeenCalledWith(
      { id: 7, body: { cadence: { interval_minutes: 90 } } },
      expect.any(Object),
    );
  });

  it("closes the cadence dialog when clicking Annuler", async () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [makeFollowed()] },
      error: null,
    });
    renderPage();

    // Open dropdown, click Cadence.
    fireEvent.pointerDown(
      screen.getByRole("button", { name: "Actions pour Top Chef" }),
    );
    fireEvent.click(await screen.findByRole("menuitem", { name: "Cadence" }));
    const dialog = await screen.findByRole("dialog", {
      name: /modifier la cadence/i,
    });
    expect(dialog).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(
      screen.queryByRole("dialog", { name: /modifier la cadence/i }),
    ).not.toBeInTheDocument();
  });

  // ── Wanted panel ───────────────────────────────────────────────────────

  it("renders the File d'acquisition panel sections", () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(
      screen.getByRole("tab", { name: "File d'acquisition" }),
    );

    // Stub renders both sections (3.1); full assertions in 3.3.
    expect(screen.getByText(/File d'acquisition — merged panel/)).toBeInTheDocument();
  });

  it("shows pagination controls with page info", () => {
    // Deferred to 3.3 — FileDAcquisitionPanel.test.tsx covers this.
    mockAllEmpty();
    renderPage();
    fireEvent.click(
      screen.getByRole("tab", { name: "File d'acquisition" }),
    );
    expect(
      screen.getByText(/File d'acquisition — merged panel/),
    ).toBeInTheDocument();
  });

  it("disables previous button on page 1", () => {
    // Deferred to 3.3 — FileDAcquisitionPanel.test.tsx covers this.
    mockAllEmpty();
    renderPage();
    fireEvent.click(
      screen.getByRole("tab", { name: "File d'acquisition" }),
    );
    expect(
      screen.getByText(/File d'acquisition — merged panel/),
    ).toBeInTheDocument();
  });

  it("calls useWanted with status filter when changed", async () => {
    // Deferred to 3.3 — FileDAcquisitionPanel.test.tsx covers this.
    mockAllEmpty();
    renderPage();
    fireEvent.click(
      screen.getByRole("tab", { name: "File d'acquisition" }),
    );
    expect(
      await screen.findByText(/File d'acquisition — merged panel/),
    ).toBeInTheDocument();
  });

  // ── Obligations panel ───────────────────────────────────────────────────

  it("renders obligation items with derived status badges", () => {
    mockAllEmpty();
    useObligationsMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          makeObligation({
            info_hash: "aaaa1111222233334444aaaa1111222233334444",
            source_tracker: "lacale",
            satisfied_at: 1_719_800_000,
          }),
          makeObligation({
            info_hash: "bbbb1111222233334444bbbb1111222233334444",
            source_tracker: "c411",
            breached_at: 1_719_780_000,
          }),
        ],
      },
      error: null,
    });
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Obligations" }));

    expect(screen.getByText("lacale")).toBeInTheDocument();
    expect(screen.getByText("c411")).toBeInTheDocument();
    // Derived status badges.
    expect(screen.getByText("Respectée")).toBeInTheDocument();
    expect(screen.getByText("Non respectée")).toBeInTheDocument();
  });

  it("shows HnR count as a danger badge when non-zero", () => {
    mockAllEmpty();
    useObligationsMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [makeObligation({ hnr_count: 3 })],
      },
      error: null,
    });
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Obligations" }));

    expect(screen.getByText("3")).toBeInTheDocument();
  });

  // ── Watcher panel ──────────────────────────────────────────────────────

  it("renders the watcher status card with enabled toggle", () => {
    mockAllEmpty();
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Watcher" }));

    expect(screen.getByText(/état du watcher/i)).toBeInTheDocument();
    // "Activé" is both the status badge and the switch label → getAll.
    expect(screen.getAllByText("Activé").length).toBeGreaterThan(0);
    // The switch should be checked.
    const switchEl = screen.getByRole("switch", { name: /activé/i });
    expect(switchEl).toBeInTheDocument();
    expect(switchEl).toHaveAttribute("aria-checked", "true");
  });

  it("calls setWatcher when the toggle is clicked", async () => {
    mockAllEmpty();
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
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Watcher" }));

    const switchEl = screen.getByRole("switch", { name: /activé/i });
    fireEvent.click(switchEl);

    // The toggle fires a react-query mutation → setWatcher runs on the next tick.
    await waitFor(() => {
      expect(setWatcherMock).toHaveBeenCalledWith({ enabled: false });
    });
  });

  it('shows "Jamais" and disabled state when watcher never ran', () => {
    mockAllEmpty();
    useAcquisitionStatusMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        watcher_enabled: false,
        last_successful_run_at: null,
        recent_runs: [],
      deferred: [],
      },
      error: null,
    });
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Watcher" }));

    expect(screen.getByText("Jamais")).toBeInTheDocument();
    expect(screen.getByText("Désactivé")).toBeInTheDocument();
    expect(screen.getByText(/aucune exécution récente/i)).toBeInTheDocument();
  });

  it("renders recent watcher runs in a table", () => {
    mockAllEmpty();
    useAcquisitionStatusMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        watcher_enabled: true,
        last_successful_run_at: 1_719_800_000,
        recent_runs: [
          {
            run_uid: "abc123def456",
            started_at: 1_719_790_000,
            ended_at: 1_719_795_000,
            outcome: "success",
            command: "follow-detect",
            trigger: "cron",
            result: { detected: 3, enqueued: 2 },
          },
          {
            run_uid: "ghi789jkl012",
            started_at: 1_719_760_000,
            ended_at: null,
            outcome: null,
            command: "grab",
            trigger: "web",
            result: null,
          },
        ],
        deferred: [],
      },
      error: null,
    });
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Watcher" }));

    // §5-aware table: run type + numeric result + outcome/running state.
    expect(screen.getByText("Détection")).toBeInTheDocument();
    expect(screen.getByText("Récupération")).toBeInTheDocument();
    expect(
      screen.getByText(/3 détecté\(s\), 2 mis en file/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Succès/)).toBeInTheDocument();
    expect(screen.getByText(/En cours…/)).toBeInTheDocument();
  });

  // ── Empty states ───────────────────────────────────────────────────────

  it("shows empty state for wanted panel when no items", () => {
    // Deferred to 3.3 — FileDAcquisitionPanel.test.tsx covers this.
    mockAllEmpty();
    renderPage();
    fireEvent.click(
      screen.getByRole("tab", { name: "File d'acquisition" }),
    );
    expect(
      screen.getByText(/File d'acquisition — merged panel/),
    ).toBeInTheDocument();
  });

  it("shows empty state for obligations panel when no items", () => {
    mockAllEmpty();
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Obligations" }));

    expect(screen.getByText(/aucune obligation de seed/i)).toBeInTheDocument();
  });

  // ── Error states ────────────────────────────────────────────────────────

  it("shows error message for wanted panel on fetch failure", () => {
    // Deferred to 3.3 — FileDAcquisitionPanel.test.tsx covers error states.
    mockAllEmpty();
    useWantedMock.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("Timeout"),
    });
    renderPage();
    fireEvent.click(
      screen.getByRole("tab", { name: "File d'acquisition" }),
    );
    expect(
      screen.getByText(/File d'acquisition — merged panel/),
    ).toBeInTheDocument();
  });

  it("shows error message for obligations panel on fetch failure", () => {
    mockAllEmpty();
    useObligationsMock.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("DB error"),
    });
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Obligations" }));

    expect(screen.getByText(/DB error/)).toBeInTheDocument();
  });

  it("shows error message for watcher panel on fetch failure", () => {
    mockAllEmpty();
    useAcquisitionStatusMock.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("Connection refused"),
    });
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Watcher" }));

    expect(screen.getByText(/Connection refused/)).toBeInTheDocument();
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

  // ── a11y ────────────────────────────────────────────────────────────────

  it("renders tablist with role presentation", () => {
    mockAllEmpty();
    renderPage();

    expect(screen.getByRole("tablist")).toBeInTheDocument();
    const tabs = screen.getAllByRole("tab");
    // Suivis, File d'acquisition, Obligations, Watcher.
    expect(tabs).toHaveLength(4);
  });

  it("renders the followed watch list as compact rows", () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [makeFollowed({ title: "Carded Show" })] },
      error: null,
    });
    renderPage();

    // The Suivis panel is now compact rows (Phase 02), not a MediaCard grid.
    expect(screen.getByText("Carded Show")).toBeInTheDocument();
    // The actions dropdown trigger is rendered.
    expect(
      screen.getByRole("button", { name: "Actions pour Carded Show" }),
    ).toBeInTheDocument();
  });

  it("add form inputs have associated labels", () => {
    mockAllEmpty();
    renderPage();
    fireEvent.click(
      screen.getByRole("button", { name: /Ajouter par ID TVDB/ }),
    );

    const tvdbInput = screen.getByLabelText("ID TVDB");
    expect(tvdbInput).toBeInTheDocument();
    const titleInput = screen.getByLabelText(/titre/i);
    expect(titleInput).toBeInTheDocument();
  });
});

describe("AcquisitionPage — badge Téléchargements (A4 limite avouée)", () => {
  it("shows the in-progress count on the File d'acquisition tab", () => {
    mockAllEmpty();
    useDownloadsMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        downloads: [
          { name: "A", state: "downloading", progress: 0.4 },
          { name: "B", state: "downloading", progress: 0.9 },
          { name: "C", state: "uploading", progress: 1 },
          { name: "D", state: "missing", progress: 0 },
        ],
        client_available: true,
      },
      error: null,
    });
    renderPage();

    const tab = screen.getByRole("tab", { name: /File d'acquisition/ });
    expect(within(tab).getByText("2")).toBeInTheDocument();
  });

  it("hides the badge when nothing is downloading", () => {
    mockAllEmpty();
    renderPage();

    const tab = screen.getByRole("tab", { name: /File d'acquisition/ });
    expect(within(tab).queryByText(/^\d+$/)).not.toBeInTheDocument();
  });
});

describe("AcquisitionPage — onglet adressable par URL (D3 / DOIT-10)", () => {
  it("ouvre l'onglet indiqué par ?tab= au chargement (deep-link)", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=obligations");

    expect(
      screen.getByRole("tab", { name: /Obligations/ }),
    ).toHaveAttribute("aria-selected", "true");
    expect(
      screen.getByRole("tab", { name: /Suivis/ }),
    ).toHaveAttribute("aria-selected", "false");
  });

  it("retombe sur « Suivis » sans paramètre (ou paramètre inconnu)", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=bogus");

    expect(screen.getByRole("tab", { name: /Suivis/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("écrit ?tab=<id> dans l'URL au changement d'onglet (partageable)", () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(
      screen.getByRole("tab", { name: /File d'acquisition/ }),
    );

    expect(screen.getByTestId("loc-search")).toHaveTextContent("?tab=file");
    expect(
      screen.getByRole("tab", { name: /File d'acquisition/ }),
    ).toHaveAttribute("aria-selected", "true");
  });

  it("nettoie le paramètre en revenant sur l'onglet par défaut", () => {
    mockAllEmpty();
    renderPage("/acquisition?tab=watcher");

    fireEvent.click(screen.getByRole("tab", { name: /Suivis/ }));

    // Default tab carries no param → clean /acquisition URL.
    expect(screen.getByTestId("loc-search")).toHaveTextContent("");
    expect(screen.getByTestId("loc-search").textContent).not.toContain("tab");
  });
});
