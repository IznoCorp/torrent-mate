// THE LEGEND — the codes a drawing uses, said once, above it.
//
// Moved here from the media feature: the season matrix drew it first, and every
// drawing that colours by state (the media sheet's seasons, the torrents) reads
// the same legend rather than a copy of it.
import { cva } from "../cva";

/** The legend over the matrix: only the states present, each with its swatch. */
export const legend = cva(
  "legend flex flex-wrap gap-y-2 gap-x-6 mb-6 text-2 text-muted-foreground " +
    "[&_span]:inline-flex [&_span]:items-center [&_span]:gap-2 [&_span]:whitespace-nowrap " +
    "[&_i]:w-[9px] [&_i]:h-[9px] [&_i]:rounded-1 [&_i]:block",
);

/**
 * A legend swatch: the state's tone at 60%, and a dashed ghost for « not verified ».
 *
 * `swatch` is its identity and carries no style: a factory's anchor is the first
 * token of its base, and a base left empty is a factory no reader can pair.
 */
export const legendSwatch = cva("swatch", {
  variants: {
    state: {
      unverified: "sw-muted [border:1px_dashed_var(--color-border)] [background:transparent]",
      announced: "sw-upcoming [background:color-mix(in_oklab,var(--color-upcoming)_60%,transparent)]",
      pending: "sw-waiting [background:color-mix(in_oklab,var(--color-waiting)_60%,transparent)]",
      to_grab: "sw-warning [background:color-mix(in_oklab,var(--color-warning)_60%,transparent)]",
      acquiring: "sw-info [background:color-mix(in_oklab,var(--color-info)_60%,transparent)]",
      in_library: "sw-success [background:color-mix(in_oklab,var(--color-success)_60%,transparent)]",
    },
  },
});
