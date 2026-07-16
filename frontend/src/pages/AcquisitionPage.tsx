/**
 * Acquisition + Watcher page (acq-watch feature).
 *
 * Four tabbed panels — Followed (CRUD), Wanted (status queue), Obligations
 * (seed/ratio), Watcher (status + toggle + recent runs) — each extracted into
 * its own component under `components/acquisition/` (C12). This shell owns only
 * the tab state, the shared followed query and the live-event invalidation.
 *
 * Live updates: the acquisition event stream (via useEventStreamContext)
 * invalidates the matching query when a relevant event arrives, using the R13
 * new-events-only ref pattern.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, type ReactElement } from "react";
import { useSearchParams } from "react-router-dom";

import { acqKeys } from "@/api/acquisition";
import { DownloadsPanel } from "@/components/acquisition/DownloadsPanel";
import { FollowedPanel } from "@/components/acquisition/FollowedPanel";
import { MediaSearchAdd } from "@/components/acquisition/MediaSearchAdd";
import {
  ACQ_EVENT_TYPES,
  FULL_INVALIDATE_EVENTS,
  OBLIGATION_INVALIDATE_EVENTS,
  TABS,
  WANTED_INVALIDATE_EVENTS,
  type TabId,
} from "@/components/acquisition/meta";
import { ObligationsPanel } from "@/components/acquisition/ObligationsPanel";
import { WantedPanel } from "@/components/acquisition/WantedPanel";
import { WatcherPanel } from "@/components/acquisition/WatcherPanel";
import { NavCountBadge } from "@/components/ds/NavCountBadge";
import { Card, CardContent } from "@/components/ui/card";
import { useDownloads, useFollowed } from "@/hooks/useAcquisition";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";

/**
 * AcquisitionPage — the authenticated acquisition route (``/acquisition``).
 *
 * Four tabbed panels for followed series CRUD, wanted queue, seed
 * obligations, and watcher status. Live events from the WebSocket invalidate
 * the matching TanStack Query caches (R13 — processes only new events, not the
 * whole ring on every render).
 *
 * Returns:
 *   The acquisition page element.
 */
export default function AcquisitionPage(): ReactElement {
  // The active tab is URL-addressable (?tab=<id>) — DOIT-10: the tab is a
  // shareable deep-link and Back returns to the previous tab. Derived from the
  // URL (single source of truth); the default "followed" carries no param so
  // /acquisition stays clean and ?tab=wanted is the shareable form.
  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = searchParams.get("tab");
  const activeTab: TabId = TABS.some((t) => t.id === rawTab)
    ? (rawTab as TabId)
    : "followed";
  const setActiveTab = useCallback(
    (id: TabId) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (id === "followed") next.delete("tab");
          else next.set("tab", id);
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );
  const queryClient = useQueryClient();
  const { events } = useEventStreamContext();

  // Only invalidate on fresh events, not re-scanning the ring every render
  // (AppShell R13 ref pattern, coherence study F13).
  const lastProcessedRef = useRef(0);
  useEffect(() => {
    const start = Math.min(lastProcessedRef.current, events.length);
    const fresh = events.slice(start);
    lastProcessedRef.current = events.length;

    for (const msg of fresh) {
      if (!ACQ_EVENT_TYPES.has(msg.type)) continue;

      if (FULL_INVALIDATE_EVENTS.has(msg.type)) {
        void queryClient.invalidateQueries({ queryKey: acqKeys.all });
        continue;
      }
      if (WANTED_INVALIDATE_EVENTS.has(msg.type)) {
        void queryClient.invalidateQueries({ queryKey: acqKeys.wanted({}) });
        void queryClient.invalidateQueries({ queryKey: acqKeys.followed({}) });
        continue;
      }
      if (OBLIGATION_INVALIDATE_EVENTS.has(msg.type)) {
        void queryClient.invalidateQueries({
          queryKey: acqKeys.obligations({}),
        });
        continue;
      }
      if (msg.type === "WatcherRunTriggered") {
        void queryClient.invalidateQueries({ queryKey: acqKeys.status() });
      }
    }
  }, [events, queryClient]);

  // Followed data is shared across tabs — kept alive by the hook at page level.
  const followedQuery = useFollowed({ active: "all" });

  // Arrival badge on the « Téléchargements » tab (A4 limite avouée s2): the
  // count of torrents still downloading, visible without opening the tab.
  const downloadsQuery = useDownloads();
  const activeDownloads = (downloadsQuery.data?.downloads ?? []).filter(
    (d) => d.state !== "missing" && d.progress < 1,
  ).length;

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Acquisition</h1>

      {/* Tabs — wrap to 2-per-row on narrow screens (4 tabs overflowed a single
          row at ~390px, clipping "Watcher"); a single filled row on sm+. */}
      <div
        role="tablist"
        className="flex flex-wrap gap-1 rounded-lg bg-muted p-1"
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => {
              setActiveTab(tab.id);
            }}
            className={`flex-1 basis-[calc(50%-0.125rem)] whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors sm:basis-0 ${
              activeTab === tab.id
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <span className="inline-flex items-center gap-1.5">
              {tab.label}
              {tab.id === "downloads" && (
                <NavCountBadge count={activeDownloads} />
              )}
            </span>
          </button>
        ))}
      </div>

      {/* Active panel */}
      <Card>
        <CardContent className="pt-4">
          {activeTab === "followed" && (
            <div className="flex flex-col gap-6">
              <MediaSearchAdd />
              <FollowedPanel
                data={followedQuery.data?.items ?? []}
                isLoading={followedQuery.isLoading}
                isError={followedQuery.isError}
                error={followedQuery.error}
              />
            </div>
          )}
          {activeTab === "wanted" && <WantedPanel />}
          {activeTab === "downloads" && <DownloadsPanel />}
          {activeTab === "obligations" && <ObligationsPanel />}
          {activeTab === "watcher" && <WatcherPanel />}
        </CardContent>
      </Card>
    </section>
  );
}
