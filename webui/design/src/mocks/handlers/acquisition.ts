// What is wanted, and what is being fetched.
import GRAB_CADENCE from "../seeds/grab-cadence.json";
import { releasesFor, releasesOfEvery } from "./releases-of";
import { knownMedium } from "./media";
import { sameItem } from "./same-item";
import { acquisitionKey } from "../../lib/arrival-slots";
import SEARCH_RESULTS from "../seeds/search-results.json";
import SUGGESTIONS from "../seeds/suggestions.json";
import { DELETE, GET, PATCH, POST, field, route, text } from "./shared";
import { launchDetection } from "./pipeline";
import { arrivalsOf, originOf } from "./staging";
import { isVerifiedInPlex, forgetLadder, ladderOf, rungIndex, stripPosition, ownTimeOf, type Position } from "./ladder";
import type { components } from "../../contract/types";
import { stagesOf } from "./acquisition-verbs";
import { withAcquisitionFacts, withRequesters } from "./requesters";
import { recoveringSeason } from "./season-recovery";
import { mockState } from "../state";
import { newFollow } from "./new-follow";
import { claimRequest, releaseRequest, requestersOf, signedInId, signedInRights } from "../identity";
import { followForKey, mediumOfKey, removedIndexForKey } from "../follow-key";
import { refused, type MockRequest, type MockRoute } from "../router";

// How many suggestions one batch of the deck carries. The engine's own batch
// size is `SUG_BATCH`, classified `interface` — the interface owns it.
// What the card says once it has been restarted. The engine's own words,
// carried verbatim (D-L08-5).
const STARTED_LABEL = "Récupération lancée";  // french-ok: a carried fixture value

// The strip's FIRST step, which is where a restarted item stands, and the tone
// a card in motion wears. The engine's own tokens, carried like every other
// value on a card.
const RUNNING_NOW = "now";
const INFORMATIVE = "info";

const BATCH_SIZE = 30;

// What the queued search's uid starts with: the layer holds no runner, so it names the run itself.
const SEARCH_RUN_PREFIX = "search-run-";
// The status read a queued search is settled at: the one before it reads the run « running ».
const SETTLED_AT_READ = 2;
// THE CURSOR THE DECK ISSUES (K3-G13). Opaque to the interface, which sends it back as it came;
// here it says where the next page starts.
const CURSOR_PREFIX = "deck-";
// AND THE ONES IT ISSUES ARE THE ONLY ONES IT READS, as a server does: one before each page past
// the first, by where that page starts.
const ISSUED_CURSORS = new Map<string, number>(
  Array.from({ length: Math.ceil(SUGGESTIONS.length / BATCH_SIZE) - 1 }, (_, page) => {
    const from = (page + 1) * BATCH_SIZE;
    return [`${CURSOR_PREFIX}${from}`, from];
  }),
);

// A search page's bounds (K3-G14), the contract's own.
const SEARCH_LIMIT = 20;
const SEARCH_MAX_LIMIT = 100;
const WHOLE_NUMBER = /^\d+$/;

// WHERE A FAMILY STANDS ON THE LADDER when its cards carry no strip: a release
// found and waiting to be taken.
const WAITING = "waiting";
const TAKEABLE_AT: Position = { current: rungIndex("grabbed"), state: WAITING };

/**
 * A family's cards, each on its ladder.
 *
 * THE LADDER REPLACES THE STRIP on an acquisition card: the card answers the
 * same list `readJourney` answers for its medium, and the five positions it was
 * seeded with say only where that ladder stands.
 *
 * @param cards The family's cards.
 * @param at Where the family stands, for cards that carry no strip.
 * @returns The cards, each with its ladder and without its strip.
 */
function onTheLadder(cards: components["schemas"]["QueueCard"][], at?: Position) {
  return cards.map(({ strip, ...card }) => {
    const position = stripPosition(strip) ?? at;
    // WHO ASKED, derived from the follow when one did: a row of the queue no
    // follow names carries none, and the card says its origin is unknown.
    const { requester, origin } = originOf(card, false);
    const asked = requester === undefined ? card : { ...card, requester };
    return position === undefined ? asked
      : { ...asked, ladder: ladderOf(acquisitionKey(card), position, { ...origin, times: ownTimeOf(card) }) };
  });
}

