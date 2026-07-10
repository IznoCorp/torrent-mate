/**
 * Unit tests for the Decisions page (scrape-arbiter §4.1 flat list).
 *
 * Mocks the data hooks so the page logic (flat list, optional multi-select
 * filter chips + counts, list/detail navigation, inline quick-dismiss) is
 * tested in isolation.  The {@link DecisionDetail} component's behaviour is
 * tested in its own suite.
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
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  DecisionListItem,
  DecisionDetail as DecisionDetailType,
} from "@/api/decisions";
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

vi.mock("@/hooks/useDecisions", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useAllDecisions: (...args: unknown[]) => useAllDecisionsMock(...args),
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useDecisionDetail: (...args: unknown[]) => useDecisionDetailMock(...args),
}));

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

import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { dismissDecision } from "@/api/decisions";
const dismissDecisionMock = vi.mocked(dismissDecision);

import Decisions from "@/pages/Decisions";

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
}

function renderPage(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <Decisions />
    </QueryClientProvider>
  );
  render(tree);
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

describe("Decisions", () => {
  // ---- Render ----------------------------------------------------------------

  it("affiche le titre de la page", () => {
    setupDecisionsList();
    renderPage();
    expect(screen.getByText("Décisions de scraping")).toBeInTheDocument();
  });

  it("affiche les chips de filtre de statut", () => {
    setupDecisionsList();
    renderPage();
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
    renderPage();
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
    renderPage();

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
    renderPage();
    expect(
      screen.getByText(/Toutes les décisions sont affichées/),
    ).toBeInTheDocument();
  });

  it("affiche la liste des décisions", () => {
    setupDecisionsList();
    renderPage();
    expect(screen.getByText("Décisions")).toBeInTheDocument();
  });

  it("affiche un message d'erreur quand la requête échoue", () => {
    setupDecisionsList({ isError: true });
    renderPage();
    expect(
      screen.getByText("Erreur lors du chargement des décisions."),
    ).toBeInTheDocument();
  });

  it("affiche un placeholder desktop quand aucune décision n'est sélectionnée", () => {
    setupDecisionsList();
    renderPage();
    expect(
      screen.getByText("Sélectionnez une décision pour voir les détails."),
    ).toBeInTheDocument();
  });

  // ---- Filter chips ---------------------------------------------------------

  it("active le filtre 'resolved' quand le chip Résolues est cliqué", () => {
    setupDecisionsList();
    renderPage();

    fireEvent.click(screen.getByText("Résolues"));

    // The active-status list now contains only 'resolved' (chip is a toggle).
    const call = lastArgs(useAllDecisionsMock);
    expect(call).toBeDefined();
    if (!call) throw new Error("unreachable");
    expect(call[0]).toEqual(["resolved"]);
  });

  it("cumule plusieurs filtres (multi-select)", () => {
    setupDecisionsList();
    renderPage();

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
    renderPage();

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
    renderPage();

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

    renderPage();

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

    renderPage();

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

    renderPage();

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

    renderPage();

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

    renderPage();

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
    renderPage();

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

    renderPage();

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
    renderPage();

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
    renderPage();

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
    renderPage();

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
    renderPage();

    fireEvent.click(screen.getByText("Ignorer"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Boom generic");
    });
  });

  it("affiche un message générique sur une erreur non-ApiError du quick-dismiss inline", async () => {
    dismissDecisionMock.mockRejectedValueOnce(new Error("network down"));
    setupDecisionsList({ items: [makeListItem({ id: 5, status: "pending" })] });
    renderPage();

    fireEvent.click(screen.getByText("Ignorer"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Erreur inattendue.");
    });
  });

  it("réinitialise dismissingId après un quick-dismiss en échec (onSettled)", async () => {
    dismissDecisionMock.mockRejectedValueOnce(new ApiError(409, "nope"));
    setupDecisionsList({ items: [makeListItem({ id: 5, status: "pending" })] });
    renderPage();

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
    renderPage();

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
});
