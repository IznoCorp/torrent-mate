import { describe, expect, it } from "vitest";

import {
  eventSummary,
  eventTypeLabel,
  severityForEventType,
} from "@/components/dashboard/eventRow.utils";

describe("eventTypeLabel (F4)", () => {
  it("maps well-known event classes to French labels", () => {
    expect(eventTypeLabel("PipelineStepStarted")).toBe("Étape démarrée");
    expect(eventTypeLabel("ItemProgressed")).toBe("Élément traité");
    expect(eventTypeLabel("CircuitBreakerOpened")).toBe("Circuit ouvert");
  });

  it("never returns a raw PascalCase class name for unmapped types", () => {
    // De-prefixed + spaced, so an operator never sees a bare class name.
    expect(eventTypeLabel("PipelineWidgetReticulated")).toBe(
      "Widget Reticulated",
    );
    expect(eventTypeLabel("SomethingHappened")).toBe("Something Happened");
  });
});

describe("eventSummary (F4)", () => {
  it("condenses salient payload fields instead of dumping raw JSON", () => {
    const summary = eventSummary({
      step: "scrape",
      status: "matched",
      timestamp: 1234567890,
      extra: { nested: true },
    });
    expect(summary).toBe("scrape · matched");
    // Never the raw JSON braces.
    expect(summary).not.toContain("{");
  });

  it("falls back to compact key: value, then a dash", () => {
    expect(eventSummary({ foo: "bar" })).toBe("foo: bar");
    expect(eventSummary({})).toBe("—");
  });
});

describe("severityForEventType", () => {
  it("classifies error/warn/neutral", () => {
    expect(severityForEventType("PipelineStepErrored")).toBe("danger");
    expect(severityForEventType("SomethingWarning")).toBe("warning");
    expect(severityForEventType("PipelineStepStarted")).toBe("neutral");
  });
});
