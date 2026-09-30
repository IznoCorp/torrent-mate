// THE « TRACKERS » PAGE'S VERBS, declared to the tap registry.
//
// THE DECLARATION RUNS AT MODULE EVALUATION, named once in
// `app/panel-contributions.ts`, like its neighbours.
import { registerVerb } from "../../lib/verbs";
import { fillLandingDoor, panel, recordAddress, redraw, replaceAddress } from "../../lib/shell-doors";
import { read, send, sharedQueryClient } from "../../lib/query-client";
import { store } from "../../lib/store-access";
import { trackersKey, type Tracker } from "./queries";
import { pendingEdits } from "../../lib/save-bar-door";
import { activationSetting } from "./trackers-tab";
import { onEditsWritten } from "../../lib/save-bar-door";
import { tabMemory } from "../../lib/tab-memory";
// « Retirer de qBittorrent » declares its own verb, and a torrent's panel its producer.
import "./remove-verb";
import "./panel-torrent";
import "./panel-selector";
import "./panel-tracker";

// « TORRENTS » THE FIRST TIME, THEN THE TAB OPENED LAST on this device — the
// rule every tabbed page follows, through the memory they share.
const TABS = new Set(["torrents", "trackers"]);
const MEMORY = tabMemory("trackers-tab", "torrents", TABS);
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

/* ARRIVING AT THIS PAGE OPENS THE TAB OPENED LAST, « Torrents » the first time —
   whoever asked for it. A control that NAMES the tab it lands on is obeyed, and
   one naming a tracker after it (`trackers:c411`, a deferred card's path) lands
   with that tracker's entry open. */
fillLandingDoor((page, dial) => {
  if (page !== "trackers") return;
  const [tab, tracker] = (dial ?? "").split(DIAL_SEPARATOR);
  store.write({ trackersTab: TABS.has(tab) ? tab : MEMORY.remembered() });
  // A LANDING THAT NAMES NO TRACKER LANDS UNFILTERED: a filter left from before
  // is not carried into an arrival that did not ask for it.
  store.write({ trackersFilter: tracker || "" });
  // A LANDING THAT NAMES A TRACKER ON « Trackers » OPENS ITS PANEL, once the
  // roster has answered — the row it names, open for the one who asked.
  if (tab === "trackers" && tracker) void openTrackerWhenRead(tracker);
});

/**
 * Opens one tracker's panel once the roster holds it.
 *
 * @param tracker The tracker's configured name.
 */
async function openTrackerWhenRead(tracker: string): Promise<void> {
  await sharedQueryClient?.ensureQueryData({ queryKey: trackersKey, queryFn: async () => read<Tracker[]>(trackersKey[0]) });
  panel.produce("tracker", tracker);
}

/* A ROW'S BODY opens its tracker's panel. */
registerVerb("tracker-open", (tracker) => panel.produce("tracker", tracker));

/* THE ROW'S SWITCH files the pending edit Réglages files for the same setting:
   nothing is written until the save bar is used, and the switch draws the
   pending value meanwhile. */
registerVerb("tracker-switch", (tracker) => {
  const door = pendingEdits();
  if (door === undefined) return;
  const identity = activationSetting(tracker);
  const served = sharedQueryClient?.getQueryData<Tracker[]>(trackersKey)?.find((one) => one.name === tracker);
  const pending = door.pending(identity);
  const on = pending === undefined ? served?.enabled === true : pending.value === true;
  door.file(identity, !on);
});

/* A SETTING SAVED, from Réglages or from this page: the trackers' summary carries
   each tracker's alert threshold, so it is asked again — the chip and the bar's
   badge move in the render that follows, never at the next ratio measured. */
onEditsWritten(() => void sharedQueryClient?.invalidateQueries({ queryKey: trackersKey }));

/**
 * Lands on the « Torrents » tab filtered to one tracker, or to none: both dials
 * of the page set at once, an adjustment like a tab.
 *
 * @param tracker The tracker, or "" for every one.
 */
function filterTo(tracker: string): void {
  MEMORY.remember("torrents");
  store.write({ trackersTab: "torrents", trackersFilter: tracker });
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
  redraw();
  replaceAddress?.();
}

/* « VOIR LES TORRENTS », in a tracker's panel: an ARRIVAL from the layer, never
   the selector's adjustment (D-L13-1). The panel closes KEEPING its entry, the
   « Torrents » tab filtered to the tracker stacks over it, and Retour reopens
   the panel on « Trackers » — as the torrent panel's « Voir la fiche » does. */
registerVerb("trackers-see", (tracker) => {
  panel.close(true);
  MEMORY.remember("torrents");
  store.write({ trackersTab: "torrents", trackersFilter: tracker });
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
  redraw();
  recordAddress?.();
});

/* THE SELECTOR'S PILL raises its choices. */
registerVerb("trackers-selector", () => panel.produce("trackers-selector"));

/* A CHOICE closes the panel, then filters — ONCE THE PANEL'S ENTRY HAS LEFT, so
   the filter's address replaces the page's own entry, never the panel's, and
   nothing is pushed. */
registerVerb("trackers-choose", (tracker) => {
  if (history.state?.layer === "sheet") {
    window.addEventListener("popstate", () => window.setTimeout(() => filterTo(tracker)), { once: true });
    panel.close();
    return;
  }
  panel.close();
  filterTo(tracker);
});

/* « VU » ON A BROKEN OBLIGATION, in its tracker's panel: the write marks it
   seen, then the summary is asked again — the row stays, saying it was seen, and
   leaves the alert's count in the render that follows. Seen is not gone. */
registerVerb("obligation-seen", (value) => {
  const [tracker, infoHash] = value.split(":");
  if (!tracker || !infoHash) return;
  void send(
    "POST",
    `/api/trackers/${encodeURIComponent(tracker)}/broken-obligations/${encodeURIComponent(infoHash)}/seen`,
  ).then(() => sharedQueryClient?.invalidateQueries({ queryKey: trackersKey }))
    // THE PANEL IT WAS TAPPED IN is drawn again from the answer: the row says « vue ».
    .then(() => panel.redraw());
});
