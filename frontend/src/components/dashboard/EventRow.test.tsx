import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { EventMessage } from "@/api/events";
import {
  EventRow,
  severityForEventType,
} from "@/components/dashboard/EventRow";

/** Build an ``EventMessage`` of ``type`` with a stream-id timestamp prefix. */
function makeEvent(type: string): EventMessage {
  return { id: "1700000000000-0", type, data: { step: type } };
}

/** Render an {@link EventRow} and return its StatusDot element. */
function renderDot(type: string): Element {
  const { container } = render(<EventRow event={makeEvent(type)} />);
  const dot = container.querySelector(".ps-dot");
  if (dot === null) {
    throw new Error("StatusDot introuvable dans l’EventRow rendu.");
  }
  return dot;
}

afterEach(() => {
  cleanup();
});

describe("severityForEventType", () => {
  it("classe les échecs en danger", () => {
    expect(severityForEventType("PipelineStepErrored")).toBe("danger");
    expect(severityForEventType("DownloadFailed")).toBe("danger");
  });

  it("classe les avertissements en warning", () => {
    expect(severityForEventType("DiskSpaceWarning")).toBe("warning");
  });

  it("classe le reste en neutral", () => {
    expect(severityForEventType("PipelineStepStarted")).toBe("neutral");
    expect(severityForEventType("PipelineStepCompleted")).toBe("neutral");
  });
});

describe("EventRow — variante du StatusDot", () => {
  it("rend un point STATIQUE (idle) pour un événement neutre, jamais l’animation running", () => {
    const dot = renderDot("PipelineStepStarted");
    expect(dot.classList.contains("ps-dot--idle")).toBe(true);
    // A historical row must not pulse: no lifecycle running/queued variant.
    expect(dot.classList.contains("ps-dot--running")).toBe(false);
    expect(dot.classList.contains("ps-dot--queued")).toBe(false);
  });

  it("garde la sémantique danger (point rouge « error ») pour un échec", () => {
    const dot = renderDot("PipelineStepErrored");
    expect(dot.classList.contains("ps-dot--error")).toBe(true);
  });

  it("rend un point ambre STATIQUE (warning) pour un avertissement, jamais l’animation running", () => {
    const dot = renderDot("DiskSpaceWarning");
    expect(dot.classList.contains("ps-dot--warning")).toBe(true);
    // A settled warning must draw the eye without pulsing forever.
    expect(dot.classList.contains("ps-dot--running")).toBe(false);
  });
});
