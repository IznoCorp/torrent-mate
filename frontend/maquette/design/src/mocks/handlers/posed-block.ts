// A tunnel stopped by an external cause — posed for the harness (Q7).
import type { components } from "../../contract/types";
import { mockState } from "../state";
import { forgetLadder, ladderOf, rungIndex } from "./ladder";
import { trackersState } from "../trackers-state";
import { emit } from "../stream";

type Rung = components["schemas"]["JourneyStage"];

// The engine's own token for a ratio under the threshold.
const RATIO_CAUSE = "ratio_below_threshold";
// Where an external block stands: the engine lifts it, so it WAITS (DECIDED 3)
// — the danger red is what needs his judgement.
const WAITING = "waiting";
// Where a tracker's own ratio threshold is set: its economy block.
const SETTING_PREFIX = "tracker.providers.";
const FLOOR_SUFFIX = ".economy.min_ratio";
// One minute, in the epoch seconds `blockedSince` is written in.
const MINUTE = 60;

/**
 * The rung each external cause stops a tunnel on (maquette-blocked § 1.2): the
 * three deferrals of a finished torrent on « arrivé », the five blocks Q7 adds
 * on the rung that cannot be passed.
 */
export const BLOCK_RUNG: Record<string, Rung["rung"]> = {
  ratio_below_threshold: "arrived",
  insufficient_space: "arrived",
  content_missing: "arrived",
  library_full: "shelved",
  tracker_unreachable: "grabbed",
  provider_unreachable: "identified",
  plex_unreachable: "verified",
  client_unreachable: "downloading",
};

// WHICH DEPENDENCY each unreachable service's cause is read on, by the row's
// name in Système (maquette-blocked § 1.3: the door lands on a page saying the
// same cause). An unreachable tracker is read on the tracker's own entry.
const SERVICE_OF: Record<string, string> = {
  provider_unreachable: "TMDB / TVDB",
  plex_unreachable: "Plex",
  client_unreachable: "qBittorrent",
};
const TRACKER_CAUSE = "tracker_unreachable";

/** The services posed down, since when, per state of the layer — renewed by a reset. */
const down = new WeakMap<object, Map<string, number>>();

/**
 * Since when one dependency does not answer, when it was posed down.
 *
 * @param service The dependency's row name.
 * @returns The epoch seconds it stopped answering, or undefined while it answers.
 */
export function serviceDownSince(service: string): number | undefined {
  return down.get(mockState())?.get(service);
}

/**
 * Poses one dependency down, until the layer is next reset — a derivation: the
 * backend serves its reachability (BK6).
 *
 * @param service The dependency's row name (« Plex », « qBittorrent »…).
 * @param minutesAgo How long ago it stopped answering.
 */
export function poseServiceDown(service: string, minutesAgo = 0): void {
  const owner = mockState();
  const held = down.get(owner) ?? new Map<string, number>();
  if (!held.has(service)) held.set(service, Math.floor(Date.now() / 1000) - minutesAgo * MINUTE);
  down.set(owner, held);
}

/** What a block names besides its cause — each read by its own sentence. */
export type BlockDetails = {
  /** For a ratio cause or an unreachable tracker, the tracker. */
  tracker?: string;
  /** For an unreachable provider, its name. */
  provider?: string;
  /** For a full library, the bytes the medium needs. */
  size?: number;
  /** How many minutes ago the tunnel stopped — what orders the list (DECIDED 1). */
  minutesAgo?: number;
};

/**
 * Poses an external block on an acquisition, until the layer is next reset — a
 * derivation, shown as one: no real card is blocked; the backend serves the
 * cause, its rung and `resumes: auto` (BK1).
 *
 * THE LADDER STOPS ON THE CAUSE'S RUNG, WAITING, with the cause's token and
 * `resumes: "auto"`: the engine lifts it on its own. A ratio cause also names
 * the tracker and THAT tracker's own threshold, read from its economy block —
 * never the global one.
 *
 * @param title The medium.
 * @param cause The cause's token — a key of `BLOCK_RUNG`.
 * @param details What the cause names, and how long ago it stopped.
 */
