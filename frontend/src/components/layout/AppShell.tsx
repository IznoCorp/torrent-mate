import { useState, type ReactElement } from "react";
import { Outlet } from "react-router-dom";

import { EventStreamProvider } from "@/components/EventStreamProvider";
import { BottomTabBar } from "@/components/layout/BottomTabBar";
import { NavSections } from "@/components/layout/NavSections";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { BRAND_ICON } from "@/lib/env";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

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
  const [navOpen, setNavOpen] = useState<boolean>(false);

  return (
    <EventStreamProvider>
      <div className="flex min-h-screen bg-background font-sans text-foreground">
        <Sidebar />
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
        <BottomTabBar />

        <Sheet open={navOpen} onOpenChange={setNavOpen}>
          <SheetContent side="left" className="w-72 gap-0 p-0">
            <SheetHeader className="border-b border-sidebar-border">
              <SheetTitle className="flex items-center gap-2 text-sm tracking-tight">
                <img src={BRAND_ICON} alt="" className="size-7 shrink-0" />
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
              onNavigate={() => {
                setNavOpen(false);
              }}
            />
          </SheetContent>
        </Sheet>
      </div>
    </EventStreamProvider>
  );
}
