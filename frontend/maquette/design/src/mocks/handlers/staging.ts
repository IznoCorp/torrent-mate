// What has arrived and not yet settled. The pipeline that moves it is its own
// subject, in `./pipeline`.
import DESTINATIONS from "../seeds/staging-destinations.json";
import { DELETE, GET, POST, route, text } from "./shared";
import { mockState } from "../state";
import { refused, type MockRequest, type MockRoute } from "../router";
import { forgetLadder, ladderOf, rungIndex, stripPosition, type Origin, type Position } from "./ladder";
import { accountName } from "../account";
import type { components } from "../../contract/types";

type QueueCard = components["schemas"]["QueueCard"];
type HeldState = ReturnType<typeof mockState>;

// The dense body of data, asked for by name. The engine has always carried two
// and the prototype's own harness switches between them.
const LOADED = "loaded";

// What « continue » was asked to mean. Agreeing with the MACHINE keeps the
// automatic result and re-scrapes nothing; agreeing with a CANDIDATE puts the
// folder back through the pipeline under the name that was picked.
const ACCEPTED_AS_FOUND = "left";

// What the card says once it has moved. These are the engine's own words,
// carried verbatim (D-L08-5) — a layer that invented them would be inventing
// interface copy, and one that decomposed them would forfeit the proof that the
// card renders what it rendered. The demand register asks the backend for the
// FACT behind them.
const LEFT_LABEL = "Laissé tel quel";       // french-ok: a carried fixture value

// THE STRIP'S FOURTH STEP, which is where a folder stands once it has been
// answered: the first three are done and this one is running. « now » is the
// engine's own token for it, carried like every other value on a card.
const RUNNING_NOW = "now";

// The two tones a settled card wears. Neutral for a result that was accepted as
// it stood, informative for one that went back through the pipeline.
const NEUTRAL = "neutral";
const INFORMATIVE = "info";

// Which of the two staging worlds a card came from and goes to. Named because
// the pairing is the decision, not the spelling.
const FROM_REAL = "stuck";
const TO_REAL = "movingReel";
const FROM_DENSE = "stuckLoaded";
const TO_DENSE = "moving";
const FROM_BLOCKED = "blocked";
const SCRAPING_LABEL = "Scraping";          // french-ok: a carried fixture value

// Where an arrival's asking happened: a follow of the account, or a direct add
// in the download client. The contract's own `Requester.via` tokens.
const ASKED_BY_FOLLOW = "follow";
const DIRECT_ADD = "qbittorrent";

// WHERE EACH STAGING LIST STANDS ON THE LADDER. A folder the sort could not
// name rests on « identifié », blocked; a settled one is in the library and
// waits for its Plex check; a moving one says where it is on its strip.
const BLOCKED = "blocked";
const PENDING = "pending";
const RUNNING = "now";
const WAITING = "waiting";
const STUCK_AT: Position = { current: rungIndex("identified"), state: BLOCKED };
const SETTLED_AT: Position = { current: rungIndex("verified"), state: PENDING };
// A settled folder whose Plex match waits for the operator: blocked there.
// Its word says it waits for his answer (ruling 30), never a done-looking rung.
const TO_CONFIRM = "confirmation";
const MATCH_TO_CONFIRM: Position = { current: rungIndex("verified"), state: BLOCKED, reason: TO_CONFIRM };
const settled = (card: QueueCard) => (card.plexMatch === undefined ? SETTLED_AT : MATCH_TO_CONFIRM);
// The pipeline's state while a maintenance run holds the lock, and the reason
// a card moving through it then gives — both the contract's own tokens.
const MAINTENANCE_HOLDS = "queued";

// The staging area's quarantine, the backend's own directory name.
const QUARANTINE_FOLDER = "_quarantine";
const PATH_SEPARATOR = "/";

// A correction of a Plex match, and why one naming no identity is refused.
const CORRECT = "correct";
const WITHOUT_IDENTITY = "a correction carries the identity picked";

