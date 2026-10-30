// THE COUNT BADGE — one drawing for every number in a filled pill.
//
// The bar's badge, the menu's, the drawer's and a tab's count were three
// drawings of one need; a placement is the only thing that differs.
import { cva } from "../cva";

/* PRIMARY, not danger: red is reserved for the « ? » of an unavailable
   counter. The outline is the sidebar's colour so the badge reads as lifted off
   the bar rather than punched into it. */
export const tabBarBadge = cva(
  "inline-flex h-[18px] min-w-[18px] items-center justify-center px-2 rounded-full bg-primary "
    + "text-primary-foreground text-2 font-semibold leading-none [font-variant-numeric:tabular-nums]",
  {
    variants: {
      // ONE BADGE, placed: on a control's corner (the bar, the menu), at the
      // end of a row (the drawer), or inline after a word (a tab).
      placement: {
        corner: "navbadge absolute right-[-10px] top-[-6px] [box-shadow:var(--mq-shadow-badge)] "
          + "[outline:2px_solid_var(--color-sidebar)]",
        end: "count ml-auto",
        inline: "n ml-2",
      },
    },
    defaultVariants: { placement: "corner" },
  },
);

/** The count at the end of a drawer entry: the bar's badge, placed at the row's end. */
export const drawerEntryCount = (): string => tabBarBadge({ placement: "end" });
