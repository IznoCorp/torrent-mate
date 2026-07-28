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
        // ``muted`` — the « je ne sais pas » of a never-verified episode. A
        // dashed border + fainter fill + the idle-signal grey keeps it visually
        // APART from the solid ``neutral`` chip (« en attente »), so the two
        // grey-family states never read as one colour (operator #9).
        muted:
          "border-dashed border-[color-mix(in_oklch,var(--neutral-signal)_45%,transparent)] bg-[color-mix(in_oklch,var(--neutral-signal)_8%,transparent)] text-[var(--neutral-signal)]",
        // ``upcoming`` — announced, not yet aired. Violet accent, live-tinted
        // from the token exactly like the other signal tones.
        upcoming:
          "border-[color-mix(in_oklch,var(--upcoming)_32%,transparent)] bg-[color-mix(in_oklch,var(--upcoming)_16%,transparent)] text-[var(--upcoming)]",
      },
      mono: { true: "font-mono tracking-normal", false: "" },
    },
    defaultVariants: { tone: "neutral", mono: false },
  },
);
