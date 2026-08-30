// The navigation table, as the dying engine reads it.
//
// The engine still draws the tab bar and the drawer, and it is the LAST thing
// it will still draw from a page list. It no longer carries one: it asks here,
// exactly as it asks `window.__address` for a path, and the answer is the one
// table (`app/navigation.ts`).
//
// THE LABELS CROSS ALREADY TRANSLATED. The table holds keys, `fr.json` holds
// the words, and the engine holds neither — no French reaches it and no `t()`
// call has to. That is the same posture `window.__panel` takes with a
// descriptor: facts cross, and the words are resolved on the side that owns
// them.
//
// THE BADGE IS EVALUATED AT THE MOMENT OF THE ASK, not stored. The engine
// rebuilds its bar on every render and its drawer on every open, so a number
// captured earlier would be a number from the previous pass — and the badge is
// the feature's own derivation over the query cache (§13: one derivation per
// question), which answers correctly at whatever instant it is called.
//
// IT DIES WITH THE ENGINE. Nothing in the product reads this file: the tab bar
// and the drawer read `app/navigation.ts` directly once they are components.
import i18next from "../i18n";
import { NAVIGATION, NOT_FOUND_ROW, rowFor } from "./navigation";

/** One row, flattened to what the engine draws with. */
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

declare global {
  interface Window {
    /** The navigation table, read by the engine while it still draws from one. */
    __navigation?: {
      rows: () => NavigationRowForEngine[];
      ids: () => string[];
      has: (id: string) => boolean;
      actionButtonOn: (id: string) => boolean;
      notFoundPage: string;
    };
  }
}

/**
 * Publishes the navigation table on the seam the engine reads.
 *
 * Called from the boot BEFORE the engine starts: the engine's own first render
 * asks for the bar, and a seam installed after it would leave the interface
 * opening with an empty bar until something moved.
 */
export function installNavigationSeam(): void {
  window.__navigation = {
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
