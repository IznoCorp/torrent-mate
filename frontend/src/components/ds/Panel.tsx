import type { ComponentPropsWithRef, ElementType, ReactElement } from "react";

import { cn } from "@/lib/utils";

/** Props for {@link Panel}: everything a `<div>` accepts, plus `as`. */
export type PanelProps = ComponentPropsWithRef<"div"> & {
  /** Element to render as, when the block is a section rather than a div. */
  readonly as?: ElementType;
};

/**
 * Panel — the bordered card surface every dashboard block sits on.
 *
 * `rounded-lg border border-border bg-card` was written out by hand in eleven
 * files. Repeating a surface as a string is how two of them end up one token
 * apart with nothing to say which is right: a surface has no content of its own
 * to be recognised by, so a drift in one is invisible until it sits next to
 * another.
 *
 * What a panel HOLDS stays with the caller — its padding, its height, whether
 * it scrolls, what it announces to a screen reader. That is what the block is,
 * not what the surface is.
 *
 * Args:
 *   as: The element to render as.
 *   className: Extra classes for what this panel holds.
 *
 * Returns:
 *   The panel element.
 */
export function Panel({
  className,
  as: Composant = "div",
  ...reste
}: PanelProps): ReactElement {
  return (
    <Composant
      className={cn("rounded-lg border border-border bg-card", className)}
      {...reste}
    />
  );
}
