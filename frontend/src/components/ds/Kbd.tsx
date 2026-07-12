import type { ReactElement, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Props for {@link Kbd}. */
export interface KbdProps {
  /** The key label (e.g. ``"⏎"``, ``"S"``). */
  readonly children: ReactNode;
  /** Optional extra classes. */
  readonly className?: string;
}

/**
 * Kbd — a keyboard-hint chip for shortcut affordances (e.g. the resolution deck).
 *
 * Args:
 *   children: The key label.
 *   className: Optional extra classes.
 *
 * Returns:
 *   A ``<kbd>`` chip styled with DS tokens.
 */
export function Kbd({ children, className }: KbdProps): ReactElement {
  return (
    <kbd
      className={cn(
        "inline-flex min-h-5 items-center rounded border border-border bg-muted px-1.5 font-mono text-xs text-muted-foreground",
        className,
      )}
    >
      {children}
    </kbd>
  );
}
