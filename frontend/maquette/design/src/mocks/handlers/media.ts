// One title, and what we hold of it.
import CAST_PORTRAITS from "../seeds/cast-portraits.json";
import HERO_IMAGES from "../seeds/hero-images.json";
import OWNED_EPISODES from "../seeds/owned-episodes.json";
import POSTERS from "../seeds/posters.json";
import POSTERS_HIGH_DEFINITION from "../seeds/posters-high-definition.json";
import SEASONS from "../seeds/seasons.json";
import MEDIA_SHEETS from "../seeds/media-sheets.json";
import TRAILERS from "../seeds/trailers.json";
import { mockState } from "../state";
import { scenario } from "../scenario";
import { GET, POST, route } from "./shared";
import type { MockRequest, MockRoute } from "../router";

// The pipeline is BUSY unless it is idle, and an ask that arrives then is
// queued VISIBLY rather than refused (DOIT-4). It is the contract's own
// `PipelineState` token, carried like every other token in this layer.
const IDLE = "idle";

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
  // WHAT A DELETE DID TO THIS MEDIUM. `found` is a seed, and a seed does not
  // know about a mutation; a sheet reopened after a confirmed delete answered
  // « Possédés 24 » and offered to delete it again.
  const deleted = titles.some((title) => mockState().deletedTitles.includes(title));
  return {
    ...found,
    ...(deleted ? { owned: false } : {}),
    // AND THE CONTRACT'S OWN « UNKNOWN ». `MediaSheetResponse.ownership` is
    // required and NULLABLE — null « when the library database is unavailable »
    // — so the layer has to be able to answer it, or a screen's unknown-ownership
    // branch is unreachable and untestable while the contract says a backend
    // reaches it every time that database is down.
    ...(mockState().libraryDatabaseAvailable ? {} : { owned: null }),
    // WHEN THE METADATA WAS LAST RE-READ, or null. It is what the sheet's
    // « Métadonnées rafraîchies » row draws, and it is the state the re-scrape
    // verb MOVES (B-383): before this field the row printed a fixed date as a
    // fact, in every state, over a sheet that had answered nothing.
    metadataRefreshedAt: refreshedAt(titles),
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

/**
 * When one medium's metadata was last re-read, under whichever title holds it.
 *
 * @param titles Every title the identity names.
 * @returns The instant, or null when it has not been re-read in this session.
 */
function refreshedAt(titles: string[]): string | null {
  const held = mockState().metadataRefreshedAt;
  for (const title of titles) {
    if (Object.hasOwn(held, title)) return held[title];
  }
  return null;
}

/**
 * How many episodes of each season have AIRED at the layer's frozen clock.
 *
 * DERIVED FROM THE CATALOGUE'S OWN EPISODE DATES, never typed a second time. A
 * « manquant » is an episode that has aired and is not held, so the denominator
 * of a season row is this count and not the catalogue's total, which counts the
 * announced episodes too: « Saison 3 · 6/10 · 4 manquants » on a season of which
 * seven had aired said three episodes were missing that nobody could have. ONE
 * derivation, here, so the sheet and the follow panel cannot answer two numbers.
 *
 * A season the catalogue lists with no episode and no list has aired nothing. A
 * season with a total and no list is UNKNOWN, and says null rather than guessing.
 * A title with no sheet answers the counts its season family carries, which is
 * the catalogue the answer falls back to beside it.
 *
 * @param sheet The sheet under whichever title holds it, if any.
 * @param counted The season family's entries for the same identity, if any.
 * @returns The aired count, keyed by season number.
 */
function airedBySeason(
  sheet: Record<string, unknown> | undefined,
  counted: unknown,
): Record<string, number | null> {
  const aired: Record<string, number | null> = {};
  const today = scenario().now;
  const catalogue = sheet?.seasons as
    | { number: number; episodes?: number | null }[]
    | undefined;
  if (catalogue !== undefined) {
    const episodes = (sheet?.episodes ?? {}) as Record<string, { airDate?: string }[]>;
    for (const season of catalogue) {
      const seasonEpisodes = episodes[String(season.number)];
      if (seasonEpisodes !== undefined) {
        aired[String(season.number)] = seasonEpisodes.filter(
          (episode) => Boolean(episode.airDate) && String(episode.airDate) <= today,
        ).length;
      } else {
        aired[String(season.number)] = season.episodes === 0 ? 0 : null;
      }
    }
    return aired;
  }
  for (const season of (counted ?? []) as { season: number; aired: number }[]) {
    aired[String(season.season)] = season.aired;
  }
  return aired;
}

/**
 * The seasons read's answer for a medium known under these titles.
 *
 * @param titles Every title the medium's identity is held under.
 * @returns The catalogue, the episodes held by season, and what aired by season.
 */
export function seasonsAnswer(titles: string[]) {
  const found = underAnyTitle(MEDIA_SHEETS as ByTitle, titles) as
    | Record<string, unknown>
    | undefined;
  const counted = underAnyTitle(SEASONS as ByTitle, titles);
  const catalogue = (found?.seasons ?? counted ?? []) as unknown[];
  return {
    seasons: catalogue,
    owned: (underAnyTitle(OWNED_EPISODES as ByTitle, titles) ?? {}) as Record<string, number[]>,
    aired: airedBySeason(found, counted),
  };
}

/* The two providers an identity is addressed by, in the order the served
   address prefers them. */
const FIRST_PROVIDER = "tvdb";
const FALLBACK_PROVIDER = "tmdb";

/**
 * The seasons read's answer for one title, resolved through its identity as the route resolves it.
 *
 * @param title The title a rule asks about.
 * @param ids Its provider identity, when one is known.
 * @returns The same answer the route gives for that identity.
 */
export function seasonsAnswerFor(title: string, ids: Record<string, unknown> | undefined) {
  const provider = ids?.[FIRST_PROVIDER] ? FIRST_PROVIDER : ids?.[FALLBACK_PROVIDER] ? FALLBACK_PROVIDER : null;
  const titles = provider ? titlesFor(provider, String(ids?.[provider])) : [];
  return seasonsAnswer(titles.length ? titles : [title]);
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
        return seasonsAnswer(titles);
      },
    ),
    route(
      "rescrapeMedia",
      POST,
      "/api/media/{provider}/{providerId}/rescrape",
      (request) => {
        const titles = titlesFor(
          request.parameters.provider,
          request.parameters.providerId,
        );
        // A MEDIUM NO IDENTITY NAMES IS NOT RE-SCRAPED, and the layer says so
        // with a 404 rather than an acknowledgement: a handler that answered a
        // success here would be the « said, not done » defect this operation
        // exists to end, wearing the layer's clothes instead of the verb's.
        if (titles.length === 0) return null;
        // THE STATE THE ANSWER IS ABOUT MOVES, and it moves for EVERY title the
        // identity names — the sheets are keyed by title and twenty identities
        // carry two keys each (B-088), so writing under the first would leave
        // the read answering null under the other.
        //
        // THE INSTANT IS THE LAYER'S FROZEN CLOCK, never `Date.now()`: this
        // layer is deterministic by contract, and a stamp drawn from the wall
        // clock would make the same state driven twice answer different bytes
        // and put the oracle out of reach.
        const when = scenario().now;
        for (const title of titles) mockState().metadataRefreshedAt[title] = when;
        return {
          provider: request.parameters.provider,
          providerId: request.parameters.providerId,
          queued: mockState().pipelineState !== IDLE,
          // NULL, ALWAYS. The layer holds no run identifier at all — every
          // other verb here answers the same — and the register asks the
          // backend for one.
          runUid: null,
        };
      },
    ),
  ];
}
