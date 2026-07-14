/**
 * PipelineActionBanner — the impossible-to-miss "human action required" banner.
 *
 * When one or more scrape decisions await a human (the `matching` station's live
 * pending stock, all triggers — including the `manual` ones enqueued from a
 * non-identified item), a warning banner with an ambre-primary CTA leads
 * straight to the resolution deck. It renders nothing at zero. A `compact`
 * variant fits the Dashboard. Sourced from the same live `usePipelineStages`
 * query as the Flow Board (poll + WS-invalidated), so it appears/updates without
 * a reload.
 */

import { TriangleAlert } from "lucide-react";
import { type ReactElement } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { usePipelineStages } from "@/hooks/usePipelineStages";
import { cn } from "@/lib/utils";

/** Props for {@link PipelineActionBanner}. */
export interface PipelineActionBannerProps {
  /** Tighter padding + shorter copy for the Dashboard. */
  readonly compact?: boolean;
}

/**
 * PipelineActionBanner — a warning banner + deck CTA when decisions are pending.
 *
 * Args:
 *   compact: Tighter layout for the Dashboard (default false).
 *
 * Returns:
 *   The banner element, or ``null`` when nothing awaits a human.
 */
export function PipelineActionBanner({
  compact = false,
}: PipelineActionBannerProps): ReactElement | null {
  const navigate = useNavigate();
  const { data } = usePipelineStages();
  const pending =
    (data?.stages ?? []).find((s) => s.key === "matching")?.count ?? 0;

  if (pending === 0) return null;
  const plural = pending > 1 ? "s" : "";

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/40 bg-warning/5",
        compact ? "px-3 py-2" : "px-4 py-3",
      )}
    >
      <div className="flex items-center gap-2 text-sm">
        <TriangleAlert
          className="size-4 shrink-0 text-warning"
          aria-hidden="true"
        />
        <span>
          <strong className="font-semibold">
            {pending} média{plural} à identifier
          </strong>
          {!compact && " — une intervention manuelle est requise"}
        </span>
      </div>
      <Button
        size="sm"
        onClick={() => {
          void navigate("/scraping");
        }}
      >
        Ouvrir la file
      </Button>
    </div>
  );
}
