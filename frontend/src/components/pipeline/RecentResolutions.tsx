/**
 * RecentResolutions — recent scrape-decision resolutions folded into the
 * pipeline run summary (webui-overhaul).
 *
 * The "Dernière exécution" narrative reflects the last *pipeline* run, which
 * ran before any ambiguity was resolved — so a decision resolved afterwards is
 * invisible there. This panel aggregates the recently-resolved scrape decisions
 * (the operator's ambiguous-match choices) so the summary accounts for them.
 */

import { CheckCircle2 } from "lucide-react";
import type { ReactElement } from "react";

import { TRIGGER_LABEL } from "@/components/decisions/triggers";
import { useDecisions } from "@/hooks/useDecisions";

/** How many recent resolutions to surface in the summary. */
const RECENT_LIMIT = 8;

/**
 * RecentResolutions — a compact list of the latest resolved scrape decisions.
 *
 * Renders nothing while loading or when there is no resolved decision, so it
 * never adds empty chrome to the pipeline page.
 *
 * Returns:
 *   The resolutions panel, or ``null`` when there is nothing to show.
 */
export function RecentResolutions(): ReactElement | null {
  const query = useDecisions({ status: "resolved", page_size: RECENT_LIMIT });
  const items = query.data?.items ?? [];

  if (query.isLoading || items.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="size-4 text-success" aria-hidden="true" />
        <h3 className="text-sm font-semibold">
          Décisions de scraping résolues récemment
        </h3>
        <span className="font-mono text-xs tabular-nums text-muted-foreground">
          {items.length}
        </span>
      </div>
      <ul className="flex flex-col gap-1">
        {items.map((d) => (
          <li
            key={d.id}
            className="ps-enter-row flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5 border-b border-border/60 py-1 text-sm last:border-b-0"
          >
            <span className="min-w-0 truncate">
              {d.extracted_title}
              {d.extracted_year != null && (
                <span className="ml-1 font-mono text-xs text-muted-foreground">
                  {d.extracted_year}
                </span>
              )}
            </span>
            <span className="shrink-0 text-xs text-muted-foreground">
              {TRIGGER_LABEL[d.trigger] ?? d.trigger} — identifiée
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
