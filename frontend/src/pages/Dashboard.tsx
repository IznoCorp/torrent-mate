import type { ReactElement } from "react";

import { HealthCard } from "@/components/dashboard/HealthCard";
import { SchedulersPanel } from "@/components/dashboard/SchedulersPanel";
import { VersionCard } from "@/components/dashboard/VersionCard";

/**
 * Dashboard — the authenticated home page (`/`), the supervision landing view.
 *
 * Lays out, mobile-first: health + version cards on top (two columns ≥ md,
 * stacked below), then the {@link SchedulersPanel} overview of the watcher and
 * cron jobs with their last runs. The live event feed + recent-events table
 * moved to the Maintenance page (webui-ux Phase 5.1) so this page stays a
 * calm at-a-glance summary; both still read the single shared event stream
 * there — no duplicate WebSocket.
 *
 * @returns The dashboard element.
 */
export default function Dashboard(): ReactElement {
  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Tableau de bord</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <HealthCard />
        <VersionCard />
      </div>

      <SchedulersPanel />
    </section>
  );
}
