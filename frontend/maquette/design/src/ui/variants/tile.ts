// THE TILE AND THE POSTER GRID, AS TYPED VARIANTS — the picture every gallery draws.
//
// A FILE OF ITS OWN, because the tile is one subject and the files the barrel
// re-exports had no room left for it under the module ceiling.
//
// EVERY FACTORY KEEPS ITS IDENTITY CLASS AT THE FRONT, but two. A rule reads
// `.sel` and `.tilebadge`, and R77 reads the suggestion feed's grid by its first
// class, `gallery`. `tile()` and
// `tileSubtitle()` lead with a utility and the markup writes `tile` and `fr`
// beside them: `fr` is claimed by the fact rows' value already.
//
// EVERY BRANCH IS ONE STRING LITERAL: `harness/factories.py` reads a factory's
// base through its literals, and its branches one per literal.
import { cva } from "../cva";

/**
 * A grid of posters: three columns on a phone, one more at each width the port
 * reaches. A container query, because the frame is narrower than the window it
 * sits in, and the port is what the columns have room in.
 */
export const posterGrid = cva(
  "gallery grid grid-cols-[repeat(3,minmax(0,1fr))] gap-5 " +
    "@min-[460px]/port:grid-cols-[repeat(4,minmax(0,1fr))] " +
    "@min-[620px]/port:grid-cols-[repeat(5,minmax(0,1fr))] " +
    "@min-[820px]/port:grid-cols-[repeat(6,minmax(0,1fr))]",
);

/**
 * A tile: a poster, its title and a line under it, as one control. A `group`,
 * because a pressed tile repaints its poster and its check from its own
 * `aria-pressed`. A MUTED tile dims, and says `off` for the readers that ask.
 */
export const tile = cva(
  "group relative min-w-0 [border:0] [background:transparent] p-0 text-left block w-full " +
    // A held tile offers the long press, never the browser's own menu or a drag of its picture.
    "select-none [-webkit-touch-callout:none] [&_img]:[-webkit-user-drag:none] [&_img]:[-webkit-touch-callout:none]",
  { variants: { muted: { true: "off" } } },
);

/** The poster's box, its size declared so a late picture moves nothing. */
export const tilePoster = cva(
  "p block w-full aspect-[2/3] rounded-2 text-8 leading-none overflow-hidden bg-muted " +
    "group-aria-pressed:[outline:2px_solid_var(--color-primary)] group-aria-pressed:[outline-offset:-2px] " +
    // The picture fills the box it is given, at the box's size and not its own.
    "[&>img]:relative [&>img]:grid [&>img]:place-items-center [&>img]:w-full [&>img]:h-full " +
    "[&>img]:object-cover [&>img]:overflow-hidden " +
    "[&>img]:[background:linear-gradient(to_bottom_right,color-mix(in_oklab,var(--color-primary)_50%,transparent),var(--color-card),var(--color-muted))]",
  { variants: { muted: { true: "opacity-[0.42]" } } },
);

/** The title, on one line. */
export const tileTitle = cva("nm block text-2 mt-2 whitespace-nowrap overflow-hidden text-ellipsis", {
  variants: { muted: { true: "opacity-[0.55]" } },
});

/** The line under the title, on one line, its figures aligned. */
export const tileSubtitle = cva(
  "block text-1 text-muted-foreground tabular-nums whitespace-nowrap overflow-hidden text-ellipsis",
);

/**
 * The badge over a poster's corner.
 *
 * ONE TONE CARRIES A FILL, the neutral scrim a rating reads over. Every other
 * tone a caller names paints none, and that is what they have always painted:
 * the fills they were drawn with named custom properties no stylesheet declares,
 * so the badge's ring and its figure were all there ever was.
 */
export const tileBadge = cva(
  "tilebadge absolute top-[5px] right-[5px] grid place-items-center h-[17px] min-w-[17px] py-0 px-2 " +
    "rounded-full border-2 border-background text-1 font-bold text-white",
  { variants: { tone: { overlay: "[background:var(--color-tile-overlay)]" } } },
);

/** Which tone a badge is drawn in. */
export type TileBadgeTone = "overlay";

/**
 * The selection check. Over a tile it is a ring in the poster's corner that fills
 * when the tile is pressed; in a selection row it stands in line, and the row
 * paints the pressed state itself.
 */
export const selectionCheck = cva("sel", {
  variants: {
    within: {
      tile:
        "absolute top-[6px] left-[6px] w-[21px] h-[21px] rounded-full border-2 border-white " +
        "[background:var(--color-scrim-soft)] grid place-items-center text-transparent " +
        "[&_svg]:w-[13px] [&_svg]:h-[13px] group-aria-pressed:[background:var(--color-primary)] " +
        "group-aria-pressed:border-primary group-aria-pressed:text-primary-foreground",
      row: "static flex-[0_0_auto]",
    },
  },
});
