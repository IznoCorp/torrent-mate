// CONFIGURATION — the rows, the panel's fields and the save bar, as typed
// variants.
//
// A SETTING ROW IS A LIST ROW, NOT A FORM FIELD: the control lives in the
// panel that opens over it (R56), deliberately, because a screen of live
// inputs on a phone is a screen where every scroll risks changing something.
import { cva } from "../../ui/cva";

/** A topic: a rubric of settings, or of maintenance actions. */
export const topicRow = cva(
  "topic flex items-center gap-6 w-full text-left border border-border " +
    "rounded-3 bg-card p-6 mb-4 text-foreground " +
    "[&_.rt]:block [&_.rt]:text-5 [&_.rt]:font-semibold " +
    "[&_.rs]:block [&_.rs]:mt-1 [&_.rs]:text-3 [&_.rs]:text-muted-foreground [&_.rs]:leading-[1.4] " +
    "[&_.rn]:flex-none [&_.rn]:text-3 [&_.rn]:font-semibold [&_.rn]:text-muted-foreground",
);

/**
 * One setting, as a row.
 *
 * `modified` marks a setting the operator has TOUCHED but not yet written. It
 * is marked on the ROW, where it is read, and not only in a counter at the
 * bottom — hence the bar drawn as a `::before` rather than a colour change
 * nobody would notice mid-list.
 */
export const settingsRow = cva(
  // `border-0 border-b`, NOT `[border:0] border-b`. The arbitrary SHORTHAND
  // is placed among the arbitrary properties and reset the bottom edge the
  // `border-b` beside it had just set — the row lost its separator. The two
  // width utilities are sorted by the generator, all-sides before one-side,
  // which is the order the prototype wrote by hand.
  "settingrow flex items-center gap-5 w-full text-left border-0 " +
    "border-b border-border bg-transparent py-5 px-1 text-foreground last:border-b-0 " +
    "[&_.rl]:block [&_.rl]:min-w-0 [&_.rl]:flex-1 [&_.rl]:text-4 " +
    "[&_.rf]:block [&_.rf]:mt-1 [&_.rf]:text-2 [&_.rf]:text-muted-foreground [&_.rf]:font-mono " +
    "[&_.rv]:flex-none [&_.rv]:max-w-[45%] [&_.rv]:overflow-hidden [&_.rv]:text-ellipsis " +
    "[&_.rv]:whitespace-nowrap [&_.rv]:text-3 [&_.rv]:font-semibold [&_.rv]:[font-variant-numeric:tabular-nums]",
  {
    variants: {
      modified: {
        true:
          "modified [&_.rv]:text-primary before:content-[''] before:w-[3px] " +
          "before:self-stretch before:rounded-full before:bg-primary before:-mr-2",
        false: "",
      },
    },
    defaultVariants: { modified: false },
  },
);

/** A field inside the panel. `list` stacks its rows instead of laying them out. */
export const panelField = cva("field flex mt-5", {
  variants: {
    // `items-*` and `gap-*` live in BOTH branches, never in the base: a
    // property a variant may change cannot sit where it would race it.
    list: {
      true: "list flex-col items-stretch gap-3",
      false: "items-center gap-5",
    },
  },
  defaultVariants: { list: false },
});

/**
 * The field's input.
 *
 * 16px, and that is not a style choice: below it iOS Safari zooms a focused
 * field, and the viewport meta no longer forbids the zoom because forbidding it
 * failed WCAG 1.4.4 (D-L06-6). The font is inherited property by property —
 * the `font` shorthand would race the size (phase 9's lesson).
 */
export const fieldInput = cva(
  "fieldinput flex-1 min-w-0 py-5 px-6 rounded-3 border border-border bg-background " +
    "text-foreground [font-weight:inherit] [font-style:inherit] " +
    "[line-height:inherit] text-6 " +
    "focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-1",
  {
    variants: {
      mono: { true: "mono font-mono", false: "[font-family:inherit]" },
    },
    defaultVariants: { mono: false },
  },
);

/** The unit a numeric field carries. */
export const fieldUnit = cva("fieldunit flex-none text-3 text-muted-foreground");

/** The label of a field that has no input of its own. */
export const fieldLabel = cva("fieldlabel text-4 text-muted-foreground");

/** The switch IS the whole field: nothing to type, nothing to validate. */
export const fieldToggle = cva(
  "fieldtoggle flex-none w-[48px] h-[28px] p-1 [border:0] rounded-full flex " +
    "transition-[background-color] duration-200 ease-standard",
  {
    variants: {
      active: { true: "active bg-primary justify-end", false: "bg-muted" },
    },
    defaultVariants: { active: false },
  },
);

/** Its knob. */
export const fieldKnob = cva(
  "fieldknob w-[22px] h-[22px] rounded-full bg-white transition-[transform] duration-200 ease-standard",
);

/** One entry of a list field. */
export const listItem = cva(
  "litem flex items-center gap-4 py-4 px-6 rounded-3 border border-border bg-background text-4 " +
    "[&_span]:flex-1 [&_span]:min-w-0 [&_span]:overflow-hidden [&_span]:text-ellipsis [&_span]:whitespace-nowrap",
);

/** The control that removes one. */
export const listRemove = cva("lremove flex-none [border:0] bg-transparent text-muted-foreground p-1 flex");

/** The control that adds one. */
export const listAdd = cva(
  "ladd flex items-center justify-center gap-3 p-5 rounded-3 border border-dashed border-border " +
    "bg-transparent text-muted-foreground text-3 font-semibold",
);

/**
 * The save bar.
 *
 * It exists only when there is something to save, and it says WHAT it will
 * write — a save that names no file asks for trust nobody owes it. It sits
 * above the tab bar, like every other fixed thing.
 */
export const saveBar = cva(
  "savebar absolute left-0 right-0 bottom-[var(--tm-bottom-bar-h,0px)] z-40 flex items-center " +
    "gap-5 py-5 px-7 border-t border-border bg-background " +
    "[&_.sn]:flex-1 [&_.sn]:min-w-0 [&_.sn]:text-3 [&_.sn]:leading-[1.35] [&_.sn]:text-muted-foreground " +
    "[&_.sn_b]:block [&_.sn_b]:text-foreground [&_.sn_b]:text-4",
);

/** Its action. */
export const saveAction = cva(
  "flex-none [border:0] rounded-3 py-5 px-7 [font:600_var(--text-4)_'Geist',system-ui,sans-serif] " +
    "bg-primary text-primary-foreground disabled:opacity-50",
);
