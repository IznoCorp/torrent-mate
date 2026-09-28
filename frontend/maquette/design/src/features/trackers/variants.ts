// TRACKERS — the « Torrents » tab's row title, as a typed variant.
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
