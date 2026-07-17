/**
 * Unit tests for the Medias page — library grid default, segments, resolution
 * deck, and decision browse (``/medias``).
 *
 * Mocks the data hooks so the page logic (tabs, library segments, optional
 * multi-select filter chips + counts, list/detail navigation, inline
 * quick-dismiss) is tested in isolation. The {@link DecisionDetail}
 * component's behaviour is tested in its own suite.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  DecisionListItem,
  DecisionDetail as DecisionDetailType,
} from "@/api/decisions";
import type { StagingMediaItem } from "@/api/staging";
import type { DecisionStatus } from "@/components/decisions/triggers";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

function makeListItem(
  overrides: Partial<DecisionListItem> = {},
): DecisionListItem {
  return {
    id: 1,
    media_kind: "movie",
    extracted_title: "Test Movie",
    extracted_year: 2024,
    staging_path: "/staging/001-MOVIES/Test Movie (2024)",
    trigger: "below_threshold",
    candidates_count: 2,
    status: "pending",
    created_at: 1_750_000_000,
    ...overrides,
  };
}

function makeDetail(
  overrides: Partial<DecisionDetailType> = {},
): DecisionDetailType {
  return {
    id: 1,
    media_kind: "movie",
    extracted_title: "Test Movie",
    extracted_year: 2024,
    staging_path: "/staging/001-MOVIES/Test Movie (2024)",
    trigger: "below_threshold",
    candidates: [],
    candidates_count: 0,
    status: "pending",
    created_at: 1_750_000_000,
    resolution_json: null,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

const useAllDecisionsMock = vi.fn();
const useDecisionDetailMock = vi.fn();
const useDecisionsMock = vi.fn();

// Stub the query hooks the page reads; keep the REAL shared mutation hooks
// (useDismissDecision for the inline quick-dismiss) so it still routes through
// the mocked @/api/decisions dismissDecision asserted below.
vi.mock("@/hooks/useDecisions", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/hooks/useDecisions")>();
  return {
    ...actual,
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return
    useAllDecisions: (...args: unknown[]) => useAllDecisionsMock(...args),
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return
    useDecisionDetail: (...args: unknown[]) => useDecisionDetailMock(...args),
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return
    useDecisions: (...args: unknown[]) => useDecisionsMock(...args),
  };
});

// The page uses dismissDecision for the inline quick-dismiss mutation; stub it
// so the mutation never hits the network. Unlike DecisionDetail's dismiss, the
// PAGE's own quickDismissMutation onError branches (410/409/generic/non-Api) +
// the onSettled dismissingId reset are covered here (R3).
vi.mock("@/api/decisions", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/decisions")>("@/api/decisions");
  return { ...actual, dismissDecision: vi.fn() };
});

// The page emits sonner toasts from the inline quick-dismiss mutation; mock the
// toast module so those branches are assertable without a real toast host.
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// The library view (?media deep-link test) mounts StagingLibrary, whose data
// hook needs the WebSocket EventStreamProvider; stub the hook only —
// stagingMediaKeys stays real (the deck/detail invalidations import it).
const useStagingMediaMock = vi.fn();

vi.mock("@/hooks/useStagingMedia", async () => {
  const actual = await vi.importActual<
    typeof import("@/hooks/useStagingMedia")
  >("@/hooks/useStagingMedia");
  return {
    ...actual,
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return
    useStagingMedia: (...args: unknown[]) => useStagingMediaMock(...args),
  };
});

import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { dismissDecision } from "@/api/decisions";
const dismissDecisionMock = vi.mocked(dismissDecision);

import Medias from "@/pages/Medias";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract the last argument passed to a mock as an array. */
function lastArgs(mock: ReturnType<typeof vi.fn>): unknown[] | undefined {
  const calls = mock.mock.calls as unknown[][];
  return calls[calls.length - 1];
}

/** Default per-status counts for the chip counters. */
const ZERO_COUNTS = {
  pending: 0,
  resolved: 0,
  dismissed: 0,
  superseded: 0,
} as const;

