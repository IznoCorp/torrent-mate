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
import { AccountsPage } from "../features/account/accounts-page";
import { AcquisitionPage } from "../features/acquisition/page";
import { acquisitionBadge, useAcquisitionBadgeReads } from "../features/acquisition/queries";
import { DiscoverPage } from "../features/acquisition/discover-page";
import { LibraryPage } from "../features/library/page";
import { MaintenancePage } from "../features/maintenance/page";
import { NotFoundPage } from "./not-found";
import { SettingsPage } from "../features/settings/page";
import { systemBadge, useSystemBadgeReads } from "../features/system/badge";
import { SystemPage } from "../features/system/page";
import { TrackersPage } from "../features/trackers/page";
import { trackersBadge, useTrackersBadgeReads } from "../features/trackers/queries";
import { PAGE_PATHS } from "../lib/addresses";
import type { Right, Rights } from "../lib/rights";
import { NoAccessPage } from "./no-access";
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
  /**
   * Whether this page's bottom slot REPLACES the tab bar rather than sitting
   * above it.
   *
   * The library's selection bar takes the bar's place while a selection is
   * being made, which is right there and wrong everywhere else: the bar hid
   * wherever the operator went, so a selection carried off its own page left
   * him with neither a tab bar nor a bar belonging to what he was looking at
   * (B-395). The fact lives in this table because it is a property of a PAGE,
   * and reading it here is what keeps the frame from naming one.
   */
  slotReplacesTabBar?: boolean;
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
  /**
   * The reads `badge` derives from, DECLARED — a hook the feature exports,
   * which the frame calls once for every row it draws (`app/badge-reads.tsx`).
   *
   * `badge` reads the cache and observes nothing, and an answer nobody observes
   * is neither refetched on a live event nor kept: the badge froze on every page
   * that did not draw its subject. A row that carries a badge carries this.
   */
  useBadgeReads?: () => void;
  /**
   * The rights that open this page — any one of them (§ 17, ruling 17: every
   * access is a right). A row with none opens for every account.
   */
  opens?: readonly Right[];
  /**
   * What an account without those rights sees of it (OPEN 3 = B). `reserved`:
   * the drawer draws it MARKED and its address explains itself — hiding it
   * would mislead. `absent`: no row, no badge, no address — the Acquisition
   * section's named exception, and the pages that belong to it.
   */
  lacking?: "absent" | "reserved";
};

/**
 * Every page, in the order the bottom bar draws them.
 *
 * THE BAR DRAWS THE BUTTONS PRESENT, each at 1/n of its width, n from 2 to 4 —
 * never an empty slot, and one page draws no bar at all (a frame rule, R232).
 * It holds the places one goes to every day, in this order: Acquisition,
 * Médiathèque, Trackers, Découvrir — four, the most it draws, and the fourth is
 * Découvrir's, never a free one. Système is reached from the drawer
 * and the menu button carries its badge (ruling 15). Réglages and Maintenance
 * are PAGES and not tabs either: a setting is what one goes to CHANGE and a
 * maintenance command is something one goes to DO. They are reached from
 * Système and from the drawer, and the back gesture walks out of them like any
 * other page.
 */
