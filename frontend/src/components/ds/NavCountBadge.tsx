import { type ReactElement } from "react";

import { cn } from "@/lib/utils";

/** Props for {@link NavCountBadge}. */
export interface NavCountBadgeProps {
  /** The count to show; the badge renders nothing at 0 or below. */
  readonly count: number;
  /** Extra classes (e.g. corner-superscript positioning on the mobile tab bar). */
  readonly className?: string;
}

/**
 * NavCountBadge — a solid, legible pending-count pill for the navigation.
 *
 * Replaces the faint tinted `Badge tone="danger"` that was illegible as a
 * mobile bottom-nav corner superscript (dark red text on a 16 %-red wash,
 * cramped into the icon corner). This is a **solid** `bg-danger` /
 * `text-danger-foreground` pill (high contrast), circular for a single digit,
 * capped at `99+`, with a `ring-sidebar` halo so it separates cleanly from the
 * icon it overlaps. Renders nothing when the count is 0.
 *
 * Args:
 *   count: The pending count (nothing rendered at ≤ 0).
 *   className: Extra classes for positioning (corner superscript on mobile).
 *
 * Returns:
 *   The count pill element, or ``null`` when there is nothing to show.
 */
export function NavCountBadge({
  count,
  className,
}: NavCountBadgeProps): ReactElement | null {
  if (count <= 0) return null;
  return (
    <span
      data-slot="nav-count"
      className={cn(
        "inline-flex h-[1.125rem] min-w-[1.125rem] items-center justify-center rounded-full bg-danger px-1 text-[0.6875rem] font-semibold leading-none text-danger-foreground shadow-sm ring-2 ring-sidebar tabular-nums",
        className,
      )}
      aria-label={`${String(count)} en attente`}
    >
      {count > 99 ? "99+" : String(count)}
    </span>
  );
}
