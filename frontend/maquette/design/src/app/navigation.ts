// THE NAVIGATION TABLE — one row per page, and the only declaration of what
// pages exist.
//
// It replaces FOUR lists that were kept identical by hand: `PAGES_OF()` in the
// dying engine (id, label, icon, badge, off-bar, action button), `NAVIGATION`
// in the same file (the drawer's grouping), `PAGES` in `page-host.tsx`
// (id → component) and, for the badge, a derivation written beside each of
// them. A fact that exists four times is stale in three of them, and this one
// was: the drawer carried an entry naming an id no page carried, and answered a
// tap with a message.
//
// INVARIANT 10 NAMES THIS TABLE BY NAME — « whatever table the shell reads to
// compose navigation » — which is why it may say `Acquisition` where the rest
// of `app/` may not. What it must NOT do is say anything ELSE about a domain:
// a badge is a FUNCTION the row points at, exported by the feature that knows
// what it counts, so the frame names the feature once and its counters never.
//
// THE ADDRESS STAYS `lib/addresses.ts`'s. That module is invariant 10's FIRST
// named exception — an address IS a page's identity (D1) — and it is imported
// by routes and by features, so a table that carried the paths and the page
// COMPONENTS would drag every feature into everything that resolves an
// address, and `features/x → lib/addresses → app/navigation → features/x` is
// an import cycle (invariant 8). The direction is therefore app → lib: the
// table reads the address model, and `path` below is typed so a page with no
// declared address does not compile.
//
// THE LABEL IS A KEY, never a word. `fr.json`'s `navigation.pages.*` carries
// what a reader sees, and `page-host.tsx`'s hidden heading — which used to read
// the label off the engine's own table because copying it « would create a
// second source that drifts silently » — reads the key now. That was the one
// step D5 asked for, and this is it.
import type { ReactElement } from "react";

import { AccountPage } from "../features/account/page";
import { AcquisitionPage } from "../features/acquisition/page";
import { acquisitionBadge } from "../features/acquisition/queries";
import { ArrivalsPage } from "../features/arrivals/page";
import { arrivalsBadge } from "../features/arrivals/queries";
import { LibraryPage } from "../features/library/page";
import { MaintenancePage } from "../features/maintenance/page";
import { NotFoundPage } from "./not-found";
import { SettingsPage } from "../features/settings/page";
import { SystemPage } from "../features/system/page";
import { PAGE_PATHS } from "../lib/addresses";
import { icons } from "./icons";

/** The groups the drawer sorts its entries into, by what one goes there FOR. */
export type NavigationGroup = "supervision" | "system" | "configuration";

export type NavigationRow = {
  /** The page id — the value of `state.page`, and an address. Data, not a name. */
  id: string;
  /** Its address, declared by `lib/addresses.ts`. The 404 page has none. */
  path?: string;
  /** What draws it. The frame names the feature; it never draws for it. */
  Body: () => ReactElement | null;
  /** The single root the page emits, where it emits one. */
  root?: string;
  /** The recorded oracle's anchor for this page's body (`regions.json`). */
  region?: string;
  /** Its name, in `fr.json` under `navigation.pages`. */
  labelKey: string;
  /** The icon's path data — `app/icons.ts`, one copy, engine included. */
  icon: string;
  /** Where the drawer files it. A page with no group is not in the drawer. */
  group?: NavigationGroup;
  /** Whether it sits in the bottom bar. */
  inBar: boolean;
  /** Whether it offers the frame's floating action button. */
  actionButton?: boolean;
  /**
   * What awaits the operator on this page, or nothing.
   *
   * A FUNCTION the row points at, never a number: the count is server state
   * and lives in the query cache (invariant 4). It is synchronous because the
   * dying engine reads it too, through the seam, in the middle of its own
   * task — and it reads the SAME derivation the page draws, which is §13's own
   * rule (one derivation per question) and the reason the engine's table said
   * so in a comment.
   */
  badge?: () => number;
};

/**
 * Every page, in the order the bottom bar draws them.
 *
 * Réglages and Maintenance are PAGES and not tabs, and that is a decision the
 * engine's own table recorded: the bar holds the four places one goes to SEE
 * what is happening; a setting is what one goes to CHANGE and a maintenance
 * command is something one goes to DO. They are reached from Système and from
 * the drawer, and the back gesture walks out of them like any other page.
 */
export const NAVIGATION: readonly NavigationRow[] = [
  {
    id: "acq",
    path: PAGE_PATHS.acq,
    Body: AcquisitionPage,
    labelKey: "navigation.pages.acq",
    icon: icons.radar,
    group: "supervision",
    inBar: true,
    actionButton: true,
    badge: acquisitionBadge,
  },
  {
    id: "lib",
    path: PAGE_PATHS.lib,
    Body: LibraryPage,
    labelKey: "navigation.pages.lib",
    icon: icons.library,
    group: "supervision",
    inBar: true,
  },
  {
    id: "arr",
    path: PAGE_PATHS.arr,
    Body: ArrivalsPage,
    root: "body",
    region: "arrivals/body",
    labelKey: "navigation.pages.arr",
    icon: icons.inbox,
    group: "supervision",
    inBar: true,
    badge: arrivalsBadge,
  },
  {
    id: "sys",
    path: PAGE_PATHS.sys,
    Body: SystemPage,
    root: "body",
    region: "system/body",
    labelKey: "navigation.pages.sys",
    icon: icons.wrench,
    group: "system",
    inBar: true,
  },
  {
    id: "maint",
    path: PAGE_PATHS.maint,
    Body: MaintenancePage,
    root: "body",
    region: "maintenance/body",
    labelKey: "navigation.pages.maint",
    icon: icons.refresh,
    group: "system",
    inBar: false,
  },
  {
    id: "cfg",
    path: PAGE_PATHS.cfg,
    Body: SettingsPage,
    root: "body",
    region: "settings/body",
    labelKey: "navigation.pages.cfg",
    icon: icons.sort,
    group: "configuration",
    inBar: false,
  },
  {
    // french-ok: this id IS the value of `state.page` and the page's address.
    // It is data, not a property name: renaming it left the shell unable to
    // find the page at all, and the account surface drew nothing.
    id: "profile",
    path: PAGE_PATHS.profile,
    Body: AccountPage,
    root: "body",
    region: "account/body",
    labelKey: "navigation.pages.profile",
    icon: icons.user,
    inBar: false,
  },
  {
    // The one page the FRAME draws: the answer to an address nobody serves. It
    // has no path — it is what an address that resolves to none lands on — and
    // no group, because there is nowhere to go to it from.
    id: "404",
    Body: NotFoundPage,
    root: "body",
    region: "not-found/body",
    labelKey: "navigation.pages.404",
    icon: icons.wrench,
    inBar: false,
  },
];

/** The page an address nobody serves lands on — the row, not the id. */
export const NOT_FOUND_ROW = NAVIGATION.find((row) => row.id === "404")!;

/**
 * The row a page id names.
 *
 * Args:
 *     id: A page id — `state.page`'s value.
 *
 * Returns:
 *     The row, or undefined for an id no page carries. Undefined is the `*`
 *     route and never a crash: looking one up and calling a renderer on
 *     nothing stopped the whole interface on a stale bookmark.
 */
export function rowFor(id: string | undefined): NavigationRow | undefined {
  if (id === undefined) return undefined;
  return NAVIGATION.find((row) => row.id === id);
}