export const NAVIGATION: readonly NavigationRow[] = [
  {
    id: "acq",
    opens: ["acquisition.request", "acquisition.see.others"],
    lacking: "absent",
    path: PAGE_PATHS.acq,
    Body: AcquisitionPage,
    labelKey: "navigation.pages.acq",
    icon: icons.radar,
    group: "supervision",
    inBar: true,
    actionButton: true,
    badge: acquisitionBadge,
    useBadgeReads: useAcquisitionBadgeReads,
  },
  {
    id: "lib",
    opens: ["library.read"],
    lacking: "absent",
    path: PAGE_PATHS.lib,
    Body: LibraryPage,
    labelKey: "navigation.pages.lib",
    icon: icons.library,
    group: "supervision",
    inBar: true,
    slotReplacesTabBar: true,
  },
  {
    // « TRACKERS », THE BAR'S THIRD PLACE: inserted between Médiathèque and
    // Découvrir, never appended after a free slot. Its two tabs are dials of
    // the page, not pages.
    id: "trackers",
    opens: ["trackers.view"],
    lacking: "reserved",
    path: PAGE_PATHS.trackers,
    Body: TrackersPage,
    labelKey: "navigation.pages.trackers",
    icon: icons.transfer,
    group: "supervision",
    inBar: true,
    badge: trackersBadge,
    useBadgeReads: useTrackersBadgeReads,
  },
  {
    // « DÉCOUVRIR », A PAGE OF THE BAR: it left
    // Acquisition's tabs. It draws its own body, as Acquisition does.
    id: "discover",
    opens: ["acquisition.request"],
    lacking: "absent",
    path: PAGE_PATHS.discover,
    Body: DiscoverPage,
    labelKey: "navigation.pages.discover",
    icon: icons.star,
    group: "supervision",
    inBar: true,
  },
  {
    id: "sys",
    opens: ["system.view"],
    lacking: "reserved",
    path: PAGE_PATHS.sys,
    Body: SystemPage,
    root: "body",
    region: "system/body",
    labelKey: "navigation.pages.sys",
    icon: icons.wrench,
    group: "system",
    inBar: false,
    badge: systemBadge,
    useBadgeReads: useSystemBadgeReads,
  },
  {
    id: "maint",
    opens: ["system.view"],
    lacking: "reserved",
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
    opens: ["configuration.view"],
    lacking: "reserved",
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
    // « COMPTES », A FIRST-LEVEL PAGE OF THE MENU, beside Réglages (round 8 Q9 =
    // B): the accounts, their roles and the roles' rights. Marked, never hidden,
    // for an account that does not manage them (OPEN 3 = B).
    id: "accounts",
    path: PAGE_PATHS.accounts,
    Body: AccountsPage,
    root: "body",
    region: "accounts/body",
    labelKey: "navigation.pages.accounts",
    icon: icons.user,
    group: "configuration",
    inBar: false,
    opens: ["accounts.manage"],
    lacking: "reserved",
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
    // WHERE A ROLE THAT OPENS NO PAGE LANDS (ruling 22, precision): it says so
    // and offers only the way out. No group, no bar — there is nowhere to go.
    id: "no-access",
    path: PAGE_PATHS["no-access"],
    Body: NoAccessPage,
    root: "body",
    region: "no-access/body",
    labelKey: "navigation.pages.noAccess",
    icon: icons.lock,
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

/**
 * Whether an account opens a page.
 *
 * Args:
 *     row: The page's row.
 *     rights: What the account may do.
 *
 * Returns:
 *     True when the row asks for no right or the account holds one it asks for.
 */
export function opensFor(row: NavigationRow, rights: Rights): boolean {
  return row.opens === undefined || rights.holdsAny(row.opens);
}

/**
 * Whether a page is ABSENT for an account — not drawn, not counted, not addressed.
 *
 * Args:
 *     row: The page's row.
 *     rights: What the account may do.
 *
 * Returns:
 *     True when the account does not open it and the page is one hiding cannot mislead about.
 */
export function absentFor(row: NavigationRow, rights: Rights): boolean {
  return !opensFor(row, rights) && row.lacking === "absent";
}

/** The pages the drawer and the bar may draw — never the frame's own two. */
const PLACES = NAVIGATION.filter((row) => row.inBar || row.group !== undefined);

/**
 * THE ACCOUNT'S ENTRY PAGE — where Back lands and the exit guard arms (round 10
 * Q7): the first page of its bar, in bar order; else the first menu page it
 * opens; else the page that says it opens none.
 *
 * Args:
 *     rights: What the account may do.
 *
 * Returns:
 *     The page id.
 */
export function entryPageFor(rights: Rights): string {
  const bar = NAVIGATION.find((row) => row.inBar && opensFor(row, rights));
  if (bar) return bar.id;
  const menu = PLACES.find((row) => opensFor(row, rights));
  return menu ? menu.id : "no-access";
}
