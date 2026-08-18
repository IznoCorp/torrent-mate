/**
 * ObligationsPanel — Phase 02 tests: title-led rows, truncated hash + copy
 * button, tracker/ratio/seed-time columns preserved.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
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

const { toastError } = vi.hoisted(() => ({
  toastError: vi.fn(),
}));

vi.mock("@/components/acquisition/MqToast", () => ({
  mqtoast: toastError,
  MqToaster: (): null => null,
}));

// X7 (ticket 250): meta passes through except obligationStatus, wrapped in a
// mock so one test can simulate a status this build does not know — the real
// derivation is a closed union, so the fallback is unreachable via item data.
const { obligationStatusMock } = vi.hoisted(() => ({
  obligationStatusMock: vi.fn(),
}));

vi.mock("./meta", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./meta")>();
  // Default to the real derivation; the X7 test overrides it and restores.
  obligationStatusMock.mockImplementation(actual.obligationStatus);
  return { ...actual, obligationStatus: obligationStatusMock };
});

import { ObligationsPanel } from "./ObligationsPanel";

/** A single obligation item matching ObligationItem shape. */
function makeObligation(
  overrides: Partial<ObligationItem> = {},
): ObligationItem {
  return {
    info_hash: "abcdef1234567890abcdef1234567890abcdef12",
    source_tracker: "c411",
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

  it("toasts error on clipboard rejection, no check icon (mutation-proof 5.2)", async () => {
    const writeText = vi.fn().mockRejectedValue(new DOMException("Blocked"));
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

    // The rejection path calls toast.error — wait for the microtask.
    await vi.waitFor(() => {
      expect(toastError).toHaveBeenCalledWith("Copie du hash impossible");
    });

    // No check icon (text-green-600) must appear — the hash was NOT copied.
    const checkIcons = document.querySelectorAll(".text-green-600");
    expect(checkIcons.length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Existing columns preserved
// ---------------------------------------------------------------------------

describe("ObligationsPanel — tracker/ratio/seed-time columns preserved", () => {
  it("renders the Tracker column", () => {
    renderPanel({
      items: [makeObligation({ source_tracker: "tr4ker" })],
    });

    expect(screen.getByText("tr4ker")).toBeInTheDocument();
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
// X7 (ticket 250): unknown-status fallback stays French
// ---------------------------------------------------------------------------

describe("ObligationsPanel — repli statut inconnu (X7, ticket 250)", () => {
  it("affiche « Statut inconnu » pour un statut hors vocabulaire, jamais le slug brut", async () => {
    // Simulate a future status the label map does not know. This test FAILS
    // if the badge fallback reverts to rendering the raw slug.
    const actual = await vi.importActual<typeof import("./meta")>("./meta");
    obligationStatusMock.mockReturnValue("weird_new_status");
    try {
      renderPanel({ items: [makeObligation({ title: "Top Chef" })] });

      expect(screen.getByText("Statut inconnu")).toBeInTheDocument();
      expect(screen.queryByText("weird_new_status")).not.toBeInTheDocument();
    } finally {
      // Hand the real derivation back to the other tests.
      obligationStatusMock.mockImplementation(actual.obligationStatus);
    }
  });
});

// ---------------------------------------------------------------------------
// Mobile column collapse + full-value titles (ticket 250)
// ---------------------------------------------------------------------------

describe("ObligationsPanel — repli mobile des colonnes (ACQUISITION-4, ticket 250)", () => {
  // Mobile-truth rule: jsdom does not lay out — these are structural
  // class-presence checks; the 390px proof happens post-deploy in Chrome.
  it("replie les colonnes machine sous md via hidden md:table-cell", () => {
    renderPanel({ items: [makeObligation({ title: "Top Chef" })] });

    for (const name of ["Hash", "Tracker", "Ratio min", "Seed min"]) {
      const th = screen.getByRole("columnheader", { name });
      expect(th.className).toContain("hidden");
      expect(th.className).toContain("md:table-cell");
    }
  });

  it("garde Titre / Ratio obs. / HnR / Statut visibles à toutes les largeurs", () => {
    renderPanel({ items: [makeObligation({ title: "Top Chef" })] });

    for (const name of ["Titre", "Ratio obs.", "HnR", "Statut"]) {
      const th = screen.getByRole("columnheader", { name });
      expect(th.className).not.toContain("hidden");
    }
  });

  it("porte la valeur complète dans le title de la cellule Titre (ACQUISITION-5)", () => {
    renderPanel({ items: [makeObligation({ title: "Top Chef" })] });
    expect(screen.getByTitle("Top Chef")).toBeInTheDocument();
  });

  it("porte le hash complet dans le title de la cellule Titre en repli hash", () => {
    const fullHash = "abcdef1234567890abcdef1234567890abcdef12";
    renderPanel({ items: [makeObligation({ title: null })] });
    // Scoped to the Titre cell: the hidden hash-cell span ALSO carries the
    // full hash in its title, so a global getAllByTitle stays green even when
    // the Titre-cell title is reverted (vacuous — review finding, ticket 250).
    const dataRow = screen.getAllByRole("row")[1];
    if (dataRow === undefined) throw new Error("no obligation data row");
    const titleCell = within(dataRow).getAllByRole("cell")[0];
    if (titleCell === undefined) throw new Error("no Titre cell in the row");
    expect(titleCell).toHaveAttribute("title", fullHash);
    // Its visible fallback text is the truncated hash.
    expect(titleCell).toHaveTextContent("abcdef123456…");
  });
});

// ---------------------------------------------------------------------------
// Empty / error states
// ---------------------------------------------------------------------------

describe("ObligationsPanel — edge states", () => {
  it("series the empty-state message when there are no items", () => {
    renderPanel({ items: [] });

    expect(
      screen.getByText(/aucune obligation de seed/i),
    ).toBeInTheDocument();
  });

  it("series the error message on fetch failure", () => {
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
