// ACQUISITION'S ADD SCREEN, as typed variants.
//
// AND DÉCOUVRIR'S SHAPES, « Suivis »' cadence line, and the small segmented
// control the add screen and the drawer share.
//
// The engine's gestures still find these surfaces by their class — `.sugwrap`,
// `.deck`, `.dcard`, `.dhint.l`, `.dhint.r` — and write `dragging`, `out` and
// `gone` straight to them, so each factory keeps its identity class and carries
// those states as class-qualified utilities. The deck card's one- and three-letter
// parts lead with a utility, and the markup writes `p`, `cap`, `t`, `m` and `why`
// beside them.
import { cva } from "../../ui/cva";

/** The add screen's form block. */
export const addForm = cva("addform pt-6 px-7 pb-0");

/** A row of the form: the field, then the button that acts on it. */
export const addRow = cva("addrow flex gap-4 mt-4");


/**
 * The results list.
 *
 * Search results are a card LIST like any other: the GAP comes from the
 * section, so the list cannot drift from the others by editing one number
 * here. This carries the screen's padding and nothing else.
 */
export const resultList = cva("reslist pt-5 px-7 pb-8");

/** The suggested searches. */
export const suggestions = cva("sugg flex flex-wrap gap-3 pt-6 px-7 pb-0");

/** One suggested search. */
export const suggestionChip = cva(
  "border border-border bg-transparent text-muted-foreground text-3 py-2 px-5 rounded-full",
);

/**
 * The « by identifier » disclosure.
 *
 * Its marker is drawn by the stylesheet rather than by the browser: the native
 * triangle differs on every platform and could not be placed.
 */
export const byIdentifier = cva(
  "byid mt-7 mx-7 mb-0 border border-border rounded-3 py-5 px-6 " +
    "[&>summary]:text-3 [&>summary]:font-semibold [&>summary]:cursor-pointer " +
    "[&>summary]:list-none [&>summary::-webkit-details-marker]:hidden " +
    "[&>summary::before]:content-['▸_'] [&>summary::before]:text-1 " +
    "open:[&>summary::before]:content-['▾_']",
);

/** The disclosure's contents. */
export const byIdentifierBody = cva("byidin mt-5 flex flex-col gap-4");

/** Why an action is refused. */
export const refusalReason = cva("whyoff text-2 text-danger");

/**
 * The screen's footer.
 *
 * ANCHORED TO THE BAR, not to the screen's edge: pinned at 0 it slid under the
 * tab bar and its actions became unreachable.
 *
 * IT OVERLAYS THE LIST AND DOES NOT RESERVE ITS SPACE, arbitrated by the
 * operator on 2026-08-29: « c'est une notification comme une autre, elle est
 * fermable ». A notification passes over what it announces and leaves; what it
 * may not do is settle there with no way out, which is what this bar did for as
 * long as its only exit was painted white on white (B-139).
 */
export const addFooter = cva(
  "addfoot sticky bottom-[var(--tm-bottom-bar-h,0px)] flex items-center gap-5 " +
    "pt-5 px-7 pb-[calc(env(safe-area-inset-bottom)+var(--spacing-5))] " +
    "bg-popover border-t border-border text-3",
);

/** The footer's own action. */
export const addFooterAction = cva(
  "ml-auto [border:0] bg-transparent text-primary font-semibold text-3",
);

/**
 * The footer's dismissal.
 *
 * A notification is dismissible or it is a state of the screen. The touch box
 * is written as an arbitrary value on purpose — 44px is a target, not a
 * spacing step, and the scale stops at 24px, so writing it as one would be a
 * lie about which system it belongs to (`styles/theme.css`).
 */
export const addFooterDismiss = cva(
  "grid place-items-center size-[44px] -mr-4 [border:0] bg-transparent " +
    "text-muted-foreground [&>svg]:size-5",
);

/** « Suivis »' line saying when the machine searches next. */
export const cadence = cva("cadence text-2 text-muted-foreground pt-4 px-7 pb-0");

/**
 * A small segmented control: its buttons side by side on a muted ground, the
 * pressed one lifted.
 */
export const segmentSmall = cva(
  "segmini flex gap-1 p-1 bg-muted rounded-3 " +
    "[&_button]:[border:0] [&_button]:rounded-2 [&_button]:[background:transparent] " +
    "[&_button]:text-muted-foreground [&_button]:text-3 [&_button]:font-semibold [&_button]:py-3 [&_button]:px-6 " +
    "[&_button[aria-pressed=true]]:bg-background [&_button[aria-pressed=true]]:text-foreground " +
    "[&_button[aria-pressed=true]]:[box-shadow:var(--mq-shadow-vsw)]",
);

/**
 * A suggestion row, which a swipe either way dismisses. It claims the vertical
 * pan, selects no text and drags no picture, for the swipe row's reasons; a
 * dismissed one collapses before it leaves.
 */
