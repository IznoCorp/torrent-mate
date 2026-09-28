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
