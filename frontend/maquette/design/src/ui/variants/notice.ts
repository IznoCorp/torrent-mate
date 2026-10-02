// THE NOTICE — a surface that says something about a read, in a tone.
//
// ONE DRAWING FOR AN ERROR AND FOR A NOTICE THAT IS NOT ONE. The error surface
// was repainted by inline styles into a warning (TMDB disconnected) and an
// information (a folder to identify), and the settings drew their banners with
// an error's variant; the tone is the only thing that differs, so it is a
// variant — and `role="alert"` stays the danger tone's alone (`SurfaceError`).
import { cva } from "../cva";

/** A surface that names what happened, in the tone of what it means. */
export const surfaceError = cva(
  "surferr rounded-3 p-7 text-3 leading-[1.5] " +
    // THE CAUSE LEADS AND THE RETRY SPANS, wherever the surface draws them.
    "[&_b]:block [&_b]:mb-2 " +
    "[&_button]:mt-5 [&_button]:w-full [&_button]:[border:1px_solid_var(--color-border)] " +
    "[&_button]:bg-transparent [&_button]:text-foreground [&_button]:text-3 " +
    "[&_button]:font-semibold [&_button]:p-4 [&_button]:rounded-2",
  {
    variants: {
      tone: {
        danger: "[border:1px_solid_color-mix(in_oklab,var(--color-danger)_45%,transparent)] " +
          "[background:color-mix(in_oklab,var(--color-danger)_8%,transparent)] [&_b]:text-danger-text",
        warning: "[border:1px_solid_color-mix(in_oklab,var(--color-warning)_45%,transparent)] " +
          "[background:color-mix(in_oklab,var(--color-warning)_8%,transparent)] [&_b]:text-warning-text",
        info: "[border:1px_solid_color-mix(in_oklab,var(--color-info)_45%,transparent)] " +
          "[background:color-mix(in_oklab,var(--color-info)_8%,transparent)] [&_b]:text-info-text",
        // AN OUTCOME THAT IS GOOD NEWS — an obligation met: neither a fault nor a mere
        // information, and drawn in the palette's own success tone, text token included.
        success: "[border:1px_solid_color-mix(in_oklab,var(--color-success)_45%,transparent)] " +
          "[background:color-mix(in_oklab,var(--color-success)_8%,transparent)] [&_b]:text-success-text",
      },
    },
    defaultVariants: { tone: "danger" },
  },
);
