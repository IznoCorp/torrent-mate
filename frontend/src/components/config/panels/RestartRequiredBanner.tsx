/**
 * RestartRequiredBanner — the "restart required" info banner for the config page.
 */

import { type ReactElement } from "react";

import { Button } from "@/components/ui/button";

/** Props for {@link RestartRequiredBanner}. */
interface RestartRequiredBannerProps {
  /** Read-only instance — hides the restart affordance. */
  readonly readOnly: boolean;
  /** Whether the daemon is configured for a web restart. */
  readonly restartConfigured: boolean;
  /** Files changed since boot. */
  readonly staleFiles: string[];
  /** ``true`` while a restart POST is in flight. */
  readonly restartPending: boolean;
  /** Open the restart confirmation dialog. */
  readonly onRestart: () => void;
}

/**
 * RestartRequiredBanner — surfaces that pending config changes need a daemon
 * restart, with a restart button (when configured + writable) or a hint.
 *
 * Args:
 *   props: {@link RestartRequiredBannerProps}.
 *
 * Returns:
 *   The banner element.
 */
export function RestartRequiredBanner({
  readOnly,
  restartConfigured,
  staleFiles,
  restartPending,
  onRestart,
}: RestartRequiredBannerProps): ReactElement {
  return (
    <div className="rounded-md border border-info bg-info/10 px-4 py-3 text-sm">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <p className="font-medium">Redémarrage requis</p>
          <p className="text-muted-foreground text-xs mt-0.5">
            Fichiers modifiés : {staleFiles.join(", ")}
          </p>
        </div>
        {!readOnly && restartConfigured && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={restartPending}
            onClick={onRestart}
          >
            Redémarrer le daemon
          </Button>
        )}
        {!readOnly && !restartConfigured && (
          <p className="text-xs text-muted-foreground">
            Redémarrage requis — non configuré sur ce daemon
            (PERSONALSCRAPER_PM2_NAME).
          </p>
        )}
      </div>
    </div>
  );
}
