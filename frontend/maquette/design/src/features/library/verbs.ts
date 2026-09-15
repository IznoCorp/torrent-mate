// THE LIBRARY'S VERBS, declared to the tap registry.
//
// The lens, the category, the layout, the sort and its two directions, the
// search's clear cross, selection mode, a selection tap, and the removal of a
// selection and of one row. Each was a branch of the document's delegation.
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
import { panel, replaceAddress, toast } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { mediaNamedBy, openDeleteDialog } from "./delete-dialog";
import { sortWays } from "./sorting";

/** Redraws the page the engine still draws beside the components. */
function redraw(): void {
  window.__referentiel.render();
}

/** Starts the listing again from its top. */
function backToTheTop(): void {
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
}

/** The titles ticked in selection mode — a set the store holds and this file mutates in place. */
function ticked(): Set<string> {
  return store.read().state.selected as Set<string>;
}

/* A LENS OR A CATEGORY CHANGES THE LIST: it starts again from the first page,
   and the SELECTION goes with it — a tick taken in another listing is one the
   reader cannot see to untick, and « Supprimer » would still offer it. A lens
   is a setting of the page, so its address replaces the entry it is on. */
registerVerb("lens", (lens) => {
  store.write({ libLens: lens, selected: new Set() });
  backToTheTop();
  redraw();
  replaceAddress?.();
});
registerVerb("cat", (category) => {
  store.write({ libCat: category, selected: new Set() });
  backToTheTop();
  redraw();
});
registerVerb("lmode", (mode) => {
  store.write({ libMode: mode });
  redraw();
});

registerVerb("sort", () => panel.produce("sort"));
registerVerb("setsort", (key, element) => {
  const reversed = element.dataset.reversed === "1";
  store.write({ sortKey: key, sortReversed: reversed, selected: new Set() });
  panel.close();
  redraw();
  const way = sortWays()[key][reversed ? "inverse" : "normal"];
  toast?.show({ message: i18next.t("verbs.library.sorted", { way: way.toLowerCase() }) });
});

// THE SELECTION GOES WITH THE QUESTION. Clearing the search widens what is on
// screen, and the ticks taken under the narrower listing are not the ones a
// reader is looking at.
registerVerb("clear-search", () => {
  store.write({ q: "", selected: new Set() });
  redraw();
});

registerVerb("selmode", (value) => {
  store.write({ selMode: value === "1", selectedMedia: 0 });
  ticked().clear();
  redraw();
});

// THE SET HOLDS TITLES, so the dialog names what the reader ticked — never an
// index into a source array the listing may have reordered.
registerVerb("delsel", () => openDeleteDialog(null, [...ticked()]));

/* THE BAR COUNTS MEDIA, not ticks. One press on a title this library holds
   twice lights both rows and the dialog says « 2 médias »; a caption counting
   ticks beside them would be the only figure in the flow counting something
   else. Written rather than touched: a write bumps the store too, which is what
   tells the components the selection changed. */
registerVerb("selected-title", (title, element) => {
  if (!store.read().state.selMode) return;
  const selection = ticked();
  if (selection.has(title)) selection.delete(title);
  else selection.add(title);
  store.write({
    selectedMedia: [...selection].reduce((total, one) => total + mediaNamedBy(one), 0),
  });
  element.setAttribute("aria-pressed", String(selection.has(title)));
});

registerVerb("del", (title) => {
  panel.close();
  openDeleteDialog(title);
});
