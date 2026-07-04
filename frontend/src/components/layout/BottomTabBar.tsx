import type { ReactElement } from "react";
import { NavLink } from "react-router-dom";

import { BOTTOM_TAB_ITEMS } from "@/components/layout/nav";
import { cn } from "@/lib/utils";

/**
 * BottomTabBar — the mobile navigation surface (visible only < md).
 *
 * A fixed bottom bar with the four primary destinations (dashboard, pipeline,
 * maintenance, config). The active tab is highlighted in DS amber
 * (`text-primary`); inactive tabs are dimmed (`text-muted-foreground`). Bottom
 * padding folds in `env(safe-area-inset-bottom)` for the home-indicator gap on
 * standalone PWAs. `NavLink` also stamps `aria-current="page"` on the active tab.
 *
 * @returns The bottom tab bar element.
 */
export function BottomTabBar(): ReactElement {
  return (
    <nav
      aria-label="Navigation principale"
      className="fixed inset-x-0 bottom-0 z-50 flex border-t border-border bg-sidebar pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {BOTTOM_TAB_ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex flex-1 flex-col items-center justify-center gap-1 py-2 text-xs transition-colors",
                isActive ? "text-primary" : "text-muted-foreground",
              )
            }
          >
            <Icon className="size-5 shrink-0" aria-hidden="true" />
            <span className="truncate">{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
