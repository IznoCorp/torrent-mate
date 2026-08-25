// THE SHARED VOCABULARY, AS TYPED VARIANTS — D2 in force.
//
// A CLASS FACTORY RATHER THAN A COMPONENT, and the choice is not stylistic.
// Wrapping these primitives in React components would change the DOM: a
// `<Section>` adds nothing visible but every element it replaces would be
// re-created, and this wave's whole claim is that the rendering did not move.
// A factory returns a class string, so the markup is byte-identical and the
// oracle can still say so — while the utilities live in ONE place and the
// variants are checked by the compiler, which is what D2 asks for.
//
// THE ORIGINAL CLASS NAME IS KEPT AT THE FRONT of every string, emptied of
// style. The engine selects several of these by CSS class, and a name removed
// here would break a reader while the styling moved cleanly. It is an identity
// anchor now, which is what D4 wants an anchor to be.
import { cva } from "class-variance-authority";

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

/**
 * The status dot — it qualifies what follows it.
 *
 * The tone class is kept beside the utility on purpose: it is the name the
 * interface uses for that state, and several readers still spell it that way.
 *
 * NAMED `statusDot` RATHER THAN AFTER ITS CLASS: the class is `pip`, and that
 * word is on the engine's declared French-debt list, reserved to the file that
 * dies at L13. A class name in markup is one thing; an exported identifier is
 * another, and the guard is right to keep them apart.
 */
export const statusDot = cva("pip w-[8px] h-[8px] rounded-full flex-none", {
  variants: {
    tone: {
      warning: "warning bg-warning",
      danger: "danger bg-danger",
      info: "info bg-info",
      waiting: "waiting bg-waiting",
      success: "success bg-success",
      neutral: "neutral bg-neutral-signal",
    },
  },
});

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
 * ONE ACTION-BUTTON SYSTEM.
 *
 * Every full-width action has its content CENTRED. The shipped component
 * left-aligned sheet rows like a menu; the product decision is the opposite,
 * and a product decision outranks the original component.
 *
 * One scale everywhere: height 44 — the touch target — radius 8, weight 600,
 * 13px. Before this rule, heights ranged from 35 to 45px depending on the
 * surface, and the same gesture did not look the same in two places, which is
 * exactly what « uniform » means.
 *
 * A button carrying an ICON is left-aligned instead, and that is held by a
 * `:has()` rule in the base layer rather than by a variant: it follows
 * STRUCTURE, so nobody has to remember to add a label.
 */
export const actionButton = cva(
  "flex items-center justify-center gap-4 w-full min-h-[44px] py-5 px-6 " +
    "rounded-3 text-4 font-semibold text-center",
);

/** An empty surface: it says WHY, and offers a way out. */
export const emptyNote = cva(
  "empty border border-dashed border-border rounded-3 py-8 px-7 text-center " +
    "text-3 text-muted-foreground leading-[1.5]",
);

/** A surface in error: it names the cause and offers a retry. */
export const surfaceError = cva(
  "surferr [border:1px_solid_color-mix(in_oklab,var(--color-danger)_45%,transparent)] " +
    "[background:color-mix(in_oklab,var(--color-danger)_8%,transparent)] " +
    "rounded-3 p-7 text-3 leading-[1.5]",
);

/**
 * The live strip: a pulsing dot and a sentence about what is happening now.
 *
 * Shared — Arrivées and Acquisition both draw one.
 */
export const liveStrip = cva(
  "live flex items-center gap-4 border border-border rounded-3 py-4 px-5 " +
    "text-2 text-muted-foreground bg-card",
);

/**
 * The strip's dot. Its pulse is declared in the base layer under a
 * reduced-motion guard — motion is a designed state, not a fallback.
 */
export const liveDot = cva("d w-[7px] h-[7px] rounded-full bg-info flex-none");

/** The emphasis inside a live strip. */
export const liveEmphasis = cva("text-foreground font-semibold");

/**
 * The cross-reference note: « this medium is also … », with a link.
 *
 * A WRAPPING SENTENCE MUST NOT BE LAID OUT AS FLEX SIBLINGS. Each fragment
 * became its own column and the line read as three broken stacks. It is one
 * paragraph, `display: block`, with the link on its own row.
 */
export const crossReference = cva(
  "crossref block w-full leading-[1.45] border border-dashed border-border " +
    "bg-transparent text-muted-foreground text-3 text-left p-5 rounded-3",
);

/** The emphasis inside a cross-reference. */
export const crossReferenceStrong = cva("text-foreground font-semibold");

/** The cross-reference's link, on its own row. */
export const crossReferenceLink = cva("block mt-3 text-primary font-semibold whitespace-nowrap");

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
  "flex-1 min-w-0 [border:0] py-4 px-0 rounded-2 text-4 font-semibold " +
    "bg-transparent text-muted-foreground whitespace-nowrap overflow-hidden text-ellipsis " +
    "transition-[background-color,color] duration-200 ease-standard " +
    "aria-selected:bg-background aria-selected:text-foreground " +
    "aria-selected:[box-shadow:var(--mq-shadow-seg)]",
);

