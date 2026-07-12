/**
 * Unit tests for the ResolutionDeck (webui-overhaul OBJ2B).
 *
 * Mocks the decision hooks + resolve/dismiss/search API so the deck's logic
 * (current decision, candidate selection, validate/dismiss, keyboard, empty
 * state) is tested in isolation.
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

import type { DecisionCandidate, DecisionListItem } from "@/api/decisions";

const useDecisionsMock = vi.fn();
const useDecisionDetailMock = vi.fn();

vi.mock("@/hooks/useDecisions", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useDecisions: (...a: unknown[]) => useDecisionsMock(...a),
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useDecisionDetail: (...a: unknown[]) => useDecisionDetailMock(...a),
}));

vi.mock("@/api/decisions", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/decisions")>("@/api/decisions");
  return {
    ...actual,
    resolveDecision: vi.fn().mockResolvedValue({ run_uid: "run-1" }),
    dismissDecision: vi.fn().mockResolvedValue({ id: 1, status: "dismissed" }),
    searchDecisionCandidates: vi.fn().mockResolvedValue({ candidates: [] }),
  };
});

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { dismissDecision, resolveDecision } from "@/api/decisions";
import { ResolutionDeck } from "@/components/decisions/ResolutionDeck";

const resolveMock = vi.mocked(resolveDecision);
const dismissMock = vi.mocked(dismissDecision);

function candidate(overrides: Partial<DecisionCandidate> = {}): DecisionCandidate {
  return {
    provider: "tmdb",
    provider_id: 27205,
    title: "Inception",
    year: 2010,
    score: 0.92,
    poster_url: null,
    overview: "Un voleur qui s'infiltre dans les rêves.",
    ...overrides,
  };
}

function listItem(overrides: Partial<DecisionListItem> = {}): DecisionListItem {
  return {
    id: 1,
    media_kind: "movie",
    extracted_title: "Inception",
    extracted_year: 2010,
    staging_path: "/staging/001-MOVIES/Inception (2010)",
    trigger: "ambiguous",
    candidates_count: 1,
    status: "pending",
    created_at: 1_750_000_000,
    ...overrides,
  };
}

function setup(opts: {
  items?: DecisionListItem[];
  candidates?: DecisionCandidate[];
}): void {
  const { items = [listItem()], candidates = [candidate()] } = opts;
  useDecisionsMock.mockReturnValue({
    data: {
      items,
      pending_count: items.length,
      total: items.length,
      page: 1,
      page_size: 200,
    },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  });
  useDecisionDetailMock.mockReturnValue({
    data:
      items.length > 0
        ? { ...items[0], candidates, resolution_json: null }
        : undefined,
    isLoading: false,
    isError: false,
    error: null,
  });
}

function renderDeck(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <ResolutionDeck />
    </QueryClientProvider>
  );
  render(tree);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ResolutionDeck", () => {
  it("shows the current decision, its trigger and a candidate with overview", () => {
    setup({});
    renderDeck();
    // The extracted title appears in the header and on the candidate card.
    expect(screen.getAllByText("Inception").length).toBeGreaterThan(0);
    expect(screen.getByText("Ambigu")).toBeInTheDocument();
    expect(
      screen.getByText("Un voleur qui s'infiltre dans les rêves."),
    ).toBeInTheDocument();
  });

  it("validates the selected candidate via resolveDecision (via=pick)", async () => {
    setup({});
    renderDeck();
    fireEvent.click(screen.getByRole("button", { name: "Valider le choix" }));
    await waitFor(() => {
      expect(resolveMock).toHaveBeenCalledWith(1, {
        provider: "tmdb",
        provider_id: 27205,
        via: "pick",
      });
    });
  });

  it("dismisses the current decision", async () => {
    setup({});
    renderDeck();
    fireEvent.click(screen.getByRole("button", { name: "Ignorer" }));
    await waitFor(() => {
      expect(dismissMock).toHaveBeenCalledWith(1);
    });
  });

  it("validates on the Enter keyboard shortcut", async () => {
    setup({});
    renderDeck();
    fireEvent.keyDown(window, { key: "Enter" });
    await waitFor(() => {
      expect(resolveMock).toHaveBeenCalledOnce();
    });
  });

  it("shows an empty state when there is nothing to resolve", () => {
    setup({ items: [] });
    renderDeck();
    expect(
      screen.getByText("Aucune décision à résoudre"),
    ).toBeInTheDocument();
  });

  it("renders the search override controls", () => {
    setup({});
    renderDeck();
    const search = screen.getByLabelText("Recherche manuelle");
    expect(search).toBeInTheDocument();
    // Seeded from the extracted title.
    expect(within(document.body).getByDisplayValue("Inception")).toBeDefined();
  });
});
