// THE MENU BUTTON'S BADGE — what the rows the bar does not hold have to say.
//
// The bar carries the badges of its own buttons; a page reached from the
// drawer has no button there, so its count rides on the button that opens the
// drawer. It is the SUM of the drawn off-bar rows' own badge functions — the
// same functions the drawer's entries draw — so the button, the entry and the
// page's own reading are one derivation, and this file names no feature.
//
// THE BUTTON IS STATIC MARKUP, and it stays so: the badge is portalled into it,
// which leaves its place, its `data-drawer` and its accessible name untouched.
import type { ReactElement } from "react";
import { createPortal } from "react-dom";

import { NAVIGATION, opensFor } from "./navigation";
import { useRights } from "../lib/account";
import { useServerStateVersion } from "../lib/query-client";
import { useUiState } from "../lib/store-access";
import { tabBarBadge } from "../ui/variants";

/** The button the badge rides on. */
const MENU_BUTTON = '[data-part="shell/header"] [data-drawer]';

/**
 * The menu button's badge, or nothing when nothing is said.
 *
 * Returns:
 *     The badge portalled into the button — absent, never « 0 ».
 */
export function MenuBadge(): ReactElement | null {
  // SUBSCRIBED TO SERVER STATE AND TO THE STORE, because a badge function reads
  // both synchronously: a read is not a subscription.
  useServerStateVersion();
  useUiState();
  const button = document.querySelector(MENU_BUTTON);
  // BY RIGHTS, the same filter as the bar (M3: « le badge du menu compte par
  // droits »): a row the account cannot open adds nothing.
  const rights = useRights();
  const count = NAVIGATION.filter((row) => !row.inBar && row.group !== undefined && opensFor(row, rights))
    .reduce((sum, row) => sum + (row.badge ? row.badge() : 0), 0);
  if (!button || !count) return null;
  return createPortal(
    <span className={tabBarBadge()} data-part="shell/menu-badge">
      {count}
    </span>,
    button,
  );
}
