/**
 * Pipeline supervision page (TorrentMateUI S2 — pipe-control).
 *
 * Replaces the former {@link ComingSoon} stub at ``/pipeline``. The page polls
 * ``GET /api/pipeline/status`` every 5 seconds via TanStack Query and passes
 * the live status down to {@link PipelineControls}, {@link PipelineStepper},
 * and {@link RunLogFeed}.
 */

import type { ReactElement } from "react";

import { PipelineControls } from "@/components/pipeline/PipelineControls";
import { PipelineStepper } from "@/components/pipeline/PipelineStepper";
import { RunLogFeed } from "@/components/pipeline/RunLogFeed";
import { usePipelineStatus } from "@/hooks/usePipelineStatus";

/**
 * Pipeline — the authenticated pipeline supervision route (``/pipeline``).
 *
 * Delegates the status poll and live-event invalidation to
 * {@link usePipelineStatus}; the returned snapshot feeds the control bar,
 * stepper, and log feed without any inline query wiring.
 *
 * Returns:
 *   The pipeline page element.
 */
export default function Pipeline(): ReactElement {
  const { snapshot: liveStatus } = usePipelineStatus();

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Pipeline</h1>

      <PipelineControls status={liveStatus} />

      <PipelineStepper currentStep={liveStatus.step ?? null} />

      <RunLogFeed runUid={liveStatus.run_uid ?? null} />
    </section>
  );
}
