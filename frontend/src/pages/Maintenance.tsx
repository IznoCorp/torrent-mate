/**
 * Maintenance dashboard page (TorrentMateUI S3 — maint-dash).
 *
 * Replaces the former {@link ComingSoon} stub at ``/maintenance``. The page
 * renders a responsive three-panel monitoring grid (disks, locks, index
 * health), the append-only {@link DestructiveLogPanel} journal, a live
 * {@link EventFeed} with its {@link RecentEventsTable}, a
 * maintenance-filtered {@link RunHistoryTable}, and the {@link ActionCatalog}
 * of maintenance commands with generated run forms.
 *
 * The pipeline-run detail view lives exclusively on ``/pipeline`` (Phase 02
 * repatriation).  Clicking a row in the maintenance history table sets
 * ``?run=<uid>`` on this route; {@link MaintenanceRunRedirect} catches the
 * param and teleports the user to ``/pipeline?run=<uid>`` where the detail
 * renders with a cross-link back to ``/maintenance``.  No inline RunDetail
 * lives here — the redirect is the single path.
 */

import { type ReactElement } from "react";
import { useSearchParams } from "react-router-dom";

import { EventFeed } from "@/components/dashboard/EventFeed";
import { RecentEventsTable } from "@/components/dashboard/RecentEventsTable";
import { ActionCatalog } from "@/components/maintenance/ActionCatalog";
import { DestructiveLogPanel } from "@/components/maintenance/DestructiveLogPanel";
import { DisksPanel } from "@/components/maintenance/DisksPanel";
import { IndexHealthPanel } from "@/components/maintenance/IndexHealthPanel";
import { LocksPanel } from "@/components/maintenance/LocksPanel";
import { RunHistoryTable } from "@/components/pipeline/RunHistoryTable";
import { TriggerLegend } from "@/components/pipeline/TriggerLegend";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";

/**
 * Maintenance — the authenticated maintenance dashboard route (``/maintenance``).
 *
 * Lays out three monitoring panels in a responsive grid (1 col mobile, 2 tablet,
 * 3 desktop) plus the {@link ActionCatalog} of maintenance commands with
 * generated, dry-run-first run forms.  The run-history table carries the trigger
 * legend so labels stay decodable here (review cycle 1, C2).
 *
 * Returns:
 *   The maintenance page element.
 */
export default function Maintenance(): ReactElement {
  // Clicking a maintenance history row sets ?run=<uid> on /maintenance.
  // MaintenanceRunRedirect (the route wrapper) catches the param and teleports
  // to /pipeline?run=<uid> — the detail renders there, never inline here
  // (pipeline-panel Phase 02 + review cycle 1 B1).
  const [, setSearchParams] = useSearchParams();

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

      {/* §7 — the append-only journal of destructive operations (overwrite /
          delete). The forensic trail that was missing during « Star City ». */}
      <DestructiveLogPanel />

      {/* Live event feed + recent-events table (relocated from the Dashboard,
          Phase 5.1). Both read the single shared stream above — no extra WS. */}
      <EventFeed events={events} />
      <RecentEventsTable events={events} />

      {/* Run-history panel filtered to maintenance runs (kind param → backend).
          Pipeline runs moved to /pipeline (pipeline-panel Phase 02).
          The trigger legend is carried here so labels stay decodable (C2). */}
      <RunHistoryTable
        kind="maintenance"
        onSelect={(uid) => {
          setSearchParams(
            (prev) => {
              const next = new URLSearchParams(prev);
              next.set("run", uid);
              return next;
            },
            { replace: false },
          );
        }}
        legend={<TriggerLegend />}
      />

      {/* Action catalog + generated forms (5.2) */}
      <ActionCatalog />
    </section>
  );
}