// The dense body of data, asked for by name.
const LOADED = "loaded";

const FILM_KIND = "movie"; // A follow of this kind ends alone once confirmed in Plex.

// The statuses of a follow still waiting on a grab, and the one a running grab moves it to.
const WAITING_ON_A_GRAB = new Set(["pending", "to_grab"]);
const BEING_ACQUIRED = "acquiring";

/**
 * Finds one follow by the key the address carries (K3-G1).
 *
 * THE KEY IS THE MEDIUM'S IDENTITY, `<provider>:<providerId>`, read as a server
 * reads it: from the records the layer holds, never from a title.
 *
 * @param key What the address named.
 * @returns The follow, or undefined.
 */
function followFor(key: string) {
  return followForKey(key);
}


/**
 * The entry a follow is created from, by title: a search result or a suggestion.
 *
 * The follow verb is emitted on those two surfaces and on the media sheet they
 * open, and both entries carry their medium's joined identity and poster.
 *
 * @param title The medium's title.
 * @returns The entry, or undefined when neither holds it.
 */
function followedFrom(title: string) {
  return SEARCH_RESULTS.results.find((result) => result.title === title)
    ?? SUGGESTIONS.find((suggestion) => suggestion.title === title);
}

// What an address that names no follow is answered with (the contract's 404).
const NO_FOLLOW = "no follow answers to that key";
const NOT_FOUND = 404;
const FORBIDDEN = 403;

// The statuses `updateFollow` accepts — the contract's own enum.
const WRITABLE_STATUSES = new Set(["disabled", "pending", "up_to_date"]);

// Why a co-requester's generic pause is refused.
const SHARED_PAUSE = "other accounts asked for this follow too: each pauses it for itself";

/**
 * Whether the caller shares a follow with other requesters and does not pilot
 * every acquisition — the one who may not act on the whole of it.
 *
 * @param title The follow.
 * @returns True for a co-requester.
 */
function sharedWithOthers(title: string): boolean {
  if (signedInRights().holds("acquisition.pilot.any")) return false;
  return requestersOf(title).some((one) => one.id !== signedInId());
}

// Why a follow nothing identifies is refused, in the problem body's own words.
const NO_IDENTITY = "a follow with no provider identity has no sheet";

/**
 * One page of a search's results, as `limit` and `offset` ask for it (K3-G14).
 *
 * @param request The search asked.
 * @param total How many the provider has.
 * @param results Every result the search found, best first.
 * @returns The page under that total, or a refusal when it is outside the contract's bounds.
 */
function searchPage(request: MockRequest, total: number, results: typeof SEARCH_RESULTS.results) {
  const asked = (name: string, absent: number) => {
    const value = request.query.get(name);
    if (value === null) return absent;
    return WHOLE_NUMBER.test(value) ? Number(value) : Number.NaN;
  };
  const limit = asked("limit", SEARCH_LIMIT);
  const offset = asked("offset", 0);
  if (!(limit >= 1 && limit <= SEARCH_MAX_LIMIT && offset >= 0)) {
    return refused(400, "a page is 1 to 100 results from an offset of 0 or more", "request.invalid");
  }
  const page = results.slice(offset, offset + limit);
  return { ...SEARCH_RESULTS, total, shown: page.length, results: page };
}

/**
 * Where an asked search's run stands, moved on by being read: running first, then settled.
 *
 * @param runUid The uid asked about, if any.
 * @returns Its state, or null when no uid is asked about or the layer named no run by it.
 */
function searchRunState(runUid: string | null): "running" | "settled" | null {
  const runs = mockState().searchRuns;
  if (runUid === null || !(runUid in runs)) return null;
  runs[runUid] += 1;
  return runs[runUid] < SETTLED_AT_READ ? "running" : "settled";
}

