// THE CARD, AS TYPED VARIANTS — the blocks every list row is built from.
//
// A FILE OF ITS OWN, because the card is one subject and the other files the
// barrel re-exports had no room left for it under the module ceiling.
//
// EVERY FACTORY KEEPS ITS IDENTITY CLASS AT THE FRONT, and two readers are why.
// The document-level delegation finds a foot's title through `.card` and
// `.ctitle`; and the residue stylesheet selected those names for the cards
// the engine built as strings, each declaration below being that stylesheet's
// own, term for term.
//
// EVERY BRANCH IS ONE STRING LITERAL: `harness/factories.py` reads a factory's
// base through its literals, and its branches one per literal.
import { cva } from "../cva";

/** A card: its poster or its folder beside a column, in one frame. */
export const card = cva(
  "card relative grid grid-cols-[auto_1fr] w-full items-stretch rounded-3 border border-border bg-card " +
    "overflow-hidden min-h-[126px] [transition:transform_var(--duration-2)_var(--ease-standard)] " +
    // The swipe gesture writes `dragging` straight to the card while a finger holds it.
    "[&.dragging]:transition-none " +
    // A LANDING NAMED THIS CARD (« Voir la carte de la saison »): it wears the
    // focus ring the base layer draws — the same outline, never a new one.
    "data-[landed]:[outline:2px_solid_var(--color-primary)] data-[landed]:[outline-offset:2px]",
);

/** The column beside the poster: the top, then the strip, then the foot. */
export const cardContent = cva("ccol flex min-w-0 flex-1 flex-col p-4");

/** The card's top row: the body, and whatever sits at its right edge. */
export const cardTop = cva("ctop flex min-w-0 items-center gap-5");

/**
 * The card's body — the control that opens the panel, or a plain block where
 * the card is itself the control. A button inheriting nothing from the browser.
 */
export const cardBody = cva("cbody min-w-0 flex-1 text-left [border:0] [background:transparent] p-0 block");

/**
 * The title: the identity everything else is addressed by. It is NEVER cut
 * (§ 12, « Rien d'essentiel n'est tronqué »): it wraps, takes its whole line,
 * and the card grows.
 */
export const cardTitle = cva("ctitle block text-4 font-semibold [overflow-wrap:anywhere]");

/** The sub-line, whole: it wraps as the title does. */
export const cardSubtitle = cva("csub block mt-1 text-2 text-muted-foreground [overflow-wrap:anywhere]");

/**
 * The reason a card is where it is. It NEVER truncates (§12, R48): it is what
 * the operator decides on, so it wraps and the card grows.
 */
export const cardReason = cva(
  "creason block mt-1 text-2 leading-[1.4] text-muted-foreground [&_b]:text-foreground [&_b]:font-semibold",
);

/**
 * A synopsis. It is background, not a reason, so it clamps — which keeps a
 * list scannable — and that is why the two are separate blocks.
 */
export const cardOverview = cva(
  "cov [display:-webkit-box] [-webkit-line-clamp:4] text-ellipsis [-webkit-box-orient:vertical] overflow-hidden " +
    "mt-2 text-2 leading-[1.4] text-muted-foreground",
);

/** The state line: what the medium is, at a glance. */
export const cardMeta = cva("cmeta mt-3 flex flex-wrap items-center gap-2");

/** A numeric aside. */
export const cardCaption = cva("caption text-2 text-muted-foreground");

/** How much of a medium is owned, in figures that keep their width as they change. */
export const cardFraction = cva("frac text-2 font-bold tabular-nums");

/** A rating, in a ring of the tone that says it is good. */
export const cardRating = cva(
  "crating text-1 font-bold py-1 px-3 rounded-full border " +
    "[border-color:color-mix(in_oklab,var(--color-success)_40%,transparent)] text-success ml-3",
);

/**
 * A byte count under way — a download's progress, filled in the tone of a
 * transfer. NOT the strip, which says which STEP a journey stands at: this says
 * how much of one step is done. The native element, so a screen reader says it.
 */
export const cardProgress = cva(
  "cprogress block w-full h-[6px] mt-3 rounded-full overflow-hidden appearance-none [border:0] bg-muted " +
    "[&::-webkit-progress-bar]:bg-muted [&::-webkit-progress-value]:bg-info [&::-moz-progress-bar]:bg-info",
);

