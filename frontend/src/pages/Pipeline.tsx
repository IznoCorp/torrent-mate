/**
 * Pipeline supervision page (TorrentMateUI S2 — pipe-control; webui-ux Phase 2).
 *
 * Polls ``GET /api/pipeline/status`` every 5 seconds via {@link usePipelineStatus}
 * and feeds the live status to {@link PipelineControls} and {@link PipelineStepper}.
 *
 * webui-ux Phase 2 reworks the log area:
 * - The DEFAULT view is the interpreted, plain-French run narrative
 *   ({@link InterpretedRunFeed}) folded from the live WS event stream.
 * - When no run is active, the interpreted feed shows the LAST run's summary
 *   (reconstructed from the persisted per-step counts via
 *   {@link useLastPipelineRun}) so the page never blanks.
 * - The raw WS log ({@link RunLogFeed}) moves inside a collapsed {@link Accordion}.
 * - The run-history table is removed here (it lives on the Maintenance page) to
 *   de-duplicate; a small trigger legend explains the trigger labels.
 */

import { type ReactElement } from "react";

import { FlowBoard } from "@/components/pipeline/FlowBoard";
import { InterpretedRunFeed } from "@/components/pipeline/InterpretedRunFeed";
import { PipelineControls } from "@/components/pipeline/PipelineControls";
import { PipelineStepper } from "@/components/pipeline/PipelineStepper";
import { RunLogFeed } from "@/components/pipeline/RunLogFeed";
import { TriggerLegend } from "@/components/pipeline/TriggerLegend";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { useLastPipelineRun } from "@/hooks/useLastPipelineRun";
import { usePipelineStatus } from "@/hooks/usePipelineStatus";

/**
 * Pipeline — the authenticated pipeline supervision route (``/pipeline``).
 *
 * Returns:
 *   The pipeline page element.
 */
export default function Pipeline(): ReactElement {
  const { snapshot: liveStatus } = usePipelineStatus();
  const activeRunUid = liveStatus.run_uid ?? null;
  const isActive = liveStatus.state !== "idle" && activeRunUid !== null;

  // When idle, reconstruct the last run's interpreted summary from history so
  // the feed never blanks. `activeRunUid` as the refetch key means a
  // freshly-finished run supersedes the previous summary.
  const lastRun = useLastPipelineRun(activeRunUid ?? "idle");

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Pipeline</h1>

      {/* OBJ1 living pipeline — the Flow Board of the nine stages. */}
      <FlowBoard />

      <PipelineControls status={liveStatus} />

      <PipelineStepper currentStep={liveStatus.step ?? null} />

      {/* Interpreted narrative — live for an active run, else the last run's
          persisted summary (never blanks). */}
      {isActive ? (
        <InterpretedRunFeed runUid={activeRunUid} />
      ) : (
        <InterpretedRunFeed lines={lastRun.lines} label="Dernière exécution" />
      )}

      {/* Raw WS log — collapsed by default inside the accordion. */}
      <Accordion className="rounded-lg border border-border bg-card px-3">
        <AccordionItem>
          <AccordionTrigger>Journal brut (avancé)</AccordionTrigger>
          <AccordionContent>
            <RunLogFeed runUid={activeRunUid} />
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <TriggerLegend />
    </section>
  );
}
