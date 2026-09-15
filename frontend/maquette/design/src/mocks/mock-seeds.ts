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
import SEASON_FAMILY from "./seeds/seasons.json";
import { seasonsAnswerFor } from "./handlers/media";
import FOLLOWS from "./seeds/follows.json";
import INCOMPLETE_SHOWS from "./seeds/incomplete-shows.json";
import { seasonsHeld } from "../lib/season-rows";

/** What the layer exposes of its seeds. */
export type MockSeeds = {
  /** Every media sheet, keyed by title, in the contract's names, with its poster. */
  sheets: () => Record<string, Record<string, unknown>>;
  /** The settings catalogue, rubric by rubric, in the contract's names. */
  settings: () => { id: string; settings: { file: string; key: string; type: string }[] }[];
  /** Every passage the history holds at rest, in the snapshot's order and the contract's names. */
  pipelineRuns: () => components["schemas"]["RunDetail"][];
  /**
   * Every medium's season rows — number, aired (null when unknown), held — as
   * the seasons read answers them and every season row is drawn from them.
   */
  seasons: () => Record<string, [number, number | null, number][]>;
  /** The season family seed, as its rows were written: `[season, aired, owned]` per title. */
  seasonFamily: () => Record<string, [number, number, number][]>;
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
  seasons: () => {
    // EVERY TITLE A RULE CAN ASK ABOUT — a follow, an incomplete show, a sheet,
    // the family — each answered under its IDENTITY, as the served read is: a
    // follow named « Silo » holds its episodes under the sheet « Silo (2023) ».
    const identityByTitle = new Map<string, Record<string, unknown> | undefined>();
    for (const title of Object.keys(MEDIA_SHEETS))
      identityByTitle.set(title, (MEDIA_SHEETS as Record<string, { ids?: Record<string, unknown> }>)[title].ids);
    for (const title of Object.keys(SEASON_FAMILY)) if (!identityByTitle.has(title)) identityByTitle.set(title, undefined);
    for (const one of [...FOLLOWS, ...INCOMPLETE_SHOWS] as { title: string; ids?: Record<string, unknown> | null }[])
      identityByTitle.set(one.title, one.ids ?? identityByTitle.get(one.title));
    return Object.fromEntries(
      [...identityByTitle].map(([title, ids]) => {
        const answer = seasonsAnswerFor(title, ids);
        const catalogue = answer.seasons.map((season) => {
          const entry = season as { number?: number; season?: number };
          return { number: Number(entry.number ?? entry.season) };
        });
        return [title, seasonsHeld({ seasons: catalogue, owned: answer.owned, aired: answer.aired })];
      }),
    );
  },
  seasonFamily: () =>
    Object.fromEntries(
      Object.entries(SEASON_FAMILY as Record<string, { season: number; aired: number; owned: number }[]>).map(
        ([title, rows]) => [title, rows.map((row) => [row.season, row.aired, row.owned])],
      ),
    ) as Record<string, [number, number, number][]>,
};
