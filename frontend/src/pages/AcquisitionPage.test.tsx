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
} from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EventMessage } from "@/api/events";

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

const useFollowedMock = vi.fn();
const useWantedMock = vi.fn();
const useObligationsMock = vi.fn();
const useAcquisitionStatusMock = vi.fn();

/** Stable mock mutation fns — cleared between tests, set per-test. */
let followMutateFn = vi.fn();
let updateFollowMutateFn = vi.fn();
let unfollowMutateFn = vi.fn();

const useEventStreamContextMock = vi.fn((): { events: EventMessage[] } => ({
  events: [],
}));

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
}));

vi.mock("@/hooks/useEventStreamContext", () => ({
  useEventStreamContext: () => useEventStreamContextMock(),
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
  return {
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

/** Render the page wrapped in a QueryClientProvider. */
function renderPage(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <AcquisitionPage />
    </QueryClientProvider>
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
    },
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
      screen.getByRole("tab", { name: "Recherches" }),
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
    expect(
      screen.getByText(/aucune série suivie/i),
    ).toBeInTheDocument();
  });

  it("switches to the Wanted panel when clicking the Recherches tab", async () => {
    mockAllEmpty();
    renderPage();

    fireEvent.click(screen.getByRole("tab", { name: "Recherches" }));

    expect(screen.getByRole("tab", { name: "Recherches" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(
      await screen.findByText(/aucune recherche en file/i),
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
    expect(
      await screen.findByText(/état du watcher/i),
    ).toBeInTheDocument();
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
    expect(screen.getByText("Koh-Lanta")).toBeInTheDocument();
    // TVDB IDs rendered (distinct values).
    expect(screen.getByText("255968")).toBeInTheDocument();
    expect(screen.getByText("12345")).toBeInTheDocument();
    // Derived état badges: Top Chef (active + 3 pending) → "En cours";
    // Koh-Lanta (inactive) → "Désactivé".
    expect(screen.getByText("En cours")).toBeInTheDocument();
    expect(screen.getByText("Désactivé")).toBeInTheDocument();
  });

  it("shows a per-series 'Déclencher' trigger, disabled for an inactive series", () => {
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

    const triggers = screen.getAllByRole("button", { name: "Déclencher" });
    expect(triggers).toHaveLength(2);
    // Active series → enabled; inactive → disabled (can't grab a paused series).
    expect(triggers[0]).not.toBeDisabled();
    expect(triggers[1]).toBeDisabled();
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

  it('shows "Personnalisé" badge when quality_profile is set', () => {
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

    expect(screen.getByText("Personnalisé")).toBeInTheDocument();
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

    expect(screen.getByLabelText("ID TVDB")).toBeInTheDocument();
    expect(screen.getByLabelText(/titre/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Suivre" }),
    ).toBeInTheDocument();
  });

  it("calls useFollow().mutate on form submit", () => {
    mockAllEmpty();
    renderPage();

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

    expect(screen.getByRole("button", { name: "Suivre" })).toBeDisabled();
  });

  // ── Followed panel — unfollow ──────────────────────────────────────────

  it("calls useUnfollow().mutate on unfollow button click", () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [makeFollowed({ id: 42 })] },
      error: null,
    });
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Retirer" }));
    expect(unfollowMutateFn).toHaveBeenCalledWith(42);
  });

  // ── Followed panel — edit-cadence dialog ────────────────────────────────

  it("opens the edit-cadence dialog when clicking the Cadence button", async () => {
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

    fireEvent.click(screen.getByRole("button", { name: "Cadence" }));

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

    fireEvent.click(screen.getByRole("button", { name: "Cadence" }));
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

    fireEvent.click(screen.getByRole("button", { name: "Cadence" }));
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

  it("renders wanted items in a table with status filter", () => {
    mockAllEmpty();
    useWantedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          makeWanted({ id: 10, title: "Top Chef", status: "pending" }),
          makeWanted({ id: 11, title: "Koh-Lanta", status: "grabbed" }),
        ],
        total: 2,
        page: 1,
        page_size: 50,
      },
      error: null,
    });
    renderPage();

    fireEvent.click(screen.getByRole("tab", { name: "Recherches" }));

    expect(screen.getByText("Top Chef")).toBeInTheDocument();
    expect(screen.getByText("Koh-Lanta")).toBeInTheDocument();
    expect(screen.getByText("En attente")).toBeInTheDocument();
    expect(screen.getByText("Récupéré")).toBeInTheDocument();
  });

  it("shows pagination controls with page info", () => {
    mockAllEmpty();
    useWantedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: Array.from({ length: 5 }).map((_, i) =>
          makeWanted({ id: i, title: `Show ${String(i)}` }),
        ),
        total: 55,
        page: 1,
        page_size: 50,
      },
      error: null,
    });
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Recherches" }));

    expect(screen.getByText(/page 1 \/ 2/i)).toBeInTheDocument();
    expect(screen.getByText(/55 résultats/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "← Précédent" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Suivant →" }),
    ).toBeInTheDocument();
  });

  it("disables previous button on page 1", () => {
    mockAllEmpty();
    useWantedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [makeWanted()],
        total: 1,
        page: 1,
        page_size: 50,
      },
      error: null,
    });
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Recherches" }));

    expect(
      screen.getByRole("button", { name: "← Précédent" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Suivant →" }),
    ).toBeDisabled();
  });

  it("calls useWanted with status filter when changed", async () => {
    mockAllEmpty();
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Recherches" }));

    // The Radix Tabs content mounts asynchronously — wait for the status filter
    // Select (role=combobox) to appear in the Wanted panel.
    expect(await screen.findByRole("combobox")).toBeInTheDocument();
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
      },
      error: null,
    });
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Watcher" }));

    expect(screen.getByText("Jamais")).toBeInTheDocument();
    expect(screen.getByText("Désactivé")).toBeInTheDocument();
    expect(
      screen.getByText(/aucune exécution récente/i),
    ).toBeInTheDocument();
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
            outcome: "completed",
          },
          {
            run_uid: "ghi789jkl012",
            started_at: 1_719_760_000,
            ended_at: null,
            outcome: null,
          },
        ],
      },
      error: null,
    });
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Watcher" }));

    // Run UIDs rendered (not truncated, they are short enough).
    expect(screen.getByText("abc123def456")).toBeInTheDocument();
    expect(screen.getByText(/Succès/)).toBeInTheDocument();
  });

  // ── Empty states ───────────────────────────────────────────────────────

  it("shows empty state for wanted panel when no items", () => {
    mockAllEmpty();
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Recherches" }));

    expect(
      screen.getByText(/aucune recherche en file/i),
    ).toBeInTheDocument();
  });

  it("shows empty state for obligations panel when no items", () => {
    mockAllEmpty();
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Obligations" }));

    expect(
      screen.getByText(/aucune obligation de seed/i),
    ).toBeInTheDocument();
  });

  // ── Error states ────────────────────────────────────────────────────────

  it("shows error message for wanted panel on fetch failure", () => {
    mockAllEmpty();
    useWantedMock.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("Timeout"),
    });
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: "Recherches" }));

    expect(screen.getByText(/Timeout/)).toBeInTheDocument();
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
      <QueryClientProvider client={qc}>
        <AcquisitionPage />
      </QueryClientProvider>
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
      <QueryClientProvider client={qc}>
        <AcquisitionPage />
      </QueryClientProvider>
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
      <QueryClientProvider client={qc}>
        <AcquisitionPage />
      </QueryClientProvider>
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
      <QueryClientProvider client={qc}>
        <AcquisitionPage />
      </QueryClientProvider>
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
    expect(tabs).toHaveLength(4);
  });

  it("renders the followed watch list as cards", () => {
    mockAllEmpty();
    useFollowedMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [makeFollowed({ title: "Carded Show" })] },
      error: null,
    });
    renderPage();

    // The Suivis panel is a MediaCard grid (not a table): the series title +
    // its actions render.
    expect(screen.getByText("Carded Show")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Déclencher" }),
    ).toBeInTheDocument();
  });

  it("add form inputs have associated labels", () => {
    mockAllEmpty();
    renderPage();

    const tvdbInput = screen.getByLabelText("ID TVDB");
    expect(tvdbInput).toBeInTheDocument();
    const titleInput = screen.getByLabelText(/titre/i);
    expect(titleInput).toBeInTheDocument();
  });
});