function setupDecisionsList(
  overrides: {
    items?: DecisionListItem[];
    isLoading?: boolean;
    isError?: boolean;
    counts?: Partial<Record<string, number | null>>;
    errored?: DecisionStatus[];
  } = {},
): void {
  const {
    items = [makeListItem()],
    isLoading = false,
    isError = false,
    counts = {},
    errored = [],
  } = overrides;

  useAllDecisionsMock.mockReturnValue({
    items,
    counts: { ...ZERO_COUNTS, ...counts },
    isLoading,
    isError,
    errored: new Set(errored),
  });

  useDecisionDetailMock.mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
  });

  // The ResolutionDeck ("À résoudre" tab) calls useDecisions; give it a benign
  // empty pending page so it mounts without crashing when a test switches to it.
  useDecisionsMock.mockReturnValue({
    data: { items: [], pending_count: 0, total: 0, page: 1, page_size: 200 },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  });

  // Default: StagingLibrary is loading (no data yet). Tests that need specific
  // staging data override this mock before rendering.
  useStagingMediaMock.mockReturnValue({
    data: undefined,
    isLoading: true,
    isError: false,
    error: null,
  });
}

/**
 * Render the page. Defaults to the library view (the grid default). Pass
 * ``"decisions"`` to switch to the Décisions tab (where the flat-list /
 * filter / detail assertions live) or ``"resolve"`` for the resolution deck.
 */
function renderPage(
  view: "decisions" | "library" | "resolve" = "library",
): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  const tree: ReactElement = (
    <MemoryRouter initialEntries={["/medias"]}>
      <QueryClientProvider client={qc}>
        <Medias />
      </QueryClientProvider>
    </MemoryRouter>
  );
  render(tree);
  if (view === "decisions") {
    fireEvent.click(screen.getByRole("button", { name: "Décisions" }));
  } else if (view === "resolve") {
    fireEvent.click(screen.getByRole("button", { name: /^À résoudre/ }));
  }
}

