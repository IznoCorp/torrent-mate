import { cva } from "class-variance-authority";

/**
 * Badge style variants (design-system `components/core/Badge`).
 *
 * Semantic tones map to the DS signal palette; the tints are derived live with
 * `color-mix(… NN%, transparent)` from the token — never hand-picked — so a chip
 * tracks any theme change. `mono` swaps to the monospace family for machine
 * values (codes, hashes, resolutions). Extracted from `badge.tsx` to satisfy the
 * `react-refresh/only-export-components` rule (as `button-variants.ts` is).
 */
export const badgeVariants = cva(
  "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-transparent px-2 py-0.5 align-middle text-[length:var(--text-2xs)] font-medium leading-none [&>svg]:size-3 [&>svg]:shrink-0",
  {
    variants: {
      tone: {
        solid: "bg-primary text-primary-foreground",
        neutral: "border-border bg-muted text-muted-foreground",
        outline: "border-border bg-transparent text-foreground",
        success:
          "border-[color-mix(in_oklch,var(--success)_32%,transparent)] bg-[color-mix(in_oklch,var(--success)_16%,transparent)] text-[var(--success)]",
        warning:
          "border-[color-mix(in_oklch,var(--warning)_32%,transparent)] bg-[color-mix(in_oklch,var(--warning)_16%,transparent)] text-[var(--warning)]",
        danger:
          "border-[color-mix(in_oklch,var(--danger)_34%,transparent)] bg-[color-mix(in_oklch,var(--danger)_16%,transparent)] text-[var(--danger)]",
        info: "border-[color-mix(in_oklch,var(--info)_32%,transparent)] bg-[color-mix(in_oklch,var(--info)_16%,transparent)] text-[var(--info)]",
      },
      mono: { true: "font-mono tracking-normal", false: "" },
    },
    defaultVariants: { tone: "neutral", mono: false },
  },
);
