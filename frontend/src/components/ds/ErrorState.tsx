import { AlertTriangle } from "lucide-react";
import type { ReactElement } from "react";

import { Button } from "@/components/ui/button";

/** Props for {@link ErrorState}. */
export interface ErrorStateProps {
  /** The error headline. @default "Une erreur est survenue" */
  readonly title?: string;
  /** Optional detail message (the caught error's text). */
  readonly message?: string;
  /** Optional retry handler; when given, a "Réessayer" button is shown. */
  readonly onRetry?: () => void;
}

/**
 * ErrorState — the single danger-tinted failure panel shared across screens.
 *
 * A ``role="alert"`` card in the danger tone with an icon, a headline, an
 * optional detail message, and an optional retry button. Adopting this
 * everywhere kills the data-illusion class where a failed fetch collapses to a
 * muted "—" indistinguishable from an empty result.
 *
 * Args:
 *   title: The headline (defaults to a generic French message).
 *   message: Optional detail message.
 *   onRetry: Optional retry callback; renders a "Réessayer" button.
 *
 * Returns:
 *   The error-state element.
 */
export function ErrorState({
  title = "Une erreur est survenue",
  message,
  onRetry,
}: ErrorStateProps): ReactElement {
  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm text-danger"
    >
      <div className="flex items-center gap-2">
        <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
        <span className="font-medium">{title}</span>
      </div>
      {message !== undefined && (
        <p className="text-xs text-muted-foreground">{message}</p>
      )}
      {onRetry !== undefined && (
        <Button
          variant="outline"
          size="sm"
          className="self-start"
          onClick={onRetry}
        >
          Réessayer
        </Button>
      )}
    </div>
  );
}