// Why a reclassification is refused, in the problem body's own words.
const UNKNOWN_DESTINATION = "not a destination the sort files a non-media folder into";

// The lists a folder can be reclassified out of, which are the lists its two
// siblings walk.
const SOURCE_LISTS = [FROM_REAL, FROM_DENSE, FROM_BLOCKED] as const;

// The two lists a settled folder can be in, one per world.
const SETTLED_REAL = "settled";
const SETTLED_DENSE = "settledLoaded";
const SETTLED_LISTS = [SETTLED_REAL, SETTLED_DENSE] as const;

type TakenOut = { card: QueueCard; list: (typeof SOURCE_LISTS)[number] };

// WHAT A RECLASSIFICATION TOOK OUT, so its inverse can put it back where it
// stood. Keyed by the state object, so a reset of the layer forgets it with
// everything else rather than restoring a card into a world that never lost it.
const takenOutIn = new WeakMap<HeldState, Map<string, TakenOut>>();

/**
 * The reclassifications held for one state of the layer.
 *
 * @param state The layer's state.
 * @returns The folders taken out, by title.
 */
function takenOut(state: HeldState): Map<string, TakenOut> {
  let held = takenOutIn.get(state);
  if (held === undefined) {
    held = new Map();
    takenOutIn.set(state, held);
  }
  return held;
}

/**
 * Whether two records name the same medium.
 *
 * BY PROVIDER IDENTITY, NEVER BY TITLE: a settled folder carries its year
 * (« Star Trek: Strange New Worlds (2022) ») and the follow does not.
 *
 * @param card The arrival.
 * @param ids The follow's identity.
 * @returns True when one provider identifier is shared.
 */
function sameMedium(card: QueueCard, ids: Record<string, unknown> | null | undefined): boolean {
  const own = card.ids as Record<string, unknown> | null;
  if (own == null || ids == null) return false;
  // A seed spells one identifier as a number and another as a string.
  return Object.entries(ids).some(([provider, value]) => value != null
    && own[provider] != null && String(own[provider]) === String(value));
}

/**
 * Who asked for a card's medium, and what of its ladder its own row lived.
 *
 * THREE ORIGINS, each read off the rows the layer holds, never invented: a
 * follow of the account asked for it, on the follow's own date; it was added
 * directly in the download client (ruling 9); or it was DROPPED BY HAND in the
 * staging area, in which case nobody asked, nothing was searched, taken or
 * downloaded, and its ladder starts at « arrivé ».
 *
 * @param card The card.
 * @param direct Whether a card no follow asked for was added in the download
 *     client — true of an arrival, unknown for a row of the queue.
 * @returns Its requester, when it has one, and what its row lived.
 */
export function originOf(card: QueueCard, direct: boolean): { requester?: QueueCard["requester"]; origin: Origin } {
  if (card.droppedByHand) return { origin: { from: "arrived" } };
  const follow = mockState().follows.find((one) => sameMedium(card, one.ids));
  if (follow !== undefined) {
    return { requester: { name: accountName(), via: ASKED_BY_FOLLOW }, origin: { asked: follow.since } };
  }
  return direct ? { requester: { name: accountName(), via: DIRECT_ADD }, origin: {} } : { origin: {} };
}

/**
 * Where a moving folder stands: on its strip — and, while a maintenance run
 * holds the lock, WAITING there rather than in motion (DOIT-4: « en file »,
 * never « occupé »).
 *
 * @param card The folder's card, its strip included.
 * @returns Its position.
 */
function moving(card: QueueCard): Position | undefined {
  const position = stripPosition(card.strip);
  if (position === undefined || position.state !== RUNNING) return position;
  if (mockState().pipelineState !== MAINTENANCE_HOLDS) return position;
  return { ...position, state: WAITING, reason: MAINTENANCE_HOLDS };
}

