// The legend — the codes a drawing uses, said once, above it.
//
// ONE COMPONENT FOR EVERY DRAWING THAT COLOURS BY STATE: the seasons' matrix,
// the torrents, the trackers. It knows no domain (invariant 10): each entry is a
// tone and its words, and which state wears which tone is the drawing's own
// word, said where the drawing lives. Only the codes present are passed — a
// legend naming a code the drawing does not use is noise.
import type { ReactElement } from "react";
import { legend, legendSwatch, type LegendTone } from "./variants";

/** One code of a legend: its tone, its words, and the name its readers find it by. */
export type LegendEntry = { key: string; tone: LegendTone; label: string };

/**
 * The legend over a drawing.
 *
 * @param props.entries The codes the drawing uses, in the order they are read.
 * @returns The legend, or nothing when no code is present.
 */
export function Legend({ entries }: { entries: readonly LegendEntry[] }): ReactElement | null {
  if (entries.length === 0) return null;
  return (
    <div className={legend()} data-part="legend">
      {entries.map((entry) => (
        <span key={entry.key} data-state={entry.key} data-tone={entry.tone}>
          <i className={legendSwatch({ tone: entry.tone })} />
          {entry.label}
        </span>
      ))}
    </div>
  );
}
