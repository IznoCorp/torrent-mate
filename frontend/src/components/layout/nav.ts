/**
 * Navigation model shared by the app shell's nav surfaces.
 *
 * The nav is organised into labelled {@link NavSection}s ("Supervision",
 * "Système", "Configuration"). The desktop {@link Sidebar} and the mobile nav
 * Sheet both render {@link NAV_SECTIONS} through the shared `NavSections`
 * component; the mobile {@link BottomTabBar} renders the four-item subset whose
 * paths are listed in {@link BOTTOM_TAB_PATHS}. {@link NAV_ITEMS} is the flat
 * projection of every section, kept for callers that need the full list.
 * Keeping the model in one place keeps every surface — and the router's route
 * table — in lock-step.
 */

import {
  Activity,
  Home,
  Plug,
  Radar,
  ScanSearch,
  Settings,
  Wrench,
  type LucideIcon,
} from "lucide-react";

/** A single navigation destination surfaced by the shell. */
export interface NavItem {
  /** Router path (also the React Router `to`). */
  readonly to: string;
  /** French label rendered next to (or under) the icon. */
  readonly label: string;
  /** Lucide icon component for the entry. */
  readonly icon: LucideIcon;
  /**
   * When `true` the entry is a non-interactive stub whose wave has not shipped
   * yet (Registre → S6). It renders greyed and unclickable — never
   * a `NavLink` — with its {@link wave} tag shown as a hint chip.
   */
  readonly disabled?: boolean;
  /** Short wave tag (e.g. `"S6"`) shown as a mono chip on {@link disabled} entries. */
  readonly wave?: string;
}

/** A labelled group of {@link NavItem}s rendered as one section of the nav. */
export interface NavSection {
  /** Uppercase micro-label shown above the section's items. */
  readonly title: string;
  /** The section's entries, in display order. */
  readonly items: readonly NavItem[];
}

/**
 * The grouped navigation model, in display order.
 *
 * - **Supervision** — the live-supervision surfaces (dashboard + the pipeline,
 *   scraping and acquisition views).
 * - **Système** — operational maintenance.
 * - **Configuration** — Registre (S6), a disabled stub
 *   until their wave ships.
 *
 * Every path here has a matching route in the router table (DESIGN §5.2): the
 * not-yet-shipped waves land on a shared "À venir" placeholder, so navigation
 * and route-gating exist from day one.
 */
export const NAV_SECTIONS: readonly NavSection[] = [
  {
    title: "Supervision",
    items: [
      { to: "/", label: "Tableau de bord", icon: Home },
      { to: "/pipeline", label: "Pipeline", icon: Activity },
      { to: "/scraping", label: "Scraping", icon: ScanSearch },
      { to: "/acquisition", label: "Acquisition", icon: Radar },
    ],
  },
  {
    title: "Système",
    items: [{ to: "/maintenance", label: "Maintenance", icon: Wrench }],
  },
  {
    title: "Configuration",
    items: [
      { to: "/registry", label: "Registre", icon: Plug, disabled: true, wave: "S6" },
      { to: "/config", label: "Config", icon: Settings },
    ],
  },
];

/** The flat projection of every {@link NavSection}'s items, in display order. */
export const NAV_ITEMS: readonly NavItem[] = NAV_SECTIONS.flatMap(
  (section) => section.items,
);

/**
 * Paths shown in the mobile bottom tab bar — a four-item subset of
 * {@link NAV_ITEMS}: Pipeline · Scraping · Acquisition · Maintenance.
 *
 * Mirrors the design-system reference TabBar, which excludes the dashboard and
 * every disabled stub. Maintenance sits last (4th).
 */
export const BOTTOM_TAB_PATHS: readonly string[] = [
  "/pipeline",
  "/scraping",
  "/acquisition",
  "/maintenance",
];

/**
 * The subset of {@link NAV_ITEMS} rendered by the bottom tab bar.
 *
 * Filtering `NAV_ITEMS` (rather than mapping `BOTTOM_TAB_PATHS`) preserves the
 * nav's display order, which already yields Pipeline · Scraping · Acquisition ·
 * Maintenance.
 */
export const BOTTOM_TAB_ITEMS: readonly NavItem[] = NAV_ITEMS.filter((item) =>
  BOTTOM_TAB_PATHS.includes(item.to),
);
