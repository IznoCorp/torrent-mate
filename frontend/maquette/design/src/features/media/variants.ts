// THE MEDIA SHEET — ONE TEMPLATE FOR EVERY MEDIUM, as typed variants.
//
// The SEASON TREE is here too — the episode rows, the matrix of cells and the
// legend. An episode's state is a variant, and its token stays in the class
// beside the identity class, which stays at the front: rules select `ep` (R3)
// and the audit reads a block's first class (`noinfo`, R13).
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
  // THE ENTRY HAS ONE OWNER, AND IT IS THE VIEW TRANSITION (steward's bench,
  // 2026-08-31). `animate-hero-in` was here as well, and the two produced a
  // flash the operator read as a bug: the transition drew the hero full for
  // 315ms, then it ENDED and the real element resumed with `heroin` at
  // currentTime 0 — opacity to zero in one frame — and replayed the entry
  // over 450ms. Appear, flash, reappear.
  //
  // The mechanism is general and it is why this is a class of defect rather
  // than one bug: CSS animations on a tree mounted under
  // `startViewTransition` do not START until the transition finishes —
  // rendering is frozen for the capture — so ANY element-side entry
  // animation on a surface reached by transition replays afterwards, over a
  // snapshot that already showed the final state. `:active-view-transition`
  // cannot guard it either: by the time the animation starts, the transition
  // is over and the selector no longer matches.
  //
  // On a cold load there is no transition and the hero simply appears, as
  // every other element on a cold load does. An entry conditioned on that
  // arrival would be new design and is not invented here.
  "herobg relative bg-cover bg-muted [background-position:center_16%] " +
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
        true: "h-[min(46dvh,400px)] min-h-[268px]",
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
// `!`: the unlayered `* { scrollbar-width: thin }` beats any layered utility (B-336).
export const castList = cva(
  "cast flex gap-4 overflow-x-auto [scrollbar-width:none]! [&::-webkit-scrollbar]:hidden " +
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

/** Their name and their role, whole: each wraps rather than being cut (§ 12). */
export const castCaption = cva(
  "mt-3 text-2 leading-[1.35] [overflow-wrap:anywhere] " +
    "[&_b]:block [&_b]:font-semibold [&_span]:block [&_span]:text-muted-foreground",
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

/** Where the trailer comes from, at the row's end: a neutral chip. */
export const trailerSourcePlace = cva("tsrc flex-none ml-auto");

/**
 * « Récupérer cette saison » — the verb a season with a hole carries (B-301).
 *
 * PLACEMENT ONLY. The button itself wears `sact`, the class every other action
 * in a panel wears, so it is painted by the same rules and dies when they do.
 * What is added here is the gap separating it from the episode grid above it,
 * and nothing outside the scale (invariant 3).
 *
 * It is drawn ONLY on a season the interface has just said is short, so it never
 * offers to take what is already held.
 */
export const seasonGrabSpacing = cva("mt-4 mb-1");

/**
 * A season act whose ask is IN FLIGHT, drawn as taken.
 *
 * The look is the controls' own disabled one, keyed on `aria-busy` rather than
 * `disabled`: a disabled button drops the focus it holds, where this one keeps
 * it and answers a second press with silence (NE-DOIT-PAS-3). Its text does not
 * change.
 */
export const seasonGrabTaken = cva("aria-busy:opacity-50");

/**
 * What a season has ANNOUNCED and not yet aired: information, never a shortfall.
 *
 * NOT THE SHORTFALL CHIP. An episode that has not aired cannot be held, so it is
 * not missing, and wearing the warning chip would read one fact as the other. The muted tone is the one the date a season
 * airs on already wears, because it is the same kind of fact: when something
 * comes out. It offers nothing to press.
 */
export const upcomingMark = cva("inline-flex items-center py-1 px-3 text-1 text-muted-foreground");

// ── The season tree ─────────────────────────────────────────────────────────

/** The season's fraction, at the end of its summary. */
export const seasonFraction = cva(
  "sfr ml-auto [font-family:ui-monospace,SFMono-Regular,Menlo,monospace] text-3 font-semibold " +
    "text-foreground [font-variant-numeric:tabular-nums] normal-case [letter-spacing:normal]",
);

/**
 * Which episodes are missing, in words, before the list.
 *
 * The question an incomplete sheet answers is « which ones », not « how many ».
 */
export const missingList = cva(
  "missing [margin:var(--spacing-4)_0_0] text-3 font-semibold text-warning-text [font-variant-numeric:tabular-nums]",
);

/** Where an empty place of the sheet sits: a step below what precedes it. */
export const noInfoPlace = cva("mt-4");

/**
 * A place still waiting for its read: a skeleton line in the frame the answer
 * will take. It is not an empty place — the empty ones draw `NoInfo`.
 */
export const noInfo = cva(
  "noinfo [margin:0_0_var(--spacing-2)] text-3 text-muted-foreground " +
    "[border:1px_dashed_var(--color-border)] rounded-3 [padding:var(--spacing-5)_var(--spacing-5)]",
);

/**
 * One episode row: a 6px dot and the number in the state's tone, the title
 * neutral — it is what one reads first — and the date.
 */
export const episodeRow = cva(
  "eprow flex items-baseline gap-4 py-4 px-[0] [border-bottom:1px_solid_var(--color-border)] " +
    "last:[border-bottom:0] text-3",
  {
    variants: {
      state: {
        unverified: "unverified",
        announced: "announced",
        pending: "pending",
        to_grab: "to_grab",
        acquiring: "acquiring",
        in_library: "in_library",
      },
    },
  },
);

/** Where the season list sits under the facts: a step below them. */
export const seasonListPlace = cva("mt-5");

/** The row's episode number, in the state's tone — a LABEL, so `to_grab` takes the tone's text colour. */
export const episodeNumber = cva(
  "en flex-[0_0_auto] [font-family:ui-monospace,Menlo,monospace] text-2 font-semibold min-w-[34px]",
  {
    variants: {
      state: {
        unverified: "text-muted-foreground",
        announced: "text-upcoming-text",
        pending: "text-waiting-text",
        to_grab: "text-warning-text",
        acquiring: "text-info-text",
        in_library: "text-success-text",
      },
    },
  },
);

/** The row's title. */
export const episodeTitle = cva("et min-w-[0] flex-1 overflow-hidden text-ellipsis whitespace-nowrap");

/** The row's air date and state. */
export const episodeDate = cva("ed flex-[0_0_auto] text-2 text-muted-foreground [font-variant-numeric:tabular-nums]");

/** The matrix of cells, when a season has numbers and no titles. */
export const episodeSet = cva("eps flex flex-wrap gap-2 mt-4");

/**
 * One cell of the matrix: 31 x 27, radius 5, mono 11 semibold, the tone at 20%.
 *
 * The border is in every branch and never in the base: with no class merging, a
 * base border and a branch border resolve by stylesheet order, not by intent.
 */
export const episodeCell = cva(
  "ep grid place-items-center w-[31px] h-[27px] rounded-2 " +
    "[font-family:ui-monospace,SFMono-Regular,Menlo,monospace] text-2 font-semibold cursor-pointer",
  {
    variants: {
      state: {
        unverified: "unverified [border:1px_dashed_var(--color-border)] [background:transparent] text-muted-foreground",
        announced: "announced [border:0] [background:color-mix(in_oklab,var(--color-upcoming)_20%,transparent)] text-upcoming-text",
        pending: "pending [border:0] [background:color-mix(in_oklab,var(--color-waiting)_20%,transparent)] text-waiting-text",
        to_grab: "to_grab [border:0] [background:color-mix(in_oklab,var(--color-warning)_20%,transparent)] text-warning-text",
        acquiring: "acquiring [border:0] [background:color-mix(in_oklab,var(--color-info)_20%,transparent)] text-info-text",
        in_library: "in_library [border:0] [background:color-mix(in_oklab,var(--color-success)_20%,transparent)] text-success-text",
      },
    },
  },
);

/** An episode's state, as the matrix, the rows and the legend all name it. */
export type EpisodeState = "unverified" | "announced" | "pending" | "to_grab" | "acquiring" | "in_library";

/** A section heading of the sheet, a step above what it names. */
export const sheetHeadingPlace = cva("mb-3");

/** A panel of the sheet, a step above the next. */
export const sheetPanelPlace = cva("mb-5");

/** The synopsis, as the sheet reads it. */
export const synopsisText = cva("m-0 text-3 leading-[1.55] text-muted-foreground");

/** Who rates, beside the rating: quieter than the figure. */
export const ratingSource = cva("font-normal text-muted-foreground");
