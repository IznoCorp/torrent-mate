// THE SEEDS A MEASUREMENT READS, through the mock layer's driving surface.
//
// READ BY THE HARNESS ALONE — the driver, the named states and the rules — and
// never by the product. The product asks the served reads, by address; this is
// what a rule compares those reads against, and what a named state needs to open
// a medium no served list happens to hold (DESIGN § 4.2: the mock layer exposes
// the seeds it answers from). Nothing outside `app/` imports `mocks/`, so a
// product module could not reach this even by mistake.
//
// THE SHEETS FAMILY ONLY, for now: every media sheet keyed by the title the seed
// holds it under, with the poster the sheet read composes beside it. The season
// counts join it when the follow panel's season block reads its served seasons.
import MEDIA_SHEETS from "./seeds/media-sheets.json";
import POSTERS from "./seeds/posters.json";
import SETTINGS from "./seeds/settings.json";

/** What the layer exposes of its seeds. */
export type MockSeeds = {
  /** Every media sheet, keyed by title, in the contract's names, with its poster. */
  sheets: () => Record<string, Record<string, unknown>>;
  /** The settings catalogue, rubric by rubric, in the contract's names. */
  settings: () => { id: string; settings: { file: string; key: string; type: string }[] }[];
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
};
