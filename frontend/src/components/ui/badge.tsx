import type { VariantProps } from "class-variance-authority";
import * as React from "react";

import { badgeVariants } from "@/components/ui/badge-variants";
import { cn } from "@/lib/utils";

/** Props for {@link Badge}. */
export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  /** Show a leading status dot in the tone colour. @default false */
  readonly dot?: boolean;
}

/**
 * Badge — the compact status / metadata chip of TorrentMate's dense tables and
 * panels (design-system `components/core/Badge`).
 *
 * Semantic tones map to the DS signal palette (success = healthy/done, danger =
 * error/HnR, warning = attention, info = scraping). Pass `mono` for machine
 * values and `dot` for a leading status dot.
 *
 * Args:
 *   tone: Colour tone (default `neutral`).
 *   mono: Use the monospace family (default `false`).
 *   dot: Show a leading status dot (default `false`).
 *
 * Returns:
 *   The badge element.
 */
export function Badge({
  tone,
  mono,
  dot = false,
  className,
  children,
  ...rest
}: BadgeProps): React.JSX.Element {
  return (
    <span
      data-slot="badge"
      className={cn(badgeVariants({ tone, mono }), className)}
      {...rest}
    >
      {dot && (
        <span
          className="size-1.5 shrink-0 rounded-full bg-current"
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
}