/** The count a tab carries. */
export const segmentCount = cva(
  "n text-2 font-bold ml-2 py-1 px-2 rounded-full bg-primary text-primary-foreground",
);

/** The « more » button beside the segment. */
export const moreButton = cva(
  "more flex-none w-[40px] h-[40px] rounded-3 border border-border bg-transparent " +
    "text-muted-foreground grid place-items-center",
);

/** The filter zone under the tabs: the search field, the pills, the switch. */
export const filterZone = cva("filters pt-0 px-7 pb-4 border-b border-border bg-background");

/** The search field's frame. */
export const searchField = cva("search flex items-center gap-4 bg-muted rounded-3 py-0 px-5");

/** The magnifier, and the clear button's icon. */
export const searchIcon = cva("w-[15px] h-[15px] text-muted-foreground flex-none");

/**
 * The search input.
 *
 * `text-6` IS 16px AND THAT IS NOT A STYLE CHOICE: below it, iOS Safari zooms
 * a focused field, and the viewport meta no longer forbids the zoom because
 * forbidding it failed WCAG 1.4.4 (D-L06-6).
 */
export const searchInput = cva(
  // THE FONT IS INHERITED PROPERTY BY PROPERTY, and neither shorthand works
  // here. `font-[inherit]` sets the FAMILY alone and left line-height at the
  // browser's input default — 0.6px. `[font:inherit]` is the real shorthand
  // and resets the SIZE too, and utilities carry no order I control, so it
  // raced `text-6` and won — 2.7px, the wrong way. Named one at a time, the
  // declarations touch different properties and cannot race at all.
  "flex-auto min-w-0 [border:0] bg-transparent text-foreground " +
    "[font-family:inherit] [font-weight:inherit] [font-style:inherit] " +
    "[line-height:inherit] text-6 " +
    "py-4 px-0 outline-none placeholder:text-muted-foreground",
);

/**
 * The clear button.
 *
 * Transplanted from the app's own stylesheet, where the class was used in
 * markup without ever having been ported — so the button had no size of its
 * own: 26px, below the touch target. It is 32px here, and the gap with the app
 * is a declared exception.
 */
export const searchClear = cva(
  "searchclear flex-none grid place-items-center w-[32px] h-[32px] -mr-4 " +
    "[border:0] rounded-full bg-transparent text-muted-foreground",
);

/** The row holding the filter pills and the view switch. */
export const pillBar = cva("pillbar flex items-center gap-0 mt-4");

/**
 * The pills' horizontal scroller.
 *
 * `touch-pan-x touch-pan-y` is COMPOSITOR-FACING and held by
 * `scripts/check-compositor-css.py`: it reserves both axes for scrolling so
 * the train cannot be mistaken for a swipe gesture.
 */
export const pillScroll = cva(
  "pillscroll flex-auto min-w-0 flex flex-nowrap gap-3 overflow-x-auto " +
    "[scrollbar-width:none] [&::-webkit-scrollbar]:hidden touch-pan-x touch-pan-y pr-4",
);

/**
 * One filter pill.
 *
 * `group` is here so the COUNT inside can answer the pill's pressed state:
 * `aria-pressed` is already on the button for assistive technology, and the
 * count reads it rather than carrying a second name for the same fact.
 */
export const filterPill = cva(
  "pill group flex-none text-3 font-semibold py-2 px-5 rounded-full border border-border " +
    "bg-transparent text-muted-foreground whitespace-nowrap " +
    "aria-pressed:bg-primary aria-pressed:border-primary aria-pressed:text-primary-foreground",
);

/**
 * The count a pill carries.
 *
 * SECONDARY IS A TONE, NOT AN OPACITY. Written as `opacity` it blended into
 * whatever sat behind it, so the tone reaching the eye was one the palette
 * never declared — the muted label lost a third of its separation and landed
 * under AA (D-L06-5).
 */
export const filterPillCount = cva(
  "c ml-2 font-medium text-pill-count-foreground " +
    "group-aria-pressed:text-pill-count-foreground-selected",
);

/** The view switch's wrapper, with its own divider drawn by a pseudo-element. */
export const viewSwitchWrap = cva(
  "vswwrap flex-none flex items-center gap-4 pl-4 bg-background " +
    "before:content-[''] before:w-[1px] before:h-[22px] before:bg-border",
);

/** The view switch itself. */
export const viewSwitch = cva("vsw flex gap-1 p-1 bg-muted rounded-3");

/** One button of the view switch. */
export const viewSwitchButton = cva(
  "w-[32px] h-[28px] [border:0] rounded-2 bg-transparent text-muted-foreground grid place-items-center",
);

/** The « N titles » line under the filters. */
export const countLine = cva(
  "countline flex items-center gap-3 pt-4 px-7 pb-0 text-2 text-muted-foreground",
);

/** The action at the end of the count line. */
export const countLineAction = cva(
  "ml-auto [border:0] bg-transparent text-primary-text text-2 font-semibold " +
    "flex items-center gap-2 p-0",
);
