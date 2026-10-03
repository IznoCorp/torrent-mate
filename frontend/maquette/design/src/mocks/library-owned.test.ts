// Every medium a sheet says is owned is a row of the library (B-688).
//
// WHAT MAKES THIS NON-VACUOUS. The reporter searched the Médiathèque for « Silo » —
// followed, its sheet saying « owned » — and found nothing: the library seed held
// no row for it, nor for « American Dad! », and three more owned sheets were in the
// same case, five incomplete series among them; and two followed shows whose rows
// carry their folder's year (« Furious (2026) ») were answered « not in the
// library » by the membership read, which compared the title exactly. Each owned
// sheet is asked by the listing's search for its title, and each followed one by
// the membership read the follow panel makes.
import { beforeEach, describe, expect, it } from "vitest";
import FOLLOWS from "./seeds/follows.json";
import MEDIA_SHEETS from "./seeds/media-sheets.json";
import { routes } from "./handlers";
import { resolve } from "./router";
import { resetMockState } from "./state";
import { baseTitle } from "../lib/titles";

type Sheet = { title?: string; year: string; owned?: boolean };

/**
 * Answers one GET the way the interface asks it.
 *
 * @param path The route's path.
 * @param query The query parameters.
 * @returns What the layer answers.
 */
function get<Answer>(path: string, query: Record<string, string>): Answer {
  const found = resolve(routes(), "GET", path);
  if (found === null) throw new Error(`no route for ${path}`);
  return found.route.handle({ path, parameters: found.parameters ?? {},
                              query: new URLSearchParams(query), body: null }) as Answer;
}

// The owned sheets, by the title a reader types: the sheet's key without its year.
const OWNED = Object.entries(MEDIA_SHEETS as Record<string, Sheet>)
  .filter(([, sheet]) => sheet.owned === true)
  .map(([key, sheet]) => ({ title: baseTitle(key), year: sheet.year }));

describe("an owned medium", () => {
  beforeEach(() => resetMockState());

  it("is found by the library's search", () => {
    const missing = OWNED.filter(({ title }) => {
      const page = get<{ items: { title: string }[] }>("/library/items", { query: title });
      return !page.items.some((row) => baseTitle(row.title) === title);
    });
    expect(missing.map((one) => one.title)).toEqual([]);
  });

  it("is in the library for the membership read a followed title is asked by", () => {
    // Asked as `lib/membership.ts` asks it: by the follow's title alone.
    const owned = new Set(OWNED.map((one) => one.title));
    const refused = FOLLOWS
      .filter((follow) => owned.has(follow.title))
      .filter((follow) => !get<{ inLibrary: boolean }>("/library/membership", { title: follow.title }).inLibrary);
    expect(refused.map((one) => one.title)).toEqual([]);
  });
});
