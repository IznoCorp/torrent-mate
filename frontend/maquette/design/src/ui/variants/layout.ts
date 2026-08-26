// THE SHELL OF A SURFACE — what holds a page, a screen or a sheet, and the
// chrome around it.
//
// ONE OF THE THREE FILES `ui/variants.ts` RE-EXPORTS. They were one module
// until it reached 518 lines against a ceiling of 400 (invariant 6). The split
// follows a SUBJECT, and the barrel keeps every call site unchanged.
import { cva } from "../cva";

/** The page body: the column every surface's sections stack in. */
export const body = cva("body flex flex-col gap-7 pt-5 px-7 pb-8");

/** One section of a page. */
export const section = cva("sec flex flex-col gap-4");

/** A section's header row: a title, an optional status dot, a count pushed right. */
export const sectionHead = cva(
  "sechead flex items-center gap-4 w-full [border:0] bg-transparent py-1 px-0 text-left",
);

/** The section title. */
export const sectionTitle = cva("t text-3 font-bold tracking-[0.01em]");

/** The count at the end of a section header. */
export const sectionCount = cva("k ml-auto text-2 font-bold text-muted-foreground");

/** A screen: the layer that slides in over a page. */
export const screen = cva(
  "screen absolute inset-0 bg-background z-[45] flex flex-col " +
    "[transform:translateX(100%)] transition-[transform] duration-300 ease-standard invisible",
);

/**
 * A screen's top bar.
 *
 * ONE back control for every page. A floating variant over the image created a
 * second design — white — which on screens without an image OVERLAPPED the
 * title instead of pushing it. A bar in the flow can cover nothing, and it
 * reads the same everywhere.
 */
export const screenBar = cva("screenbar flex-none flex items-center gap-3 py-5 px-6 bg-background");

/** The back control itself. */
export const backAction = cva(
  "fback flex items-center gap-2 [border:0] bg-transparent text-primary text-4 font-semibold py-2 px-1",
);

/**
 * A scrollport — the element a surface scrolls inside.
 *
 * FIVE SCREENS WEAR THIS BESIDE THE SHELL, and that is what made converting it
 * as « the shell's `<main>` » wrong: the class was a shared primitive all
 * along. Its utilities went onto one element in phase 5, and the five screens
 * silently stopped scrolling — the oracle could not see it, because a screen's
 * viewport is not one of the 33 measured regions, and it surfaced as a lost
 * scroll POSITION two rules away.
 *
 * It ESTABLISHES the container the gallery's three `@container port` queries
 * ask. A component asks the width it HAS, never the window's (invariant 12).
 */
export const scrollport = cva(
  "port @container/port flex-auto min-h-0 overflow-y-auto overflow-x-clip " +
    "overscroll-y-none [-webkit-overflow-scrolling:touch] " +
    "pb-[calc(var(--tm-bottom-bar-h,0px)+var(--spacing-7))]",
);

/** The scrim behind a sheet. */
export const sheetScrim = cva(
  "scrim absolute inset-0 bg-scrim z-[46] transition-[opacity] duration-200 ease-standard",
  { variants: { open: { true: "open opacity-100 visible", false: "opacity-0 invisible" } },
    defaultVariants: { open: false } },
);

/**
 * The bottom sheet.
 *
 * THE TAB BAR SITS ABOVE THE LAYERS (z-50), so a sheet must reserve its height
 * or its last actions are unreachable — internal scrolling stops before them.
 * Same rule as for screens, extended to sheets and dialogs: one defect family
 * deserves one rule, not three.
 */
export const bottomSheet = cva(
  "sheet absolute left-0 right-0 bottom-0 z-[47] bg-popover border-t border-border " +
    "rounded-t-4 rounded-b-none max-h-[78%] flex flex-col " +
    // The transition lives in the base because the state that CANCELS it is
    // not a prop: the drag handler writes `dragging` straight to the DOM
    // through a ref, exactly as the legacy one did, so `.sheet.dragging`
    // stays a rule in the residue. A variant here would never be told.
    "transition-[transform] duration-300 ease-standard",
  {
    variants: {
      open: { true: "open [transform:none] visible", false: "[transform:translateY(100%)] invisible" },
    },
    defaultVariants: { open: false },
  },
);