/**
 * EVERY ARRIVAL, AS AN ACQUISITION CARD (ruling 2): what the staging area holds
 * in the scenario's world, each carrying who asked for it. The account is the
 * mock's single one, which owns the Plex server by construction (§17); an
 * arrival no follow of it asked for was added directly in the download client.
 *
 * COMPOSED, NEVER STORED: a folder that leaves the staging area — continued,
 * discarded, reclassified — leaves the arrivals with it, because there is only
 * the one list.
 *
 * @param dense Whether the dense world is asked for.
 * @returns The arrival cards.
 */
export function arrivalsOf(dense: boolean): QueueCard[] {
  const state = mockState();
  const lists: [QueueCard[], (card: QueueCard) => Position | undefined][] = dense
    ? [[state.stuckLoaded, () => STUCK_AT], [state.moving, moving], [state.settledLoaded, settled]]
    : [[state.stuck, () => STUCK_AT], [state.movingReel, moving], [state.settled, settled]];
  // A TUNNEL ERROR IS A STEP NO PICK UNBLOCKS: a row a pending decision names
  // is resolved by that decision, whatever step it stopped at.
  const namedByDecision = new Set(state.pendingDecisions.map((decision) => decision.folder));
  const inStaging = lists.flatMap(([cards, at]) => cards.map(({ strip, failedStep, ...stopped }) => {
    const card = failedStep === undefined || namedByDecision.has(stopped.title) ? stopped : { ...stopped, failedStep };
    const position = at({ ...card, strip });
    const { requester, origin } = originOf(card, true);
    const asked = requester === undefined ? card : { ...card, requester };
    return position === undefined ? asked : { ...asked, ladder: ladderOf(card.title, position, origin) };
  }));
  return inStaging;
}

