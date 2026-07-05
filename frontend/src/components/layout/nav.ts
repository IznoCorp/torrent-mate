/**
 * Navigation model shared by the app shell's two nav surfaces.
 *
 * The {@link Sidebar} (desktop, ≥ md) renders every entry in {@link NAV_ITEMS};
 * the {@link BottomTabBar} (mobile, < md) renders the four-item subset whose
 * paths are listed in {@link BOTTOM_TAB_PATHS}. Keeping the list in one place
 * keeps both surfaces — and the router's route table — in lock-step.
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
}

/**
 * The full navigation set, in display order.
 *
 * Dashboard (`/`) plus the six S2–S7 slot routes. The trailing slots stay
 * navigable even before their wave ships — each lands on a shared "À venir"
 * placeholder — so navigation and route-gating exist from day one (DESIGN §5.2).
 */
export const NAV_ITEMS: readonly NavItem[] = [
  { to: "/", label: "Tableau de bord", icon: Home },
  { to: "/pipeline", label: "Pipeline", icon: Activity },
  { to: "/maintenance", label: "Maintenance", icon: Wrench },
  { to: "/scraping", label: "Scraping", icon: ScanSearch },
  { to: "/acquisition", label: "Acquisition", icon: Radar },
  { to: "/registry", label: "Registre", icon: Plug },
  { to: "/config", label: "Config", icon: Settings },
];

/**
 * Paths shown in the mobile bottom tab bar (a four-item subset of
 * {@link NAV_ITEMS}): dashboard, pipeline, maintenance, config.
 */
export const BOTTOM_TAB_PATHS: readonly string[] = [
  "/",
  "/pipeline",
  "/maintenance",
  "/config",
];

/** The subset of {@link NAV_ITEMS} rendered by the bottom tab bar. */
export const BOTTOM_TAB_ITEMS: readonly NavItem[] = NAV_ITEMS.filter((item) =>
  BOTTOM_TAB_PATHS.includes(item.to),
);
