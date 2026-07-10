/**
 * Pipeline page tests (webui-ux Phase 2.4).
 *
 * Asserts the reworked pipeline log area:
 * - No run-history table on the Pipeline page (de-dup — it lives on Maintenance).
 * - Idle → the last run's interpreted summary is shown (never blanks).
 * - Active run → the live interpreted lines are shown.
 * - The raw WS log is collapsed by default inside the accordion.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
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
}));

vi.mock("@/hooks/usePipelineStatus", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/hooks/usePipelineStatus")>()),
  usePipelineStatus: mocks.usePipelineStatus,
}));

vi.mock("@/hooks/useLastPipelineRun", () => ({
  useLastPipelineRun: mocks.useLastPipelineRun,
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

function renderPage(events: EventMessage[] = []): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <MemoryRouter>
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
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Pipeline page", () => {
  it("does not render the run-history table (de-dup — lives on Maintenance)", () => {
    renderPage();
    expect(
      screen.queryByText("Historique des exécutions"),
    ).not.toBeInTheDocument();
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
});
