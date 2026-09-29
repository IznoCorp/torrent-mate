// THE « TRACKERS » PAGE'S VERBS, declared to the tap registry.
//
// THE DECLARATION RUNS AT MODULE EVALUATION, named once in
// `app/panel-contributions.ts`, like its neighbours.
import { registerVerb } from "../../lib/verbs";
import { fillLandingDoor, redraw, replaceAddress } from "../../lib/shell-doors";
import { send, sharedQueryClient } from "../../lib/query-client";
import { store } from "../../lib/store-access";
import { trackersKey } from "./queries";
import { tabMemory } from "../../lib/tab-memory";
// « Retirer de qBittorrent » declares its own verb.
import "./remove-verb";

// « TRACKERS » THE FIRST TIME, THEN THE TAB OPENED LAST on this device — the
// rule every tabbed page follows, through the memory they share.
const TABS = new Set(["torrents", "trackers"]);
const MEMORY = tabMemory("trackers-tab", "trackers", TABS);
// Between a landing dial's tab and the tracker it names.
const DIAL_SEPARATOR = ":";

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
   whoever asked for it. A control that NAMES the tab it lands on is obeyed, and
   one naming a tracker after it (`trackers:c411`, a deferred card's path) lands
   with that tracker's entry open. */
fillLandingDoor((page, dial) => {
  if (page !== "trackers") return;
  const [tab, tracker] = (dial ?? "").split(DIAL_SEPARATOR);
  store.write({ trackersTab: TABS.has(tab) ? tab : MEMORY.remembered() });
  if (tracker) store.write({ trackersFilter: tracker });
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

/* « VU » ON A BROKEN OBLIGATION: the write marks it seen, then the summary is
   asked again — the row stays, saying it was seen, and leaves the alert's count
   in the render that follows. Seen is not gone. */
registerVerb("obligation-seen", (value) => {
  const [tracker, infoHash] = value.split(":");
  if (!tracker || !infoHash) return;
  void send(
    "POST",
    `/api/trackers/${encodeURIComponent(tracker)}/broken-obligations/${encodeURIComponent(infoHash)}/seen`,
  ).then(() => sharedQueryClient?.invalidateQueries({ queryKey: trackersKey }));
});
