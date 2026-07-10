import type { ReactElement, ReactNode } from "react";

/** Props for {@link PageHeader}. */
export interface PageHeaderProps {
  /** The page title (rendered as the page ``h1``). */
  readonly title: string;
  /** Optional one-line description under the title. */
  readonly description?: string;
  /** Optional actions (buttons, toggles) rendered on the trailing side. */
  readonly actions?: ReactNode;
}

/**
 * PageHeader — the single page-title rhythm shared by every screen.
 *
 * Renders the page ``h1`` (``text-xl font-semibold tracking-tight``) with an
 * optional muted description and a trailing actions slot. Stacks on mobile and
 * becomes a space-between row from ``sm`` up.
 *
 * Args:
 *   title: The page title.
 *   description: Optional one-line description.
 *   actions: Optional trailing actions node.
 *
 * Returns:
 *   The page header element.
 */
export function PageHeader({
  title,
  description,
  actions,
}: PageHeaderProps): ReactElement {
  return (
    <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-0.5">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description !== undefined && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {actions !== undefined && (
        <div className="flex items-center gap-2">{actions}</div>
      )}
    </header>
  );
}
