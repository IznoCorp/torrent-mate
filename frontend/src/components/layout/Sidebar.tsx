import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import {
  useCallback,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

import { BrandMark } from "@/components/ds/BrandMark";
import { NavSections } from "@/components/layout/NavSections";
import { cn } from "@/lib/utils";

/** localStorage key persisting the sidebar collapsed/expanded preference. */
const COLLAPSE_STORAGE_KEY = "tm-sidebar-collapsed";

/** Read the persisted collapsed preference (defaults to expanded / `false`). */
function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSE_STORAGE_KEY) === "true";
  } catch {
    // localStorage may be unavailable (private mode / SSR) — default to expanded.
    return false;
  }
}

/**
 * Sidebar collapsed state, persisted to localStorage.
 *
 * Returns:
 *   A `[collapsed, toggle]` pair; `toggle` flips the state and writes it back
 *   (write failures are swallowed — the in-memory state still updates).
 */
function useSidebarCollapsed(): readonly [boolean, () => void] {
  const [collapsed, setCollapsed] = useState<boolean>(readCollapsed);
  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(COLLAPSE_STORAGE_KEY, String(next));
      } catch {
        // Persisting failed — keep the toggled in-memory value regardless.
      }
      return next;
    });
  }, []);
  return [collapsed, toggle] as const;
}

/**
 * Sidebar — the desktop navigation rail (visible only ≥ md).
 *
 * Renders the grouped {@link NavSections} (Supervision / Système /
 * Configuration). The active entry is highlighted in DS amber (`text-primary`)
 * over a subtle accent surface; inactive entries are dimmed and disabled stubs
 * are greyed. A footer toggle collapses the rail to an icon strip, persisting
 * the choice across reloads via localStorage.
 *
 * @returns The sidebar element.
 */
export function Sidebar({
  badges,
}: {
  readonly badges?: Record<string, ReactNode>;
}): ReactElement {
  const [collapsed, toggle] = useSidebarCollapsed();

  return (
    <aside
      className={cn(
        "hidden shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex sticky top-0 h-screen overflow-y-auto",
        collapsed ? "md:w-16" : "md:w-56",
      )}
    >
      <div
        className={cn(
          "flex items-center gap-2 border-b border-sidebar-border px-4 py-4",
          collapsed && "justify-center px-0",
        )}
      >
        <BrandMark className="shrink-0" />
        {!collapsed && (
          <span className="text-sm font-semibold tracking-tight">
            Torrent<span className="text-primary">Mate</span>
          </span>
        )}
      </div>

      <NavSections
        ariaLabel="Navigation latérale"
        collapsed={collapsed}
        {...(badges ? { badges } : {})}
      />

      <div className="border-t border-sidebar-border p-2">
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? "Déployer le menu" : "Réduire le menu"}
          aria-expanded={!collapsed}
          className={cn(
            "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent/50 hover:text-foreground",
            collapsed && "justify-center px-0",
          )}
        >
          {collapsed ? (
            <PanelLeftOpen className="size-5 shrink-0" aria-hidden="true" />
          ) : (
            <PanelLeftClose className="size-5 shrink-0" aria-hidden="true" />
          )}
          {!collapsed && <span>Réduire</span>}
        </button>
      </div>
    </aside>
  );
}
