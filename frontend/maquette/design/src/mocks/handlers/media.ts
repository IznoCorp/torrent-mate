// One title, and what we hold of it.
import CAST from "../seeds/CAST.json";
import HERO_IMAGES from "../seeds/HERO_IMAGES.json";
import OWNED from "../seeds/OWNED.json";
import POSTERS from "../seeds/POSTERS.json";
import POSTERS_HD from "../seeds/POSTERS_HD.json";
import SEASONS from "../seeds/SEASONS.json";
import SHEETS_RAW from "../seeds/SHEETS_RAW.json";
import SYNOPSIS from "../seeds/SYNOPSIS.json";
import trailerIds from "../seeds/trailerIds.json";
import { GET, route } from "./shared";
import type { MockRequest, MockRoute } from "../router";

type Sheets = Record<string, Record<string, unknown>>;

/**
 * Finds the title one provider identity names.
 *
 * The sheets are keyed by TITLE and carry their provider identifiers inside,
 * which is the fixture's own arrangement: the demand register asks the backend
 * for a sheet reachable by identity, since `/media/:provider/:id` is the
 * address the constitution's DOIT-11 gives it.
 *
 * @param provider The provider, `tmdb` or `tvdb`.
 * @param identifier The identifier at that provider.
 * @returns The title, or null.
 */
function titleFor(provider: string, identifier: string): string | null {
  for (const [title, sheet] of Object.entries(SHEETS_RAW as Sheets)) {
    const identifiers = sheet.ids as Record<string, unknown> | undefined;
    if (identifiers && String(identifiers[provider] ?? "") === identifier) return title;
  }
  return null;
}

/**
 * Answers one media sheet, composed from the seven families that hold it.
 *
 * @param request The request.
 * @returns The sheet, or null when no title answers that identity.
 */
function sheet(request: MockRequest): unknown {
  const title = titleFor(request.parameters.provider, request.parameters.providerId);
  if (title === null) return null;
  const sheets = SHEETS_RAW as Sheets;
  const synopses = SYNOPSIS as Record<string, string>;
  const found = sheets[title];
  // The synopsis, the poster and the wide visual live in families of their
  // own, keyed by the same title. Composing them here is what the demand
  // register asks the backend to do once, in one payload.
  return {
    ...found,
    overview: synopses[title] ?? found.overview,
    poster: (POSTERS as Record<string, string>)[title],
    posterHighDefinition: (POSTERS_HD as Record<string, string>)[title],
    hero: (HERO_IMAGES as Record<string, string>)[title],
    trailerVideo: (trailerIds as Record<string, unknown>)[title],
    castPortraits: CAST,
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
        const title = titleFor(
          request.parameters.provider,
          request.parameters.providerId,
        );
        const seasons = SEASONS as Record<string, unknown>;
        const owned = OWNED as Record<string, unknown>;
        return {
          seasons: title === null ? [] : (seasons[title] ?? []),
          owned: title === null ? {} : (owned[title] ?? {}),
        };
      },
    ),
  ];
}
