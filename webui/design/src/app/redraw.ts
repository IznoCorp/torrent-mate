// How the page is redrawn after a verb changed what it shows.
//
// EVERY PAGE IS A COMPONENT, so a redraw is first a bump of the store's version:
// every component reading it reads again. Two things are not components and are
// refilled here — the discovery deck and its loader, whose containers React
// draws and whose content the feed fills, because a replaced node cannot
// animate the gesture that spends it.
//
// AND AN ID NO PAGE CARRIES IS NOT A CRASH: it is the not-found page, and the
// address that was asked for is kept for it to name. Refused rather than made
// with `undefined` where the navigation table cannot answer, which only happens
// with the table absent — installed before anything redraws.
import { mountDeck, remountSuggestionLoader } from "../features/acquisition/discover-feed";
import { fillRedrawDoor } from "../lib/shell-doors";
import { store } from "../lib/store-access";
import { navigation } from "./navigation-seam";

/** Redraws the page, and moves an id no page carries onto the not-found page. */
function redraw(): void {
  store.touch();
  const page = store.read().state.page as string;
  if (!(navigation?.rows() ?? []).some((row) => row.id === page)) {
    if (navigation === undefined)
      // ENGLISH, and not in `fr.json`: a console message is a tool message.
      console.error("redraw: the navigation table answered nothing");
    else store.write({ notFound: "/" + page, page: navigation.notFoundPage });
  }
  mountDeck();
  remountSuggestionLoader();
}

/** Installs the redraw behind its door, from the boot. */
export function installRedraw(): void {
  fillRedrawDoor(redraw);
}
