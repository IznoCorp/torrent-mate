import type { ReactElement } from "react";

import { EventFeed } from "@/components/dashboard/EventFeed";
import { HealthCard } from "@/components/dashboard/HealthCard";
import { RecentEventsTable } from "@/components/dashboard/RecentEventsTable";
import { VersionCard } from "@/components/dashboard/VersionCard";
import { useEventStreamContext } from "@/components/EventStreamProvider";

/**
 * Dashboard — the authenticated home page (`/`), the real-time supervision view.
 *
 * Reads the app's single live-event stream (via {@link useEventStreamContext})
 * and lays out, mobile-first: health + version cards on top (two columns ≥ md,
 * stacked below), the virtualized live feed as the main area, and a sortable
 * recent-events table underneath. Every panel proves one S1 foundation —
 * TanStack Virtual (feed), TanStack Table (recent events), TanStack Query
 * (health/version cards) — over the same WebSocket the TopBar's StatusDot reads.
 *
 * @returns The dashboard element.
 */
export default function Dashboard(): ReactElement {
  const { events } = useEventStreamContext();

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Tableau de bord</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <HealthCard />
        <VersionCard />
      </div>

      <EventFeed events={events} />
      <RecentEventsTable events={events} />
    </section>
  );
}
