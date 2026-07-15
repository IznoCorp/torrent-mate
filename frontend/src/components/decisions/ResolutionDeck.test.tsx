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
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

import {
  dismissDecision,
  resolveDecision,
  searchDecisionCandidates,
} from "@/api/decisions";
import { ResolutionDeck } from "@/components/decisions/ResolutionDeck";

const resolveMock = vi.mocked(resolveDecision);
const dismissMock = vi.mocked(dismissDecision);
const searchMock = vi.mocked(searchDecisionCandidates);

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

function renderDeck(initialDecisionId?: number): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <ResolutionDeck
        {...(initialDecisionId != null ? { initialDecisionId } : {})}
      />
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
    expect(screen.getByText("Candidats ambigus")).toBeInTheDocument();
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

  it("releases the search input and preselects the first result, so a pure keyboard flow validates the override (C7)", async () => {
    setup({});
    renderDeck();
    const search = screen.getByLabelText("Recherche manuelle");
    search.focus();
    expect(document.activeElement).toBe(search);
    // A manual search returns one fresh candidate (a different provider id).
    searchMock.mockResolvedValueOnce({
      candidates: [candidate({ provider_id: 99999, title: "Inception (VF)" })],
    });
    fireEvent.click(screen.getByRole("button", { name: "Chercher" }));
    await waitFor(() => {
      expect(screen.getByText("Inception (VF)")).toBeInTheDocument();
    });
    // C7: focus left the input — the deck now owns the keyboard.
    expect(document.activeElement).not.toBe(search);
    // The fresh result is preselected (index === baseCandidates.length), so a
    // bare Enter validates it as a search override without any arrow press.
    fireEvent.keyDown(window, { key: "Enter" });
    await waitFor(() => {
      expect(resolveMock).toHaveBeenCalledWith(1, {
        provider: "tmdb",
        provider_id: 99999,
        via: "search_override",
      });
    });
  });

  it("Escape inside the search input releases focus back to the deck (C7)", () => {
    setup({});
    renderDeck();
    const search = screen.getByLabelText("Recherche manuelle");
    search.focus();
    fireEvent.keyDown(search, { key: "Escape" });
    expect(document.activeElement).not.toBe(search);
  });

  it("wraps to the head of the queue on skip and counts the pass (C9)", () => {
    setup({
      items: [listItem({ id: 1 }), listItem({ id: 2, extracted_title: "Dune" })],
    });
    renderDeck();
    // Two decisions remain, none skipped yet.
    expect(screen.getByText(/2 restante\(s\)/)).toBeInTheDocument();
    expect(screen.queryByText(/passée\(s\)/)).not.toBeInTheDocument();
    // Skip once → the counter shows one pass.
    fireEvent.keyDown(window, { key: "n" });
    expect(screen.getByText(/1 passée\(s\)/)).toBeInTheDocument();
  });

  it("exposes a polite live region announcing the current selection (C10)", () => {
    setup({});
    renderDeck();
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status.textContent).toContain("Inception");
  });

  it("opens positioned on initialDecisionId when it is in the queue (C18)", () => {
    setup({
      items: [
        listItem({ id: 1, extracted_title: "Inception" }),
        listItem({ id: 2, extracted_title: "Interstellar" }),
      ],
    });
    // Without a target the head (Inception) would show; targeting id 2 jumps
    // the deck to Interstellar.
    renderDeck(2);
    expect(
      screen.getByRole("group", { name: /résolution/i }),
    ).toBeInTheDocument();
    // The header shows the targeted decision's extracted title.
    expect(screen.getAllByText("Interstellar").length).toBeGreaterThan(0);
  });
});

describe("ResolutionDeck — 409 pendant un run pipeline (Lucky, revue 2026-07-15)", () => {
  it("explique le verrou pipeline en français au lieu du détail brut", async () => {
    const { ApiError } = await import("@/api/client");
    resolveMock.mockRejectedValueOnce(
      new ApiError(409, "Pipeline lock held"),
    );
    setup({});
    renderDeck();
    fireEvent.click(screen.getByRole("button", { name: "Valider le choix" }));

    const { toast } = await import("sonner");
    await waitFor(() => {
      expect(vi.mocked(toast.error)).toHaveBeenCalledWith(
        expect.stringContaining("Un pipeline est en cours"),
      );
    });
  });
});
