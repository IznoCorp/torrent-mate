import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import { Outlet } from "react-router-dom";

import { EventStreamProvider } from "@/components/EventStreamProvider";
import { BottomTabBar } from "@/components/layout/BottomTabBar";
import { NavSections } from "@/components/layout/NavSections";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { NavCountBadge } from "@/components/ds/NavCountBadge";
import { BrandMark } from "@/components/ds/BrandMark";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { decisionsKeys } from "@/api/decisions";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";
import { useDecisions } from "@/hooks/useDecisions";
import { useQueryClient } from "@tanstack/react-query";
import { isEvent } from "@/api/events";

/**
 * AppShellInner — the shell content with access to the event-stream context
 * (mounted inside {@link EventStreamProvider}).  Owns the pending-count badge
 * query and the WebSocket listener that refreshes it on
 * ``queued_for_decision`` events.
 *
 * @returns The shell layout element.
 */
function AppShellInner(): ReactElement {
  const [navOpen, setNavOpen] = useState<boolean>(false);
  const queryClient = useQueryClient();
  const { events } = useEventStreamContext();

  // Lightweight count-only query for the badge — page_size=1 so we never
  // pull the full list just to show the chip.
  const { data } = useDecisions({ status: "pending", page_size: 1 });
  const pendingCount: number = data?.pending_count ?? 0;

  // Listen for ItemProgressed WS events carrying status "queued_for_decision"
  // and invalidate the decisions cache so the badge refreshes live.
  //
  // Scan every event appended since the last render, not just the last one:
  // useEventStream coalesces a synchronous replay burst (reconnect, or several
  // items in one scrape tick) into ONE re-render, so inspecting only
  // events[length-1] would silently drop a queued_for_decision buried in the
  // batch (coherence study F13).
  const lastProcessedRef = useRef(0);
  useEffect(() => {
    const start = Math.min(lastProcessedRef.current, events.length);
    const fresh = events.slice(start);
    lastProcessedRef.current = events.length;
    const hasQueued = fresh.some(
      (e) =>
        isEvent(e) &&
        e.type === "ItemProgressed" &&
        e.data.status === "queued_for_decision",
    );
    if (hasQueued) {
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
      void queryClient.invalidateQueries({
        queryKey: ["pipeline", "history"],
      });
    }
  }, [events, queryClient]);

  const badges = useMemo(
    () =>
      pendingCount > 0
        ? {
            "/scraping": <NavCountBadge count={pendingCount} />,
          }
        : undefined,
    [pendingCount],
  );

  return (
    <div className="flex min-h-screen bg-background font-sans text-foreground">
      <Sidebar {...(badges ? { badges } : {})} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          onOpenNav={() => {
            setNavOpen(true);
          }}
        />
        <main className="flex-1 p-4 pb-[calc(env(safe-area-inset-bottom)+5rem)] md:p-6 md:pb-6">
          <Outlet />
        </main>
      </div>
      <BottomTabBar {...(badges ? { badges } : {})} />

      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetContent side="left" className="w-72 gap-0 p-0">
          <SheetHeader className="border-b border-sidebar-border">
            <SheetTitle className="flex items-center gap-2 text-sm tracking-tight">
              <BrandMark className="shrink-0" />
              <span>
                Torrent<span className="text-primary">Mate</span>
              </span>
            </SheetTitle>
            <SheetDescription className="sr-only">
              Menu de navigation principal
            </SheetDescription>
          </SheetHeader>
          <NavSections
            ariaLabel="Navigation mobile"
            {...(badges ? { badges } : {})}
            onNavigate={() => {
              setNavOpen(false);
            }}
          />
        </SheetContent>
      </Sheet>
    </div>
  );
}

/**
 * AppShell — the responsive layout route wrapping every authenticated page.
 *
 * Mobile-first: a fixed {@link BottomTabBar} (< md) gives way to a collapsible
 * {@link Sidebar} (≥ md). The {@link TopBar} stays sticky at the top on every
 * viewport, and the routed page renders through `<Outlet />`. On mobile a
 * hamburger in the TopBar opens a left {@link Sheet} carrying the same grouped
 * {@link NavSections} as the desktop rail; this shell owns that Sheet's open
 * state and closes it on navigation.
 *
 * The whole tree is wrapped in {@link EventStreamProvider}: the app's single
 * live-event WebSocket is opened here — inside the authenticated shell, so the
 * login page never connects — and shared by the TopBar's connection dot and the
 * dashboard feed via `useEventStreamContext`.
 *
 * The main scroll region reserves bottom room on mobile (bar height +
 * `env(safe-area-inset-bottom)`) so content never hides behind the fixed tab
 * bar; on desktop that reservation collapses to normal padding.
 *
 * @returns The app shell layout element.
 */
export function AppShell(): ReactElement {
  return (
    <EventStreamProvider>
      <AppShellInner />
    </EventStreamProvider>
  );
}
