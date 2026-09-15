// The navigation table, flattened — as the engine read it
// (`engine/legacy.js@13a66a35b`), and as its three readers still do.
//
// The engine drew the tab bar and the drawer from it, the last things it drew
// from a page list; it asked here, exactly as it asked the address model for a
// path, and the answer was the one table (`app/navigation.ts`). The tab bar and
// the drawer are components now and read that table directly.
//
// THE LABELS CROSS ALREADY TRANSLATED. The table holds keys, `fr.json` holds
// the words, and the engine held neither — no French reached it and no `t()`
// call had to. That is the same posture `window.__panel` takes with a
// descriptor: facts cross, and the words are resolved on the side that owns
// them.
//
// THE BADGE IS EVALUATED AT THE MOMENT OF THE ASK, not stored. The engine
// rebuilt its bar on every render and its drawer on every open, so a number
// captured earlier would be a number from the previous pass — and the badge is
// the feature's own derivation over the query cache (§13: one derivation per
// question), which answers correctly at whatever instant it is called.
//
// IT OUTLIVED THE ENGINE, and three readers keep it: `app/redraw.ts` refuses a
// page id the table does not hold (the not-found page), `harness/drive.ts`
// publishes the page ids as `window.__pages`, and `app/shell.tsx` fills it at
// boot.
import i18next from "../i18n";
import { NAVIGATION, NOT_FOUND_ROW, rowFor } from "./navigation";

/** One row, flattened to what the engine drew with. */
export type NavigationRowForEngine = {
  id: string;
  label: string;
  icon: string;
  group?: string;
  groupLabel?: string;
  inBar: boolean;
  actionButton: boolean;
  badge: number;
};

/** The navigation table, flattened for its readers. Filled at install. */
export let navigation:
  | {
      rows: () => NavigationRowForEngine[];
      ids: () => string[];
      has: (id: string) => boolean;
      actionButtonOn: (id: string) => boolean;
      notFoundPage: string;
    }
  | undefined;

/**
 * Fills the flattened navigation table.
 *
 * Called from the boot before the first redraw: a redraw asks the table whether
 * the page exists, and a seam installed after it would send every page to the
 * not-found page until something moved.
 */
export function installNavigationSeam(): void {
  navigation = {
    rows: () =>
      NAVIGATION.map((row) => ({
        id: row.id,
        label: i18next.t(row.labelKey),
        icon: row.icon,
        group: row.group,
        groupLabel: row.group
          ? i18next.t(`navigation.groups.${row.group}`)
          : undefined,
        inBar: row.inBar,
        actionButton: row.actionButton === true,
        badge: row.badge ? row.badge() : 0,
      })),
    ids: () => NAVIGATION.map((row) => row.id),
    has: (id: string) => rowFor(id) !== undefined,
    actionButtonOn: (id: string) => rowFor(id)?.actionButton === true,
    notFoundPage: NOT_FOUND_ROW.id,
  };
}
