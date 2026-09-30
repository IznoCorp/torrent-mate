// The tracker selector's panel — the choices a tap on the pill raises.
//
// « Tous les trackers » first, then every tracker of the roster in its
// configuration order, each with the number of entries it runs. A choice closes
// the panel and filters; it pushes nothing, the filter being a setting of the page.
//
// NO ADDRESS: a choice among the page's own dials, like the library's sort.
import i18next from "i18next";
import type { Schemas } from "../../lib/contract-schemas";
import { read } from "../../lib/query-client";
import { store } from "../../lib/store-access";
import { registerProducer, type Choice, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { downloadsKey, trackersKey, type Tracker } from "./queries";

/**
 * Builds the selector's descriptor.
 *
 * @param _subject Unused: the panel has one subject, the page's filter.
 * @param cache What the query cache holds.
 * @returns The descriptor, or null while the roster or the entries have not landed.
 */
function selectorPanel(_subject: string, cache: PanelCache): PanelDescriptor | null {
  const trackers = cache.held<Tracker[]>(trackersKey);
  const downloads = cache.held<Schemas["Downloads"]>(downloadsKey)?.downloads;
  if (trackers === undefined || downloads === undefined) return null;
  const say = (key: string, values: Record<string, string | number> = {}) =>
    i18next.t(`screens.torrents.${key}`, values);
  const current = String(store.read().state.trackersFilter ?? "");
  const choice = (name: string, label: string, count: number): Choice => ({
    text: label,
    hint: say("selectorCount", { count }),
    checked: current === name,
    target: { "trackers-choose": name },
  });
  return {
    title: say("selectorTitle"),
    // THE HEAD SAYS WHAT THE COUNTS ARE, and it keeps the first choice clear of
    // the band a finger drags the panel by.
    meta: say("selectorMeta"),
    blocs: [
      {
        type: "choices",
        options: [
          choice("", say("selectorAll"), downloads.length),
          ...trackers.map((tracker) =>
            choice(tracker.name, tracker.name, downloads.filter((entry) => entry.tracker === tracker.name).length)),
        ],
      },
    ],
  };
}

registerProducer("trackers-selector", {
  produce: selectorPanel,
  needs: () => [
    { queryKey: trackersKey, queryFn: async () => read<Tracker[]>(trackersKey[0]) },
    { queryKey: downloadsKey, queryFn: async () => read<Schemas["Downloads"]>(downloadsKey[0]) },
  ],
});
