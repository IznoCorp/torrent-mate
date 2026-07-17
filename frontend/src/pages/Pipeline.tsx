/**
 * Pipeline supervision page (TorrentMateUI S2 — pipe-control; pipeline-panel).
 *
 * Polls ``GET /api/pipeline/status`` every 5 seconds via {@link usePipelineStatus}
 * and feeds the live status to {@link PipelineControls}. The eight-stage
 * {@link FlowBoard} is the single canonical pipeline view (OBJ1).
 *
 * pipeline-panel Phase 02 repatriates the pipeline run-history table + RunDetail
 * drawer from the Maintenance page. The ``?run=<uid>`` query param opens the
 * inline RunDetail drawer (DOIT-10: every detail view is URL-addressable).
 *
 * Log area:
 * - The DEFAULT view is the interpreted, plain-French run narrative
 *   ({@link InterpretedRunFeed}) folded from the live WS event stream.
 * - When no run is active, the interpreted feed shows the LAST run's summary
 *   (reconstructed from the persisted per-step counts via
 *   {@link useLastPipelineRun}) so the page never blanks.
 * - The raw WS log ({@link RunLogFeed}) moves inside a collapsed {@link Accordion}.
 * - The trigger legend lives as a popover on the history table header
 *   (tap-accessible, never hover-only — DOIT-9).
 */

import { useCallback, type ReactElement } from "react";
import { useSearchParams } from "react-router-dom";

import { FlowBoard } from "@/components/pipeline/FlowBoard";
import { PipelineActionBanner } from "@/components/pipeline/PipelineActionBanner";
import { InterpretedRunFeed } from "@/components/pipeline/InterpretedRunFeed";
import { PipelineControls } from "@/components/pipeline/PipelineControls";
import { RecentResolutions } from "@/components/pipeline/RecentResolutions";
import { RunDetail } from "@/components/pipeline/RunDetail";
import { RunHistoryTable } from "@/components/pipeline/RunHistoryTable";
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

  // Run-detail selection is URL-addressable (?run=<uid>) — DOIT-10.
  const [searchParams, setSearchParams] = useSearchParams();
  // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing
  const selectedRun = searchParams.get("run") || null;
  const openRun = useCallback(
    (uid: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("run", uid);
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );
  const closeRun = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("run");
        return next;
      },
      { replace: true },
    );
  }, [setSearchParams]);

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Pipeline</h1>

      {/* Human-action banner — impossible to miss when decisions await (C5). */}
      <PipelineActionBanner />

      {/* OBJ1 living pipeline — the Flow Board of the eight stages. */}
      <FlowBoard />

      <PipelineControls status={liveStatus} />

      {/* Interpreted narrative — live for an active run, else the last run's
          persisted summary (never blanks). */}
      {isActive ? (
        <InterpretedRunFeed runUid={activeRunUid} />
      ) : (
        <InterpretedRunFeed lines={lastRun.lines} label="Dernière exécution" />
      )}

      {/* Fold the operator's resolved ambiguous-match choices into the summary
          — the last-run narrative predates them (webui-overhaul #4). */}
      <RecentResolutions />

      {/* Raw WS log — collapsed by default inside the accordion. */}
      <Accordion className="rounded-lg border border-border bg-card px-3">
        <AccordionItem>
          <AccordionTrigger>Journal brut (avancé)</AccordionTrigger>
          <AccordionContent>
            <RunLogFeed runUid={activeRunUid} />
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      {/* Pipeline run-history — repatriated from Maintenance (pipeline-panel
          Phase 02). The trigger legend lives as a popover on the history
          header (tap-accessible, never hover-only — DOIT-9). */}
      <RunHistoryTable
        kind="pipeline"
        onSelect={openRun}
        legend={<TriggerLegend />}
      />

      {/* Inline detail view when a history row is selected (URL: ?run=<uid>).
          showMaintenanceLink adds a cross-link to /systeme?tab=maintenance when
          the selected run is a maintenance run (systeme-hub Phase 02). */}
      {selectedRun !== null && (
        <RunDetail
          runUid={selectedRun}
          onClose={closeRun}
          showMaintenanceLink
        />
      )}
    </section>
  );
}
