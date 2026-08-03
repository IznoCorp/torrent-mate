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

describe("download event labels (seed-caps)", () => {
  it("renders DownloadStarted with French label", () => {
    expect(eventTypeLabel("DownloadStarted")).toBe("Téléchargement démarré");
  });

  it("renders DownloadProgressed with French label", () => {
    expect(eventTypeLabel("DownloadProgressed")).toBe("Téléchargement en cours");
  });

  it("renders DownloadCompleted with French label", () => {
    expect(eventTypeLabel("DownloadCompleted")).toBe("Téléchargement terminé");
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

  it("renders a download threshold crossing as title — pct %", () => {
    const summary = eventSummary({
      info_hash: "abc123",
      title: "Breaking Bad S05E01",
      progress: 0.52,
      threshold_pct: 50,
    });
    expect(summary).toBe("Breaking Bad S05E01 — 50 %");
    // Never the raw JSON braces.
    expect(summary).not.toContain("{");
  });

  it("renders a download start/finish payload as title (provider)", () => {
    expect(
      eventSummary({
        info_hash: "abc123",
        title: "Dune",
        provider: "c411",
        kind: "movie",
      }),
    ).toBe("Dune (c411)");
  });

  it("omits an unknown provider gracefully", () => {
    expect(
      eventSummary({
        info_hash: "abc123",
        title: "Dune",
        provider: "unknown",
        kind: "movie",
      }),
    ).toBe("Dune");
  });
});

describe("severityForEventType", () => {
  it("classifies error/warn/neutral", () => {
    expect(severityForEventType("PipelineStepErrored")).toBe("danger");
    expect(severityForEventType("SomethingWarning")).toBe("warning");
    expect(severityForEventType("PipelineStepStarted")).toBe("neutral");
  });
});
