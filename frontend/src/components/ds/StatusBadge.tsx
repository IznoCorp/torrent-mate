import type { ReactElement } from "react";

import { Badge } from "@/components/ui/badge";

/** The canonical state tones, mapped to the DS signal palette. */
export type StatusTone = "success" | "warning" | "danger" | "info" | "neutral";

/** Props for {@link StatusBadge}. */
export interface StatusBadgeProps {
  /** The signal tone. */
  readonly tone: StatusTone;
  /** The French state label. */
  readonly label: string;
  /** Show the leading tone dot. @default true */
  readonly dot?: boolean;
}

/**
 * StatusBadge — the canonical state chip (tone + dot + label) that unifies the
 * ad-hoc status badges across the app (circuit state, decision status, wanted
 * status, acquisition état). A thin, correct wrapper over the shadcn
 * {@link Badge} so every state reads consistently.
 *
 * Args:
 *   tone: The signal tone.
 *   label: The French state label.
 *   dot: Whether to show the leading dot (default ``true``).
 *
 * Returns:
 *   The status chip element.
 */
export function StatusBadge({
  tone,
  label,
  dot = true,
}: StatusBadgeProps): ReactElement {
  return (
    <Badge tone={tone} dot={dot}>
      {label}
    </Badge>
  );
}
