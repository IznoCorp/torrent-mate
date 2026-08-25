// What is wanted, and what is being fetched.
import BLOCKED from "../seeds/blocked.json";
import GRAB_CADENCE from "../seeds/grab-cadence.json";
import DONE_TODAY from "../seeds/done-today.json";
import IN_FLIGHT from "../seeds/in-flight.json";
import NOT_FOUND from "../seeds/not-found.json";
import NOT_FOUND_LOADED from "../seeds/not-found-loaded.json";
import RELEASES from "../seeds/releases.json";
import SEARCH_RESULTS from "../seeds/search-results.json";
import SUGGESTIONS from "../seeds/suggestions.json";
import TAKEABLE from "../seeds/takeable.json";
import JOURNEY_STAGES from "../seeds/journey-stages.json";
import { DELETE, GET, PATCH, POST, field, route, text } from "./shared";
import { mockState } from "../state";
import type { MockRequest, MockRoute } from "../router";

// How many suggestions one batch of the deck carries. The engine's own batch
// size is `SUG_BATCH`, classified `interface` — the interface owns it.
const BATCH_SIZE = 30;

// The dense body of data, asked for by name.
const LOADED = "loaded";

// What a follow the request does not fully describe starts as. Every one of
// these is a token or a blank, never a value copied off another record.
const NEWLY_ADDED_STATUS = "pending";
const NEWLY_ADDED_SINCE = "";
const NEWLY_ADDED_YEAR = 0;

/**
 * Finds one follow by the identifier the address carries.
 *
 * The fixture's follows carry no identifier of their own — they are keyed by
 * TITLE, which is what the engine draws them by — so the address's identifier
 * is read as a title. The demand register asks the backend for a stable
 * identifier, because a title is not one.
 *
 * @param identifier What the address named.
 * @returns The follow, or undefined.
 */
function followFor(identifier: string) {
  return mockState().follows.find((follow) => follow.title === identifier);
}

/** Every route this subject answers. */
export function acquisitionRoutes(): MockRoute[] {
  return [
    route("readFollows", GET, "/api/acquisition/followed", () => mockState().follows),
    route("createFollow", POST, "/api/acquisition/followed", (request) => {
      const state = mockState();
      // BUILT FROM ITS OWN REQUEST, and from nothing else. An earlier version
      // spread the first seeded follow of the same kind and overrode three
      // fields, so a new title inherited a stranger's year, a stranger's date
      // and a stranger's run status. A value taken from the wrong record is
      // worse than an invented one: it typechecks, and it reads as real.
      const year = Number(field(request.body, "year"));
      const added = {
        title: text(request.body, "title"),
        kind: text(request.body, "kind"),
        year: Number.isFinite(year) ? year : NEWLY_ADDED_YEAR,
        status: NEWLY_ADDED_STATUS,
        showStatus: null,
        since: NEWLY_ADDED_SINCE,
        searches: 0,
        fresh: true,
      };
      state.follows = [added, ...state.follows];
      return added;
    }),
    route(
      "updateFollow",
      PATCH,
      "/api/acquisition/followed/{followedId}",
      (request) => {
        const found = followFor(request.parameters.followedId);
        if (found === undefined) return null;
        const asked = field(request.body, "status");
        if (typeof asked === "string") found.status = asked;
        return found;
      },
    ),
    route(
      "deleteFollow",
      DELETE,
      "/api/acquisition/followed/{followedId}",
      (request) => {
        const state = mockState();
        state.follows = state.follows.filter(
          (follow) => follow.title !== request.parameters.followedId,
        );
        return { ok: true };
      },
    ),
    route(
      "searchForFollow",
      POST,
      "/api/acquisition/followed/{followedId}/search",
      (request) => {
        const found = followFor(request.parameters.followedId);
        if (found !== undefined) found.searches += 1;
        // Derived from the seeded releases: how many the profile would accept.
        return { found: RELEASES.length };
      },
    ),
    route(
      "grabForFollow",
      POST,
      "/api/acquisition/followed/{followedId}/grab",
      (request) => {
        // THE RELEASE'S NAME, under a field that says so. It answered
        // `infoHash` with this value, and a release name is not a torrent
        // digest — the same class of wrong name as calling a run status a
        // series. The fixture carries no info hash at all, which is what the
        // demand register asks the backend for.
        const asked = text(request.body, "releaseName");
        const taken = RELEASES.find((release) => release.name === asked) ?? RELEASES[0];
        return { releaseName: taken.name };
      },
    ),
    route("searchProviders", GET, "/api/acquisition/search", (request: MockRequest) => {
      const wanted = (request.query.get("query") ?? "").toLowerCase();
      if (wanted === "") return SEARCH_RESULTS;
      const results = SEARCH_RESULTS.results.filter((result) =>
        result.title.toLowerCase().includes(wanted),
      );
      return { ...SEARCH_RESULTS, shown: results.length, results };
    }),
    // The deck PAGES. Answering the first batch to every request made the
    // contract's own `after` parameter unusable and turned a deck that pages
    // into an endless loop of the same thirty cards.
    route("readSuggestions", GET, "/api/acquisition/suggestions", (request) => {
      const after = request.query.get("after") ?? "";
      const from = after === "" ? 0 : SUGGESTIONS.findIndex((one) => one.title === after) + 1;
      return SUGGESTIONS.slice(from, from + BATCH_SIZE);
    }),
    route("readAcquisitionStatus", GET, "/api/acquisition/status", () => ({
      cadence: GRAB_CADENCE,
      nextSearch: null,
    })),
    route("runDetection", POST, "/api/acquisition/detect", () => ({
      detected: TAKEABLE.length + IN_FLIGHT.length,
      available: TAKEABLE.length,
      grabbed: IN_FLIGHT.length,
    })),
    route("readAcquisitionQueue", GET, "/api/acquisition/to-handle", (request) => ({
      takeable: TAKEABLE,
      blocked: BLOCKED,
      inFlight: IN_FLIGHT,
      notFound: request.query.get("scenario") === LOADED ? NOT_FOUND_LOADED : NOT_FOUND,
      doneToday: DONE_TODAY,
    })),
    route("readJourney", GET, "/api/acquisition/journeys/{infoHash}", () => JOURNEY_STAGES),
    route("readReleases", GET, "/api/acquisition/releases", () => RELEASES),
  ];
}
