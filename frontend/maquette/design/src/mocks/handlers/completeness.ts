// A follow's completeness, season by season (L24, NE-DOIT-PAS-1).
//
// DERIVED FROM THE SAME SEASONS the seasons read answers — never a second set
// of figures: what aired and what is held, per season, for the medium the
// follow names. A follow whose seasons nobody catalogued answers
// `source: unknown` and no season, never a fabricated all-missing grid.
import { GET, route } from "./shared";
import { mockState } from "../state";
import { refused, type MockRoute } from "../router";
import { seasonsAnswerFor } from "./media";
import type { components } from "../../contract/types";

type SeasonCompleteness = components["schemas"]["SeasonCompleteness"];

/** The status of a completeness asked of a follow nobody holds. */
const NOT_FOUND = 404;

/** An episode's state in the matrix, as the contract names it. */
const IN_LIBRARY = "in_library";
const TO_GRAB = "to_grab";

/**
 * The completeness of one follow.
 *
 * @param followedId The follow, which the layer names by its title.
 * @returns The matrix, or a refusal when no follow carries that name.
 */
function completenessOf(followedId: string): unknown {
  const follow = mockState().follows.find((one) => one.title === followedId);
  if (follow === undefined) return refused(NOT_FOUND, "no follow carries that name");
  const held = seasonsAnswerFor(follow.title, follow.ids as Record<string, unknown> | undefined);
  const catalogue = held.seasons as { number?: number; season?: number; episodes?: number | null }[];
  const seasons: SeasonCompleteness[] = catalogue.map((entry) => {
    const season = Number(entry.number ?? entry.season);
    const total = held.aired[String(season)] ?? entry.episodes ?? 0;
    const owned = [...new Set(held.owned[String(season)] ?? [])].filter((episode) => episode <= total);
    return {
      season,
      total,
      owned: owned.length,
      queued: 0,
      announced: Math.max((entry.episodes ?? total) - total, 0),
      episodes: Array.from({ length: total }, (_, index) => ({
        episode: index + 1,
        state: owned.includes(index + 1) ? IN_LIBRARY : TO_GRAB,
      })),
    };
  });
  return {
    followedId: mockState().follows.indexOf(follow),
    title: follow.title,
    kind: follow.kind,
    seasons,
    source: seasons.length > 0 ? "cache" : "unknown",
    providerCatalogEmpty: seasons.length === 0,
    catalogRefreshedAt: null,
  };
}

/** Every route this subject answers. */
export function completenessRoutes(): MockRoute[] {
  return [
    route("readFollowCompleteness", GET, "/acquisition/followed/{followedId}/completeness", (request) =>
      completenessOf(request.parameters.followedId),
    ),
  ];
}
