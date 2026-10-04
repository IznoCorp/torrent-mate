// The ranking preview: the fixed sample set scored under a candidate ranking.
//
// THE BACKEND'S OWN SEMANTICS, `rank()` in `personalscraper/api/tracker/_ranking.py`:
// a criterion scores the field it names — a score per value, matched without
// regard to case, or the best threshold met — times its weight, truncated; the
// economy bonuses are added. Unlike `rank()`, nothing is dropped: a sample under
// the minimum seeders is kept, flagged excluded and sunk last, so the editor
// shows what the real ranking would drop.
import SAMPLES from "../seeds/ranking-samples.json";
import { mockState } from "../state";
import { trackersState } from "../trackers-state";
import type { components } from "../../contract/types";

type Schemas = components["schemas"];
type Sample = Schemas["RankingSample"];
type Criterion = Schemas["RankingCriterion"];
type RatioState = Schemas["RankingPreviewRelease"]["trackerRatioState"];

// Where a tracker's floor and target are set: its economy block.
const SETTING_PREFIX = "tracker.providers.";
const FLOOR_SUFFIX = ".economy.min_ratio";
const TARGET_SUFFIX = ".economy.target_ratio";
// A threshold where lower is better.
const LOWER = "lower";

/**
 * A tracker's economy setting, when the settings hold a number for it.
 *
 * @param tracker The tracker.
 * @param suffix The setting's key after the tracker's name.
 * @returns The number, or undefined.
 */
function economyOf(tracker: string, suffix: string): number | undefined {
  const key = SETTING_PREFIX + tracker + suffix;
  const raw = mockState().settings.flatMap((topic) => topic.settings).find((row) => row.key === key)?.raw;
  return typeof raw === "number" ? raw : undefined;
}

/**
 * Where a tracker's ratio stands against its own economy.
 *
 * @param tracker The tracker.
 * @returns Under its floor, under its target, comfortable — or null without a policy.
 */
function ratioStateOf(tracker: string): RatioState {
  const ratio = trackersState().trackers.find((one) => one.name === tracker)?.ratio;
  const floor = economyOf(tracker, FLOOR_SUFFIX);
  const target = economyOf(tracker, TARGET_SUFFIX);
  if (ratio === null || ratio === undefined || floor === undefined) return null;
  if (ratio < floor) return "under_floor";
  return target !== undefined && ratio < target ? "under_target" : "comfortable";
}

/**
 * The points one criterion awards one value.
 *
 * @param criterion The criterion.
 * @param value The sample's value for the field it names.
 * @returns The points, before the weight.
 */
function pointsOf(criterion: Criterion, value: string | number): number {
  if (criterion.values) {
    const wanted = String(value).toLowerCase();
    const found = Object.entries(criterion.values).find(([key]) => key.toLowerCase() === wanted);
    return found ? found[1] : 0;
  }
  const numeric = Number(value);
  const met = (criterion.thresholds ?? []).filter((threshold) =>
    criterion.prefer === LOWER ? numeric <= threshold.at : numeric >= threshold.at);
  return met.reduce((best, threshold) => Math.max(best, threshold.score), 0);
}

/**
 * The sample set scored and ordered under a ranking.
 *
 * @param ranking The candidate ranking.
 * @returns Every sample, the kept ones by score, the excluded ones last.
 */
export function previewOf(ranking: Schemas["RankingConfig"]): Schemas["RankingPreview"] {
  const scored = (SAMPLES as Sample[]).map((sample) => {
    const trackerRatioState = ratioStateOf(sample.provider);
    const fields: Record<string, string | number | boolean | null> = { ...sample, trackerRatioState };
    let score = 0;
    for (const criterion of ranking.criteria) {
      const value = fields[criterion.field];
      if (value === null || value === undefined || typeof value === "boolean") continue;
      score += Math.trunc(pointsOf(criterion, value) * criterion.weight);
    }
    if (sample.freeleech) score += ranking.bonuses.freeleech;
    return { ...sample, score, excluded: sample.seeders < ranking.minSeeders, trackerRatioState };
  });
  // STABLE: equal scores keep the sample set's own order, as `rank()` does.
  const ordered = [...scored].sort((one, other) =>
    Number(one.excluded) - Number(other.excluded) || other.score - one.score);
  return { ranked: ordered, knownTrackers: trackersState().trackers.map((tracker) => tracker.name) };
}
