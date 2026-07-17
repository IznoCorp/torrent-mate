import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RunHistoryTable } from "@/components/pipeline/RunHistoryTable";

import type { HistoryResponse } from "@/api/pipeline";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

/** A single completed run summary. */
function makeRun(
  overrides: Partial<{
    run_uid: string;
    trigger: string;
    outcome: "success" | "error" | "killed" | "running" | "paused" | null;
    duration_s: number | null;
    started_at: string;
    ended_at: string | null;
  }> = {},
): HistoryResponse["runs"][number] {
  return {
    run_uid: "abc123",
    kind: "pipeline",
    trigger: "web",
    dry_run: false,
    started_at: "2026-07-06T10:00:00Z",
    ended_at: "2026-07-06T10:05:30Z",
    outcome: "success",
    duration_s: 330,
    ...overrides,
  };
}

/** Build a HistoryResponse page. */
function makePage(
  runs: ReturnType<typeof makeRun>[],
  total?: number,
): HistoryResponse {
  return { runs, total: total ?? runs.length };
}

// ---------------------------------------------------------------------------
// Mock the client module
// ---------------------------------------------------------------------------

vi.mock("@/api/pipeline", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/pipeline")>("@/api/pipeline");
  return {
    ...actual,
    getPipelineHistory: vi.fn(),
  };
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Cached import ref for the mocked getPipelineHistory. */
async function mockGetHistory() {
  const mod = await import("@/api/pipeline");
  return mod.getPipelineHistory as ReturnType<typeof vi.fn>;
}

/** Render RunHistoryTable wrapped in a fresh QueryClientProvider. */
function renderTable(
  onSelect: (uid: string) => void = vi.fn(),
  kind?: string,
): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <RunHistoryTable
        onSelect={onSelect}
        {...(kind !== undefined ? { kind } : {})}
      />
    </QueryClientProvider>
  );
  render(tree);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(cleanup);

describe("RunHistoryTable", () => {
  it("affiche les colonnes Date, Déclencheur, Issue, Durée", async () => {
    const getHistory = await mockGetHistory();
    getHistory.mockResolvedValue(makePage([makeRun()]));
    renderTable();

    // Column headers.
    expect(await screen.findByText("Date")).toBeInTheDocument();
    expect(screen.getByText("Déclencheur")).toBeInTheDocument();
    expect(screen.getByText("Issue")).toBeInTheDocument();
    expect(screen.getByText("Durée")).toBeInTheDocument();
  });

  it("affiche les données mockées dans les lignes", async () => {
    const getHistory = await mockGetHistory();
    getHistory.mockResolvedValue(
      makePage([
        makeRun({
          run_uid: "run-1",
          trigger: "cli",
          outcome: "success",
          duration_s: 125,
        }),
      ]),
    );
    renderTable();

    // Outcome badge with French label.
    expect(await screen.findByText("Succès")).toBeInTheDocument();
    // Trigger rendered as its human label (cell + legend both list it → ≥1).
    expect(screen.getAllByText("Ligne de commande").length).toBeGreaterThan(0);
    // Duration formatted as "2m 05s".
    expect(screen.getByText("2m 05s")).toBeInTheDocument();
  });

  it("affiche les Badges avec le bon tone par outcome", async () => {
    const getHistory = await mockGetHistory();
    getHistory.mockResolvedValue(
      makePage([
        makeRun({ run_uid: "r1", outcome: "success" }),
        makeRun({ run_uid: "r2", outcome: "error" }),
        makeRun({ run_uid: "r3", outcome: "killed" }),
        makeRun({ run_uid: "r4", outcome: "running" }),
        makeRun({ run_uid: "r5", outcome: "paused" }),
        makeRun({ run_uid: "r6", outcome: null }),
      ]),
    );
    renderTable();

    await screen.findByText("Succès");
    expect(screen.getByText("Erreur")).toBeInTheDocument();
    expect(screen.getByText("Arrêté")).toBeInTheDocument();
    // "running" → "En cours", "paused" → "En pause" (distinct labels).
    expect(screen.getByText("En cours")).toBeInTheDocument();
    expect(screen.getByText("En pause")).toBeInTheDocument();
    // Null outcome → "—".
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("bascule le tri côté serveur quand on clique un en-tête", async () => {
    const getHistory = await mockGetHistory();
    getHistory.mockResolvedValue(makePage([makeRun()]));
    renderTable();

    await screen.findByText("Date");

    // Click "Durée" header to toggle sort.
    fireEvent.click(screen.getByRole("button", { name: /Durée/ }));

    // Should re-fetch with a duration-based sort param (asc or desc).
    expect(getHistory).toHaveBeenLastCalledWith(
      expect.objectContaining({
        sort: expect.stringMatching(/^-?duration$/) as unknown as string,
      }),
    );
  });

  it("affiche l'état vide", async () => {
    const getHistory = await mockGetHistory();
    getHistory.mockResolvedValue(makePage([], 0));
    renderTable();

    expect(
      await screen.findByText("Aucune exécution enregistrée."),
    ).toBeInTheDocument();
  });

  it("affiche la pagination", async () => {
    const getHistory = await mockGetHistory();
    // 25 runs with a limit of 20 → 2 pages.
    const runs = Array.from({ length: 25 }, (_, i) =>
      makeRun({ run_uid: `run-${String(i)}` }),
    );
    getHistory.mockResolvedValue(makePage(runs.slice(0, 20), 25));
    renderTable();

    // Wait for data to load — the pagination bar texts signal ready.
    await screen.findByText(/25 exécutions/);

    // Pagination info should show page 1/2.
    expect(screen.getByText(/page 1\/2/)).toBeInTheDocument();
    expect(screen.getByText("Suivant")).not.toBeDisabled();

    // Click "Suivant" → offset advances.
    getHistory.mockResolvedValue(makePage(runs.slice(20), 25));
    fireEvent.click(screen.getByText("Suivant"));

    expect(getHistory).toHaveBeenLastCalledWith(
      expect.objectContaining({ offset: 20 }),
    );
  });

  it("appelle onSelect quand on clique une ligne", async () => {
    const getHistory = await mockGetHistory();
    getHistory.mockResolvedValue(
      makePage([makeRun({ run_uid: "selected-uid" })]),
    );
    const onSelect = vi.fn();
    renderTable(onSelect);

    // Click the first data row. The trigger "web" renders as its human label
    // "Interface web" in both the row cell and the legend; the cell comes
    // first in DOM order, so clicking [0] hits the row.
    await screen.findByText("Succès");
    const cells = screen.getAllByText("Interface web");
    const cell = cells[0];
    if (cell === undefined) throw new Error("trigger cell not rendered");
    fireEvent.click(cell);

    expect(onSelect).toHaveBeenCalledWith("selected-uid");
  });

  it("passe kind=maintenance dans les query params", async () => {
    const getHistory = await mockGetHistory();
    getHistory.mockResolvedValue(makePage([makeRun()]));
    renderTable(vi.fn(), "maintenance");

    await screen.findByText("Date");

    expect(getHistory).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "maintenance" }),
    );
  });

  it("n'inclut pas kind quand le prop est absent", async () => {
    const getHistory = await mockGetHistory();
    getHistory.mockResolvedValue(makePage([makeRun()]));
    renderTable(vi.fn()); // no kind prop

    await screen.findByText("Date");

    const callArgs = getHistory.mock.calls[0]?.[0] as
      Record<string, unknown> | undefined;
    expect(callArgs).toBeDefined();
    expect(callArgs).not.toHaveProperty("kind");
  });
});
