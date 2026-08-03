/**
 * EpisodeStateLegende — the colour key under the completeness matrix (#9).
 *
 * One row per {@link EpisodeState}: its DS-tone swatch (a dotted {@link Badge})
 * next to its French label. The whole legend is DERIVED from the single-source
 * vocabulary maps in `meta.ts` (`EPISODE_STATE_TONE` × `EPISODE_STATE_LABEL`) —
 * it rewrites no label and picks no colour of its own, so a state added to those
 * maps appears here automatically and a drift is a test failure, never a silent
 * mismatch between chip and key.
 */

import type { ReactElement } from "react";

import { Badge } from "@/components/ui/badge";

import {
  EPISODE_LEGEND_ORDER,
  EPISODE_STATE_LABEL,
  EPISODE_STATE_TONE,
} from "./meta";

/**
 * The states in lifecycle order, as the operator walks them: unknown →
 * announced → searched-but-nothing → takeable → being taken → owned. Declared
 * once in `meta.ts` (never `Object.keys`, whose order is an accident of
 * declaration) and shared with the tests that pin it.
 */
const LEGEND_ORDER = EPISODE_LEGEND_ORDER;

/**
 * EpisodeStateLegende — the per-state colour legend.
 *
 * Returns:
 *   The legend element: a wrapping row of swatch + label pairs, legible in both
 *   themes (the swatches are the same tinted DS tones the chips use).
 */
export function EpisodeStateLegende(): ReactElement {
  return (
    <div
      aria-label="Légende des statuts d'épisode"
      className="flex flex-wrap gap-x-3 gap-y-1.5 pt-2"
    >
      {LEGEND_ORDER.map((state) => (
        // The chip IS the swatch: its tone shows the colour, its text the label
        // — one element, no risk of a swatch and a caption drifting apart.
        <Badge key={state} tone={EPISODE_STATE_TONE[state]} dot>
          {EPISODE_STATE_LABEL[state]}
        </Badge>
      ))}
    </div>
  );
}