/** Find a button whose text includes the given string, or throw. */
function findButtonByText(text: string): HTMLElement {
  const rows = screen.getAllByRole("button");
  const found = rows.find((el) => el.textContent.includes(text));
  if (found == null) {
    throw new Error(`No button found with text "${text}"`);
  }
  return found;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Medias", () => {
  // ---- Render ----------------------------------------------------------------

  it("affiche le titre de la page", () => {
    setupDecisionsList();
    renderPage("decisions");
    expect(screen.getByText("Médias")).toBeInTheDocument();
  });

  it("un chargement direct avec ?media ouvre la vue bibliothèque (deep-link)", () => {
    // Regression (caught live): a FRESH load of /medias?media=<id> landed on
    // a non-library view and silently dropped the param. The view must
    // initialize from the URL so the route-addressable promise (#255) holds on
    // a fresh load too.
    setupDecisionsList();
    const qc = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    render(
      <MemoryRouter initialEntries={["/medias?media=0268dd337626b989"]}>
        <QueryClientProvider client={qc}>
          <Medias />
        </QueryClientProvider>
      </MemoryRouter>,
    );
    // The library view (search box) is shown, not the deck's empty state.
    expect(
      screen.getByPlaceholderText("Rechercher un titre…"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Aucune décision à résoudre"),
    ).not.toBeInTheDocument();
  });

  // ---- Library view (default) -------------------------------------------------

  it("affiche la grille de la bibliothèque par défaut", () => {
    setupDecisionsList();
    renderPage();
    // The StagingLibrary search input is visible — proves we're on the library
    // grid, not the deck or the decision browse.
    expect(
      screen.getByPlaceholderText("Rechercher un titre…"),
    ).toBeInTheDocument();
    // The Décisions tab's status filter chips are NOT visible on the library tab.
    expect(
      screen.queryByRole("group", {
        name: /Filtrer les décisions par statut/,
      }),
    ).not.toBeInTheDocument();
  });

  it("affiche les segments de filtrage de la bibliothèque", () => {
    setupDecisionsList();
    renderPage();
    const group = screen.getByRole("group", {
      name: /Filtrer par étape du pipeline/,
    });
    expect(within(group).getByText("Tous")).toBeInTheDocument();
    expect(within(group).getByText("À traiter")).toBeInTheDocument();
    expect(within(group).getByText("En cours")).toBeInTheDocument();
    expect(within(group).getByText("Prêts")).toBeInTheDocument();
  });

  it("marque le segment actif avec aria-pressed", () => {
    setupDecisionsList();
    renderPage();
    const group = screen.getByRole("group", {
      name: /Filtrer par étape du pipeline/,
    });
    const tousBtn = within(group).getByText("Tous").closest("button");
    expect(tousBtn).toHaveAttribute("aria-pressed", "true");

    const pretsBtn = within(group).getByText("Prêts").closest("button");
    if (pretsBtn == null) throw new Error("Prêts button not found");
    fireEvent.click(pretsBtn);
    expect(within(group).getByText("Prêts").closest("button")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(tousBtn).toHaveAttribute("aria-pressed", "false");
  });

  it("affiche les chips de filtre de statut", () => {
    setupDecisionsList();
    renderPage("decisions");
    // Scope to the filter-chip group: "En attente" also appears as the row's
    // status badge (STATUS_SHORT_LABEL.pending === STATUS_LABEL.pending).
    const group = screen.getByRole("group", {
      name: /Filtrer les décisions par statut/,
    });
    expect(within(group).getByText("En attente")).toBeInTheDocument();
    expect(within(group).getByText("Résolues")).toBeInTheDocument();
    expect(within(group).getByText("Ignorées")).toBeInTheDocument();
    expect(within(group).getByText("Remplacées")).toBeInTheDocument();
  });

  it("affiche un compteur live par statut sur les chips", () => {
    setupDecisionsList({
      counts: { pending: 3, resolved: 12, dismissed: 4, superseded: 1 },
    });
    renderPage("decisions");
    // Each chip shows its per-status total in parentheses.
    expect(screen.getByText("(3)")).toBeInTheDocument();
    expect(screen.getByText("(12)")).toBeInTheDocument();
    expect(screen.getByText("(4)")).toBeInTheDocument();
    expect(screen.getByText("(1)")).toBeInTheDocument();
  });

  it("affiche toutes les décisions par défaut sans sélectionner de statut", () => {
    // Default view = no active filter → the hook is called with an empty array
    // (which fetches + merges every status). The list shows all items.
    setupDecisionsList({
      items: [
        makeListItem({ id: 1, extracted_title: "Movie A", status: "pending" }),
        makeListItem({ id: 2, extracted_title: "Movie B", status: "resolved" }),
      ],
    });
    renderPage("decisions");

    expect(screen.getByText("Movie A")).toBeInTheDocument();
    expect(screen.getByText("Movie B")).toBeInTheDocument();

    // The hook received an empty active-status list (show all).
    const call = lastArgs(useAllDecisionsMock);
    expect(call).toBeDefined();
    if (!call) throw new Error("unreachable");
    expect(call[0]).toEqual([]);
  });

  it("affiche un texte d'aide indiquant que tout est affiché par défaut", () => {
    setupDecisionsList();
    renderPage("decisions");
    expect(
      screen.getByText(/Toutes les décisions sont affichées/),
    ).toBeInTheDocument();
  });

  it("affiche la liste des décisions", () => {
    setupDecisionsList();
    renderPage("decisions");
    // Two nodes match "Décisions": the tab button (clicked by renderPage) AND the
    // CardTitle inside DecisionList. Both must exist to prove the decisions tab
    // rendered correctly.
    expect(screen.getAllByText("Décisions")).toHaveLength(2);
  });

  it("affiche un message d'erreur quand la requête échoue", () => {
    setupDecisionsList({ isError: true });
    renderPage("decisions");
    expect(
      screen.getByText("Erreur lors du chargement des décisions."),
    ).toBeInTheDocument();
  });

  it("affiche un placeholder desktop quand aucune décision n'est sélectionnée", () => {
    setupDecisionsList();
    renderPage("decisions");
    expect(
      screen.getByText("Sélectionnez une décision pour voir les détails."),
    ).toBeInTheDocument();
  });

  // ---- Filter chips ---------------------------------------------------------

  it("active le filtre 'resolved' quand le chip Résolues est cliqué", () => {
    setupDecisionsList();
    renderPage("decisions");

    fireEvent.click(screen.getByText("Résolues"));

    // The active-status list now contains only 'resolved' (chip is a toggle).
    const call = lastArgs(useAllDecisionsMock);
    expect(call).toBeDefined();
    if (!call) throw new Error("unreachable");
    expect(call[0]).toEqual(["resolved"]);
  });

  it("cumule plusieurs filtres (multi-select)", () => {
    setupDecisionsList();
    renderPage("decisions");

    fireEvent.click(screen.getByText("Résolues"));
    fireEvent.click(screen.getByText("Ignorées"));

    // Both statuses active at once — the filter is multi-select, not a tab.
    const call = lastArgs(useAllDecisionsMock);
    expect(call).toBeDefined();
    if (!call) throw new Error("unreachable");
    expect(call[0]).toEqual(["resolved", "dismissed"]);
  });

  it("désactive un filtre déjà actif au second clic", () => {
    setupDecisionsList();
    renderPage("decisions");

    fireEvent.click(screen.getByText("Résolues"));
    fireEvent.click(screen.getByText("Résolues"));

    // Toggled off → back to "show all" (empty active list).
    const call = lastArgs(useAllDecisionsMock);
    expect(call).toBeDefined();
    if (!call) throw new Error("unreachable");
    expect(call[0]).toEqual([]);
  });

  it("marque le chip actif avec aria-pressed", () => {
    setupDecisionsList();
    renderPage("decisions");

    const chip = screen.getByText("Résolues").closest("button");
    expect(chip).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(chip as HTMLElement);
    expect(chip).toHaveAttribute("aria-pressed", "true");
  });

  it("réinitialise la sélection quand le statut change", () => {
    setupDecisionsList();
    useDecisionDetailMock.mockReturnValue({
      data: makeDetail(),
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPage("decisions");

    // getAllByText — "Test Movie" appears in both the list row and the
    // detail-panel header after selection, so a single getByText would throw.
    const rows = screen.getAllByText("Test Movie");
    const row = rows[0];
    if (row == null) throw new Error("No row found");
    fireEvent.click(row);

    fireEvent.click(screen.getByText("Résolues"));

    const call = lastArgs(useDecisionDetailMock);
    expect(call).toBeDefined();
    if (!call) throw new Error("unreachable");
    expect(call[0]).toBe(0);
  });

  // ---- Selection → detail ---------------------------------------------------

  it("charge le détail quand une ligne est sélectionnée", () => {
    setupDecisionsList();
    useDecisionDetailMock.mockReturnValue({
      data: makeDetail(),
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPage("decisions");

    const selectRow = findButtonByText("Test Movie");
    fireEvent.click(selectRow);

    const call = lastArgs(useDecisionDetailMock);
    expect(call).toBeDefined();
    if (!call) throw new Error("unreachable");
    expect(call[0]).toBe(1);
  });

  it("affiche le bouton retour sur mobile après sélection", () => {
    setupDecisionsList();
    useDecisionDetailMock.mockReturnValue({
      data: makeDetail(),
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPage("decisions");

    const selectRow = findButtonByText("Test Movie");
    fireEvent.click(selectRow);

    expect(screen.getByText("← Retour à la liste")).toBeInTheDocument();
  });

  it("retourne à la liste quand le bouton retour est cliqué", async () => {
    setupDecisionsList();
    useDecisionDetailMock.mockReturnValue({
      data: makeDetail(),
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPage("decisions");

    const selectRow = findButtonByText("Test Movie");
    fireEvent.click(selectRow);

    await waitFor(() => {
      fireEvent.click(screen.getByText("← Retour à la liste"));
    });

    const call = lastArgs(useDecisionDetailMock);
    expect(call).toBeDefined();
    if (!call) throw new Error("unreachable");
    expect(call[0]).toBe(0);
  });

  // ---- Decision handled callback ---------------------------------------------

  it("réinitialise la sélection quand le filtre change après sélection", () => {
    setupDecisionsList();
    useDecisionDetailMock.mockReturnValue({
      data: makeDetail(),
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPage("decisions");

    const selectRow = findButtonByText("Test Movie");
    fireEvent.click(selectRow);

    fireEvent.click(screen.getByText("Résolues"));

    const call = lastArgs(useDecisionDetailMock);
    expect(call).toBeDefined();
    if (!call) throw new Error("unreachable");
    expect(call[0]).toBe(0);
  });

  // ---- Loading state ---------------------------------------------------------

  it("affiche des skeletons pendant le chargement de la liste", () => {
    setupDecisionsList({ isLoading: true, items: [] });
    renderPage("decisions");

    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("affiche un skeleton pour le détail en chargement", () => {
    setupDecisionsList();
    useDecisionDetailMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    renderPage("decisions");

    const selectRow = findButtonByText("Test Movie");
    fireEvent.click(selectRow);

    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  // ---- Inline quick-dismiss (§4.1) ------------------------------------------

  it("ignore une décision pending inline sans ouvrir le détail", async () => {
    dismissDecisionMock.mockResolvedValueOnce(
      makeDetail({ status: "dismissed" }),
    );
    setupDecisionsList({
      items: [makeListItem({ id: 5, status: "pending" })],
    });
    renderPage("decisions");

    fireEvent.click(screen.getByText("Ignorer"));

    await waitFor(() => {
      expect(dismissDecisionMock).toHaveBeenCalledWith(5);
    });

    // No detail panel was opened — the placeholder stays visible on desktop.
    expect(
      screen.getByText("Sélectionnez une décision pour voir les détails."),
    ).toBeInTheDocument();
  });

  // ---- Inline quick-dismiss error branches (R3) -----------------------------
  // These exercise the page's OWN quickDismissMutation onError paths — a DIFFERENT
  // code path from DecisionDetail's dismiss mutation (covered in its own suite).

  it("affiche le message 410 sur échec du quick-dismiss inline", async () => {
    dismissDecisionMock.mockRejectedValueOnce(new ApiError(410, "Superseded"));
    setupDecisionsList({ items: [makeListItem({ id: 5, status: "pending" })] });
    renderPage("decisions");

    fireEvent.click(screen.getByText("Ignorer"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Cette décision a été remplacée par une version plus récente.",
      );
    });
  });

  it("affiche le message 409 sur échec du quick-dismiss inline", async () => {
    dismissDecisionMock.mockRejectedValueOnce(
      new ApiError(409, "No longer pending"),
    );
    setupDecisionsList({ items: [makeListItem({ id: 5, status: "pending" })] });
    renderPage("decisions");

    fireEvent.click(screen.getByText("Ignorer"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Cette décision n'est plus en attente.",
      );
    });
  });

  it("affiche le detail brut sur un autre statut ApiError du quick-dismiss inline", async () => {
    dismissDecisionMock.mockRejectedValueOnce(
      new ApiError(500, "Boom generic"),
    );
    setupDecisionsList({ items: [makeListItem({ id: 5, status: "pending" })] });
    renderPage("decisions");

    fireEvent.click(screen.getByText("Ignorer"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Boom generic");
    });
  });

  it("affiche un message générique sur une erreur non-ApiError du quick-dismiss inline", async () => {
    dismissDecisionMock.mockRejectedValueOnce(new Error("network down"));
    setupDecisionsList({ items: [makeListItem({ id: 5, status: "pending" })] });
    renderPage("decisions");

    fireEvent.click(screen.getByText("Ignorer"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Erreur inattendue.");
    });
  });

  it("réinitialise dismissingId après un quick-dismiss en échec (onSettled)", async () => {
    dismissDecisionMock.mockRejectedValueOnce(new ApiError(409, "nope"));
    setupDecisionsList({ items: [makeListItem({ id: 5, status: "pending" })] });
    renderPage("decisions");

    const dismissButton = screen.getByText("Ignorer");
    fireEvent.click(dismissButton);

    // While in flight the button shows the "…" spinner label (dismissingId set).
    await waitFor(() => {
      expect(screen.getByText("…")).toBeInTheDocument();
    });

    // onSettled resets dismissingId → the button returns to its "Ignorer" label
    // and is re-enabled (proves the reset fires on the ERROR path too).
    await waitFor(() => {
      expect(screen.getByText("Ignorer")).toBeInTheDocument();
    });
    expect(screen.getByText("Ignorer")).not.toBeDisabled();
  });

  // ---- Partial-failure: pending query failed (SF2) --------------------------

  it("distingue « 0 pending » de « pending failed to load »", () => {
    // The `pending` query errored (others succeeded). The page must NOT render a
    // misleading "0 pending" — it shows a "?" count + an explicit error banner.
    setupDecisionsList({
      items: [makeListItem({ id: 2, status: "resolved" })],
      counts: { pending: null, resolved: 7, dismissed: 0, superseded: 0 },
      errored: ["pending"],
    });
    renderPage("decisions");

    // An explicit alert surfaces the pending-load failure.
    expect(
      screen.getByText(/Impossible de charger les décisions en attente/),
    ).toBeInTheDocument();

    // The pending chip shows "?" (undetermined), NOT "(0)".
    const group = screen.getByRole("group", {
      name: /Filtrer les décisions par statut/,
    });
    expect(within(group).getByText("(?)")).toBeInTheDocument();
    // The successful resolved chip still shows its real count.
    expect(within(group).getByText("(7)")).toBeInTheDocument();
  });

  // ---- Position-based segment filtering (§8 fix) -----------------------------

  /** Minimal staging-media item for the position-filter tests. */
  function makeStagingItem(
    overrides: Partial<StagingMediaItem> = {},
  ): StagingMediaItem {
    return {
      id: "abc123",
      category: "001-MOVIES",
      folder: "Test Movie (2024)",
      relative_path: "001-MOVIES/Test Movie (2024)",
      media_kind: "movie",
      title: "Test Movie",
      year: 2024,
      overview: null,
      provider_ids: {},
      match: "matched",
      decision_id: null,
      decision_trigger: null,
      has_nfo: false,
      has_poster: false,
      has_trailer: false,
      poster_url: null,
      seasons: null,
      episode_count: null,
      video_count: 1,
      size_bytes: 0,
      modified_at: null,
      position_stage: "verify",
      position_state: "pending",
      stages: [],
      dispatch_target: null,
      ...overrides,
    };
  }

  it("affiche un item blocked-at-verify sous « À traiter » et pas sous « Prêts »", () => {
    // Regression (§8): a matched-but-verify-blocked item (position_state="blocked",
    // match="matched") is counted by the nav badge (awaiting_action) but was
    // INVISIBLE under the old match="ambiguous" proxy. The position filter
    // (client-side on position_state) fixes this: blocked items appear under
    // "À traiter", ready items under "Prêts", and the two never cross.
    setupDecisionsList();

    const blockedItem = makeStagingItem({
      id: "blocked-1",
      title: "Blocked Verified Movie",
      match: "matched",
      position_state: "blocked",
      position_stage: "verify",
      blocked_reason: "awaiting_verify",
    });

    const readyItem = makeStagingItem({
      id: "ready-1",
      title: "Ready Movie",
      match: "matched",
      position_state: "pending",
      position_stage: "dispatch",
    });

    useStagingMediaMock.mockReturnValue({
      data: {
        items: [blockedItem, readyItem],
        counts: {
          total: 2,
          matched: 2,
          ambiguous: 0,
          absent: 0,
          scraped: 0,
          with_trailer: 0,
          awaiting_action: 1,
        },
        total: 2,
        page: 1,
        page_size: 24,
      },
      isLoading: false,
      isError: false,
      error: null,
    });

    renderPage();

    // ---- Default "Tous" segment: both items visible ----
    expect(screen.getByText("Blocked Verified Movie")).toBeInTheDocument();
    expect(screen.getByText("Ready Movie")).toBeInTheDocument();

    // ---- "À traiter" segment (position=blocked) ----
    const group = screen.getByRole("group", {
      name: /Filtrer par étape du pipeline/,
    });
    fireEvent.click(within(group).getByText("À traiter"));

    // The blocked item appears — this is the fix: under the old match="ambiguous"
    // proxy, a match="matched" item would NEVER appear here.
    expect(screen.getByText("Blocked Verified Movie")).toBeInTheDocument();
    // The ready item does NOT appear — it's not blocked.
    expect(screen.queryByText("Ready Movie")).not.toBeInTheDocument();

    // ---- "Prêts" segment (position=ready) ----
    fireEvent.click(within(group).getByText("Prêts"));

    // The blocked item does NOT appear — it fails the ready filter
    // (match === "matched" && position_state !== "blocked").
    expect(
      screen.queryByText("Blocked Verified Movie"),
    ).not.toBeInTheDocument();
    // The ready item appears — matched and not blocked.
    expect(screen.getByText("Ready Movie")).toBeInTheDocument();

    // ---- "En cours" segment (position=active) ----
    fireEvent.click(within(group).getByText("En cours"));

    // Neither item is position_state="active", so both are filtered out.
    expect(
      screen.queryByText("Blocked Verified Movie"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Ready Movie")).not.toBeInTheDocument();
  });
});
