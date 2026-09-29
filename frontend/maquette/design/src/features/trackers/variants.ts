// TRACKERS — the « Torrents » tab's row title and its filter line, as typed variants.
import { cva } from "../../ui/cva";

/**
 * A torrent's title, which is a path to its medium's sheet.
 *
 * A BUTTON THAT READS AS A NAME: the browser's own button ground and border
 * are taken off, so the title keeps the row's text colour and contrast, and it
 * keeps a finger's height.
 */
export const torrentTitle = cva(
  "fn text-3 font-semibold text-left text-foreground bg-transparent [border:0] p-0 min-h-[44px] cursor-pointer",
);

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

/**
 * A row's head: its origin mark and its title, on one line — the mark a flex
 * item, so it keeps its box, never an inline span drawn at 0 × 0.
 */
export const torrentHead = cva("flex items-center gap-4 min-w-0");

/** A row's marks and its gesture, under its title and ratio, across the row. */
export const torrentChipLine = cva("col-span-full flex flex-wrap items-center gap-4");

/** « Vu » on a broken obligation: a finger's target in both directions. */
export const seenControl = cva(
  "text-2 font-semibold text-primary-text bg-transparent [border:0] p-0 min-h-[44px] min-w-[44px] cursor-pointer",
);

/** A tab of the page's strip: a finger's height, as Acquisition's own tabs. */
export const trackersTab = cva("min-h-[44px]");

/** « Voir les torrents »: a path, at a finger's height. */
export const seeTorrents = cva("min-h-[44px]");

/** A row's « Retirer de qBittorrent »: a destructive act, said in its colour, at a finger's height. */
export const torrentRemove = cva(
  "text-2 font-semibold text-danger-text bg-transparent [border:0] p-0 min-h-[44px] cursor-pointer text-left",
);
