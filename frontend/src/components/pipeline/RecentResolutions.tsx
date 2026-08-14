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

import { decisionFacts } from "@/components/decisions/decisionFacts";
import { DecisionRow } from "@/components/ds/DecisionRow";
import { useDecisions } from "@/hooks/useDecisions";
import { Panel } from "@/components/ds/Panel";

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
    <Panel className="flex flex-col gap-2 p-4">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="size-4 text-success" aria-hidden="true" />
        <h3 className="text-sm font-semibold">Réglées récemment</h3>
        <span className="font-mono text-xs tabular-nums text-muted-foreground">
          {items.length}
        </span>
      </div>
      {/* The shared decision card, not a hand-built row: what these lines are
          about is a FOLDER, and the queue and this journal are two views of one
          thing. Drawing them differently made the same decision read « Réglée »
          on one screen and « identifiée » on the other. */}
      <ul className="flex flex-col gap-2">
        {items.map((d) => (
          <li key={d.id} className="ps-enter-row">
            <DecisionRow {...decisionFacts(d)} />
          </li>
        ))}
      </ul>
    </Panel>
  );
}
