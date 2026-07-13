import { useQuery } from "@tanstack/react-query";
import type { ReactElement } from "react";

import { decisionsKeys, fetchDecisionActivity } from "@/api/decisions";

/** Poll cadence while scrapes are in flight (ms). */
const ACTIVE_POLL_MS = 2000;

/** Format seconds-elapsed as a short French duration ("42 s" / "3 min"). */
function formatElapsed(startedAt: number): string {
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - startedAt));
  return seconds < 60
    ? `${String(seconds)} s`
    : `${String(Math.floor(seconds / 60))} min`;
}

/**
 * "Scrapes en cours" surface for the /scraping page.
 *
 * Shows each scrape running right now (title + elapsed, with a live pulse) and the
 * pending-queue size, so the operator can actually SEE true-parallel scraping happen
 * instead of facing an opaque queue (product-intent.md §3). Polls only while work is
 * in flight; renders nothing when the pipeline is idle and the queue is empty.
 */
export function ScrapeActivityPanel(): ReactElement | null {
  const { data } = useQuery({
    queryKey: decisionsKeys.activity,
    queryFn: fetchDecisionActivity,
    // Poll briefly while something runs; go idle otherwise (WS invalidation and the
    // deck's own refetches revive it when a new scrape starts).
    refetchInterval: (query) =>
      (query.state.data?.in_progress.length ?? 0) > 0 ? ACTIVE_POLL_MS : false,
  });

  const inProgress = data?.in_progress ?? [];
  const pending = data?.pending_count ?? 0;

  if (inProgress.length === 0 && pending === 0) {
    return null;
  }

  return (
    <section
      aria-label="Scrapes en cours"
      className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3"
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Scrapes en cours</span>
        <span className="text-xs text-muted-foreground">
          En file&nbsp;: {String(pending)}
        </span>
      </div>

      {inProgress.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Aucun scrape en cours — {String(pending)} média(s) en attente de
          résolution.
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {inProgress.map((item) => (
            <li
              key={item.decision_id}
              className="flex items-center gap-2 text-sm"
            >
              <span
                aria-hidden
                className="size-2 shrink-0 animate-pulse rounded-full bg-primary"
              />
              <span className="min-w-0 truncate">{item.title}</span>
              <span className="ml-auto shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                {formatElapsed(item.started_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
