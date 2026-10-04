// The sort panel — what the Médiathèque's sort pill raises.
//
// It lives with the Médiathèque because that is what makes it change: how a
// library may be ordered. It was built INLINE in the engine's click delegation,
// the only one of the ten producers in that shape, and moving it is what gives
// it a name.
//
// NO ADDRESS, and that is not an omission: the panel's own note says the sort
// « is a preference, not a location: it stays on this device and does not enter
// the URL ». D1's third tier — Back still closes it, it simply has no URL.
//
// A PRODUCER IS NOT A HOOK: it is called from the click delegation, and it
// reads the sort in force from the store, which is where invariant 4 puts
// ephemeral interface state.
import i18next from "i18next";
import { registerProducer, type PanelDescriptor } from "../../ui/panel/contract";
import { choicesDescriptor } from "../../ui/pill-select";
import { SORT_DIRECTIONS, SORT_KEYS, sortWays } from "./sorting";
import { store } from "../../lib/store-access";

/**
 * Builds the sort panel's descriptor.
 *
 * THE ONE PILL'S PANEL (maquette-blocked DECIDED 1, § 1.9): the count line's
 * control became the sort pill beside the filter pill, and its sheet of six
 * actions became the pill's list of choices — the six ways unchanged, in the
 * declared order, the one in force checked.
 *
 * Returns:
 *     The descriptor. It never answers null: the ways of sorting are the
 *     interface's own, so there is no cache to be waiting for.
 */
function sortPanel(): PanelDescriptor {
  const named = sortWays();
  const { sortKey, sortReversed } = store.read().state;
  return choicesDescriptor(
    i18next.t("panels.sort.title"),
    i18next.t("panels.sort.note"),
    SORT_KEYS.flatMap((key) =>
      SORT_DIRECTIONS.map((direction) => ({
        text: named[key][direction],
        // THE SORT IN FORCE IS THE PAIR: a key alone would check both of its
        // directions, a panel saying the library is sorted two opposite ways.
        checked: sortKey === key && Boolean(sortReversed) === (direction === "inverse"),
        // TWO SHAPES, NOT ONE WITH AN UNDEFINED FIELD: the target is a map of
        // DATA ATTRIBUTES, and `reversed: undefined` would be an attribute the
        // delegation reads as present.
        target: (direction === "inverse"
          ? { setsort: key, reversed: "1" }
          : { setsort: key }) as Record<string, string>,
      })),
    ),
  );
}

registerProducer("sort", { produce: sortPanel });
