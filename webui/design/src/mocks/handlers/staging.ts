// What has arrived and not yet settled. The pipeline that moves it is its own
// subject, in `./pipeline`.
import DESTINATIONS from "../seeds/staging-destinations.json";
import { DELETE, GET, POST, route, text } from "./shared";
import { mockState } from "../state";
import { FROM_BLOCKED, SOURCE_LISTS, arrivedOnly, copiesOf, takeOutOfStaging } from "./staged-folders";
import { scenario } from "../scenario";
import { refused, type MockRequest, type MockRoute } from "../router";
import { confirmInPlex, forgetLadder, ladderOf, rungIndex, stripPosition, ownTimeOf, type Origin, type Position } from "./ladder";
import { accountName } from "../account";
import { backToSearch } from "./follow-errors";
import { continueMedia } from "./continued";
import { acquisitionKey } from "../../lib/arrival-slots";
import type { components } from "../../contract/types";

type QueueCard = components["schemas"]["QueueCard"];
type HeldState = ReturnType<typeof mockState>;

// The dense body of data, asked for by name. The engine has always carried two
// and the prototype's own harness switches between them.
const LOADED = "loaded";

// What « continue » was asked to mean. Agreeing with a CANDIDATE puts the
// folder back through the pipeline under the name that was picked; LEAVING it as
// it is means LATER (ruling 6): the folder stays where it is queued, set aside.
const LEFT_AS_IT_IS = "left";

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
// The rung state of a folder the operator set aside: the contract's own token.
const ASIDE = "aside";
const settled = (card: QueueCard) => (disagrees(card) ? MATCH_TO_CONFIRM : SETTLED_AT);

/**
 * Whether Plex's match disagrees with the identity held — the only match that
 * waits for the operator (RULINGS 24). An agreeing match is no question.
 *
 * @param card The settled folder.
 * @returns True when a match is carried and names another identity.
 */
function disagrees(card: QueueCard): boolean {
  const match = card.plexMatch;
  if (match === undefined) return false;
  const held = (card.ids ?? {}) as Record<string, unknown>;
  const matched = (match.ids ?? {}) as Record<string, unknown>;
  return Object.keys(matched).some((provider) => String(matched[provider]) !== String(held[provider]));
}

/**
 * A settled folder as it is served: its Plex match only when that match is a question.
 *
 * @param card The settled folder.
 * @returns The folder, without an agreeing match.
 */
function served(card: QueueCard): QueueCard {
  if (card.plexMatch === undefined || disagrees(card)) return card;
  const { plexMatch, ...agreed } = card;
  return plexMatch === undefined ? card : agreed;
}
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
  return direct ? { requester: { name: accountName(), via: DIRECT_ADD }, origin: { direct: true } } : { origin: {} };
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
 * Poses a DISAGREEING Plex match on a settled folder, until the layer is next
 * reset — a derivation, shown as one (RULINGS 24): no seeded row carries a
 * disagreement; the backend compares Plex's real match with the identity held.
 *
 * @param title The settled folder.
 * @param match The identity Plex is posed to have matched it to.
 */
export function poseDisagreement(title: string, match: NonNullable<QueueCard["plexMatch"]>): void {
  const state = mockState();
  for (const list of SETTLED_LISTS) {
    state[list] = state[list].map((card) => (card.title === title ? { ...card, plexMatch: match } : card));
  }
  forgetLadder(title);
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
    ? [[state.stuckLoaded, () => STUCK_AT], [arrivedOnly(state.moving), moving], [state.settledLoaded, settled]]
    : [[state.stuck, () => STUCK_AT], [state.movingReel, moving], [state.settled, settled]];
  // A TUNNEL ERROR IS A STEP NO PICK UNBLOCKS: a row a pending decision names
  // is resolved by that decision, whatever step it stopped at.
  const namedByDecision = new Set(state.pendingDecisions.map((decision) => decision.folder));
  const inStaging = lists.flatMap(([cards, at]) => cards.map(served).map(({ strip, failedStep, ...stopped }) => {
    const card = failedStep === undefined || namedByDecision.has(stopped.title) ? stopped : { ...stopped, failedStep };
    const position = at({ ...card, strip });
    const { requester, origin } = originOf(card, true);
    const asked = requester === undefined ? card : { ...card, requester };
    return position === undefined ? asked
      : { ...asked, ladder: ladderOf(acquisitionKey(card), position, { ...origin, times: ownTimeOf(card) }) };
  }));
  return inStaging;
}