export const suggestionWrap = cva(
  "sugwrap relative overflow-hidden rounded-3 touch-pan-y select-none [&_img]:[-webkit-user-drag:none] " +
    "[&.gone]:[transition:height_var(--duration-3)_var(--ease-standard),opacity_var(--duration-2)_var(--ease-standard),margin_var(--duration-3)_var(--ease-standard)] " +
    "[&.gone]:[height:0]! [&.gone]:opacity-0 [&.gone]:mb-[calc(var(--spacing-7)*-1)]",
);

/** What a sliding suggestion uncovers: the dismissal's word, on both sides. */
export const suggestionBack = cva(
  "sugback absolute inset-0 flex items-center justify-between py-0 px-8 rounded-3 bg-muted " +
    "text-muted-foreground text-3 font-bold [&_span]:flex [&_span]:items-center [&_span]:gap-3 " +
    "[&_svg]:w-[16px] [&_svg]:h-[16px]",
);

/**
 * The surface holding the deck: the body, with less room under the pile. The
 * utility is qualified by its own class so it outranks the body's own padding.
 */
export const deckBody = cva("deckbody [&.deckbody]:pb-5");

/**
 * The pile. No `flex: 1`: in a column flex container that sets a 0 basis on the
 * vertical axis, which silently overrides the height the deck measures.
 */
export const deckPile = cva(
  "deck relative flex-[0_0_auto] min-h-[340px] touch-pan-y select-none [&_img]:[-webkit-user-drag:none]",
);

/**
 * One card of the pile. The cards behind say « there is more » without costing
 * a pixel of the card being read, and one joining the back rises from under the
 * deck. The two curves differ on purpose: the card settles a touch after it has
 * finished fading, which reads as picked up rather than snapped.
 */
export const deckCardFrame = cva(
  "dcard absolute inset-0 flex flex-col border border-border rounded-4 bg-card overflow-hidden " +
    "[box-shadow:var(--mq-shadow-pop)] origin-[50%_100%] will-change-transform " +
    "[transition:transform_var(--duration-4)_var(--ease-emphasized),opacity_var(--duration-3)_var(--ease-standard)] " +
    "data-[depth='1']:[transform:translateY(9px)_scale(0.955)] data-[depth='1']:opacity-75 " +
    "data-[depth='2']:[transform:translateY(18px)_scale(0.91)] data-[depth='2']:opacity-45 " +
    "data-[depth='3']:[transform:translateY(30px)_scale(0.86)] data-[depth='3']:opacity-0 " +
    "[&.dragging]:transition-none [&.out]:opacity-0 " +
    "select-none [-webkit-touch-callout:none] [&_img]:[-webkit-user-drag:none] [&_img]:[-webkit-touch-callout:none]",
);

/** The deck card's poster: the control that opens the sheet, filling the card. */
export const deckPoster = cva(
  "flex-1 min-h-0 block w-full [border:0] p-0 bg-muted relative [font-size:var(--text-display)] leading-none " +
    "[&_img]:w-full [&_img]:h-full [&_img]:object-cover [&_img]:block",
);

/**
 * The caption on the poster's foot, on a gradient that closes on a solid colour.
 * It reserves the floating « + »'s footprint rather than running under it.
 */
export const deckCaption = cva(
  "absolute [inset:auto_0_0] pt-[40px] pr-[76px] pb-[12px] pl-[14px] text-left " +
    "[background:linear-gradient(to_bottom,transparent,color-mix(in_oklab,var(--color-card)_72%,transparent)_46%,var(--color-card))]",
);

/** The deck card's title. */
export const deckTitle = cva("block text-7 font-bold tracking-[-0.015em] leading-[1.15]");

/** The deck card's year, kind and rating. */
export const deckMeta = cva("block mt-1 text-3 text-muted-foreground");

/** Why the suggestion is made, set off by a rule on its left. */
export const deckReason = cva(
  "block mt-3 text-2 text-muted-foreground border-l-2 border-border pl-4 leading-[1.4] " +
    "[&_b]:text-foreground [&_b]:font-semibold",
);

/**
 * The verb a swipe shows under the thumb, on the side the card is going. The two
 * directions do not mean the same thing: « Passer » decides nothing and does not
 * wear the colour of a refusal; « Pas intéressé » removes the card.
 */
export const deckHint = cva(
  "dhint absolute top-[14px] py-2 px-5 rounded-full border-2 text-3 font-extrabold tracking-[0.03em] opacity-0 " +
    "[transition:opacity_var(--duration-1)_var(--ease-standard)] pointer-events-none",
  {
    variants: {
      side: {
        left:
          "l left-[14px] [transform:rotate(-9deg)] border-muted-foreground text-muted-foreground " +
          "[background:color-mix(in_oklab,var(--color-muted-foreground)_12%,var(--color-card))]",
        right:
          "r right-[14px] [transform:rotate(9deg)] border-danger text-danger " +
          "[background:color-mix(in_oklab,var(--color-danger)_14%,var(--color-card))]",
      },
    },
  },
);
