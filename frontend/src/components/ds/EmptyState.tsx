import type { LucideIcon } from "lucide-react";
import type { ReactElement, ReactNode } from "react";

/** Props for {@link EmptyState}. */
export interface EmptyStateProps {
  /** Optional lucide icon shown above the title. */
  readonly icon?: LucideIcon;
  /** The empty-state headline. */
  readonly title: string;
  /** Optional supporting line under the title. */
  readonly description?: string;
  /** Optional primary action (e.g. a Button). */
  readonly action?: ReactNode;
}

/**
 * EmptyState — the soigné "no data yet" panel shared across screens.
 *
 * A centered, dashed-border card with an optional icon, a headline, an optional
 * description, and an optional action. Distinct from {@link ErrorState} so an
 * empty result never reads as a failure (no data-illusion).
 *
 * Args:
 *   icon: Optional lucide icon component.
 *   title: The headline.
 *   description: Optional supporting line.
 *   action: Optional action node.
 *
 * Returns:
 *   The empty-state element.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: EmptyStateProps): ReactElement {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border p-8 text-center">
      {Icon !== undefined && (
        <Icon className="size-8 text-muted-foreground" aria-hidden="true" />
      )}
      <p className="text-sm font-medium">{title}</p>
      {description !== undefined && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      {action !== undefined && <div className="mt-1">{action}</div>}
    </div>
  );
}
