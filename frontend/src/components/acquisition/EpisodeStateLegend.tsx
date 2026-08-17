/**
 * EpisodeStateLegend — the colour key under the completeness matrix (#9).
 *
 * One row per {@link EpisodeState}: its DS-tone swatch (a dotted {@link Badge})
 * next to its French label. The whole legend is DERIVED from the single-source
 * vocabulary maps in `meta.ts` (`EPISODE_STATE_TONE` × `EPISODE_STATE_LABEL`) —
 * it rewrites no label and picks no colour of its own, so a state added to those
 * maps appears here automatically and a drift is a test failure, never a silent
 * mismatch between chip and key.
 */

import type { ReactElement } from "react";

import {
  EPISODE_LEGEND_ORDER,
  EPISODE_STATE_LABEL,
  EPISODE_STATE_TONE,
  TONE_SWATCH_CLASS,
} from "./meta";

/**
 * The states in lifecycle order, as the operator walks them: unknown →
 * announced → searched-but-nothing → takeable → being taken → owned. Declared
 * once in `meta.ts` (never `Object.keys`, whose order is an accident of
 * declaration) and shared with the tests that pin it.
 */
const LEGEND_ORDER = EPISODE_LEGEND_ORDER;

/**
 * EpisodeStateLegend — the per-state colour legend.
 *
 * Returns:
 *   The legend element: a wrapping row of swatch + label pairs, legible in both
 *   themes (the swatches are the same tinted DS tones the chips use).
 */
export function EpisodeStateLegend(): ReactElement {
  return (
    <div
      aria-label="Légende des statuts d'épisode"
      className="flex flex-wrap gap-x-2.5 gap-y-1.5 border-y border-border py-2.5 text-[length:var(--text-2xs)] text-muted-foreground"
    >
      {LEGEND_ORDER.map((state) => (
        // SQUARE swatch + plain label — the matrix cells are squares, and a
        // key drawn with a different shape than what it explains misleads.
        <span key={state} className="inline-flex items-center gap-1.5">
          <i
            aria-hidden="true"
            className={`inline-block size-[9px] rounded-[2px] ${TONE_SWATCH_CLASS[EPISODE_STATE_TONE[state]] ?? "bg-muted"}`}
          />
          {EPISODE_STATE_LABEL[state]}
        </span>
      ))}
    </div>
  );
}
