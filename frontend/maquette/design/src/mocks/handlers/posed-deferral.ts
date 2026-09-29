// A finished torrent the engine did not take in: posed for the harness.
import { mockState } from "../state";
import { forgetLadder, ladderOf, rungIndex } from "./ladder";

// The engine's own token for a ratio under the threshold.
const RATIO_CAUSE = "ratio_below_threshold";
// Where a deferral stands: the download is over, the arrival waits.
const WAITING = "waiting";
// Where a tracker's own ratio threshold is set: its economy block.
const SETTING_PREFIX = "tracker.providers.";
const FLOOR_SUFFIX = ".economy.min_ratio";

/**
 * Poses a deferral on an acquisition in flight, until the layer is next reset —
 * a derivation, shown as one: no real card is deferred; the backend reads the
 * cause `classify_deferrals` answers.
 *
 * THE LADDER STOPS ON « ARRIVÉ », WAITING, with the cause's token: the torrent
 * finished and was not taken in. A ratio cause also names the tracker and THAT
 * tracker's own threshold, read from its economy block — never the global one.
 *
 * @param title The medium, one in flight that has not arrived.
 * @param cause The cause's token — `ratio_below_threshold`, `insufficient_space` or `content_missing`.
 * @param tracker For a ratio cause, the tracker it is under.
 */
export function poseDeferral(title: string, cause: string, tracker?: string): void {
  forgetLadder(title);
  const ladder = ladderOf(title, { current: rungIndex("arrived"), state: WAITING, reason: cause });
  if (cause !== RATIO_CAUSE || tracker === undefined) return;
  const key = SETTING_PREFIX + tracker + FLOOR_SUFFIX;
  const threshold = mockState().settings.flatMap((topic) => topic.settings).find((row) => row.key === key)?.raw;
  const rung = ladder[rungIndex("arrived")];
  rung.tracker = tracker;
  rung.minimumRatio = typeof threshold === "number" ? threshold : null;
}
