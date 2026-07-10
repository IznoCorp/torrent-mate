import { describe, expect, it } from "vitest";

import type { components } from "@/api/schema";
import type { InterpretedLine } from "@/components/pipeline/interpretRun";
import { summariseSteps } from "@/components/pipeline/summariseSteps";

type StepTiming = components["schemas"]["StepTiming"];

/** Build a StepTiming with sensible defaults. */
function step(partial: Partial<StepTiming> & { name: string }): StepTiming {
  return {
    status: "success",
    started_at: null,
    ended_at: null,
    elapsed_s: null,
    success_count: null,
    skip_count: null,
    error_count: null,
    unmatched_count: null,
    counts: null,
    ...partial,
  };
}

describe("summariseSteps", () => {
  it("returns no lines for an empty step list", () => {
    expect(summariseSteps([])).toEqual([]);
  });

  it("builds one count-bearing line per known step (golden)", () => {
    const lines = summariseSteps([
      step({ name: "ingest", success_count: 2, skip_count: 1 }),
      step({
        name: "scrape",
        success_count: 3,
        unmatched_count: 2,
      }),
      step({ name: "dispatch", success_count: 4 }),
    ]);
    expect(lines).toEqual<InterpretedLine[]>([
      {
        step: "ingest",
        text: "Récupération des téléchargements — 2 traités, 1 ignoré",
        tone: "success",
      },
      {
        step: "scrape",
        text: "Recherche des métadonnées — 3 traités, 2 en attente de décision",
        tone: "warning",
      },
      {
        step: "dispatch",
        text: "Rangement vers le stockage — 4 traités",
        tone: "success",
      },
    ]);
  });

  it("marks an errored step as danger", () => {
    const lines = summariseSteps([
      step({ name: "scrape", status: "error", error_count: 1, success_count: 0 }),
    ]);
    expect(lines).toEqual<InterpretedLine[]>([
      { step: "scrape", text: "Recherche des métadonnées — échec", tone: "danger" },
    ]);
  });

  it("falls back to a bare line for a legacy step with null counts", () => {
    const lines = summariseSteps([
      step({ name: "verify", status: "success", success_count: null }),
    ]);
    expect(lines).toEqual<InterpretedLine[]>([
      { step: "verify", text: "Vérification finale — terminée", tone: "info" },
    ]);
  });

  it("renders a skipped step with no counts as ignorée", () => {
    const lines = summariseSteps([
      step({ name: "dispatch", status: "skipped", skip_count: null }),
    ]);
    expect(lines).toEqual<InterpretedLine[]>([
      { step: "dispatch", text: "Rangement vers le stockage — ignorée", tone: "info" },
    ]);
  });

  it("skips unknown step names", () => {
    const lines = summariseSteps([
      step({ name: "future_step", success_count: 5 }),
      step({ name: "ingest", success_count: 1 }),
    ]);
    expect(lines.map((l) => l.step)).toEqual(["ingest"]);
  });
});
