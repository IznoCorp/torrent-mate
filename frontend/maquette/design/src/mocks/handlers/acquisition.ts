// What is wanted, and what is being fetched.
import BLOCKED from "../seeds/BLOCKED.json";
import CADENCE_CRON from "../seeds/CADENCE_CRON.json";
import DONE_TODAY from "../seeds/DONE_TODAY.json";
import INFLIGHT from "../seeds/INFLIGHT.json";
import NOTFOUND_REAL from "../seeds/NOTFOUND_REAL.json";
import RELEASES from "../seeds/RELEASES.json";
import SEARCH from "../seeds/SEARCH.json";
import SUGGESTIONS from "../seeds/SUGGESTIONS.json";
import TAKEABLE from "../seeds/TAKEABLE.json";
import steps from "../seeds/openJourneySheet-steps.json";
import { DELETE, GET, PATCH, POST, field, route, text } from "./shared";
import { mockState } from "../state";
import type { MockRequest, MockRoute } from "../router";

// How many suggestions one batch of the deck carries. The engine's own batch
// size is `SUG_BATCH`, classified `interface` — the interface owns it.
const BATCH_SIZE = 30;

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
      // Built from the REQUEST over a seeded follow: every field the fixture
      // carries and this request does not is taken from the first follow of
      // the same kind, so nothing here is invented.
      const kind = text(request.body, "kind");
      const like = state.follows.find((follow) => follow.kind === kind) ?? state.follows[0];
      const added = {
        ...like,
        title: text(request.body, "title"),
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
        const asked = text(request.body, "releaseName");
        const taken = RELEASES.find((release) => release.name === asked) ?? RELEASES[0];
        return { infoHash: taken.name };
      },
    ),
    route("searchProviders", GET, "/api/acquisition/search", (request: MockRequest) => {
      const wanted = (request.query.get("query") ?? "").toLowerCase();
      if (wanted === "") return SEARCH;
      const results = SEARCH.results.filter((result) =>
        result.title.toLowerCase().includes(wanted),
      );
      return { ...SEARCH, shown: results.length, results };
    }),
    route("readSuggestions", GET, "/api/acquisition/suggestions", () =>
      SUGGESTIONS.slice(0, BATCH_SIZE),
    ),
    route("readAcquisitionStatus", GET, "/api/acquisition/status", () => ({
      cadence: CADENCE_CRON,
      nextSearch: null,
    })),
    route("runDetection", POST, "/api/acquisition/detect", () => ({
      detected: TAKEABLE.length + INFLIGHT.length,
      available: TAKEABLE.length,
      grabbed: INFLIGHT.length,
    })),
    route("readAcquisitionQueue", GET, "/api/acquisition/to-handle", () => ({
      takeable: TAKEABLE,
      blocked: BLOCKED,
      inFlight: INFLIGHT,
      notFound: NOTFOUND_REAL,
      doneToday: DONE_TODAY,
    })),
    route("readJourney", GET, "/api/acquisition/journeys/{infoHash}", () => steps),
    route("readReleases", GET, "/api/acquisition/releases", () => RELEASES),
  ];
}