/**
 * Sets one queued folder aside, where it stands (ruling 6, placed by ruling 16).
 *
 * THE FOLDER STAYS WHERE IT IS QUEUED: its files are still on the machine and
 * still have to be dealt with, so it leaves no list. What changes is its
 * ladder — the rung it was stopped on is now set aside, dated with the layer's
 * frozen clock, never the wall clock (the layer is deterministic by contract).
 *
 * THE ENGINE'S `dismissed` ACCEPTS the automatic result; the interface's
 * « Laisser tel quel » means later, and the backend follows the interface.
 *
 * @param title The folder.
 * @returns Whether a queued folder carried that title.
 */
export function setAside(title: string): boolean {
  const state = mockState();
  for (const list of SOURCE_LISTS) {
    const found = state[list].find((card) => card.title === title);
    if (found === undefined) continue;
    // Set aside on the rung it STANDS on (a staging folder « identifié », a blocked card its strip's
    // current cell) — never the first one not done, « demandé » for a folder that never lived it.
    const position = (list === FROM_BLOCKED ? stripPosition(found.strip) : undefined) ?? STUCK_AT;
    const ladder = ladderOf(title, position);
    const standing = position.current;
    ladder[standing] = { rung: ladder[standing].rung, state: ASIDE, when: scenario().now };
    return true;
  }
  return false;
}

/**
 * Queues more stuck folders, each a copy of the dense world's first one under its own title, until
 * the layer is next reset: « À traiter » then holds enough cards asking for « Résoudre » to scroll
 * at a phone's width (B-683 — the last « Résoudre » must be reachable above the « + »).
 *
 * @param titles One title per folder to add.
 */
export function poseStuckFolders(titles: string[]): void {
  const state = mockState();
  const [model] = state.stuckLoaded;
  if (model === undefined) return;
  for (const list of ["stuck", "stuckLoaded"] as const)
    for (const title of titles) state[list].push({ ...model, title });
}

/** Every route this subject answers. */
export function stagingRoutes(): MockRoute[] {
  return [
    route("readStaging", GET, "/staging/media", (request: MockRequest) => {
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
          moving: arrivedOnly(state.moving),
          settled: state.settledLoaded.map(served),
        };
      }
      return { stuck: state.stuck, moving: state.movingReel, settled: state.settled.map(served) };
    }),
    route(
      "continueStagedMedia",
      POST,
      "/staging/media/{mediaId}/continue",
      (request) => {
        const asked = request.parameters.mediaId;
        if (text(request.body, "outcome") === LEFT_AS_IT_IS) return { ok: setAside(asked) };
        return { ok: continueMedia(asked, text(request.body, "choice")) };
      },
    ),
    route(
      "discardStagedMedia",
      POST,
      "/staging/media/{mediaId}/discard",
      (request) => {
        const asked = request.parameters.mediaId;
        // QUARANTINED, NOT DELETED, journaled, at the backend's own path; a follow's folder is searched again.
        const quarantinePath = [QUARANTINE_FOLDER, asked].join(PATH_SEPARATOR);
        const followed = (card: QueueCard) => mockState().follows.some((follow) => sameMedium(card, follow.ids));
        if (backToSearch(asked, followed)) return { ok: true, journaled: true, quarantine_path: quarantinePath };
        const removed = takeOutOfStaging(asked);
        return { ok: removed, journaled: removed, quarantine_path: quarantinePath };
      },
    ),
    // DELETED, NOT QUARANTINED: « Supprimer » on a folder set aside removes it
    // from the disk and journals it; the answer carries no place it went.
    route("readStagedMediaCopies", GET, "/staging/media/{mediaId}/copies", (request) => ({
      case: copiesOf(request.parameters.mediaId),
    })),
    route("deleteStagedMedia", DELETE, "/staging/media/{mediaId}", (request) => {
      const removed = takeOutOfStaging(request.parameters.mediaId);
      return { ok: removed, journaled: removed };
    }),
    route("readStagingDestinations", GET, "/staging/destinations", () => DESTINATIONS),
    route(
      "resolvePlexMatch",
      POST,
      "/acquisition/journeys/{infoHash}/plex-match",
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
          // « CORRIGER » ASKS PLEX TO MATCH IT TO WHAT WE HOLD: the card
          // waits in « À traiter » until the corrected match is checked, its
          // last rung not done. « CONFIRMER » answers the question: the
          // match leaves, and « vérifié dans Plex » is done.
          if (outcome === CORRECT) return { ok: true, outcome };
          const { plexMatch, ...answered } = found;
          state[list] = state[list].map((card) => (card === found ? answered : card));
          forgetLadder(asked);
          confirmInPlex(asked);
          return { ok: plexMatch !== undefined, outcome };
        }
        return { ok: false, outcome };
      },
    ),
    route(
      "reclassifyStagedMedia",
      POST,
      "/staging/media/{mediaId}/reclassify",
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
      "/staging/media/{mediaId}/reclassify",
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
