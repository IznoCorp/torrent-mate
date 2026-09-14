// THE ACQUISITION'S VERBS, declared to the tap registry.
//
// The page's tabs, the follows list's pill and layout, the discover surface's
// mode and its TMDB connection, and the acts the acquisition panels offer — a
// followed medium's primary act, an incomplete series' completion, the watch's
// run, the journey and the « more » panel. Each was a branch of the document's
// delegation; each is answered here, where what it acts on is known.
//
// THE DECLARATION RUNS AT MODULE EVALUATION, named once in
// `app/panel-contributions.ts`, like its neighbours `follow-verbs.ts` and
// `deck-verbs.ts`.
//
// THE PAGE IS REDRAWN THROUGH `window.__referentiel.render()`, the way every
// verb that still shares its page with the engine's drawing redraws it
// (`features/arrivals/verbs.ts` is the precedent).
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { queueActions } from "../../lib/queue";
import { panel, replaceAddress, toast } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { baseTitle } from "../../lib/titles";
import { settleSwipeRow } from "./follow-verbs";

/** Redraws the page the engine still draws beside the components. */
function redraw(): void {
  window.__referentiel.render();
}

/* THE PAGE'S SELECTORS. A TAB IS A SETTING OF THE PAGE, so its address
   REPLACES the entry it is on and the list starts again from the top; a pill or
   a layout changes what the list shows and writes no address at all. */
registerVerb("acqtab", (tab) => {
  store.write({ acqTab: tab });
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
  redraw();
  replaceAddress?.();
});
registerVerb("pill", (pill) => {
  store.write({ pill });
  redraw();
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

/* THE PANELS' ACTS. The primary act closes the panel and acts 240 ms LATER,
   the choreography the panel was built against, kept until the ladder takes
   one shape. Its value is `<title>|<status>`: a medium waiting to be taken is
   taken, any other is searched for. */
registerVerb("sheetprim", (value) => {
  const [title, status] = value.split("|");
  panel.close();
  window.setTimeout(() => {
    if (status === "to_grab") {
      queueActions?.take(title);
      redraw();
      toast?.show({
        message: i18next.t("verbs.acquisition.taken", { title: baseTitle(title) }),
      });
      return;
    }
    toast?.show({
      message: i18next.t("verbs.acquisition.searchStarted", { title: baseTitle(title) }),
    });
  }, 240);
});
// An incomplete series: the search for its missing episodes is said where it
// will be seen moving, on « Maintenant ».
registerVerb("complete", (title) => {
  store.write({ page: "acq", acqTab: "now" });
  panel.close();
  redraw();
  toast?.show({
    message: i18next.t("verbs.acquisition.completionStarted", { title: baseTitle(title) }),
  });
});
registerVerb("standby", () => {
  panel.close();
  toast?.show({ message: i18next.t("verbs.acquisition.watchStarted") });
});
// The panel leaves inside the navigation's own commit, with no wait between
// the two.
registerVerb("journey", (title) => {
  panel.close();
  panel.produce("journey", title);
});
registerVerb("more", () => panel.produce("more"));

// The follows' search cross: an empty filter shows the whole list again.
registerVerb("clear-filter", () => {
  store.write({ filter: "" });
  redraw();
});

// A swipe row's « search again »: the row comes back to rest and the act is
// said, as the delegation said it.
registerVerb("search-again", (title, element) => {
  settleSwipeRow(element);
  const label = (element.textContent ?? "").trim();
  toast?.show({ message: i18next.t("verbs.acquisition.searchAgain", { label, title }) });
});
