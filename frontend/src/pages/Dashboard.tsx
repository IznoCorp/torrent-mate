import type { ReactElement } from "react";

import { AcquisitionSummaryCard } from "@/components/dashboard/AcquisitionSummaryCard";
import { HealthCard } from "@/components/dashboard/HealthCard";
import { SchedulersPanel } from "@/components/dashboard/SchedulersPanel";
import { VersionCard } from "@/components/dashboard/VersionCard";
import { DisksPanel } from "@/components/maintenance/DisksPanel";
import { IndexHealthPanel } from "@/components/maintenance/IndexHealthPanel";
import { PipelineActionBanner } from "@/components/pipeline/PipelineActionBanner";
import { PipelineControls } from "@/components/pipeline/PipelineControls";
import { usePipelineStatus } from "@/hooks/usePipelineStatus";

/**
 * Dashboard — the authenticated home page (`/`), the operator's control
 * station (A3).
 *
 * From this single view the operator can SEE the load-bearing state — health,
 * disks, index health, acquisitions, schedulers — and ACT: the pipeline
 * controls (run / pause / resume / kill / watcher) live here too, and the
 * action banner leads to the resolution deck. Panels are the same
 * self-contained components used by their home pages (Pipeline / Maintenance /
 * Acquisition), so the dashboard adds no new data path — only composition.
 *
 * @returns The dashboard element.
 */
export default function Dashboard(): ReactElement {
  const { data: pipelineStatus } = usePipelineStatus();

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Tableau de bord</h1>

      {/* Compact human-action banner (C5) — leads to the resolution deck. */}
      <PipelineActionBanner compact />

      {/* Control station (A3): the pipeline is drivable from home. */}
      {pipelineStatus !== undefined && (
        <PipelineControls status={pipelineStatus} />
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <HealthCard />
        <VersionCard />
        <AcquisitionSummaryCard />
        <IndexHealthPanel />
      </div>

      <DisksPanel />

      <SchedulersPanel />
    </section>
  );
}
