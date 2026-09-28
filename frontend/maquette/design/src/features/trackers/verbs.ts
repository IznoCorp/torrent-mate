// THE « TRACKERS » PAGE'S VERBS, declared to the tap registry.
//
// THE DECLARATION RUNS AT MODULE EVALUATION, named once in
// `app/panel-contributions.ts`, like its neighbours.
import { registerVerb } from "../../lib/verbs";
import { fillLandingDoor, redraw, replaceAddress } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { tabMemory } from "../../lib/tab-memory";

// « TRACKERS » THE FIRST TIME, THEN THE TAB OPENED LAST on this device — the
// rule every tabbed page follows, through the memory they share.
const TABS = new Set(["torrents", "trackers"]);
const MEMORY = tabMemory("trackers-tab", "trackers", TABS);

/* A TAB IS A SETTING OF THE PAGE, never an arrival: its address REPLACES the
   entry it is on, so a back leaves the page rather than stepping between tabs,
   and the list starts again from the top. */
registerVerb("trackers-tab", (tab) => {
  MEMORY.remember(tab);
  store.write({ trackersTab: tab });
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
  redraw();
  replaceAddress?.();
});

/* ARRIVING AT THIS PAGE OPENS THE TAB OPENED LAST, « Trackers » the first time —
   whoever asked for it. A control that NAMES the tab it lands on is obeyed. */
fillLandingDoor((page, dial) => {
  if (page !== "trackers") return;
  store.write({ trackersTab: dial !== undefined && TABS.has(dial) ? dial : MEMORY.remembered() });
});

/* « VOIR LES TORRENTS »: the « Torrents » tab, filtered to the tracker whose entry
   offered it — both dials of the page set at once, an adjustment like a tab. */
registerVerb("trackers-filter", (tracker) => {
  MEMORY.remember("torrents");
  store.write({ trackersTab: "torrents", trackersFilter: tracker });
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
  redraw();
  replaceAddress?.();
});
