// THE SEEDS A MEASUREMENT READS, through the mock layer's driving surface.
//
// READ BY THE HARNESS ALONE — the driver, the named states and the rules — and
// never by the product. The product asks the served reads, by address; this is
// what a rule compares those reads against, and what a named state needs to open
// a medium no served list happens to hold (DESIGN § 4.2: the mock layer exposes
// the seeds it answers from). Nothing outside `app/` imports `mocks/`, so a
// product module could not reach this even by mistake.
//
// THREE FAMILIES: every media sheet keyed by the title the seed holds it under,
// with the poster the sheet read composes beside it; the settings catalogue; and
// the passages, so a named state opens a run by what it is about — a failure,
// a maintenance command — rather than by an identifier written into it.
import MEDIA_SHEETS from "./seeds/media-sheets.json";
import POSTERS from "./seeds/posters.json";
import SETTINGS from "./seeds/settings.json";
import PIPELINE_RUNS from "./seeds/pipeline-runs.json";
import type { components } from "../contract/types";

/** What the layer exposes of its seeds. */
export type MockSeeds = {
  /** Every media sheet, keyed by title, in the contract's names, with its poster. */
  sheets: () => Record<string, Record<string, unknown>>;
  /** The settings catalogue, rubric by rubric, in the contract's names. */
  settings: () => { id: string; settings: { file: string; key: string; type: string }[] }[];
  /** Every passage the history holds at rest, in the snapshot's order and the contract's names. */
  pipelineRuns: () => components["schemas"]["RunDetail"][];
};

/** The seeds the harness reads, composed on each call so no caller holds a copy it could mutate. */
export const mockSeeds: MockSeeds = {
  sheets: () =>
    Object.fromEntries(
      Object.entries(MEDIA_SHEETS as Record<string, Record<string, unknown>>).map(
        ([title, sheet]) => [
          title,
          { ...sheet, poster: (POSTERS as Record<string, string>)[title] ?? null },
        ],
      ),
    ),
  settings: () => structuredClone(SETTINGS) as ReturnType<MockSeeds["settings"]>,
  pipelineRuns: () => structuredClone(PIPELINE_RUNS) as ReturnType<MockSeeds["pipelineRuns"]>,
};
