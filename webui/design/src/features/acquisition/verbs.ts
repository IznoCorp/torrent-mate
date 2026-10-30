// THE ACQUISITION'S VERBS, declared to the tap registry.
//
// The page's tabs, the follows list's layout (its pills are
// `follows-pill-verbs.ts`'s), the discover surface's mode and its TMDB connection, and the acts the acquisition panels offer — a
// followed medium's primary act, an incomplete series' completion, the watch's
// run, the journey and the « more » panel. Each was a branch of the document's
// delegation; each is answered here, where what it acts on is known.
//
// THE DECLARATION RUNS AT MODULE EVALUATION, named once in
// `app/panel-contributions.ts`, like its neighbours `follow-verbs.ts` and
// `deck-verbs.ts`.
//
// THE PAGE IS REDRAWN THROUGH `redraw()`, the way every
// verb that still shares its page with the engine's drawing redraws it
// (`features/acquisition/resolution-verbs.ts` is the precedent).
import { landingTab, rememberTab } from "./tab-memory";
import { dialParts, landOnCard } from "./landing";
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { refusalWords } from "../../lib/refusal";
import { sendVerb } from "./verb-outcome";
import { queueActions } from "../../lib/queue";
import { fillLandingDoor, followLink, panel, replaceAddress, toast, redraw } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { baseTitle } from "../../lib/titles";
import { settleSwipeRow } from "./follow-verbs";

/* THE PAGE'S SELECTORS. A TAB IS A SETTING OF THE PAGE, so its address
   REPLACES the entry it is on and the list starts again from the top; a
   layout changes what the list shows and writes no address at all. */
registerVerb("acqtab", (tab) => {
  rememberTab(tab);
  store.write({ acqTab: tab });
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
  redraw();
  replaceAddress?.();
});
registerVerb("fmode", (mode) => {
  store.write({ followMode: mode });
  redraw();
});
registerVerb("sugmode", (mode) => {
  store.write({ sugMode: mode });
  redraw();
});
registerVerb("tmdb", () => {
  store.write({ tmdb: true });
  redraw();
  toast?.show({ message: i18next.t("verbs.acquisition.tmdbConnected") });
});

/* THE PANELS' ACTS. The primary act closes the panel and acts in the same
   tap. Its value is `<title>|<status>`: a medium waiting to be taken is taken,
   any other is searched for. */
registerVerb("sheetprim", (value) => {
  const [title, status] = value.split("|");
  panel.close();
  if (status === "to_grab") {
    queueActions?.take(title);
    redraw();
    toast?.show({
      message: i18next.t("verbs.acquisition.taken", { title: baseTitle(title) }),
    });
    return;
  }
  void searchNow(title);
});

/**
 * Searches for one follow now, and says what the search found.
 *
 * WHAT WAS NOT FOUND IS CONFIRMED BY A LIVE SEARCH: the act sends the follow's
 * own search and reads its answer — « aucun torrent trouvé » or how many. A search the
 * outbox holds, the layer refuses or the network loses is said in its own words, never thrown.
 * Announcing a search nothing sent was the promise of a result no surface drew.
 *
 * @param title The follow's title — its address.
 */
async function searchNow(title: string): Promise<void> {
  const sent = await sendVerb<{ found: number }>(
    "POST", `/api/v1/acquisition/followed/${encodeURIComponent(title)}/search`);
  // HELD: the outbox keeps the search, nothing was searched, and nothing is announced as found.
  if (sent.kind === "held") return void toast?.show({ message: i18next.t("verbs.acquisition.held") });
  if (sent.kind === "refused") return void toast?.show({ message: refusalWords(sent.failure, "verbs.acquisition.refused") });
  if (sent.kind === "failed") return void toast?.show({ message: i18next.t("verbs.acquisition.failed") });
  if (sent.answer === undefined) return;
  const named = baseTitle(title);
  toast?.show({
    message: sent.answer.found === 0
      ? i18next.t("verbs.acquisition.searchFoundNone", { title: named })
      : i18next.t("verbs.acquisition.searchFound", { title: named, count: sent.answer.found }),
  });
}
// An incomplete series: the search for its missing episodes is said where it
// will be seen moving, on « Maintenant ». A LINK from the panel, followed as
// one (§ 16, Q12): it stacks on the panel, whose entry is kept, so Retour gives
// the page and the panel back.
registerVerb("complete", (title) => {
  followLink?.("acq", "now");
  toast?.show({
    message: i18next.t("verbs.acquisition.completionStarted", { title: baseTitle(title) }),
  });
});
// The journey is a panel of its own, opened OVER the one it was asked from:
// that panel keeps its entry, so a Back from the journey puts it back.
registerVerb("journey", (title) => panel.produce("journey", title));
registerVerb("more", () => panel.produce("more"));

// A search cross: an empty search shows the whole list again. The attribute names
// the tab's key; « Suivis »' own, `filter`, is what an empty one means.
registerVerb("clear-filter", (key) => {
  store.write({ [key || "filter"]: "" });
  redraw();
});

// A swipe row's « search again »: the row comes back to rest and the act is
// said, as the delegation said it.
registerVerb("search-again", (title, element) => {
  settleSwipeRow(element);
  toast?.show({
    message: i18next.t("verbs.acquisition.searchAgain", {
      label: (element.textContent ?? "").trim(),
      title: title,
    }),
  });
});

/* ARRIVING AT THIS PAGE OPENS THE TAB OPENED LAST on this device, « Suivis » the
   first time — whoever asked for it: the tab is a setting of the page, and a
   landing from somewhere else is not the same as looking at the page one is
   already on. Beneath the candidates screen it is « À traiter », the list that
   screen answers (`landingTab`). The engine's own landing branch wrote
   this dial itself; the frame that answers the tap now cannot, since the dial is
   this page's name and not the frame's (invariant 10), so it asks through the
   landing door and the write is made here. A control that NAMES the tab it
   lands on is obeyed: a link to what waits for the hand opens « À traiter ». */
fillLandingDoor((page, dial) => {
  if (page !== "acq") return;
  // A LANDING MAY NAME ONE CARD after its tab (`now:Silo|S03`): that card is
  // brought into view, focused and highlighted (`./landing`).
  const { tab, acquisition } = dialParts(dial);
  store.write({ acqTab: landingTab(tab) });
  if (acquisition !== undefined) landOnCard(acquisition);
});

/* DÉCOUVRIR'S HEADER, cut at the view switch, says its sentence whole in a panel. */
registerVerb("discover-header", () => panel.produce("discover-header"));
