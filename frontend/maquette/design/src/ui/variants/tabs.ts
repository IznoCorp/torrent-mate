// THE TAB BAR — one drawing, whatever page it lens.
//
// Split from `controls.ts` when that module reached its ceiling: a tab bar is a
// subject of its own, and `ui/tabs.tsx` is its one component.
import { cva } from "../cva";
import { tabBarBadge } from "./badge";

/**
 * The view tabs' row: a segmented control and, sometimes, a « more » button.
 *
 * Sticky at the top of its scrollport, so the lens a page is read through
 * stays reachable while the list under it scrolls.
 */
export const viewTabs = cva(
  "viewtabs flex gap-4 items-center pt-5 px-7 pb-4 sticky top-0 z-30 bg-background",
);

/** The segmented control itself. */
export const segment = cva(
  "seg flex-auto flex gap-2 p-2 bg-muted rounded-3 min-w-0",
);

/**
 * One tab of the segment.
 *
 * The selected state is an `aria-selected` VARIANT rather than a class: the
 * attribute is already there for assistive technology, and a second name for
 * the same fact is a second thing to keep in step.
 */
export const segmentTab = cva(
  "flex-1 min-w-0 min-h-[44px] [border:0] py-4 px-0 rounded-2 text-4 font-semibold " +
    "bg-transparent text-muted-foreground whitespace-nowrap overflow-hidden text-ellipsis " +
    "transition-[background-color,color] duration-200 ease-standard " +
    "aria-selected:bg-background aria-selected:text-foreground " +
    "aria-selected:[box-shadow:var(--mq-shadow-seg)]",
);

/** The count a tab carries: the bar's badge, placed inline. */
export const segmentCount = (): string => tabBarBadge({ placement: "inline" });

/** The « more » button beside the segment, at the finger's floor. */
export const moreButton = cva(
  "more flex-none w-[44px] h-[44px] rounded-3 border border-border bg-transparent " +
    "text-muted-foreground grid place-items-center",
);
