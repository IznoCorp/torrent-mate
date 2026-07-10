/**
 * Unit tests for the RegistryPage component (reg-health Phase 4).
 *
 * Mocks the data hooks so the page logic (provider cards, circuit-state
 * badges, baseline indicator, WS invalidation) is tested in isolation.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

const useRegistryStatusMock = vi.fn();
const useEventStreamContextMock = vi.fn(() => ({ events: [] }));

vi.mock("@/hooks/useRegistryStatus", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useRegistryStatus: () => useRegistryStatusMock(),
}));

vi.mock("@/hooks/useEventStreamContext", () => ({
  useEventStreamContext: () => useEventStreamContextMock(),
}));

import RegistryPage from "@/pages/RegistryPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <RegistryPage />
    </QueryClientProvider>
  );
  render(tree);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("RegistryPage", () => {
  it("shows skeleton while loading", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });

    renderPage();

    // The page renders the title even during loading.
    expect(screen.getByText("Registre des fournisseurs")).toBeInTheDocument();
    // Skeletons have the animate-pulse class.
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders provider cards on success", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        providers: [
          {
            provider_name: "tmdb",
            circuit_state: "closed",
            failure_count_recent: 0,
            last_success_at: 1_719_792_000,
            last_failure_at: null,
            last_latency_ms: 42.5,
            live: true,
          },
          {
            provider_name: "tvdb",
            circuit_state: "open",
            failure_count_recent: 5,
            last_success_at: null,
            last_failure_at: 1_719_705_600,
            last_latency_ms: null,
            live: true,
          },
        ],
      },
      error: null,
    });

    renderPage();

    // Both provider names are rendered.
    expect(screen.getByText("tmdb")).toBeInTheDocument();
    expect(screen.getByText("tvdb")).toBeInTheDocument();

    // Badge labels for each circuit state.
    expect(screen.getByText("OK")).toBeInTheDocument();
    expect(screen.getByText("Ouvert")).toBeInTheDocument();

    // Latency is shown (42.5 rounds to "43 ms" via toFixed(0)).
    expect(screen.getByText(/43 ms/)).toBeInTheDocument();
  });

  it("nests a sub-circuit under its parent provider card (not a twin)", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        providers: [
          {
            provider_name: "tvdb",
            circuit_state: "closed",
            failure_count_recent: 0,
            last_success_at: 1_719_792_000,
            last_failure_at: null,
            last_latency_ms: 30,
            live: true,
          },
          {
            provider_name: "tvdb-bootstrap",
            circuit_state: "open",
            failure_count_recent: 2,
            last_success_at: null,
            last_failure_at: 1_719_705_600,
            last_latency_ms: null,
            live: true,
          },
        ],
      },
      error: null,
    });

    renderPage();

    // The parent provider name renders once; the raw sub-circuit name does not
    // appear as its own card title — it is relabelled "Authentification".
    expect(screen.getByText("tvdb")).toBeInTheDocument();
    expect(screen.queryByText("tvdb-bootstrap")).not.toBeInTheDocument();
    expect(screen.getByText("Authentification")).toBeInTheDocument();
    // The "Sous-circuits" section header is present under the parent.
    expect(screen.getByText("Sous-circuits")).toBeInTheDocument();
  });

  it("renders empty state when no providers", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { providers: [] },
      error: null,
    });

    renderPage();
    expect(
      screen.getByText("Aucun fournisseur configuré."),
    ).toBeInTheDocument();
  });

  it("shows baseline indicator for a live:false provider", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        providers: [
          {
            provider_name: "omdb",
            circuit_state: "open",
            failure_count_recent: 0,
            last_success_at: null,
            last_failure_at: null,
            last_latency_ms: null,
            live: false,
          },
        ],
      },
      error: null,
    });

    renderPage();

    // The baseline indicator text is present.
    expect(screen.getByText("En attente de données live")).toBeInTheDocument();

    // Stats are still rendered even when not live.
    expect(screen.getByText("omdb")).toBeInTheDocument();
    expect(screen.getByText("Ouvert")).toBeInTheDocument();
  });

  it("shows error message on fetch failure", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("Network error"),
    });

    renderPage();
    expect(screen.getByText(/Impossible de charger/)).toBeInTheDocument();
  });
});
