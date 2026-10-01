// The « Trackers » feature's own drawing, where it composes into another
// surface: the media sheet's cross-seed block.
import { cva } from "../../ui/cva";

/** The block's heading, set apart from its list as the sheet's other headings are. */
export const mediaCrossSeedHeading = cva("mb-3");

/** One origin torrent's own line, above its pairs. */
export const mediaCrossSeedOrigin = cva("mt-4 mb-2 text-3 text-muted-foreground [overflow-wrap:anywhere]");