/** The state's second line: what is pending, what has just arrived. */
export const cardAnnotations = cva("cannotations mt-2 flex flex-wrap items-center gap-2");

/** The mark a medium that has just arrived wears. */
export const cardFreshTag = cva(
  "freshtag flex-[0_0_auto] text-1 font-bold py-1 px-4 rounded-full text-primary-foreground bg-primary whitespace-nowrap",
);

/**
 * A FOLDER, in a poster's footprint: what a card wears when no medium stands
 * behind it. It promises the folder's own actions and nothing a sheet could show.
 */
export const cardFolder = cva(
  "folder w-[58px] [align-self:start] [justify-self:start] mt-4 mr-0 mb-4 ml-4 aspect-[2/3] rounded-3 flex-none grid " +
    "place-content-center gap-2 border border-dashed border-border bg-muted text-muted-foreground p-0 " +
    "[&_svg]:w-[22px] [&_svg]:h-[22px] [&_svg]:mx-auto [&_svg]:my-0",
);

/** The word under a folder's icon. */
export const cardFolderLabel = cva("dlabel text-1 font-semibold tracking-[0.02em] uppercase");

/**
 * The progress strip: its own full-width line under the top (R2).
 *
 * ONE COLUMN PER CELL, and the count is the caller's: each count is written
 * out whole so the stylesheet carries it. Five is the default and draws what a
 * strip always drew.
 */
export const cardStrip = cva(
  "strip mt-4 pt-4 border-t border-border grid gap-0",
  {
    variants: {
      cells: {
        2: "grid-cols-[repeat(2,minmax(0,1fr))]",
        3: "grid-cols-[repeat(3,minmax(0,1fr))]",
        4: "grid-cols-[repeat(4,minmax(0,1fr))]",
        5: "grid-cols-[repeat(5,minmax(0,1fr))]",
        6: "grid-cols-[repeat(6,minmax(0,1fr))]",
        7: "grid-cols-[repeat(7,minmax(0,1fr))]",
        8: "grid-cols-[repeat(8,minmax(0,1fr))]",
        9: "grid-cols-[repeat(9,minmax(0,1fr))]",
        10: "grid-cols-[repeat(10,minmax(0,1fr))]",
      },
    },
    defaultVariants: { cells: 5 },
  },
);

/**
 * One step of the strip, joined to the step before it by a line that is
 * coloured once the journey has passed through.
 */
export const stripStep = cva(
  "st flex flex-col items-center gap-2 relative min-w-0 before:content-[''] before:absolute " +
    "before:top-[4px] before:left-[-50%] before:w-full before:h-[1px] first:before:hidden",
  {
    variants: {
      state: {
        done: "done before:bg-success",
        now: "now before:bg-success",
        blocked: "blocked before:bg-border",
        pending: "before:bg-border",
        waiting: "waiting before:bg-border",
        aside: "aside before:bg-border",
        skipped: "skipped before:bg-border",
      },
    },
    defaultVariants: { state: "pending" },
  },
);

/**
 * A step's dot, in the colour of where the journey stands.
 *
 * IT LEADS WITH A UTILITY, AND THE CALL SITE WRITES `d` BESIDE IT. A one-letter
 * identity collides across contexts — the live strip's dot claims the same
 * letter — so this factory claims no anchor of its own.
 */
export const stripDot = cva("w-[9px] h-[9px] rounded-full z-1", {
  variants: {
    state: {
      done: "bg-success",
      now: "bg-primary [box-shadow:0_0_0_3px_color-mix(in_oklab,var(--color-primary)_25%,transparent)]",
      blocked: "bg-danger",
      pending: "bg-border",
      waiting: "bg-waiting",
      aside: "bg-neutral-signal",
      skipped: "bg-transparent [box-shadow:inset_0_0_0_1px_var(--color-border)]",
    },
  },
  defaultVariants: { state: "pending" },
});

/**
 * A step's label, on one line. It leads with a utility and the call site writes
 * `l` beside it, for the reason `stripDot()` gives.
 */
export const stripLabel = cva(
  "text-1 text-muted-foreground whitespace-nowrap overflow-hidden text-ellipsis max-w-full",
);
