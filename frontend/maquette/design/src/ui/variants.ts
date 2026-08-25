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
