import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EventMessage } from "@/api/events";
import type { EventStreamState } from "@/hooks/useEventStream";
import { EventStreamContext } from "@/hooks/useEventStreamContext";
import { RunLogFeed } from "@/components/pipeline/RunLogFeed";

/** Build an ``EventMessage`` with a stream-id timestamp prefix. */
function makeEvent(
  ms: number,
  type: string,
  data?: Record<string, unknown>,
): EventMessage {
  return { id: `${String(ms)}-0`, type, data: data ?? {} };
}

/** A connected stream state with the given events. */
function makeStreamState(events: EventMessage[]): EventStreamState {
  return {
    events,
    connectionState: "connected",
    buildCommit: "abc1234",
    lastEventId: events[events.length - 1]?.id ?? null,
  };
}

/** Render RunLogFeed wrapped in the required context provider. */
function renderFeed(
  runUid: string | null | undefined,
  events: EventMessage[] = [],
): void {
  const state = makeStreamState(events);
  const tree: ReactElement = (
    <EventStreamContext.Provider value={state}>
      <RunLogFeed runUid={runUid} />
    </EventStreamContext.Provider>
  );
  render(tree);
}

beforeEach(() => {
  // jsdom does not implement scrollTo — mock it as a no-op.
  Object.defineProperty(Element.prototype, "scrollTo", {
    value: vi.fn(),
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("RunLogFeed", () => {
  it("affiche les événements avec LogLine (type + données)", () => {
    const events = [
      makeEvent(1_700_000_000_000, "PipelineStepStarted", {
        step: "ingest",
      }),
      makeEvent(1_700_000_001_000, "PipelineStepCompleted", {
        step: "ingest",
      }),
    ];
    renderFeed("run-1", events);

    expect(screen.getByText("PipelineStepStarted")).toBeInTheDocument();
    expect(screen.getByText("PipelineStepCompleted")).toBeInTheDocument();
    // The JSON data preview should be visible (both events have same data).
    const dataElements = screen.getAllByText('{"step":"ingest"}');
    expect(dataElements).toHaveLength(2);
  });

  it("affiche l'état vide quand aucun événement ne correspond", () => {
    renderFeed("run-1", []);
    expect(
      screen.getByText("Aucun log pour cette exécution."),
    ).toBeInTheDocument();
  });

  it("filtre les événements par runUid via data.run_uid", () => {
    const events = [
      makeEvent(1_700_000_000_000, "PipelineStarted", { run_uid: "run-A" }),
      makeEvent(1_700_000_001_000, "PipelineStarted", { run_uid: "run-B" }),
      makeEvent(1_700_000_002_000, "PipelineEnded", { run_uid: "run-A" }),
    ];
    renderFeed("run-A", events);

    // Only run-A events should be visible.
    expect(screen.getAllByText("PipelineStarted").length).toBe(1);
    expect(screen.getByText("PipelineEnded")).toBeInTheDocument();
    // run-B event with data.run_uid="run-B" should NOT appear.
    const bodies = screen.getAllByText(/run_uid/);
    // Two events: the ones with run_uid "run-A".
    expect(bodies).toHaveLength(2);
  });

  it("affiche tous les événements quand runUid est null", () => {
    const events = [
      makeEvent(1_700_000_000_000, "PipelineStarted", { run_uid: "run-A" }),
      makeEvent(1_700_000_001_000, "PipelineStarted", { run_uid: "run-B" }),
    ];
    renderFeed(null, events);

    expect(screen.getAllByText("PipelineStarted")).toHaveLength(2);
  });

  it("affiche tous les événements quand runUid est undefined", () => {
    const events = [
      makeEvent(1_700_000_000_000, "PipelineStarted", { run_uid: "run-A" }),
      makeEvent(1_700_000_001_000, "PipelineStarted", { run_uid: "run-B" }),
    ];
    renderFeed(undefined, events);

    expect(screen.getAllByText("PipelineStarted")).toHaveLength(2);
  });

  it('montre le bouton "Revenir en bas" quand on scroll vers le haut', () => {
    const events = Array.from({ length: 5 }, (_, i) =>
      makeEvent(1_700_000_000_000 + i * 1_000, `Step${String(i)}`),
    );
    renderFeed("run-1", events);

    const log = screen.getByRole("log");

    // Simulate scrolling up (far from the bottom).
    Object.defineProperty(log, "scrollHeight", {
      value: 1_000,
      configurable: true,
    });
    Object.defineProperty(log, "clientHeight", {
      value: 400,
      configurable: true,
    });
    Object.defineProperty(log, "scrollTop", { value: 0, configurable: true });
    fireEvent.scroll(log);

    expect(
      screen.getByRole("button", { name: "Revenir en bas" }),
    ).toBeInTheDocument();
  });

  it("affiche le titre du journal", () => {
    renderFeed("run-1", [makeEvent(1_700_000_000_000, "PipelineStarted")]);

    expect(
      screen.getByText(/Journal d.exécution/),
    ).toBeInTheDocument();
  });

  it("utilise le niveau error pour les événements d'erreur", () => {
    const events = [
      makeEvent(1_700_000_000_000, "PipelineStepErrored", {
        error: "something broke",
      }),
    ];
    renderFeed("run-1", events);

    // The LogLine for an error event should have the error CSS class.
    const errBadge = screen.getByText("ERR");
    expect(errBadge).toBeInTheDocument();
  });

  it("utilise le niveau warn pour les avertissements", () => {
    const events = [
      makeEvent(1_700_000_000_000, "PipelineWarning", {
        msg: "disk low",
      }),
    ];
    renderFeed("run-1", events);

    const warnBadge = screen.getByText("WRN");
    expect(warnBadge).toBeInTheDocument();
  });
});
