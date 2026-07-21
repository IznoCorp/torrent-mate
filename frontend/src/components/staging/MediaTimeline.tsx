import type { ReactElement } from "react";

import type { StagingStageStep } from "@/api/staging";
import { cn } from "@/lib/utils";

/** Per-stage tone dot + French state label for the timeline rows. */
const STATE_META: Record<
  StagingStageStep["state"],
  { dot: string; label: string; muted: boolean }
> = {
  done: { dot: "bg-success", label: "Fait", muted: false },
  active: { dot: "bg-info ps-pulse", label: "En cours", muted: false },
  blocked: { dot: "bg-danger", label: "Bloqué", muted: false },
  pending: { dot: "bg-muted-foreground/40", label: "En attente", muted: true },
  skipped: { dot: "bg-muted-foreground/20", label: "Non applicable", muted: true },
};

/** Props for {@link MediaTimeline}. */
export interface MediaTimelineProps {
  /** The nine-stage per-media pipeline timeline. */
  readonly stages: readonly StagingStageStep[];
}

/**
 * MediaTimeline — a vertical stage-by-stage timeline for one staged media.
 *
 * Renders each pipeline stage (Arrivée → Dispatch) as a connected row: a tone
 * dot (green done / blue active / red blocked / grey pending / faint skipped),
 * the stage label, and its French state. Shared by the OBJ2A staging detail
 * drawer and the OBJ1 Flow Board per-media drill-down.
 *
 * Args:
 *   stages: The ordered timeline steps from the staging read-model.
 *
 * Returns:
 *   The timeline element.
 */
export function MediaTimeline({ stages }: MediaTimelineProps): ReactElement {
  return (
    <ol className="flex flex-col" aria-label="Étapes du pipeline pour ce média">
      {stages.map((step, i) => {
        const meta = STATE_META[step.state];
        const isLast = i === stages.length - 1;
        return (
          <li key={step.key} className="flex gap-3">
            {/* Rail: dot + connecting line. */}
            <div className="flex flex-col items-center">
              <span
                className={cn("mt-1 size-2.5 shrink-0 rounded-full", meta.dot)}
                aria-hidden="true"
              />
              {!isLast && <span className="w-px flex-1 bg-border" aria-hidden="true" />}
            </div>
            {/* Row body. */}
            <div
              className={cn(
                "flex flex-1 items-center justify-between gap-2 pb-3",
                meta.muted && "opacity-60",
              )}
            >
              <span className="text-sm">{step.label}</span>
              <span className="text-xs text-muted-foreground">{meta.label}</span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