/** Every route this subject answers. */
export function stagingRoutes(): MockRoute[] {
  return [
    route("readStaging", GET, "/api/staging/media", (request: MockRequest) => {
      const state = mockState();
      // THE SCENARIO PICKS THE WORLD, and the pairing is the engine's own
      // `derived`. Under the DENSE one the queue is what a busy morning looks
      // like; under the REAL one it is what the operator's own run recorded —
      // and what has MOVED starts empty there, because nothing has moved yet.
      // Answering the dense lists under the real scenario would put cards on
      // screen that no run produced.
      if (request.query.get("scenario") === LOADED) {
        return {
          stuck: state.stuckLoaded,
          moving: state.moving,
          settled: state.settledLoaded,
        };
      }
      return { stuck: state.stuck, moving: state.movingReel, settled: state.settled };
    }),
    route(
      "continueStagedMedia",
      POST,
      "/api/staging/media/{mediaId}/continue",
      (request) => {
        const state = mockState();
        // FROM WHEREVER IT IS QUEUED, and the list it leaves decides the list
        // it joins. The engine's `leaveQueue` walked the real stuck list, the
        // dense one and the blocked one in that order; a card released from the
        // real world moves within the real world, and one released from the
        // dense world moves within it. Mixing them put a card in a queue no
        // scenario would ever show it in.
        const asked = request.parameters.mediaId;
        const lists = [
          { from: FROM_REAL, to: TO_REAL },
          { from: FROM_DENSE, to: TO_DENSE },
          { from: FROM_BLOCKED, to: TO_DENSE },
        ] as const;
        for (const { from, to } of lists) {
          const found = state[from].find((card) => card.title === asked);
          if (found === undefined) continue;
          state[from] = state[from].filter((card) => card !== found);
          // WHAT THE CARD SAYS AFTERWARDS is the engine's own: agreeing with a
          // candidate puts it back in the pipeline and says « Scraping »;
          // agreeing with the machine keeps the automatic result and says it
          // was left as it stood. The strip is the same in both — the folder
          // has passed the first three steps and is at the fourth.
          const settled = text(request.body, "outcome") === ACCEPTED_AS_FOUND;
          const named = text(request.body, "choice");
          state[to] = [
            {
              ...found,
              title: named === "" ? found.title : named,
              strip: [1, 1, 1, RUNNING_NOW, 0],
              chip: settled
                ? { tone: NEUTRAL, text: LEFT_LABEL }
                : { tone: INFORMATIVE, text: SCRAPING_LABEL },
            },
            ...state[to],
          ];
          return { ok: true };
        }
        return { ok: false };
      },
    ),
    route(
      "discardStagedMedia",
      POST,
      "/api/staging/media/{mediaId}/discard",
      (request) => {
        // THE SAME THREE LISTS ITS SIBLING WALKS. This filtered `stuck` alone,
        // so a card served from the DENSE world — or from « ça bloque » — was
        // asked to be discarded, nothing was removed, `{ok: false}` came back
        // and the card stayed on screen. The list a card is IN is a fact about
        // the scenario in force, never about the operation being asked for.
        const state = mockState();
        const asked = request.parameters.mediaId;
        // QUARANTINED, NOT DELETED: the answer says where the folder went, the
        // way the backend composes it — the staging area's quarantine, then the
        // folder's own name — and that the move was journaled.
        const quarantinePath = [QUARANTINE_FOLDER, asked].join(PATH_SEPARATOR);
        for (const list of [FROM_REAL, FROM_DENSE, FROM_BLOCKED] as const) {
          const before = state[list].length;
          state[list] = state[list].filter((card) => card.title !== asked);
          if (state[list].length !== before) return { ok: true, journaled: true, quarantine_path: quarantinePath };
        }
        return { ok: false, journaled: false, quarantine_path: quarantinePath };
      },
    ),
    route("readStagingDestinations", GET, "/api/staging/destinations", () => DESTINATIONS),
    route(
      "resolvePlexMatch",
      POST,
      "/api/acquisition/journeys/{infoHash}/plex-match",
      (request) => {
        // THE ANSWER MOVES THE CARD: confirmed or corrected, the match no
        // longer waits for the operator, so the card leaves « À traiter » and
        // its ladder is laid again from where it now stands.
        const state = mockState();
        const asked = request.parameters.infoHash;
        const outcome = text(request.body, "outcome");
        // A CORRECTION NAMES THE RIGHT IDENTITY, or it corrects nothing.
        const identity = (request.body as { identity?: { title?: unknown } } | undefined)?.identity;
        if (outcome === CORRECT && (typeof identity?.title !== "string" || identity.title === "")) {
          return refused(400, WITHOUT_IDENTITY);
        }
        for (const list of SETTLED_LISTS) {
          const found = state[list].find((card) => card.title === asked && card.plexMatch !== undefined);
          if (found === undefined) continue;
          const { plexMatch, ...answered } = found;
          state[list] = state[list].map((card) => (card === found ? answered : card));
          forgetLadder(asked);
          return { ok: plexMatch !== undefined, outcome };
        }
        return { ok: false, outcome };
      },
    ),
    route(
      "reclassifyStagedMedia",
      POST,
      "/api/staging/media/{mediaId}/reclassify",
      (request) => {
        // « CE N'EST PAS UN MÉDIA »: the folder leaves the staging area — and
        // so the arrivals — for a destination the configuration declares.
        const state = mockState();
        const asked = request.parameters.mediaId;
        const destination = text(request.body, "destination");
        if (!DESTINATIONS.some((known) => known.name === destination)) {
          return refused(400, UNKNOWN_DESTINATION);
        }
        for (const list of SOURCE_LISTS) {
          const found = state[list].find((card) => card.title === asked);
          if (found === undefined) continue;
          state[list] = state[list].filter((card) => card !== found);
          takenOut(state).set(asked, { card: found, list });
          return { ok: true, destination };
        }
        return { ok: false, destination };
      },
    ),
    route(
      "restoreReclassifiedMedia",
      DELETE,
      "/api/staging/media/{mediaId}/reclassify",
      (request) => {
        // THE INVERSE: the folder goes back to the list it was taken from.
        const state = mockState();
        const asked = request.parameters.mediaId;
        const taken = takenOut(state).get(asked);
        if (taken === undefined) return { ok: false };
        takenOut(state).delete(asked);
        state[taken.list] = [taken.card, ...state[taken.list]];
        return { ok: true };
      },
    ),
  ];
}
