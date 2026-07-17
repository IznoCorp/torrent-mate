import type { ReactElement, ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { BOTTOM_TAB_ITEMS } from "@/components/layout/nav";
import { cn } from "@/lib/utils";

/**
 * BottomTabBar — the mobile navigation surface (visible only < md).
 *
 * A fixed bottom bar with the four primary destinations (Contrôle · Pipeline ·
 * Médias · Acquisition) — the design-system reference TabBar set, which
 * excludes the dashboard and the disabled stubs. The active tab is highlighted
 * in DS amber (`text-primary`); inactive tabs are dimmed
 * (`text-muted-foreground`). Each tab is a ≥ 44 px touch target (`min-h-11`).
 * Bottom padding folds in `env(safe-area-inset-bottom)` for the home-indicator
 * gap on standalone PWAs. `NavLink` also stamps `aria-current="page"` on the
 * active tab.
 *
 * Args:
 *   badges: Optional per-path badge nodes rendered next to the label (e.g.
 *       pending-count chip on a tab).  Keys are router paths;
 *       missing keys render no badge.
 *
 * @returns The bottom tab bar element.
 */
export function BottomTabBar({
  badges,
}: {
  readonly badges?: Record<string, ReactNode>;
}): ReactElement {
  return (
    <nav
      aria-label="Navigation principale"
      className="fixed inset-x-0 bottom-0 z-50 flex border-t border-border bg-sidebar pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {BOTTOM_TAB_ITEMS.map((item) => {
        const Icon = item.icon;
        const badge = badges?.[item.to];
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex min-h-11 flex-1 flex-col items-center justify-center gap-1 py-2 text-xs transition-colors",
                isActive ? "text-primary" : "text-muted-foreground",
              )
            }
          >
            {/* Badge is a corner superscript on the icon so it never becomes a
                third flow child that makes the tab taller (SHELL-2). */}
            <span className="relative">
              <Icon className="size-5 shrink-0" aria-hidden="true" />
              {badge != null && (
                <span className="absolute -right-2.5 -top-1.5">{badge}</span>
              )}
            </span>
            <span className="truncate">{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
