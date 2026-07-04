import type { ReactElement } from "react";
import { Outlet } from "react-router-dom";

import { EventStreamProvider } from "@/components/EventStreamProvider";
import { BottomTabBar } from "@/components/layout/BottomTabBar";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

/**
 * AppShell — the responsive layout route wrapping every authenticated page.
 *
 * Mobile-first: a fixed {@link BottomTabBar} (< md) gives way to a collapsible
 * {@link Sidebar} (≥ md). The {@link TopBar} stays sticky at the top on every
 * viewport, and the routed page renders through `<Outlet />`.
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
      <div className="flex min-h-screen bg-background font-sans text-foreground">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main className="flex-1 p-4 pb-[calc(env(safe-area-inset-bottom)+5rem)] md:p-6 md:pb-6">
            <Outlet />
          </main>
        </div>
        <BottomTabBar />
      </div>
    </EventStreamProvider>
  );
}
