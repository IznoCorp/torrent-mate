// THE TWO RELEASE SCREENS, as typed variants.
//
// What the engine found, WITH WHAT DRIVES THE RANKING VISIBLE: without it,
// « take this one » is a bet. Each row states its resolution, its source, its
// language, its seeders and its size.
import { cva } from "../../ui/cva";

/** One release candidate. `best` marks the one the ranking would take. */
export const releaseRow = cva(
  "rel flex flex-col gap-3 border bg-card rounded-3 p-5",
  {
    variants: { best: { true: "best border-primary", false: "border-border" } },
    defaultVariants: { best: false },
  },
);

/** The release's name, read as an identifier rather than as a title. */
export const releaseName = cva(
  "rn font-mono text-2 leading-[1.4] [word-break:break-all]",
);

/** The row of tags describing the release. */
export const releaseTags = cva("rt flex flex-wrap gap-2 items-center");

/** The score the ranking gave it. */
export const releaseScore = cva(
  "sc ml-auto text-2 font-bold text-primary whitespace-nowrap",
);

/** One group of the quality profile. */
export const qualityGroup = cva("qgroup flex flex-col gap-4");
