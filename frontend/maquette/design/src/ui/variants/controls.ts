// WHAT THE OPERATOR TOUCHES — buttons, switches, options, filters and tabs.
//
// ONE OF THE THREE FILES `ui/variants.ts` RE-EXPORTS. They were one module
// until it reached 518 lines against a ceiling of 400 (invariant 6). The split
// follows a SUBJECT, and the barrel keeps every call site unchanged.
import { cva } from "../cva";

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

/**
 * The switch — FIXED dimensions, always the same.
 *
 * A « Oui/Non » chip inside a flex row took the label's height
 * (`align-items: stretch`) and changed width with the word, so two identical
 * toggles had different sizes depending on the section. A switch also states
 * its value through its SHAPE, not only through a word — hence the knob, drawn
 * as an `::after` and moved by a transform.
 *
 * The checked state reads `aria-checked`, which is already there for assistive
 * technology.
 */
export const toggleSwitch = cva(
  "switch flex-none self-center relative w-[46px] h-[28px] min-h-[28px] p-0 " +
    "rounded-full border border-border bg-muted " +
    "transition-[background-color,border-color] duration-200 ease-standard " +
    "after:content-[''] after:absolute after:top-[2px] after:left-[2px] " +
    "after:w-[22px] after:h-[22px] after:rounded-full after:bg-muted-foreground " +
    "after:transition-[transform,background-color] after:duration-200 after:ease-standard " +
    "aria-checked:bg-primary aria-checked:border-primary " +
    "aria-checked:after:[transform:translateX(18px)] aria-checked:after:bg-primary-foreground " +
    "disabled:opacity-50",
);

/**
 * A settings row.
 *
 * It does not stretch: the label can wrap without dragging the control with it.
 */
export const settingRow = cva("setting items-start [&>span:first-child]:pr-2");

/** A group of options. */
export const optionList = cva("optlist flex flex-col gap-3");

/**
 * One option.
 *
 * SHAPE STATES THE RULE: a circle means one choice, a square means several.
 * Identical pills for both said nothing, and their width followed the word
 * length, so two options of the same group had different sizes. The row is
 * full width here: every option is identical, in every group.
 *
 * Checked is read from `aria-checked`, which is already there for assistive
 * technology.
 */
export const option = cva(
  // `group` so the MARK inside can read this row's `aria-checked` — the
  // attribute is already there for assistive technology, and a second name for
  // the same fact is a second thing to keep in step.
  //
  // The checked border is a VARIANT SELECTOR, so it carries an attribute's
  // specificity and beats the plain `border-border` beside it whatever order
  // the generator picks. That is why this one needs no `false` branch, where
  // the toggle and the release row did.
  // `bg-transparent` IS NOT DECORATION: dropped, the browser paints its own
  // button grey — rgb(239,239,239) under near-white text, and the
  // accessibility audit read ten contrast failures. The oracle could not:
  // these buttons sit in none of its 33 measured regions.
  "opt group flex items-center gap-5 w-full min-h-[48px] py-4 px-6 border border-border " +
    "rounded-3 bg-transparent text-left aria-checked:border-primary " +
    "aria-checked:[background:color-mix(in_oklab,var(--color-primary)_8%,transparent)]",
);

/**
 * The option's mark.
 *
 * A checked radio is a solid dot; a checked box is a tick. Two distinct shapes,
 * including once checked — which is the whole point of the rule above.
 */
export const optionMark = cva(
  "mark relative flex-none w-[20px] h-[20px] border-2 " +
    "transition-[border-color,background-color] duration-150 ease-standard " +
    "group-aria-checked:border-primary group-aria-checked:bg-primary",
  {
    variants: {
      kind: {
        radio:
          "rounded-full group-aria-checked:after:content-[''] group-aria-checked:after:absolute group-aria-checked:after:inset-[4px] group-aria-checked:after:rounded-full group-aria-checked:after:bg-primary-foreground",
        check:
          "rounded-2 group-aria-checked:after:content-[''] group-aria-checked:after:absolute group-aria-checked:after:left-[5px] group-aria-checked:after:top-[1px] group-aria-checked:after:w-[5px] group-aria-checked:after:h-[10px] group-aria-checked:after:border-solid group-aria-checked:after:border-primary-foreground group-aria-checked:after:[border-width:0_2px_2px_0] group-aria-checked:after:[transform:rotate(45deg)]",
      },
    },
  },
);

/**
 * The option's label.
 *
 * A HINT THAT WRAPS makes its row taller than its neighbours and the group
 * loses its single size. One line only.
 */
export const optionLabel = cva(
  "lb flex-1 min-w-0 text-4 font-medium " +
    "[&_small]:block [&_small]:overflow-hidden [&_small]:text-ellipsis [&_small]:whitespace-nowrap " +
    "[&_small]:text-2 [&_small]:font-normal [&_small]:text-muted-foreground [&_small]:mt-1",
);

/** What kind of choice a group is. */
export const optionKind = cva("optkind text-2 text-muted-foreground mt-0 mx-0 mb-3");

/** A hint under a quality setting. */
export const qualityHint = cva("qhint text-2 text-muted-foreground leading-[1.45]");

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

/** The filter zone under the tabs: the search field, the pills, the switch. */
export const filterZone = cva("filters pt-0 px-7 pb-4 border-b border-border bg-background");

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
