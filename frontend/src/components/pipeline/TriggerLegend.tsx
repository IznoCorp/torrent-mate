/**
 * TriggerLegend — a compact caption explaining the run-trigger labels.
 *
 * Renders one chip per known trigger (label + tone) with its one-line French
 * meaning, so the human labels shown in the run tables / detail are decoded in
 * place (webui-ux Phase 2.1). Purely presentational — reads the static
 * {@link TRIGGER_INFO} map.
 */

import { type ReactElement } from "react";

import { TRIGGER_INFO } from "@/components/pipeline/triggers";
import { Badge } from "@/components/ui/badge";

/**
 * TriggerLegend — the trigger-label legend caption.
 *
 * Returns:
 *   A caption listing every known trigger with its badge + meaning.
 */
export function TriggerLegend(): ReactElement {
  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground"
      aria-label="Légende des déclencheurs"
    >
      <span className="font-medium">Déclencheurs :</span>
      {Object.entries(TRIGGER_INFO).map(([key, info]) => (
        <span key={key} className="inline-flex items-center gap-1.5">
          <Badge tone={info.tone} dot>
            {info.label}
          </Badge>
          <span>{info.meaning}</span>
        </span>
      ))}
    </div>
  );
}
