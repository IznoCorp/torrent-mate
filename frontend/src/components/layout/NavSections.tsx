import type { ReactElement, ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { NAV_SECTIONS, type NavItem } from "@/components/layout/nav";
import { cn } from "@/lib/utils";

/** Props shared by the desktop rail and the mobile Sheet nav. */
interface NavSectionsProps {
  /**
   * Accessible landmark name for the `<nav>`. Distinct per surface (sidebar vs
   * mobile Sheet) so multiple nav landmarks stay disambiguated.
   */
  readonly ariaLabel: string;
  /**
   * Collapsed (icon-only) desktop rail: hides item labels, section micro-labels
   * and wave chips, centring each icon. Never set on the mobile Sheet.
   */
  readonly collapsed?: boolean;
  /**
   * Called after a real (enabled) destination is chosen — used by the mobile
   * Sheet to close itself on navigation.
   */
  readonly onNavigate?: () => void;
  /**
   * Optional per-path badge nodes rendered next to the label (e.g. pending-count
   * chip on the Médias entry).  Keys are router paths (``"/medias"``);
   * missing keys render no badge.
   */
  readonly badges?: Record<string, ReactNode>;
}

/** Props for a single rendered nav row. */
interface NavRowProps {
  readonly item: NavItem;
  readonly collapsed: boolean;
  readonly onNavigate?: (() => void) | undefined;
  /** Optional badge node rendered next to the label (e.g. pending count). */
  readonly badge?: ReactNode;
}

/**
 * One nav row: an active-aware {@link NavLink} for a live destination, or a
 * non-interactive greyed stub (with a mono wave chip) for a disabled entry.
 *
 * @returns The row element.
 */
function NavRow({
  item,
  collapsed,
  onNavigate,
  badge,
}: NavRowProps): ReactElement {
  const Icon = item.icon;

  if (item.disabled) {
    return (
      <div
        aria-disabled="true"
        title={collapsed ? `${item.label} · ${item.wave ?? ""}` : undefined}
        className={cn(
          "flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground opacity-50",
          collapsed && "justify-center px-0",
        )}
      >
        <Icon className="size-5 shrink-0" aria-hidden="true" />
        {!collapsed && (
          <>
            <span className="truncate">{item.label}</span>
            {item.wave && (
              <span className="ml-auto rounded-sm bg-muted px-1.5 py-0.5 font-mono text-[length:var(--text-2xs)] text-muted-foreground">
                {item.wave}
              </span>
            )}
          </>
        )}
      </div>
    );
  }

  return (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      title={collapsed ? item.label : undefined}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-sidebar-accent text-primary"
            : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
          collapsed && "justify-center px-0",
        )
      }
    >
      <Icon className="size-5 shrink-0" aria-hidden="true" />
      {!collapsed && <span className="truncate">{item.label}</span>}
      {badge}
    </NavLink>
  );
}

/**
 * NavSections — the grouped navigation shared by the desktop {@link Sidebar}
 * and the mobile nav Sheet.
 *
 * Renders every {@link NAV_SECTIONS} group with an uppercase micro-label and a
 * hairline separator above each section (except the first). The active entry is
 * highlighted in DS amber (`text-primary`) over a subtle accent surface;
 * disabled entries are greyed and non-interactive. When `collapsed`, labels and
 * section titles are hidden for the icon-only rail — the separators remain.
 *
 * @returns The grouped `<nav>` element.
 */
export function NavSections({
  ariaLabel,
  collapsed = false,
  onNavigate,
  badges,
}: NavSectionsProps): ReactElement {
  return (
    <nav aria-label={ariaLabel} className="flex flex-1 flex-col gap-1 p-2">
      {NAV_SECTIONS.map((section, index) => (
        <div
          key={section.title}
          className={cn(
            "flex flex-col gap-1",
            index > 0 && "mt-2 border-t border-sidebar-border pt-2",
          )}
        >
          {!collapsed && (
            <p className="px-3 pb-1 text-[length:var(--text-2xs)] font-medium uppercase tracking-[0.08em] text-muted-foreground">
              {section.title}
            </p>
          )}
          {section.items.map((item) => (
            <NavRow
              key={item.to}
              item={item}
              collapsed={collapsed}
              onNavigate={onNavigate}
              badge={badges?.[item.to]}
            />
          ))}
        </div>
      ))}
    </nav>
  );
}
