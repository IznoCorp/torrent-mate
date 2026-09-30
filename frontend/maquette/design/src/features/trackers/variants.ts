// TRACKERS — the « Torrents » tab's filter line and the « Trackers » tab's controls, as typed variants.
import { cva } from "../../ui/cva";

/**
 * The line saying the list is filtered to one tracker, and offering to lift it.
 *
 * SAID ABOVE THE ROWS, never implied by their number: a list that silently
 * lost some of its rows reads as a defect.
 */
export const torrentFilter = cva("flex items-center justify-between gap-4 px-5 text-3 text-muted-foreground");

/** The filter line's « lift it » control, at a finger's height. */
export const torrentFilterClear = cva(
  "text-3 font-semibold text-primary-text bg-transparent [border:0] p-0 min-h-[44px] cursor-pointer",
);

/** « Vu » on a broken obligation: a finger's target in both directions. */
export const seenControl = cva(
  "text-2 font-semibold text-primary-text bg-transparent [border:0] p-0 min-h-[44px] min-w-[44px] cursor-pointer",
);

/** « Voir les torrents »: a path, at a finger's height. */
export const seeTorrents = cva("min-h-[44px]");