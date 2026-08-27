// One title, and what we hold of it.
import CAST_PORTRAITS from "../seeds/cast-portraits.json";
import HERO_IMAGES from "../seeds/hero-images.json";
import OWNED_EPISODES from "../seeds/owned-episodes.json";
import POSTERS from "../seeds/posters.json";
import POSTERS_HIGH_DEFINITION from "../seeds/posters-high-definition.json";
import SEASONS from "../seeds/seasons.json";
import MEDIA_SHEETS from "../seeds/media-sheets.json";
import TRAILERS from "../seeds/trailers.json";
import { GET, route } from "./shared";
import type { MockRequest, MockRoute } from "../router";

type Sheets = Record<string, Record<string, unknown>>;
type ByTitle = Record<string, unknown>;

/**
 * Finds EVERY title one provider identity names.
 *
 * ONE IDENTITY NAMES MORE THAN ONE KEY, and returning the first was a defect.
 * The sheets are keyed by title and carry their provider identifiers inside —
 * the fixture's own arrangement — and twenty identities are carried by two keys
 * at once: `Silo (2023)` and `Silo` hold the same three identifiers. The other
 * families are keyed by only ONE of the two, and never the same one: the
 * seasons and the holdings of Silo, Furious and President Curtis are under the
 * bare form while the sheets answer with the dated one. Taking the first match
 * returned nine empty season lists for the three shows a reader opens first.
 *
 * So every match is returned, and each composition below takes the first key
 * the family it is reading actually holds. The demand register asks the backend
 * for a sheet reachable by identity — `/media/:provider/:id` is the address the
 * constitution's DOIT-11 gives it — which removes the question entirely.
 *
 * @param provider The provider, `tmdb`, `tvdb` or `imdb`.
 * @param identifier The identifier at that provider.
 * @returns Every title carrying that identity, in the fixture's own order.
 */
function titlesFor(provider: string, identifier: string): string[] {
  const found: string[] = [];
  for (const [title, sheet] of Object.entries(MEDIA_SHEETS as Sheets)) {
    const identifiers = sheet.ids as Record<string, unknown> | undefined;
    if (identifiers && String(identifiers[provider] ?? "") === identifier) {
      found.push(title);
    }
  }
  return found;
}

/**
 * Reads one family keyed by title, under whichever of the titles it holds.
 *
 * @param family The family, keyed by title.
 * @param titles Every title the identity names.
 * @returns The value, or undefined when no title answers.
 */
function underAnyTitle(family: ByTitle, titles: string[]): unknown {
  for (const title of titles) {
    if (Object.hasOwn(family, title)) return family[title];
  }
  return undefined;
}

/**
 * Picks the portraits of one sheet's own cast out of the global map.
 *
 * @param cast The sheet's cast list.
 * @returns The portraits, keyed by the name each belongs to.
 */
function portraitsFor(cast: unknown): Record<string, string> {
  const portraits = CAST_PORTRAITS as Record<string, string>;
  const found: Record<string, string> = {};
  if (!Array.isArray(cast)) return found;
  for (const member of cast) {
    const name = (member as { name?: unknown }).name;
    if (typeof name === "string" && Object.hasOwn(portraits, name)) {
      found[name] = portraits[name];
    }
  }
  return found;
}

/**
 * Answers one media sheet, composed from the families that hold it.
 *
 * @param request The request.
 * @returns The sheet, or null when no title answers that identity.
 */
function sheet(request: MockRequest): unknown {
  const titles = titlesFor(request.parameters.provider, request.parameters.providerId);
  const found = underAnyTitle(MEDIA_SHEETS as ByTitle, titles) as
    | Record<string, unknown>
    | undefined;
  if (found === undefined) return null;
  // The posters and the wide visual live in families of their own, keyed by the
  // same titles. Composing them here is what the demand register asks the
  // backend to do once, in one payload.
  //
  // THE SYNOPSIS IS NOT AMONG THEM, and it was. `SYNOPSIS` is what the engine
  // puts on a LIBRARY CARD; a media sheet carries its own `ov`. Substituting
  // one for the other answered a different text on 213 of the 259 titles both
  // hold, several of them in English — a re-derivation, which the projection
  // rule forbids for exactly this reason.
  return {
    ...found,
    poster: underAnyTitle(POSTERS as ByTitle, titles),
    posterHighDefinition: underAnyTitle(POSTERS_HIGH_DEFINITION as ByTitle, titles),
    hero: underAnyTitle(HERO_IMAGES as ByTitle, titles),
    trailerVideo: underAnyTitle(TRAILERS as ByTitle, titles),
    // THIS TITLE's cast, not the whole map. The fixture is a global lookup of
    // 170 portraits; serving it entire on every sheet gave the payload a scope
    // the fixture does not have.
    castPortraits: portraitsFor(found.cast),
  };
}

/** Every route this subject answers. */
export function mediaRoutes(): MockRoute[] {
  return [
    route("readMediaSheet", GET, "/api/media/{provider}/{providerId}", sheet),
    route(
      "readMediaSeasons",
      GET,
      "/api/media/{provider}/{providerId}/seasons",
      (request) => {
        const titles = titlesFor(
          request.parameters.provider,
          request.parameters.providerId,
        );
        // THE CATALOGUE IS THE SHEET'S OWN, and this answered a different
        // family. `SEASONS` is keyed by title like everything else here, but it
        // is not what the engine crossed: `seasonsOf` read `sheetFor(title)
        // .seasons` — the catalogue carried INSIDE the sheet — and fell back to
        // the owned numbers only when it was empty. Measured on « mediasheet-
        // series »: the sheet carries four seasons and `SEASONS` holds three,
        // so the matrix drew one short. Same class as B-088: two families
        // keyed the same way are not the same answer.
        const found = underAnyTitle(MEDIA_SHEETS as ByTitle, titles) as
          | Record<string, unknown>
          | undefined;
        const catalogue = found?.seasons ?? underAnyTitle(SEASONS as ByTitle, titles) ?? [];
        return {
          seasons: catalogue,
          owned: underAnyTitle(OWNED_EPISODES as ByTitle, titles) ?? {},
        };
      },
    ),
  ];
}
