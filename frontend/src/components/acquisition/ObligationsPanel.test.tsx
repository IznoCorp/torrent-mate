/**
 * ObligationsPanel — Phase 02 tests: title-led rows, truncated hash + copy
 * button, tracker/ratio/seed-time columns preserved.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ObligationItem } from "@/api/acquisition";

// Inert hook mocks — only the markup derived from the hook response is tested.
const useObligationsMock = vi.fn();

vi.mock("@/hooks/useAcquisition", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useObligations: (...args: unknown[]) => useObligationsMock(...args),
  useFollowed: () => ({
    isLoading: false,
    isError: false,
    data: { items: [] },
  }),
  useFollow: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateFollow: () => ({ mutate: vi.fn(), isPending: false }),
  useUnfollow: () => ({ mutate: vi.fn(), isPending: false }),
  useDownloads: () => ({ isLoading: false, isError: false }),
  useAcquisitionStatus: () => ({ isLoading: false, isError: false }),
  useMediaSearch: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: () => undefined,
  }),
  useCompleteness: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }),
  useTrackedAcquisitionRun: () => undefined,
}));

import { ObligationsPanel } from "./ObligationsPanel";

/** A single obligation item matching ObligationItem shape. */
function makeObligation(
  overrides: Partial<ObligationItem> = {},
): ObligationItem {
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
    title: null,
    ...overrides,
  };
}

interface ObligationsData {
  items: ObligationItem[];
}

function renderPanel(data: ObligationsData): void {
  useObligationsMock.mockReturnValue({
    isLoading: false,
    isError: false,
    data,
    error: null,
  });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ObligationsPanel />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Title-led rows
// ---------------------------------------------------------------------------

describe("ObligationsPanel — title-led rows (Phase 02)", () => {
  it("renders the resolved title when non-null", () => {
    renderPanel({
      items: [makeObligation({ title: "Top Chef" })],
    });

    expect(screen.getByText("Top Chef")).toBeInTheDocument();
  });

  it("falls back to truncated info_hash when title is null", () => {
    renderPanel({
      items: [
        makeObligation({
          title: null,
          info_hash: "aaaa1111222233334444aaaa1111222233334444",
        }),
      ],
    });

    // The truncated hash appears both in the Titre cell (primary) and the
    // Hash cell — getAllByText handles the duplicate.
    const matches = screen.getAllByText("aaaa11112222…");
    expect(matches.length).toBeGreaterThanOrEqual(2);
  });

  it("renders the truncated info_hash in the Hash column as mono", () => {
    renderPanel({
      items: [
        makeObligation({
          info_hash: "aaaa1111222233334444aaaa1111222233334444",
          title: "Some Title",
        }),
      ],
    });

    // The hash column cell is font-mono.  Find the truncated hash text — it
    // is rendered both as the column value AND on the button aria-label, so
    // getAllByText is needed.
    const hashEls = screen.getAllByText("aaaa11112222…");
    expect(hashEls.length).toBeGreaterThanOrEqual(1);
    // The hash cell should have font-mono — check its parent.
    const firstHashEl = hashEls[0];
    expect(firstHashEl).toBeDefined();
    const hashCell = firstHashEl?.closest("td");
    expect(hashCell?.className).toContain("font-mono");
  });
});

// ---------------------------------------------------------------------------
// Copy button
// ---------------------------------------------------------------------------

describe("ObligationsPanel — hash copy button", () => {
  it("renders a copy button for every obligation row", () => {
    renderPanel({
      items: [
        makeObligation({
          info_hash: "aaaa1111222233334444aaaa1111222233334444",
        }),
        makeObligation({
          info_hash: "bbbb1111222233334444bbbb1111222233334444",
        }),
      ],
    });

    const buttons = screen.getAllByRole("button", {
      name: /copier le hash/i,
    });
    expect(buttons).toHaveLength(2);
  });

  it("copies the full hash to the clipboard on click", () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      writable: true,
      configurable: true,
    });

    const fullHash = "aaaa1111222233334444aaaa1111222233334444";
    renderPanel({
      items: [makeObligation({ info_hash: fullHash })],
    });

    const btn = screen.getByRole("button", { name: /copier le hash/i });
    fireEvent.click(btn);

    expect(writeText).toHaveBeenCalledWith(fullHash);
  });
});

// ---------------------------------------------------------------------------
// Existing columns preserved
// ---------------------------------------------------------------------------

describe("ObligationsPanel — tracker/ratio/seed-time columns preserved", () => {
  it("renders the Tracker column", () => {
    renderPanel({
      items: [makeObligation({ source_tracker: "lacale" })],
    });

    expect(screen.getByText("lacale")).toBeInTheDocument();
  });

  it("renders the Ratio min column", () => {
    renderPanel({
      items: [makeObligation({ min_ratio: 2.5 })],
    });

    expect(screen.getByText("2.50")).toBeInTheDocument();
  });

  it("renders the Ratio obs. column", () => {
    renderPanel({
      items: [makeObligation({ observed_ratio: 1.2 })],
    });

    expect(screen.getByText("1.20")).toBeInTheDocument();
  });

  it('renders "—" when observed_ratio is null', () => {
    renderPanel({
      items: [makeObligation({ observed_ratio: null })],
    });

    // "—" is the em-dash fallback.
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders the Seed min column in hours", () => {
    renderPanel({
      items: [makeObligation({ min_seed_time_s: 7200 })],
    });

    expect(screen.getByText("2 h")).toBeInTheDocument();
  });

  it('renders "—" when min_seed_time_s is 0', () => {
    renderPanel({
      items: [makeObligation({ min_seed_time_s: 0 })],
    });

    // The seed-time cell shows "—" for zero.
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Status badges (regression — derived from timestamps)
// ---------------------------------------------------------------------------

describe("ObligationsPanel — status badges", () => {
  it("renders satisfied status badge", () => {
    renderPanel({
      items: [makeObligation({ satisfied_at: 1_719_800_000 })],
    });

    expect(screen.getByText("Respectée")).toBeInTheDocument();
  });

  it("renders breached status badge", () => {
    renderPanel({
      items: [makeObligation({ breached_at: 1_719_780_000 })],
    });

    expect(screen.getByText("Non respectée")).toBeInTheDocument();
  });

  it("renders pending status badge", () => {
    renderPanel({
      items: [makeObligation({ breached_at: null, satisfied_at: null })],
    });

    // STATUS_LABEL["pending"] is "En attente" (not "En cours" which is the
    // filter-option label for the pending filter).
    expect(screen.getByText("En attente")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Empty / error states
// ---------------------------------------------------------------------------

describe("ObligationsPanel — edge states", () => {
  it("shows the empty-state message when there are no items", () => {
    renderPanel({ items: [] });

    expect(
      screen.getByText(/aucune obligation de seed enregistrée/i),
    ).toBeInTheDocument();
  });

  it("shows the error message on fetch failure", () => {
    useObligationsMock.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("DB error"),
    });
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <ObligationsPanel />
      </QueryClientProvider>,
    );

    expect(screen.getByText(/DB error/)).toBeInTheDocument();
  });
});