/** Every route this subject answers. */
export function acquisitionRoutes(): MockRoute[] {
  return [
    // A FILM'S FOLLOW ENDS ALONE once its last rung, « vérifié dans Plex », is done (ruling 3); a series' never
    // does. The engine deletes it at DETECTION today, earlier: a demand owed (DESIGN § 6.2).
    // A FOLLOW WHOSE WHOLE SEASON IS ON ITS WAY IS BEING ACQUIRED, as the engine
    // says of a follow with a grab running: never « en attente de torrent »
    // beside the season's pack downloading. IN THE WORLD ASKED, as the queue
    // is: a recovery the dense world holds runs nowhere in the real one.
    route("readFollows", GET, "/acquisition/followed", (request) => {
      const dense = request.query.get("scenario") === LOADED;
      return withAcquisitionFacts(mockState().follows
        .filter((follow) => follow.kind !== FILM_KIND || !isVerifiedInPlex(follow.title))
        .map((follow) => (WAITING_ON_A_GRAB.has(follow.status) && recoveringSeason(follow.title, dense)
          ? { ...follow, status: BEING_ACQUIRED } : follow)));
    }),
    route("createFollow", POST, "/acquisition/followed", (request) => {
      const state = mockState();
      // BUILT FROM ITS OWN REQUEST, and from nothing else. An earlier version
      // spread the first seeded follow of the same kind and overrode three
      // fields, so a new title inherited a stranger's year, a stranger's date
      // and a stranger's run status. A value taken from the wrong record is
      // worse than an invented one: it typechecks, and it reads as real.
      const year = Number(field(request.body, "year"));
      const title = text(request.body, "title");
      const provider = field(request.body, "provider");
      const providerId = field(request.body, "providerId");
      const source = followedFrom(title);
      // A MEDIUM ANOTHER ACCOUNT ALREADY FOLLOWS is joined, never duplicated:
      // the caller becomes one more of its requesters (round 9 Q16).
      const followed = state.follows.find((follow) => follow.title === title);
      if (followed !== undefined) {
        claimRequest(title, true);
        return withAcquisitionFacts([followed])[0];
      }
      // THE MEDIUM'S IDENTITY: the request's own AND the joined identity of the
      // entry it was followed from, MERGED. A create naming neither is REFUSED
      // (B-366): a follow with no identity has no sheet to open, and a follow
      // without a sheet is not a state this interface has. The layer invents
      // none and records none.
      //
      // MERGED RATHER THAN CHOSEN BETWEEN, and the difference is a whole
      // identity against a third of one. The contract's create body carries ONE
      // provider pair — the interface sends the first identifier that is a
      // number — while the entry it was followed from carries all three, so a
      // layer that PREFERRED the request recorded `{tmdb}` where the interface's
      // own copy held `{tmdb, imdb, tvdb}`: two ends disagreeing about one
      // medium, and the cross-provider reach of the follow lost on the way in.
      // The request wins on a key both name, because it is the more recent
      // statement about the same medium.
      const asked = typeof provider === "string" && typeof providerId === "number"
        ? { [provider]: providerId }
        : {};
      // The cast reaches the seed's own optional fields, never a null: the line
      // below is what refuses that.
      // AND WHAT THE IDENTITY NAMES, wherever the act was taken (B-673): the
      // title join reaches the search results and the deck alone, so a medium
      // followed from « Incomplets » or a library sheet is found by identity.
      const known = knownMedium({ ...(source?.ids ?? {}), ...asked });
      const together = { ...(known?.ids ?? {}), ...(source?.ids ?? {}), ...asked };
      const identity = (Object.keys(together).length > 0
        ? together
        : null) as (typeof state.follows)[number]["ids"] | null;
      if (identity === null) return refused(400, NO_IDENTITY);
      const added = newFollow(title, text(request.body, "kind"),
                              Number.isFinite(year) ? year : source?.year ?? known?.year ?? year,
                              identity, source?.poster ?? known?.poster ?? null);
      state.follows = [added, ...state.follows];
      claimRequest(title, false);
      return withAcquisitionFacts([added])[0];
    }),
    route(
      "updateFollow",
      PATCH,
      "/acquisition/followed/{followedId}",
      (request) => {
        const found = followFor(request.parameters.followedId);
        if (found === undefined) return refused(NOT_FOUND, NO_FOLLOW, "acquisition.not_found");
        // THE GENERIC PAUSE IS THE WHOLE FOLLOW'S: a co-requester pauses for
        // itself (`setAcquisitionPause`), never for the others (round 10 Q6).
        // The code is the contract's (K3-G11), which the interface words.
        if (sharedWithOthers(found.title)) return refused(FORBIDDEN, SHARED_PAUSE, "acquisition.follow_shared");
        const asked = field(request.body, "status");
        // THE BODY'S STATUS IS THE CONTRACT'S ENUM, never a free string (K3-G10).
        if (typeof asked !== "string" || !WRITABLE_STATUSES.has(asked)) {
          return refused(400, "status is one of disabled, pending, up_to_date", "request.invalid");
        }
        found.status = asked as typeof found.status;
        return found;
      },
    ),
    // THE REMOVAL IS SOFT, and that is not a mock's convenience — it is what
    // makes the undo possible at all. Dropping the record left one road back,
    // a create, and a create carries a title and a kind: the year, « suivi
    // depuis » and the search count were lost every time (B-353). What is
    // taken out of the listing waits here, whole.
    route(
      "deleteFollow",
      DELETE,
      "/acquisition/followed/{followedId}",
      (request) => {
        const state = mockState();
        const standing = followFor(request.parameters.followedId);
        if (standing === undefined) return refused(NOT_FOUND, NO_FOLLOW, "acquisition.not_found");
        const title = standing.title;
        // A FOLLOW OTHERS ASKED FOR TOO STAYS FOR THEM: the caller alone
        // leaves its requesters; it goes with its last one (round 9 Q16).
        if (requestersOf(title).length > 1
          && requestersOf(title).some((one) => one.id === signedInId())) {
          releaseRequest(title);
          return { ok: true };
        }
        const removed = state.follows.filter((follow) => follow === standing);
        state.follows = state.follows.filter((follow) => follow !== standing);
        // NEWEST FIRST, so a title removed twice restores the record that left
        // last. Anything else would put back a version the operator has not
        // seen since before the one they just removed.
        state.removedFollows = [...removed, ...state.removedFollows];
        return { ok: true };
      },
    ),
    // AND PUTTING ONE BACK IS ITS OWN OPERATION, never a create. It answers
    // the record as it WAS: same year, same date, same count of searches.
    route(
      "restoreFollow",
      POST,
      "/acquisition/followed/{followedId}/restore",
      (request) => {
        const state = mockState();
        // A FOLLOW THE CALLER ONLY LEFT is still there: putting it back makes
        // the caller one of its requesters again.
        const standing = followFor(request.parameters.followedId);
        if (standing !== undefined) {
          claimRequest(standing.title, true);
          return withAcquisitionFacts([standing])[0];
        }
        const at = removedIndexForKey(request.parameters.followedId);
        // NOTHING RESTORABLE UNDER THAT KEY. Answering a made-up record here
        // would be the same lie the create told, arrived at from the layer's
        // side; the contract declares a 404 for it.
        if (at === -1) return refused(NOT_FOUND, "nothing removed under that key is still restorable", "follow.not_restorable");
        const [restored] = state.removedFollows.splice(at, 1);
        state.follows = [restored, ...state.follows];
        return restored;
      },
    ),
    route(
      "searchForFollow",
      POST,
      "/acquisition/followed/{followedId}/search",
      (request) => {
        const found = followFor(request.parameters.followedId);
        if (found === undefined) return refused(NOT_FOUND, NO_FOLLOW, "acquisition.not_found");
        // QUEUED, LIKE THE GRAB (operator ruling O-6 B): the answer says « en file »
        // and carries no result. What the search leaves is read afterwards, once
        // `readAcquisitionStatus` answers its run settled. THE LAYER HOLDS NO
        // RUNNER, so the follow counts the search as soon as it is asked.
        found.searches += 1;
        const runs = mockState().searchRuns;
        const runUid = SEARCH_RUN_PREFIX + String(Object.keys(runs).length + 1);
        runs[runUid] = 0;
        return { queued: true, runUid };
      },
    ),
    route(
      "grabForFollow",
      POST,
      "/acquisition/followed/{followedId}/grab",
      (request) => {
        // THE FOLLOW'S CLAIM, launched: what its last search found and marked
        // takeable leaves the queue and is in flight. The backend answers the
        // run it spawned; the layer holds no runner, and answers none.
        const state = mockState();
        // THE MEDIUM THE KEY NAMES, followed or not: what waits to be taken is a release a
        // search found, and a takeable card is claimed whether or not a follow asked for it.
        const medium = mediumOfKey(request.parameters.followedId);
        if (medium === null) return refused(NOT_FOUND, NO_FOLLOW, "acquisition.not_found");
        const asked = medium.title;
        // THE RELEASE THE PICKER CHOSE is named by its handle (K3-G5); one the
        // layer does not hold is refused, never taken for another.
        const chosen = field(request.body, "releaseId");
        if (typeof chosen === "string" && !releasesFor(asked).some((release) => release.id === chosen)) {
          return refused(400, "no release answers to that id", "request.invalid");
        }
        const found = state.takeable.find((card) => card.title === asked);
        if (found !== undefined) {
          state.takeable = state.takeable.filter((card) => card !== found);
          forgetLadder(asked);
          state.inFlight = [
            {
              ...found,
              strip: [RUNNING_NOW, 0, 0, 0, 0],
              chip: { tone: INFORMATIVE, text: STARTED_LABEL },
            },
            ...state.inFlight,
          ];
        }
        return { runUid: null };
      },
    ),
    route("searchProviders", GET, "/acquisition/search", (request: MockRequest) => {
      const wanted = (request.query.get("query") ?? "").toLowerCase();
      if (wanted === "") return searchPage(request, SEARCH_RESULTS.total, SEARCH_RESULTS.results);
      // MATCHED ON WORDS, NOT ON THE WHOLE STRING, and a provider is what this
      // stands in for. The interface pre-fills this field with a staging
      // FOLDER's name — « Backrooms 2026 » — and a provider asked that returns
      // Backrooms; a substring match returns nothing, because the title is
      // « Backrooms » and the year is not in it. Measured: the identify screen
      // drew no candidate at all, on the one surface whose job is to offer them
      // (DOIT-7 — never a dead end).
      const words = wanted.split(/\s+/).filter((word) => word !== "");
      const results = SEARCH_RESULTS.results.filter((result) => {
        const title = result.title.toLowerCase();
        return words.some((word) => title.includes(word));
      });
      // AND THE COUNTS ARE THE ANSWER'S, both of them. `total` was spread
      // through untouched, so a search matching nothing drew « 0 résultat
      // affiché sur 257 trouvés » — a screen saying « nothing » while claiming
      // 257, which is the very defect the library listing was repaired for two
      // files away (« answering 1 861 over a search for two rows made the count
      // describe the library rather than the answer »).
      return searchPage(request, results.length, results);
    }),
    // ONE MEDIUM BY ITS IDENTIFIER (B-691): the result a source knows under the
    // identifier asked, and nothing else — no title matching, no neighbour.
    route("searchProviderById", GET, "/acquisition/search/by-id", (request: MockRequest) => {
      const source = request.query.get("provider") ?? "";
      const id = (request.query.get("id") ?? "").trim();
      const results = SEARCH_RESULTS.results.filter(
        (result) => id !== "" && String((result.ids as Record<string, unknown> | undefined)?.[source] ?? "") === id,
      );
      return { ...SEARCH_RESULTS, total: results.length, shown: results.length, results };
    }),
    // The deck PAGES, by the cursor it issued with the page before (K3-G13). Answering the
    // first batch to every request turns a deck that pages into an endless loop of the same
    // thirty cards.
    route("readSuggestions", GET, "/acquisition/suggestions", (request) => {
      const cursor = request.query.get("cursor");
      const from = cursor === null ? 0 : ISSUED_CURSORS.get(cursor);
      if (from === undefined) return refused(400, "the deck gave no such cursor", "request.invalid");
      const to = from + BATCH_SIZE;
      return {
        suggestions: SUGGESTIONS.slice(from, to),
        nextCursor: to < SUGGESTIONS.length ? `${CURSOR_PREFIX}${to}` : null,
      };
    }),
    route("readAcquisitionStatus", GET, "/acquisition/status", (request) => ({
      cadence: GRAB_CADENCE,
      nextSearch: null,
      runState: searchRunState(request.query.get("runUid")),
    })),
    // THE VEILLE IS A RUN, and the 202 names it. Its figures are read from the
    // run once it has ended — an answer carrying them at once would be a lie
    // about a run that takes minutes, with no « en cours » left to draw.
    route("runDetection", POST, "/acquisition/detect", launchDetection),
    route("readAcquisitionQueue", GET, "/acquisition/to-handle", (request) => {
      const state = mockState();
      // THE SCENARIO PICKS THE WORLD, exactly as the engine's `derived` does.
      // It used to pick the EMPTIES too — under the real scenario nothing was
      // takeable and nothing blocked, on the reasoning that a run found what it
      // found and a dense queue there would show cards no run produced.
      //
      // THE OPERATOR OVERRULED THAT, and the ruling is his rather than a
      // wave's: « the data the design host serves AT REST holds at least one
      // subject in every state every surface can draw ». At rest, on his phone,
      // IS this branch — the dial sits here unless something moves it — so a
      // state served only under `loaded` is a state he cannot try at all. He
      // found that out through « Récupérer maintenant »: the verb was repaired,
      // measured and green, and unreachable to his hand because no arrival was
      // takeable here.
      //
      // WHAT DID NOT CHANGE is D7: these are the shapes the running backend
      // answers, seeded from it and not invented. What changed is which of them
      // this branch admits to holding. The in-flight list keeps its real-world
      // counterpart, because those ARE a mutation's
      // record — « nothing has moved yet » is true of a run just read off the
      // disk, and filling them would claim movements that never happened.
      // ONE ITEM, ONE CARD: a follow's folder in the staging area JOINS the
      // follow's card in flight — the arrivals are composed FIRST, so the item's
      // ladder is laid where the staging area has it, and the flight drops it.
      const dense = request.query.get("scenario") === LOADED;
      const arrivals = arrivalsOf(dense);
      const inFlight = (dense ? state.inFlight : state.inFlightReel)
        .filter((card) => !arrivals.some((arrival) => sameItem(arrival, card)));
      return {
        takeable: withRequesters(onTheLadder(state.takeable, TAKEABLE_AT)),
        blocked: withRequesters(onTheLadder(state.blocked)),
        inFlight: withRequesters(onTheLadder(inFlight)),
        arrivals: withRequesters(arrivals),
      };
    }),
    // THE STAGES THE VERBS MOVE, not the seed itself. This answered the
    // imported list to every journey ever asked for, which was enough while the
    // sheet only displayed them; « Remettre en file » and « Re-scraper » are
    // proved by the stages MOVING, and a shared constant moves for nobody — it
    // would also have been mutated in place for every other medium at once.
    route("readJourney", GET, "/acquisition/journeys/{infoHash}",
          (request) => stagesOf(request.parameters.infoHash)),
    // THE RELEASES OF THE MEDIUM ASKED FOR, by its key (K3-G5). The contract
    // declares `followedId`, `season` and `episode`; this answered the same eight
    // releases to every question, so the picker opened on « Ted Lasso » and then
    // on « Silo » showed one list — and the second came from the cache without a
    // request, because the query key carried no medium either. A release list
    // that does not depend on what it is a list OF is not a list.
    //
    // WITHOUT A KEY, EVERY ITEM'S CANDIDATES: what the quality profile counts against.
    route("readReleases", GET, "/acquisition/releases", (request) => {
      const key = request.query.get("followedId") ?? "";
      const season = request.query.get("season") ?? "";
      const episode = request.query.get("episode") ?? "";
      const medium = key === "" ? null : mediumOfKey(key);
      // A KEY NOTHING KNOWN ANSWERS TO HAS NO RELEASES, never every one.
      if (key !== "" && medium === null) return [];
      const listed = medium === null ? releasesOfEvery() : releasesFor(medium.title);
      // THE SEASON AND THE EPISODE ARE FIELDS OF THE RELEASE (SR6), read from
      // its own record. A release that says neither is a whole-series pack and
      // answers to any ask, as one no name numbers does.
      return listed.filter((release) => {
        if (season !== "" && release.season !== null && release.season !== Number(season)) return false;
        if (episode !== "" && release.episode !== null && release.episode !== Number(episode)) return false;
        return true;
      });
    }),
  ];
}
