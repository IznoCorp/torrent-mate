// The episode states' order, their tones, and the legend that says them.
//
// ONE VOCABULARY FOR EVERY DRAWING OF EPISODES. The follow sheet's seasons and
// the media sheet's season list colour the same six states; the order, the
// dot's tone and the swatch's tone are said here once, and the legend both
// draw names only the states present — an absent legend is a defect (order 57),
// and a legend listing states the drawing does not use is noise.
import type { ReactElement } from "react";
import { Legend } from "../../ui/legend";
import type { StatusTone } from "../../ui/variants";
import { episodeStateLabel } from "./format";

/** Lifecycle order, as the operator reads it. */
export const EPISODE_ORDER = ["unverified", "announced", "pending", "to_grab", "acquiring", "in_library"] as const;

/** One episode state. */
export type EpisodeStateName = (typeof EPISODE_ORDER)[number];

/** The tone each state's swatch wears in the legend. */
export const EPISODE_SWATCH = {
  unverified: "unknown",
  announced: "upcoming",
  pending: "waiting",
  to_grab: "warning",
  acquiring: "info",
  in_library: "success",
} as const;

/** The tone each state's dot wears: the status dot's own tones. */
export const EPISODE_DOT: Record<EpisodeStateName, StatusTone> = {
  unverified: "neutral",
  announced: "upcoming",
  pending: "waiting",
  to_grab: "warning",
  acquiring: "info",
  in_library: "success",
};

/**
 * The legend over a drawing of episodes: only the states present, in order.
 *
 * @param props.present The states the drawing uses.
 * @returns The legend, or nothing when no state is present.
 */
export function EpisodeLegend({ present }: {
  /** The states the drawing uses. */
  present: ReadonlySet<string>;
}): ReactElement | null {
  const shown = EPISODE_ORDER.filter((state) => present.has(state));
  return <Legend entries={shown.map((state) => ({ key: state, tone: EPISODE_SWATCH[state], label: episodeStateLabel(state) }))} />;
}
