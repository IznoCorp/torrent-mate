// THE ACCOUNT'S ENTRY PAGE, kept where the address model reads it (round 10 Q7).
//
// The first page of the role's bar, in bar order — or its only page, or the
// first menu page it opens, or the page that says it opens none. The frame
// derives it from the rights the moment they are read, and whenever they move;
// Back, the exit guard and the bare root read it through `addressSeam`.
//
// AND THE MENU GOES WITH THE PAGES: a role that opens no page has no menu
// button to raise one (ruling 22, precision) — only the way out.
import { useLayoutEffect } from "react";

import { entryPageFor } from "./navigation";
import { useRights } from "../lib/account";
import { setEntryPage } from "../lib/addresses";

// The button that raises the menu, in the header's static markup.
const MENU_BUTTON = '[data-part="shell/header"] [data-drawer]';
// The page a role that opens nothing lands on.
const NO_ACCESS = "no-access";

/** Keeps the entry page and the menu button in step with the account's rights. */
export function EntryPage(): null {
  const rights = useRights();
  const entry = rights.known ? entryPageFor(rights) : undefined;
  useLayoutEffect(() => {
    if (entry === undefined) return;
    setEntryPage(entry);
    // SAID ON THE DOCUMENT, so a reader can tell where this account enters
    // without composing it again.
    document.documentElement.dataset.entryPage = entry;
    const button = document.querySelector<HTMLElement>(MENU_BUTTON);
    if (button) button.hidden = entry === NO_ACCESS;
  }, [entry]);
  return null;
}
