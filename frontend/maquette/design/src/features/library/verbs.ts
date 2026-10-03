// THE LIBRARY'S VERBS, declared to the tap registry.
//
// The lens, the filter pill and its category, the layout, the sort pill and its
// six ways, the search's clear cross, selection mode, a selection tap, and the
// removal of a selection and of one row. Each was a branch of the document's delegation.
//
// A ROW HANDS OVER ITS OWN IDENTITY. The swipe's `data-del` and the selection's
// `data-selected-title` name the title, and the row's `data-del-ref` /
// `data-selected-ref` carry the provider identity it was drawn with — what a
// removal is handed, because two media may share a title (« RoboCop » 1987 and
// 2014). A control that carries no identity removes nothing.
//
// A SELECTION TAP ANSWERS ON `data-selected-title`, NOT ON `data-tile`. The
// registry answers the first REGISTERED key in attribute order and stops the
// tap there, and a tile carries `data-tile` before `data-mediasheet`: a verb on
// `tile` would swallow every tap that opens a sheet. `data-selected-title` is
// drawn only in selection mode, so outside it a tile's tap still reaches the
// sheet, and `data-tile` stays the index the rules read.
//
// THE DECLARATION RUNS AT MODULE EVALUATION, named once in
// `app/panel-contributions.ts`.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { panel, replaceAddress, toast, redraw } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { mediaNamedBy, openDeleteDialog, type Doomed } from "./delete-dialog";
import { refOfKey } from "../../lib/membership";
import { sortWays } from "./sorting";
import { closeThenApply } from "../../ui/pill-select";

/** Starts the listing again from its top. */
function backToTheTop(): void {
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
}

/** The media ticked in selection mode, keyed by identity — a map the store holds and this file mutates in place. */
function ticked(): Map<string, Doomed> {
  return store.read().state.selected as Map<string, Doomed>;
}

/* A LENS OR A CATEGORY CHANGES THE LIST: it starts again from the first page,
   and the SELECTION STAYS. It is keyed by identity, so a tick cannot land on
   another medium, and a tick the listing now hides is still counted by the bar
   and named by the delete dialog. A lens is a setting of the page, so its
   address replaces the entry it is on. */
registerVerb("lens", (lens) => {
  store.write({ libLens: lens });
  backToTheTop();
  redraw();
  replaceAddress?.();
});
// THE ONE PILL (maquette-blocked § 1.9): the filter pill raises the categories;
// a choice closes the panel first, so the address the category writes replaces
// the page's own entry, never the panel's.
registerVerb("library-filter-pill", () => panel.produce("library-filter"));
registerVerb("cat", (category) => closeThenApply(() => {
  store.write({ libCat: category });
  backToTheTop();
  redraw();
}));
registerVerb("lmode", (mode) => {
  store.write({ libMode: mode });
  redraw();
});

registerVerb("sort", () => panel.produce("sort"));
registerVerb("setsort", (key, element) => {
  const reversed = element.dataset.reversed === "1";
  closeThenApply(() => {
    store.write({ sortKey: key, sortReversed: reversed });
    redraw();
    const way = sortWays()[key][reversed ? "inverse" : "normal"];
    toast?.show({ message: i18next.t("verbs.library.sorted", { way: way.toLowerCase() }) });
  });
});

// THE SELECTION OUTLIVES THE QUESTION. Clearing the search widens what is on
// screen, and every tick taken under the narrower listing is drawn again.
registerVerb("clear-search", () => {
  store.write({ q: "" });
  redraw();
});

registerVerb("selmode", (value) => {
  store.write({ selMode: value === "1", selectedMedia: 0 });
  ticked().clear();
  redraw();
});

// THE MAP HOLDS IDENTITIES, so the dialog names what the reader ticked — never an
// index into a source array the listing may have reordered, nor a title two
// media may share.
registerVerb("delsel", () => openDeleteDialog([...ticked().values()]));

/* THE BAR COUNTS MEDIA, not ticks. One press on an identity this library holds
   twice lights both rows and the dialog says « 2 médias »; a caption counting
   ticks beside them would be the only figure in the flow counting something
   else. Written rather than touched: a write bumps the store too, which is what
   tells the components the selection changed. */
registerVerb("selected-title", (title, element) => {
  if (!store.read().state.selMode) return;
  const key = element.dataset.selectedRef;
  const ref = refOfKey(key);
  if (key === undefined || ref === null) return;
  const selection = ticked();
  if (selection.has(key)) selection.delete(key);
  else selection.set(key, { title, ref });
  store.write({
    selectedMedia: [...selection.values()].reduce((total, one) => total + mediaNamedBy(one.ref), 0),
  });
  element.setAttribute("aria-pressed", String(selection.has(key)));
});

registerVerb("del", (title, element) => {
  const ref = refOfKey(element.dataset.delRef);
  if (ref === null) return;
  panel.close();
  openDeleteDialog([{ title, ref }]);
});