/**
 * The grab handle.
 *
 * `touch-none` is COMPOSITOR-FACING and held by `check-compositor-css.py`: a
 * drag on the handle is never a scroll.
 */
export const sheetGrab = cva(
  "sheetgrab h-[22px] grid place-items-center flex-none touch-none cursor-grab " +
    "before:content-[''] before:w-[36px] before:h-[4px] before:rounded-full before:bg-border",
);

/** The sheet's scrolling viewport. */
export const sheetViewport = cva(
  "sheetin overflow-y-auto pt-1 px-7 pb-[calc(var(--tm-bottom-bar-h,0px)+var(--spacing-8))]",
);

/** The sheet's title. */
export const sheetTitle = cva("sheettitle text-6 font-bold tracking-[-0.01em] mt-0 mx-0 mb-1");

/** The line under it. */
export const sheetMeta = cva("sheetmeta text-3 text-muted-foreground mb-7");

/**
 * The sheet's head.
 *
 * A head carrying a POSTER aligns to the TOP: an 84px picture next to two short
 * lines centred against it leaves the title floating in the middle of nothing.
 * It also breathes below rather than inside — against an 84px picture the same
 * 4px reads as nothing at all.
 */
export const sheetHead = cva(
  "sheethead flex gap-6 [&_.sheetmeta]:mb-3 " +
    "[&_.sheetsub]:block [&_.sheetsub]:mt-1 [&_.sheetsub]:text-3 [&_.sheetsub]:text-muted-foreground",
  {
    variants: {
      withPoster: {
        true: "withposter items-start pb-0 mb-6",
        false: "items-center pb-2",
      },
    },
    defaultVariants: { withPoster: false },
  },
);

/** The identity block inside the head. */
export const sheetIdentity = cva("sheetid min-w-0 flex-1");

/** The avatar, at the size a sheet gives it. */
export const sheetAvatar = cva("big w-[42px] h-[42px] text-6");

/**
 * An entry that is COMING says so instead of being absent: a menu that grows an
 * item later teaches its shape twice.
 */
export const comingSoon = cva(
  "soon ml-auto text-1 font-bold tracking-[0.03em] py-1 px-3 rounded-full bg-muted text-muted-foreground",
);

/** The sheet's actions. `secondary` separates what is not the main path. */
export const sheetActions = cva("sheetacts flex flex-col gap-3 mt-2 mx-0 mb-7", {
  variants: { secondary: { true: "secondary mt-8 pt-7 border-t border-border", false: "" } },
  defaultVariants: { secondary: false },
});

/**
 * A paragraph that GUIDES the reader of the application, not of the design.
 *
 * IT EXISTS BECAUSE `.note` DID NOT DISTINGUISH THE TWO, and the distinction is
 * load-bearing: `.note` is the prototype's annotation, styled in the harness
 * sheet and hidden until the reader asks for it — so a paragraph wearing it is
 * invisible by default. Four paragraphs wearing it were not annotations at all.
 * They tell the operator what a control does, what a displayed value means, or
 * what an action is about to do, and one of them is the only sentence saying
 * that a maintenance rubric DELETES.
 *
 * THE TEST, applied to all twenty-seven: a paragraph is an annotation if it
 * addresses the reader of the MAQUETTE — what changed, what was drawn anew,
 * which section of the constitution it serves. It is guidance if it addresses
 * the operator USING the application. Twenty-three were annotations and stay
 * `.note`; four are guidance and wear this.
 *
 * It carries the annotation's own shape deliberately — the reader has learnt
 * that a left-bordered tinted paragraph is an explanation — in the muted tone
 * rather than the accent, because guidance is part of the page and an
 * annotation is a layer over it.
 */
export const guidance = cva(
  "guidance border-l-[3px] border-border bg-muted rounded-r-2 py-4 px-5 " +
    "text-2 leading-[1.5] text-foreground",
);

/** A note stating a rule, set off by a rule of its own. */
export const ruleNote = cva(
  "rulenote mt-0 mx-0 mb-7 text-3 leading-[1.45] text-muted-foreground " +
    "border-l-2 border-border pt-1 pr-0 pb-1 pl-5",
);
