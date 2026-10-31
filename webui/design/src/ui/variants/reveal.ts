// THE SHOW/HIDE CONTROL OF A SECRET FIELD — one icon button on the field's right edge.
//
// A SEPARATE FILE: `controls.ts` is already over the module ceiling (invariant 6), and a control
// that belongs to the sign-in form's field rather than to a row of buttons has a subject of its own.
import { cva } from "../cva";

/**
 * The wrapper that puts the button inside the field's box.
 *
 * The input keeps its own box and its own border (the gate's stylesheet draws them); the wrapper
 * only gives the button something to be positioned against.
 */
export const passwordRevealHost = cva("relative flex [&>input]:flex-1 [&>input]:min-w-0");

/**
 * The input's padding, making room for the button so a long secret never runs under it.
 *
 * `!` because the gate's field rule is unlayered and beats any layered utility; the room is the
 * button's 32 px and a spacing token.
 */
export const passwordRevealField = cva("pr-[calc(32px+var(--spacing-4))]!");

/**
 * The show/hide button, in its two named states.
 *
 * AT REST the drawing is muted; PRESSED (`aria-pressed="true"`) it takes the foreground. The state is
 * read from the attribute assistive technology is told, never from a second class. Tokens only.
 */
export const passwordReveal = cva(
  "absolute right-[var(--spacing-2)] top-1/2 -translate-y-1/2 inline-grid place-items-center " +
    "w-[32px] h-[32px] rounded-full [border:0] bg-transparent p-0 " +
    "text-muted-foreground aria-pressed:text-foreground " +
    "focus-visible:outline-2 focus-visible:outline-primary [&>svg]:w-[16px] [&>svg]:h-[16px] [&>svg]:flex-none",
);
