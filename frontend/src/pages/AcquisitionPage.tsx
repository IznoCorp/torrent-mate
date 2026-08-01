/**
 * Acquisition + Watcher page (acq-watch feature).
 *
 * Four tabbed panels — Followed (CRUD), File d&apos;acquisition (wanted queue
 * + live downloads), Obligations (seed/ratio), Watcher (status + toggle +
 * recent runs) — each extracted into its own component under
 * ``components/acquisition/`` (C12). This shell owns only the tab state, the
 * shared followed query, the downloads poll (for the File d&apos;acquisition
 * badge), and the live-event invalidation.
 *
 * Live updates: the acquisition event stream (via useEventStreamContext)
 * invalidates the matching query when a relevant event arrives, using the R13
 * new-events-only ref pattern.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, type ReactElement } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { acqKeys } from "@/api/acquisition";
import { FileDAcquisitionPanel } from "@/components/acquisition/FileDAcquisitionPanel";
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
import { OverviewPanel } from "@/components/acquisition/OverviewPanel";
import { ParcoursPanel } from "@/components/acquisition/ParcoursPanel";
import { ReglagesPanel } from "@/components/acquisition/ReglagesPanel";
import { WatcherPanel } from "@/components/acquisition/WatcherPanel";
import { NavCountBadge } from "@/components/ds/NavCountBadge";
import { PageHeader } from "@/components/ds/PageHeader";
import { useDownloads, useFollowed } from "@/hooks/useAcquisition";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";
import { handleTablistKeyDown } from "@/lib/tablist";

/**
 * AcquisitionPage — the authenticated acquisition route (``/acquisition``).
 *
 * Four tabbed panels for followed series CRUD, File d&apos;acquisition
 * (wanted queue + live downloads), seed obligations, and watcher status.
 * This shell also owns the downloads poll so the File d&apos;acquisition tab
 * badge renders the live download count. Live events from the WebSocket
 * invalidate the matching TanStack Query caches (R13 — processes only new
 * events, not the whole ring on every render).
 *
 * Returns:
 *   The acquisition page element.
 */
export default function AcquisitionPage(): ReactElement {
  // The active tab is URL-addressable (?tab=<id>) — DOIT-10: the tab is a
  // shareable deep-link and Back returns to the previous tab. Derived from the
  // URL (single source of truth); the default "followed" carries no param so
  // /acquisition stays clean and ?tab=file is the shareable form.
  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = searchParams.get("tab");

  // Redirect legacy ?tab=wanted|downloads → ?tab=file (replace so Back doesn't
  // cycle through the redirect — DOIT-10 deep-link survives).
  useEffect(() => {
    if (rawTab === "wanted" || rawTab === "downloads") {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("tab", "file");
          return next;
        },
        { replace: true },
      );
    }
  }, [rawTab, setSearchParams]);

  const activeTab: TabId = TABS.some((t) => t.id === rawTab)
    ? (rawTab as TabId)
    : "followed";
  // ACQUISITION-7 (ticket 250): keyboard-driven activation (arrows follow
  // focus) REPLACES the current history entry — holding ArrowRight must not
  // stack one entry per keystroke. Click activation keeps push (D3
  // addressable URLs: Back returns to the previous tab).
  const setActiveTab = useCallback(
    (id: TabId, viaKeyboard = false) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (id === "followed") next.delete("tab");
          else next.set("tab", id);
          return next;
        },
        { replace: viaKeyboard },
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

      // reswitch (ticket 342) — tell the operator WHY an « en cours » item just
      // went back to searching (a dead/blocked release was swapped). The wanted
      // invalidation below still runs so the card refreshes.
      if (msg.type === "GrabReswitched") {
        toast.info("Source bloquée — bascule vers une autre release.");
      }

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

  // Arrival badge on the « File d&apos;acquisition » tab (A4 limite avouée
  // s2): the count of torrents still downloading, visible without opening
  // the tab. This shell owns the downloads poll so the badge is always live.
  const downloadsQuery = useDownloads();
  const activeDownloads = (downloadsQuery.data?.downloads ?? []).filter(
    (d) => d.state !== "missing" && d.progress < 1,
  ).length;

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader title="Acquisition" />

      {/* Tabs — horizontal scroll on narrow screens (5 tabs at ~390px: no wrap,
          natural width per tab, scroll inside the tablist). On sm+ tabs fill
          the row evenly (flex-1). E5 segmented control.
          ACQUISITION-7 (ticket 250): full WAI-ARIA tablist wiring — roving
          tabIndex + arrow-key navigation + tab/panel linkage. */}
      <div
        role="tablist"
        aria-label="Sections de la page Acquisition"
        className="flex flex-nowrap gap-1 overflow-x-auto rounded-lg bg-muted p-1"
        onKeyDown={(e) => {
          handleTablistKeyDown(
            e,
            TABS.map((t) => t.id),
            activeTab,
            (id) => {
              setActiveTab(id, true);
            },
            (id) => `acq-tab-${id}`,
          );
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            id={`acq-tab-${tab.id}`}
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls="acq-tabpanel"
            tabIndex={activeTab === tab.id ? 0 : -1}
            onClick={() => {
              setActiveTab(tab.id);
            }}
            className={`whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors sm:flex-1 ${
              activeTab === tab.id
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <span className="inline-flex items-center gap-1.5">
              {tab.label}
              {tab.id === "file" && <NavCountBadge count={activeDownloads} />}
            </span>
          </button>
        ))}
      </div>

      {/* Active panel — no wrapping Card: the tab content uses the full width
          (esp. mobile), where a Card's border + padding stacked on the section
          margin wasted space on both sides (#12). Vertical rhythm kept via gap. */}
      <div
        id="acq-tabpanel"
        role="tabpanel"
        aria-labelledby={`acq-tab-${activeTab}`}
        className="flex flex-col gap-4 pt-1"
      >
        {activeTab === "apercu" && <OverviewPanel />}
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
        {activeTab === "file" && <FileDAcquisitionPanel />}
        {activeTab === "obligations" && <ObligationsPanel />}
        {activeTab === "watcher" && <WatcherPanel />}
        {activeTab === "parcours" && <ParcoursPanel />}
        {activeTab === "reglages" && <ReglagesPanel />}
      </div>
    </section>
  );
}
