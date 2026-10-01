// A tunnel stopped by an external cause — posed for the harness (Q7).
import type { components } from "../../contract/types";
import { mockState } from "../state";
import { forgetLadder, ladderOf, rungIndex } from "./ladder";

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
  if (details.provider !== undefined) rung.provider = details.provider;
  if (details.size !== undefined) rung.size = details.size;
  if (details.tracker === undefined) return;
  rung.tracker = details.tracker;
  if (cause !== RATIO_CAUSE) return;
  const key = SETTING_PREFIX + details.tracker + FLOOR_SUFFIX;
  const threshold = mockState().settings.flatMap((topic) => topic.settings).find((row) => row.key === key)?.raw;
  rung.minimumRatio = typeof threshold === "number" ? threshold : null;
}
