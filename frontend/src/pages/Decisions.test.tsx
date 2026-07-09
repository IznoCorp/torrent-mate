/**
 * Unit tests for the Decisions page (scrape-arbiter §4.2).
 *
 * Mocks the data hooks so the page logic (filter chips, list/detail
 * navigation, layout) is tested in isolation.  The {@link DecisionDetail}
 * component's behaviour is tested in its own suite.
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
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  DecisionListItem,
  DecisionDetail as DecisionDetailType,
} from "@/api/decisions";

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

const useDecisionsMock = vi.fn();
const useDecisionDetailMock = vi.fn();

vi.mock("@/hooks/useDecisions", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useDecisions: (...args: unknown[]) => useDecisionsMock(...args),
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useDecisionDetail: (...args: unknown[]) => useDecisionDetailMock(...args),
  useResolveDecision: vi.fn(),
  useDismissDecision: vi.fn(),
  useSearchCandidates: vi.fn(),
}));

import Decisions from "@/pages/Decisions";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract the last argument passed to a mock as an array. */
function lastArgs(mock: ReturnType<typeof vi.fn>): unknown[] | undefined {
  const calls = mock.mock.calls as unknown[][];
  return calls[calls.length - 1];
}

function setupDecisionsList(
  overrides: {
    items?: DecisionListItem[];
    isLoading?: boolean;
    isError?: boolean;
  } = {},
): void {
  const {
    items = [makeListItem()],
    isLoading = false,
    isError = false,
  } = overrides;

  useDecisionsMock.mockReturnValue({
    data: {
      items,
      pending_count: items.length,
      total: items.length,
      page: 1,
      page_size: 50,
    },
    isLoading,
    isError,
    error: isError ? new Error("fetch failed") : null,
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
    expect(screen.getByText("En attente")).toBeInTheDocument();
    expect(screen.getByText("Résolues")).toBeInTheDocument();
    expect(screen.getByText("Ignorées")).toBeInTheDocument();
    expect(screen.getByText("Remplacées")).toBeInTheDocument();
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

  it("passe le statut 'resolved' quand le chip Résolues est cliqué", () => {
    setupDecisionsList();
    renderPage();

    fireEvent.click(screen.getByText("Résolues"));

    const call = lastArgs(useDecisionsMock);
    expect(call).toBeDefined();
    if (!call) throw new Error("unreachable");
    expect(call[0]).toEqual({ status: "resolved" });
  });

  it("passe le statut 'dismissed' quand le chip Ignorées est cliqué", () => {
    setupDecisionsList();
    renderPage();

    fireEvent.click(screen.getByText("Ignorées"));

    const call = lastArgs(useDecisionsMock);
    expect(call).toBeDefined();
    if (!call) throw new Error("unreachable");
    expect(call[0]).toEqual({ status: "dismissed" });
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
});
