import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EventMessage } from "@/api/events";
import { EventFeed } from "@/components/dashboard/EventFeed";

/** Build an ``EventMessage`` with a stream-id timestamp prefix. */
function makeEvent(ms: number, type: string): EventMessage {
  return { id: `${String(ms)}-0`, type, data: { step: type } };
}

/** Original prototype descriptors, restored after each test. */
const originalOffsetHeight = Object.getOwnPropertyDescriptor(
  HTMLElement.prototype,
  "offsetHeight",
);
const originalOffsetWidth = Object.getOwnPropertyDescriptor(
  HTMLElement.prototype,
  "offsetWidth",
);

/** Force a non-zero layout size (TanStack Virtual measures via ``offsetHeight``). */
function defineOffset(name: "offsetHeight" | "offsetWidth", value: number): void {
  Object.defineProperty(HTMLElement.prototype, name, {
    configurable: true,
    get: () => value,
  });
}

beforeEach(() => {
  // jsdom reports zero-size layout; seed a real viewport so the virtualizer
  // computes a visible window, and make `scrollTo` a harmless no-op.
  defineOffset("offsetHeight", 600);
  defineOffset("offsetWidth", 800);
  Object.defineProperty(Element.prototype, "scrollTo", {
    value: vi.fn(),
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  if (originalOffsetHeight) {
    Object.defineProperty(HTMLElement.prototype, "offsetHeight", originalOffsetHeight);
  }
  if (originalOffsetWidth) {
    Object.defineProperty(HTMLElement.prototype, "offsetWidth", originalOffsetWidth);
  }
});

describe("EventFeed", () => {
  it("affiche les événements du flux virtualisé", () => {
    const events = [
      makeEvent(1_700_000_000_000, "PipelineStepStarted"),
      makeEvent(1_700_000_001_000, "PipelineStepCompleted"),
      makeEvent(1_700_000_002_000, "PipelineStepErrored"),
    ];
    render(<EventFeed events={events} />);

    expect(screen.getByText("PipelineStepStarted")).toBeInTheDocument();
    expect(screen.getByText("PipelineStepCompleted")).toBeInTheDocument();
    expect(screen.getByText("PipelineStepErrored")).toBeInTheDocument();
  });

  it("montre l’état vide en l’absence d’événements", () => {
    render(<EventFeed events={[]} />);
    expect(screen.getByText("En attente d’événements…")).toBeInTheDocument();
  });

  it("met le suivi en pause quand on remonte, puis le reprend au clic", () => {
    const events = [makeEvent(1_700_000_000_000, "PipelineStepStarted")];
    render(<EventFeed events={events} />);

    // Following by default → the toggle is disabled and labelled as active.
    const toggle = screen.getByRole("button", { name: "Suivi auto activé" });
    expect(toggle).toBeDisabled();

    // Simulate the operator scrolling up (far from the bottom).
    const feed = screen.getByRole("log");
    Object.defineProperty(feed, "scrollHeight", {
      value: 1_000,
      configurable: true,
    });
    Object.defineProperty(feed, "clientHeight", {
      value: 600,
      configurable: true,
    });
    Object.defineProperty(feed, "scrollTop", { value: 0, configurable: true });
    fireEvent.scroll(feed);

    // Follow pauses → the toggle re-enables and offers to resume.
    const resume = screen.getByRole("button", { name: "Reprendre le suivi" });
    expect(resume).toBeEnabled();

    // Clicking resumes auto-follow.
    fireEvent.click(resume);
    expect(
      screen.getByRole("button", { name: "Suivi auto activé" }),
    ).toBeDisabled();
  });
});
