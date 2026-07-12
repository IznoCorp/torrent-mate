/**
 * Maintenance dashboard page (TorrentMateUI S3 — maint-dash).
 *
 * Replaces the former {@link ComingSoon} stub at ``/maintenance``. The page
 * renders a responsive grid of monitoring panels: disks, locks, index health,
 * and run history, plus the {@link ActionCatalog} of maintenance commands with
 * generated run forms.
 */

import { useState, type ReactElement } from "react";

import { EventFeed } from "@/components/dashboard/EventFeed";
import { RecentEventsTable } from "@/components/dashboard/RecentEventsTable";
import { ActionCatalog } from "@/components/maintenance/ActionCatalog";
import { DisksPanel } from "@/components/maintenance/DisksPanel";
import { IndexHealthPanel } from "@/components/maintenance/IndexHealthPanel";
import { LocksPanel } from "@/components/maintenance/LocksPanel";
import { RunDetail } from "@/components/pipeline/RunDetail";
import { RunHistoryTable } from "@/components/pipeline/RunHistoryTable";
import { TriggerLegend } from "@/components/pipeline/TriggerLegend";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";

/**
 * Maintenance — the authenticated maintenance dashboard route (``/maintenance``).
 *
 * Lays out four monitoring panels in a responsive grid (1 col mobile, 2 tablet,
 * 4 desktop) plus the {@link ActionCatalog} of maintenance commands with
 * generated, dry-run-first run forms.
 *
 * Returns:
 *   The maintenance page element.
 */
export default function Maintenance(): ReactElement {
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  // Single shared live-event stream (same WebSocket the TopBar StatusDot reads);
  // the feed + recent-events table moved here from the Dashboard (Phase 5.1).
  const { events } = useEventStreamContext();

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Maintenance</h1>

      {/* Monitoring panels: 1 col mobile → 2 tablet → 3 desktop (there are
          exactly 3 panels; a 4th column left a dead third on wide screens). */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <DisksPanel />
        <LocksPanel />
        <IndexHealthPanel />
      </div>

      {/* Live event feed + recent-events table (relocated from the Dashboard,
          Phase 5.1). Both read the single shared stream above — no extra WS. */}
      <EventFeed events={events} />
      <RecentEventsTable events={events} />

      {/* Pipeline run-history — relocated here from the Pipeline page
          (webui-ux Phase 2.4 de-dup: the Pipeline page now shows only the
          interpreted last-run summary, so pipeline history lives here). */}
      <RunHistoryTable kind="pipeline" onSelect={setSelectedRun} />

      {/* Run-history panel filtered to maintenance runs (kind param → backend) */}
      <RunHistoryTable kind="maintenance" onSelect={setSelectedRun} />

      {/* One shared trigger-label legend for both history tables above (it used
          to render inside each RunHistoryTable → duplicated on this page). */}
      <TriggerLegend />

      {/* Inline detail view when a history row is selected */}
      {selectedRun !== null && (
        <RunDetail
          runUid={selectedRun}
          onClose={() => {
            setSelectedRun(null);
          }}
        />
      )}

      {/* Action catalog + generated forms (5.2) */}
      <ActionCatalog />
    </section>
  );
}