export function poseBlock(title: string, cause: string, details: BlockDetails = {}): void {
  forgetLadder(title);
  const at = rungIndex(BLOCK_RUNG[cause] ?? "arrived");
  const ladder = ladderOf(title, { current: at, state: WAITING, reason: cause });
  const rung = ladder[at];
  rung.resumes = "auto";
  rung.blockedSince = Math.floor(Date.now() / 1000) - (details.minutesAgo ?? 0) * MINUTE;
  // THE LANDING SAYS THE SAME CAUSE: the service the block waits on is down
  // where its door lands — Système's dependency row, the tracker's entry.
  const service = SERVICE_OF[cause];
  if (service !== undefined) poseServiceDown(service, details.minutesAgo);
  if (cause === TRACKER_CAUSE && details.tracker !== undefined) {
    const tracker = trackersState().trackers.find((one) => one.name === details.tracker);
    if (tracker !== undefined) {
      tracker.reachable = false;
      tracker.unreachableSince = rung.blockedSince;
    }
  }
  if (details.provider !== undefined) rung.provider = details.provider;
  if (details.size !== undefined) rung.size = details.size;
  if (details.tracker === undefined) return;
  rung.tracker = details.tracker;
  if (cause !== RATIO_CAUSE) return;
  const key = SETTING_PREFIX + details.tracker + FLOOR_SUFFIX;
  const threshold = mockState().settings.flatMap((topic) => topic.settings).find((row) => row.key === key)?.raw;
  rung.minimumRatio = typeof threshold === "number" ? threshold : null;
}

// The live event the engine emits when it sees a cause lifted and resumes the
// step (BK2): « À traiter » and « En cours » read the queue again.
const LIFTED_EVENT = "BlockLifted";
// The state a resumed rung runs in.
const RUNNING = "now";

/**
 * Lifts the block one ladder stands on, as the engine does once it sees the
 * cause gone: the rung runs again, its block kept in the rung's trace.
 *
 * @param subject The acquisition's key.
 * @returns The cause it was stopped by, or undefined when it stood on none.
 */
function liftOne(subject: string): string | undefined {
  const ladder = mockState().journeyStages[subject];
  const rung = ladder?.find((one) => one.resumes === "auto");
  if (rung === undefined || rung.reason === undefined) return undefined;
  const reason = rung.reason;
  const resumedAt = Math.floor(Date.now() / 1000);
  rung.blocks = [...(rung.blocks ?? []), { reason, since: rung.blockedSince ?? resumedAt, resumedAt }];
  rung.state = RUNNING;
  for (const field of ["reason", "resumes", "blockedSince", "tracker", "minimumRatio", "provider", "size"] as const)
    delete rung[field];
  return reason;
}

/**
 * What a cause's lift puts back where its door lands: the service answering,
 * once no block waits on it any more.
 *
 * @param cause The cause lifted.
 */
function answerAgain(cause: string): void {
  const stillHeld = Object.values(mockState().journeyStages)
    .some((ladder) => ladder.some((rung) => rung.resumes === "auto" && rung.reason === cause));
  if (stillHeld) return;
  const service = SERVICE_OF[cause];
  if (service !== undefined) down.get(mockState())?.delete(service);
  if (cause !== TRACKER_CAUSE) return;
  for (const tracker of trackersState().trackers) {
    tracker.reachable = true;
    tracker.unreachableSince = null;
  }
}

/**
 * The engine sees ONE acquisition's cause lifted, resumes it, and says so with
 * a live event — a derivation, shown as one: the backend watches each cause's
 * lift (BK2).
 *
 * @param subject The acquisition's key.
 */
export function liftBlock(subject: string): void {
  const cause = liftOne(subject);
  if (cause === undefined) return;
  answerAgain(cause);
  emit(LIFTED_EVENT, { subjects: [subject], cause });
}

/**
 * The engine sees ONE cause lifted — qBittorrent answering again — and resumes
 * every acquisition it held, in one lift and one live event; a card another
 * cause holds stays.
 *
 * @param cause The cause's token.
 */
export function liftCause(cause: string): void {
  const subjects = Object.entries(mockState().journeyStages)
    .filter(([, ladder]) => ladder.some((rung) => rung.resumes === "auto" && rung.reason === cause))
    .map(([subject]) => subject);
  for (const subject of subjects) liftOne(subject);
  if (subjects.length === 0) return;
  answerAgain(cause);
  emit(LIFTED_EVENT, { subjects, cause });
}
