import type { ReactElement } from "react";

import { ATraiterList } from "@/components/controle/ATraiterList";
import { CompactHealth } from "@/components/controle/CompactHealth";
import { LastRunDigest } from "@/components/controle/LastRunDigest";
import { AcquisitionSummaryCard } from "@/components/dashboard/AcquisitionSummaryCard";
import { SchedulersPanel } from "@/components/dashboard/SchedulersPanel";
import { ScrapeActivityPanel } from "@/components/decisions/ScrapeActivityPanel";
import { PipelineControls } from "@/components/pipeline/PipelineControls";
import { StalledPanel } from "@/components/pipeline/StalledPanel";
import { useLastPipelineRun } from "@/hooks/useLastPipelineRun";
import { usePipelineStatus } from "@/hooks/usePipelineStatus";

/**
 * Contrôle — the authenticated home page (``/``), the operator's attention-first
 * control station.
 *
 * Panels are ordered by operator attention priority (DESIGN §2.1):
 *
 * 1. **À traiter** — every blocked staged item, unified across all pipeline
 *    stages (the reason the operator opens the app).
 * 2. **Activité scraping** — live scrape-activity feed (relocated from
 *    ``/medias``).
 * 3. **Ce qui n'a pas avancé** — per-step skip/defer/error reasons from the
 *    last pipeline run, so stalled items are visible at a glance.
 * 4. **Acquisitions & planificateurs** — pending wanted + active downloads +
 *    deferred torrents, plus the scheduler overview, visually merged.
 * 5. **Santé** — health card, index health, and disk usage (compacted in 5.4).
 * 6. **Pipeline** — single state-dependent primary control button.
 *
 * Returns:
 *   The Contrôle page element.
 */
export default function Dashboard(): ReactElement {
  const { data: pipelineStatus } = usePipelineStatus();
  const lastRun = useLastPipelineRun();

  return (
    <section className="mx-auto flex max-w-[1280px] flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Contrôle</h1>

      {/* 1. À traiter — all blocked cases, unified (DESIGN §2.1). */}
      <ATraiterList />

      {/* 2. Activité scraping — live scrape feed, relocated from /medias. */}
      <ScrapeActivityPanel />

      {/* 3. Dernier run — digest card (trigger + counts + detail link). */}
      <LastRunDigest lastRun={lastRun} />

      {/* 4. Ce qui n'avance pas — StalledPanel on the last run. */}
      <StalledPanel stepReasons={lastRun.stepReasons} />

      {/* 4. Acquisitions & planificateurs — merged section (guarantor amendment a). */}
      <section>
        <h2 className="mb-3 text-base font-semibold tracking-tight">
          Acquisitions &amp; planificateurs
        </h2>
        <div className="flex flex-col gap-4">
          <AcquisitionSummaryCard />
          <SchedulersPanel />
        </div>
      </section>

      {/* 5. Santé — compact rows (disks, index, Redis, providers). */}
      <CompactHealth />

      {/* 6. Pipeline control — single state-dependent primary (DESIGN §2.1). */}
      {pipelineStatus !== undefined && (
        <PipelineControls status={pipelineStatus} />
      )}
    </section>
  );
}
