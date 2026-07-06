import { cva } from "class-variance-authority";

/**
 * Switch track style variants (design-system ``components/core/Switch``).
 *
 * Extracted from ``switch.tsx`` to satisfy the
 * ``react-refresh/only-export-components`` lint rule (as ``button-variants.ts``
 * and ``badge-variants.ts`` are). The track is the visible 38×22 rounded pill;
 * ``checked`` drives the fill colour and ``tone`` chooses between the primary
 * and success signal palettes.
 */
export const switchTrackVariants = cva(
  "relative inline-flex h-[22px] w-[38px] shrink-0 items-center rounded-full border transition-colors duration-200 ease-out motion-reduce:transition-none",
  {
    variants: {
      checked: {
        true: "bg-primary border-primary",
        false: "bg-input border-input",
      },
      tone: {
        primary: "",
        success: "",
      },
    },
    compoundVariants: [
      {
        checked: true,
        tone: "success",
        className: "bg-[var(--success)] border-[var(--success)]",
      },
    ],
    defaultVariants: {
      checked: false,
      tone: "primary",
    },
  },
);

/**
 * Switch thumb style variants.
 *
 * The thumb is the 16×16 sliding circle inside the track. Its position and fill
 * follow ``checked`` and ``tone``, reflecting the DS contract: foreground-coloured
 * when off, primary-/success-foreground when on, and translated 16 px to the right.
 */
export const switchThumbVariants = cva(
  "pointer-events-none absolute top-[2px] left-[2px] block size-4 rounded-full shadow-xs transition-transform duration-200 ease-out motion-reduce:transition-none",
  {
    variants: {
      checked: {
        true: "translate-x-[16px] bg-primary-foreground",
        false: "translate-x-0 bg-foreground",
      },
      tone: {
        primary: "",
        success: "",
      },
    },
    compoundVariants: [
      {
        checked: true,
        tone: "success",
        className: "translate-x-[16px] bg-[var(--success-foreground)]",
      },
    ],
    defaultVariants: {
      checked: false,
      tone: "primary",
    },
  },
);
