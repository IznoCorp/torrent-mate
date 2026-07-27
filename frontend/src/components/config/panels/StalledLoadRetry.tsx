/**
 * StalledLoadRetry — an exit from an eternal « Chargement… » on the config page.
 */

import { useEffect, useState, type ReactElement } from "react";

import { Button } from "@/components/ui/button";

/** Props for {@link StalledLoadRetry}. */
interface StalledLoadRetryProps {
  /** Refetch every stalled query. */
  readonly onRetry: () => void;
}

/**
 * StalledLoadRetry — an exit from an eternal « Chargement… ».
 *
 * On mobile/PWA a flaky network at mount can leave the initial queries
 * pending forever (paused networkMode), stranding the page on the loading
 * text with no recourse (operator report 2026-07-15). After a short grace
 * period this surfaces an explicit retry button that refetches the stalled
 * queries.
 *
 * Args:
 *   props: {@link StalledLoadRetryProps}.
 *
 * Returns:
 *   The retry affordance, or null during the grace period.
 */
export function StalledLoadRetry({
  onRetry,
}: StalledLoadRetryProps): ReactElement | null {
  const [stalled, setStalled] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setStalled(true);
    }, 8_000);
    return () => {
      window.clearTimeout(timer);
    };
  }, []);
  if (!stalled) return null;
  return (
    <div className="flex flex-col items-start gap-2">
      <p className="text-sm text-muted-foreground">
        Le chargement prend plus de temps que prévu.
      </p>
      <Button type="button" variant="outline" size="sm" onClick={onRetry}>
        Recharger
      </Button>
    </div>
  );
}
