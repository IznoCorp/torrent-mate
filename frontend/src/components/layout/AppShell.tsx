import {
  useMemo,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import { Outlet } from "react-router-dom";

import { EventStreamProvider } from "@/components/EventStreamProvider";
import { BottomTabBar } from "@/components/layout/BottomTabBar";
import { NavSections } from "@/components/layout/NavSections";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { NavCountBadge } from "@/components/ds/NavCountBadge";
import { BrandMark } from "@/components/ds/BrandMark";
import { StatusDot } from "@/components/ds/StatusDot";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { usePipelineStatus } from "@/hooks/usePipelineStatus";
import { useStagingMedia } from "@/hooks/useStagingMedia";
import { useWanted } from "@/hooks/useAcquisition";
import { useWsInvalidation } from "@/hooks/useWsInvalidation";
import { SHELL_BADGE_EVENT_TYPES } from "@/api/events";
import { decisionsKeys } from "@/api/decisions";
import { pipelineKeys } from "@/api/pipeline";
import { stagingMediaKeys } from "@/hooks/useStagingMedia";

/**
 * AppShellInner — the shell content with access to the event-stream context
 * (mounted inside {@link EventStreamProvider}).  Owns three nav badge queries
 * ({@link NavCountBadge} for /medias and /acquisition, {@link StatusDot} for
 * /pipeline) and the WebSocket listener that refreshes the staging badge,
 * decisions, and pipeline history on run-lifecycle + step-boundary events
 * ({@link useStagingMedia} has its own WS listener for the grid; /acquisition
 * polls at 60 s — no WS dependency).
 *
 * @returns The shell layout element.
 */
function AppShellInner(): ReactElement {
  const [navOpen, setNavOpen] = useState<boolean>(false);

  // ── Badge 1: /medias = awaiting_action count from staging ──────────
  // page_size=1 so we pull only the counts aggregate, not the full list.
  // Poll at 60 s (DESIGN §1.1 — the endpoint runs a filesystem scan, so
  // the badge query must not inherit the grid's 8 s cadence).
  const { data: stagingData, isError: stagingIsError } = useStagingMedia(
    { page_size: 1 },
    { refetchInterval: 60_000, staleTime: 55_000 },
  );
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- runtime schema-drift guard (SF-6)
  const awaitingAction: number = stagingData?.counts?.awaiting_action ?? 0;

  // ── Badge 2: /pipeline = running dot when a run is active ────────────
  const { snapshot: pipelineStatus } = usePipelineStatus();
  const pipelineRunning: boolean = pipelineStatus.state !== "idle";

  // ── Badge 3: /acquisition = pending wanted count ─────────────────────
  const { data: wantedData, isError: wantedIsError } = useWanted(
    { status: "pending", page_size: 1 },
    { refetchInterval: 60_000, staleTime: 55_000 },
  );
  const pendingWanted: number = wantedData?.total ?? 0;

  // ── WS listener: invalidate staging counts + decisions + pipeline ───
  // history on ItemProgressed status changes and run-lifecycle events
  // (PipelineStarted included — deliberate widening vs the DESIGN's
  // "run-finished" wording, because a run start flips the pipeline dot from
  // idle and a new scrape tick may have queued decision rows). The pipeline-
  // status invalidation is handled by usePipelineStatus's own listener;
  // the acquisition badge has no WS dependency (wanted state changes on
  // its own 60 s poll cycle). The shared map scans every event appended since
  // the last render (fresh-slice), so a batched replay burst is never dropped.
  useWsInvalidation([
    {
      types: SHELL_BADGE_EVENT_TYPES,
      keys: [stagingMediaKeys.all, pipelineKeys.history, decisionsKeys.all],
    },
  ]);

  // ── Badge map — entries inserted only when non-zero/active, or when ─
  // the query backing the badge is in error (an indeterminate "?" marker
  // replaces the silent absence).
  const badges = useMemo<Record<string, ReactNode>>(() => {
    const map: Record<string, ReactNode> = {};
    if (stagingIsError) {
      map["/medias"] = (
        <span
          data-slot="nav-count"
          className="inline-flex h-[1.125rem] min-w-[1.125rem] items-center justify-center rounded-full bg-danger px-1 text-[0.6875rem] font-semibold leading-none text-danger-foreground shadow-sm ring-2 ring-sidebar"
          aria-label="Compteur indisponible"
        >
          ?
        </span>
      );
    } else if (awaitingAction > 0) {
      map["/medias"] = <NavCountBadge count={awaitingAction} />;
    }
    if (pipelineStatus.state === "paused") {
      map["/pipeline"] = (
        <StatusDot
          status="warning"
          showLabel={false}
          aria-label="Pipeline en pause"
        />
      );
    } else if (pipelineRunning) {
      map["/pipeline"] = (
        <StatusDot
          status="running"
          showLabel={false}
          aria-label="Pipeline en cours d'exécution"
        />
      );
    }
    if (wantedIsError) {
      map["/acquisition"] = (
        <span
          data-slot="nav-count"
          className="inline-flex h-[1.125rem] min-w-[1.125rem] items-center justify-center rounded-full bg-danger px-1 text-[0.6875rem] font-semibold leading-none text-danger-foreground shadow-sm ring-2 ring-sidebar"
          aria-label="Compteur indisponible"
        >
          ?
        </span>
      );
    } else if (pendingWanted > 0) {
      map["/acquisition"] = <NavCountBadge count={pendingWanted} />;
    }
    return map;
  }, [
    awaitingAction,
    pipelineRunning,
    pendingWanted,
    stagingIsError,
    wantedIsError,
    pipelineStatus.state,
  ]);

  return (
    <div className="flex min-h-screen bg-background font-sans text-foreground">
      <Sidebar badges={badges} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          onOpenNav={() => {
            setNavOpen(true);
          }}
        />
        <main className="flex-1 p-4 pb-[calc(env(safe-area-inset-bottom)+5rem)] md:p-6 md:pb-6 max-w-7xl mx-auto w-full">
          <Outlet />
        </main>
      </div>
      <BottomTabBar badges={badges} />

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
            badges={badges}
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
