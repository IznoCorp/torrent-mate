// The example an identifier field shows, typed as it is, adds a medium (B-691).
//
// WHAT MAKES THIS NON-VACUOUS. The reporter typed the example the field showed —
// « 1234 » under TMDB — and nothing could come of it: no medium of the maquette
// carries that identifier, and « Ajouter » never answered. Each source's example
// is asked of the provider search by identifier, the way the screen asks it, and
// must find exactly one medium, not yet owned, that the act can follow.
import { beforeEach, describe, expect, it } from "vitest";
import { routes } from "./handlers";
import { resolve } from "./router";
import { resetMockState } from "./state";
import { ID_EXAMPLES, idQuery, type IdProvider } from "../features/acquisition/id-examples";
import type { SearchResults } from "../features/acquisition/types";

/**
 * Asks the provider search one question, the way the screen asks it.
 *
 * @param query The search's text.
 * @returns What the layer answers.
 */
function search(query: string): SearchResults {
  const path = "/api/acquisition/search";
  const found = resolve(routes(), "GET", path);
  if (found === null) throw new Error(`no route for ${path}`);
  return found.route.handle({ path, parameters: found.parameters ?? {},
                              query: new URLSearchParams({ query }), body: null }) as SearchResults;
}

const PROVIDERS: IdProvider[] = ["TMDB", "TVDB", "IMDB"];

describe("an identifier field's example", () => {
  beforeEach(() => resetMockState());

  it.each(PROVIDERS)("%s: typed as shown, finds exactly one medium not yet owned", (provider) => {
    const example = ID_EXAMPLES[provider];
    const answer = search(idQuery(provider, example));
    expect(answer.results.map((result) => result.title)).toHaveLength(1);
    const [found] = answer.results;
    expect(found.owned).toBe(false);
    expect(String(found.ids?.[provider.toLowerCase() as "tmdb" | "tvdb" | "imdb"])).toBe(example);
  });

  it("shows a different identifier for each source", () => {
    expect(new Set(PROVIDERS.map((provider) => ID_EXAMPLES[provider])).size).toBe(PROVIDERS.length);
  });

  it("finds nothing for an identifier no medium carries", () => {
    expect(search(idQuery("TMDB", "1234")).results).toEqual([]);
  });
});
