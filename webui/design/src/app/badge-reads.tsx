// THE READS A BADGE DERIVES FROM, KEPT OBSERVED BY THE FRAME.
//
// A badge is a synchronous read of the query cache (`app/navigation.ts`), and a
// read is not an observer. The cache refetches, on a live event, only the
// answers something observes, and drops an unobserved one a few minutes after
// its last observer left. So a badge whose subject was drawn by no mounted
// component — the bar's, on any other page — kept the number the boot had
// fetched, whatever the server said after.
//
// EACH ROW DECLARES ITS OWN READS (`useBadgeReads`, a hook its feature
// exports), and this layer calls it once per row the frame DRAWS — in the bar
// or in the drawer. The observer is born keyed on the row: a row the frame does
// not draw asks the server for nothing.
//
// IT NAMES NO FEATURE. The table does; this file only walks it.
import type { ReactElement } from "react";

import { NAVIGATION, opensFor, type NavigationRow } from "./navigation";
import { useRights } from "../lib/account";
import { useServerStateVersion } from "../lib/query-client";

/**
 * Observes one row's declared reads, and draws nothing.
 *
 * @param row The row, whose `useBadgeReads` is called on every render: one
 *     fixed hook per mounted instance, since the key is the row's id.
 */
function RowReads({ row }: { row: NavigationRow }): null {
  row.useBadgeReads?.();
  return null;
}

/**
 * Every drawn row's badge reads, observed for the document's lifetime.
 *
 * Rendered once, with the frame: the chrome outlives every navigation, and so
 * must what its badges read.
 */
export function BadgeReads(): ReactElement {
  // REDRAWN WHEN THE CACHE MOVES, and a cleared cache is the case that needs
  // it: an observer keeps the query it was given, so after the cache is emptied
  // it observes an entry the cache no longer holds, and nothing asks again.
  // Redrawing hands each hook the cache's new entry, which it then fetches.
  useServerStateVersion();
  // AND ONLY THE ROWS THE ACCOUNT OPENS: a badge it may not read is a read the
  // server refuses, and a count on a marked row would be a number it cannot
  // explain (F29).
  const rights = useRights();
  const drawn = NAVIGATION.filter(
    (row) => row.useBadgeReads && (row.inBar || row.group !== undefined) && opensFor(row, rights),
  );
  return (
    <>
      {drawn.map((row) => (
        <RowReads key={row.id} row={row} />
      ))}
    </>
  );
}
