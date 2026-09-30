// TRACKERS — the « Trackers » tab's controls, as typed variants.
import { cva } from "../../ui/cva";

/** « Vu » on a broken obligation: a finger's target in both directions. */
export const seenControl = cva(
  "text-2 font-semibold text-primary-text bg-transparent [border:0] p-0 min-h-[44px] min-w-[44px] cursor-pointer",
);

/** « Voir les torrents »: a path, at a finger's height. */
export const seeTorrents = cva("min-h-[44px]");