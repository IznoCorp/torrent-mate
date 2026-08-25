// ACQUISITION'S ADD SCREEN, as typed variants.
//
// `.btnprimary` and `.segmini` are NOT here: the engine emits both, so their
// rules are in `src/styles/legacy.css` with their date of death (D-L07-5).
import { cva } from "../../ui/cva";

/** The add screen's form block. */
export const addForm = cva("addform pt-6 px-7 pb-0");

/** A row of the form: the field, then the button that acts on it. */
export const addRow = cva("addrow flex gap-4 mt-4");

/** The « N results » line. */
export const resultCount = cva("rescount pt-6 px-7 pb-0 text-2 text-muted-foreground");

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
