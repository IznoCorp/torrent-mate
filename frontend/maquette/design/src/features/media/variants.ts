// THE MEDIA SHEET — ONE TEMPLATE FOR EVERY MEDIUM, as typed variants.
//
// What is NOT here is the EPISODE machinery and the season matrix: the engine
// draws those rows and toggles the state classes that colour them, so their
// rules are in `src/styles/legacy.css` with their date of death (D-L07-5).
import { cva } from "../../ui/cva";

/**
 * The hero's wrapper.
 *
 * The negative top margin cancels the body's own padding so the image touches
 * the bar. WITHOUT AN IMAGE the same pull would glue the title to it, which is
 * why the `poster: false` variant restores the breathing room.
 *
 * `overflow-x: clip`, not `hidden`: forbid overflow without creating a scroll
 * container — an animation must never be able to push the page sideways.
 */
export const heroWrap = cva("herowrap relative -mt-5 -mx-7 mb-0 isolate overflow-x-clip", {
  variants: { poster: { true: "", false: "noposter pt-8" } },
  // A DEFAULT, BECAUSE `VariantProps` MAKES THE PROP OPTIONAL. A call that
  // forgets it type-checks; `true` is the shape a sheet has when it has an
  // image, which is the case the layout was drawn for.
  defaultVariants: { poster: true },
});

/**
 * The hero's image.
 *
 * Without a poster it collapses to a 72px band carrying a brand gradient, so
 * the template does not change — only the content does.
 */
export const heroImage = cva(
  // `motion-safe:`, NOT a bare `animate-*`. The residue rule this variant
  // shadows sits inside `@media (prefers-reduced-motion: no-preference)`, so
  // under `reduce` the residue drops out and an unconditional utility kept
  // animating — the hero entrance ran for a reader who asked for no motion,
  // against invariant 14. Found by widening R80 to measure both motion
  // preferences; under `no-preference` the two sides agreed exactly, which is
  // why nothing else saw it.
  "herobg relative bg-cover bg-muted [background-position:center_16%] motion-safe:animate-hero-in " +
    // THE MELT: the image gives itself fully at the top, then dissolves into
    // the body colour. No edge, no seam — that is the whole effect.
    //
    // THE GRADIENT IS ONE LITERAL, however long, AND IT HAS TO BE. Split
    // across `+` concatenation, no single string held the whole class name and
    // TAILWIND'S SCANNER NEVER SAW IT — the `::after` came out with no
    // background at all. The oracle stayed green through it: it measures the
    // element's own computed style and its rectangle, and a missing
    // pseudo-element changes neither. R26 caught it, by reading
    // `getComputedStyle(bg, '::after')`. A gate proves what it reads.
    "after:content-[''] after:absolute after:inset-0 " +
    "after:[background:linear-gradient(to_bottom,transparent_0%,transparent_34%,color-mix(in_oklab,var(--color-background)_45%,transparent)_66%,color-mix(in_oklab,var(--color-background)_88%,transparent)_87%,var(--color-background)_100%)]",
  {
    variants: {
      poster: {
        true: "h-[min(46vh,400px)] min-h-[268px]",
        false:
          // One literal, for the reason written at the melt above.
          "h-[72px] min-h-0 [background-image:linear-gradient(160deg,color-mix(in_oklab,var(--color-primary)_45%,var(--color-background)),var(--color-card)_58%,var(--color-muted))]",
      },
    },
    // A DEFAULT, AND HERE IT IS THE ONE THAT MATTERS. Height lives ONLY in the
    // variant, so a call that omits the prop type-checks and emits no height
    // at all — the hero collapses to nothing and the melt has no image to melt
    // from. `VariantProps` cannot ask for it; this can.
    defaultVariants: { poster: true },
  },
);

/**
 * The hero's text block.
 *
 * The title OVERLAPS the end of the melt: it belongs to the image as much as
 * to the body, and that is what stitches the two together.
 */
export const heroText = cva("hero relative -mt-[62px] py-0 px-7");

/** The medium's title. */
export const heroTitle = cva(
  "ht m-0 text-8 font-semibold leading-[1.12] tracking-[-0.025em] text-balance " +
    "[text-shadow:0_2px_14px_color-mix(in_oklab,var(--color-background)_70%,transparent)]",
);

/** The line of facts under the title. */
export const heroMeta = cva("hm mt-3 mx-0 mb-0 text-3 text-muted-foreground leading-[1.55]");

/** A note beside the facts, in the brand colour. */
export const heroNote = cva("hn inline-flex items-center gap-2 mt-3 text-3 font-bold text-primary");

/**
 * The cast carousel.
 *
 * `touch-pan-x touch-pan-y` — and BOTH axes on purpose. `pan-x` alone forbids
 * vertical panning, so a finger resting on the carousel could no longer scroll
 * the sheet, which is exasperating. Let the browser decide from the gesture's
 * direction. COMPOSITOR-FACING, and held by `check-compositor-css.py`.
 */
export const castList = cva(
  "cast flex gap-4 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden " +
    "touch-pan-x touch-pan-y pb-1",
);

/** One member of the cast. */
export const castFigure = cva("flex-none w-[74px] m-0");

/** Their portrait, or their initials when there is none. */
export const castPortrait = cva(
  "ca w-[74px] h-[74px] rounded-full bg-muted grid place-items-center font-mono " +
    "text-7 font-semibold text-muted-foreground overflow-hidden " +
    "[&_img]:w-full [&_img]:h-full [&_img]:object-cover [&_img]:block",
);

/** Their name and their role. */
export const castCaption = cva(
  "mt-3 text-2 leading-[1.35] " +
    "[&_b]:block [&_b]:font-semibold [&_b]:overflow-hidden [&_b]:text-ellipsis [&_b]:whitespace-nowrap " +
    "[&_span]:block [&_span]:text-muted-foreground [&_span]:overflow-hidden " +
    "[&_span]:text-ellipsis [&_span]:whitespace-nowrap",
);

/** The trailer's row. THE DESTINATION IS INFORMATION: this control LEAVES the application. */
export const trailerRow = cva(
  "trailer flex items-center gap-5 w-full border border-border bg-card rounded-3 " +
    "py-5 px-6 text-4 font-semibold text-left " +
    // DESCENDANT, not child: the prototype wrote `.trailer small`, and
    // `[&>small]` matched nothing — the row came up 4.4px short.
    "[&_small]:block [&_small]:text-2 [&_small]:font-normal [&_small]:text-muted-foreground [&_small]:mt-1",
);

/** Its play mark. */
export const trailerPlay = cva(
  "pl flex-none w-[30px] h-[30px] rounded-full bg-primary text-primary-foreground grid place-items-center",
);

/** Where the trailer comes from. */
export const trailerSource = cva(
  "tsrc flex-none inline-flex items-center gap-2 ml-auto text-1 font-bold tracking-[0.02em] " +
    "py-1 px-3 rounded-full bg-muted text-muted-foreground",
);
