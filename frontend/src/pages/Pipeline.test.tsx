/**
 * Pipeline page tests (pipeline-panel Phase 02).
 *
 * Asserts the repatriated run-history area:
 * - The run-history table renders on the Pipeline page (repatriated from Maintenance).
 * - The ``?run=`` query param opens the RunDetail drawer.
 * - Idle → the last run's interpreted summary is shown (never blanks).
 * - Active run → the live interpreted lines are shown.
 * - The raw WS log is collapsed by default inside the accordion.
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
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EventMessage } from "@/api/events";
import type { EventStreamState } from "@/hooks/useEventStream";
import { EventStreamContext } from "@/hooks/useEventStreamContext";
import type { InterpretedLine } from "@/components/pipeline/interpretRun";
import type { PipelineStatusSnapshot } from "@/hooks/usePipelineStatus";
import Pipeline from "@/pages/Pipeline";

// ---------------------------------------------------------------------------
// Hook mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  usePipelineStatus: vi.fn(),
  useLastPipelineRun: vi.fn(),
  getPipelineHistory: vi.fn(),
  getPipelineRunDetail: vi.fn(),
}));

vi.mock("@/hooks/usePipelineStatus", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/hooks/usePipelineStatus")>()),
  usePipelineStatus: mocks.usePipelineStatus,
}));

vi.mock("@/hooks/useLastPipelineRun", () => ({
  useLastPipelineRun: mocks.useLastPipelineRun,
}));

vi.mock("@/api/pipeline", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/pipeline")>()),
  getPipelineHistory: mocks.getPipelineHistory,
  getPipelineRunDetail: mocks.getPipelineRunDetail,
}));

// PipelineControls issues its own mutations/queries — stub it to keep the page
// test focused on the log area.
vi.mock("@/components/pipeline/PipelineControls", () => ({
  PipelineControls: () => <div data-testid="controls" />,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function snapshot(
  overrides: Partial<PipelineStatusSnapshot> = {},
): PipelineStatusSnapshot {
  return {
    state: "idle",
    run_uid: null,
    step: null,
    paused: false,
    watcher_enabled: true,
    pid: null,
    ...overrides,
  };
}

function streamState(events: EventMessage[]): EventStreamState {
  return {
    events,
    connectionState: "connected",
    buildCommit: "abc1234",
    lastEventId: events.at(-1)?.id ?? null,
  };
}

function renderPage(
  events: EventMessage[] = [],
  initialEntries: string[] = ["/pipeline"],
): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={initialEntries}>
        <EventStreamContext.Provider value={streamState(events)}>
          <Pipeline />
        </EventStreamContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>
  );
  render(tree);
}

beforeEach(() => {
  Object.defineProperty(Element.prototype, "scrollTo", {
    value: vi.fn(),
    writable: true,
    configurable: true,
  });
  mocks.usePipelineStatus.mockReturnValue({ snapshot: snapshot() });
  mocks.useLastPipelineRun.mockReturnValue({
    runUid: null,
    lines: [],
    isLoading: false,
  });
  mocks.getPipelineHistory.mockResolvedValue({
    runs: [],
    total: 0,
    limit: 20,
    offset: 0,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Pipeline page", () => {
  it("renders the run-history table (repatriated from Maintenance — pipeline-panel Phase 02)", async () => {
    renderPage();
    expect(
      await screen.findByText("Historique des exécutions"),
    ).toBeInTheDocument();
  });

  it("shows the last run's interpreted summary when idle", () => {
    const lines: InterpretedLine[] = [
      {
        step: "dispatch",
        text: "Rangement vers le stockage — 4 traités",
        tone: "success",
      },
    ];
    mocks.useLastPipelineRun.mockReturnValue({
      runUid: "last-run",
      lines,
      isLoading: false,
    });
    renderPage();
    expect(screen.getByText("Dernière exécution")).toBeInTheDocument();
    expect(
      screen.getByText("Rangement vers le stockage — 4 traités"),
    ).toBeInTheDocument();
  });

  it("shows live interpreted lines when a run is active", () => {
    mocks.usePipelineStatus.mockReturnValue({
      snapshot: snapshot({
        state: "running",
        run_uid: "active-run",
        step: "scrape",
      }),
    });
    const events: EventMessage[] = [
      {
        id: "1-0",
        type: "ItemProgressed",
        data: {
          run_uid: "active-run",
          step: "scrape",
          item: "Unknown.Show.S01",
          status: "queued_for_decision",
          details: { trigger: "ambiguous", confidence: 0.4 },
        },
      },
    ];
    renderPage(events);
    expect(screen.getByText("Résumé de l'exécution")).toBeInTheDocument();
    expect(
      screen.getByText("Ambigu — en attente d'une décision : Unknown.Show.S01"),
    ).toBeInTheDocument();
  });

  it("collapses the raw WS log by default (content unmounted until expanded)", () => {
    renderPage();
    // The accordion trigger is present and collapsed…
    const trigger = screen.getByRole("button", { name: /Journal brut/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    // …and the RunLogFeed inside is unmounted, so its empty-state marker (only
    // the raw feed renders it) is absent while collapsed.
    expect(
      screen.queryByText("Aucun log pour cette exécution."),
    ).not.toBeInTheDocument();
    // Expanding the accordion mounts the raw feed.
    fireEvent.click(trigger);
    expect(
      screen.getByText("Aucun log pour cette exécution."),
    ).toBeInTheDocument();
  });

  it("opens RunDetail drawer when ?run=<uid> is in the URL (DOIT-10 — URL-addressable detail)", async () => {
    // A conscious reversal of the old de-dup assertion: the history table AND
    // RunDetail now coexist on the Pipeline page (repatriated from Maintenance
    // — pipeline-panel Phase 02). The drawer opens because the URL carries
    // ?run=<uid>.
    mocks.getPipelineRunDetail.mockResolvedValue({
      run_uid: "abc123-run-uid",
      kind: "pipeline",
      trigger: "web",
      dry_run: false,
      started_at: "2026-07-06T10:00:00Z",
      ended_at: "2026-07-06T10:05:30Z",
      outcome: "success",
      duration_s: 330,
      error: null,
      steps: [
        { name: "ingest", status: "done", elapsed_s: 12.3 },
        { name: "sort", status: "done", elapsed_s: 5.1 },
        { name: "scrape", status: "done", elapsed_s: 180.5 },
        { name: "dispatch", status: "done", elapsed_s: 83.1 },
      ],
    });
    renderPage([], ["/pipeline?run=abc123-run-uid"]);

    // The drawer opens — the run UID (truncated) and outcome are visible.
    expect(await screen.findByText("abc123-r…")).toBeInTheDocument();
    expect(screen.getByText("Succès")).toBeInTheDocument();
    // The "Retour" button is rendered.
    expect(screen.getByText("Retour")).toBeInTheDocument();
  });

  it("shows no RunDetail drawer when ?run= is absent from the URL", () => {
    renderPage([], ["/pipeline"]);

    // RunDetail heading text "Exécution abc123-r…" must NOT be present.
    // (/Exécution/ with capital E is specific to the RunDetail CardTitle —
    //  "Historique des exécutions" uses lowercase "e" and won't match.)
    expect(screen.queryByText(/Exécution/)).not.toBeInTheDocument();
    // "Retour" button (exclusive to RunDetail) is not rendered.
    expect(screen.queryByText("Retour")).not.toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // G4 — maintenance cross-link
  // -----------------------------------------------------------------------

  it("renders the maintenance cross-link when viewing a maintenance run from Pipeline (G4)", async () => {
    mocks.getPipelineRunDetail.mockResolvedValue({
      run_uid: "maint-run-uid",
      kind: "maintenance",
      command: "library-clean",
      trigger: "web",
      dry_run: false,
      started_at: "2026-07-06T10:00:00Z",
      ended_at: "2026-07-06T10:01:00Z",
      outcome: "success",
      duration_s: 60,
      error: null,
      steps: [],
    });
    renderPage([], ["/pipeline?run=maint-run-uid"]);

    await screen.findByText("maint-ru…");

    // G4: Pipeline page passes showMaintenanceLink → cross-link renders.
    expect(
      screen.getByText("→ Voir les exécutions de maintenance"),
    ).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // G6 — row click → ?run= set; Retour removes ?run= preserving ?stage=
  // -----------------------------------------------------------------------

  it("row click sets ?run= and Retour removes it while preserving ?stage= (G6)", async () => {
    mocks.getPipelineHistory.mockResolvedValue({
      runs: [
        {
          run_uid: "row-click-run",
          started_at: "2026-07-06T10:00:00Z",
          trigger: "web",
          outcome: "success",
          duration_s: 120,
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    });
    mocks.getPipelineRunDetail.mockResolvedValue({
      run_uid: "row-click-run",
      kind: "pipeline",
      trigger: "web",
      dry_run: false,
      started_at: "2026-07-06T10:00:00Z",
      ended_at: "2026-07-06T10:02:00Z",
      outcome: "success",
      duration_s: 120,
      error: null,
      steps: [],
    });

    /** Renders the live location so tests can verify URL search params. */
    function LocationProbe(): React.ReactElement {
      const location = useLocation();
      return (
        <span data-testid="loc">{location.pathname + location.search}</span>
      );
    }

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/pipeline?stage=verify"]}>
          <EventStreamContext.Provider value={streamState([])}>
            <Pipeline />
          </EventStreamContext.Provider>
          <LocationProbe />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // Wait for the history table to load — trigger label "Interface web" maps
    // from "web". run_uid is NOT a rendered column; find the row by trigger text.
    await screen.findByText("Interface web");

    // Click the history row (the <tr> ancestor of the trigger cell).
    const row = screen.getByText("Interface web").closest("tr");
    if (row === null) throw new Error("expected table row");
    fireEvent.click(row);

    await waitFor(() => {
      expect(screen.getByTestId("loc").textContent).toContain(
        "?stage=verify&run=row-click-run",
      );
    });

    // The RunDetail drawer must open — the UID (possibly truncated) is visible.
    expect(await screen.findByText(/row-cli/)).toBeInTheDocument();

    // Click "Retour" → closeRun removes ?run= but preserves ?stage=.
    fireEvent.click(screen.getByText("Retour"));

    await waitFor(() => {
      expect(screen.getByTestId("loc").textContent).toContain("?stage=verify");
      expect(screen.getByTestId("loc").textContent).not.toContain("run=");
    });
  });

  // -----------------------------------------------------------------------
  // B2 — empty ?run= shows no drawer
  // -----------------------------------------------------------------------

  it("shows no RunDetail drawer when ?run= is empty (B2)", () => {
    renderPage([], ["/pipeline?run="]);

    // "Retour" button (exclusive to RunDetail) must NOT be rendered.
    expect(screen.queryByText("Retour")).not.toBeInTheDocument();
    // No run detail text.
    expect(screen.queryByText(/Exécution/)).not.toBeInTheDocument();
  });
});
