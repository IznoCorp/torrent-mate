// The sort sheet — what the count line's control raises.
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
import { SORT_DIRECTIONS, SORT_KEYS, sortWays } from "./sorting";

// THE ICONS COME THROUGH THE ENGINE'S DRAWING SLICE, not by importing
// `app/icons.ts`: that module is outside `ui/` and `lib/`, so invariant 8's
// fan-in ceiling of four features applies to it, and a producer per feature
// importing it directly walks it past four. Same object, and it dies with the
// engine.
const icons = () => window.__referentiel.icons;

/**
 * Builds the sort sheet's descriptor.
 *
 * Returns:
 *     The descriptor. It never answers null: the ways of sorting are the
 *     interface's own, so there is no cache to be waiting for.
 */
function sortPanel(): PanelDescriptor {
  const translate = i18next.t.bind(i18next);
  const named = sortWays();
  const { sortKey, sortReversed } = window.__store.read().state;
  return {
    title: translate("panels.sort.title"),
    meta: translate("panels.sort.note"),
    blocs: [
      {
        type: "actions",
        actions: SORT_KEYS.flatMap((key) =>
          SORT_DIRECTIONS.map((direction) => ({
            text: named[key][direction],
            icone: icons().sort,
            // THE SORT IN FORCE IS THE PRIMARY ONE, and it is the pair that
            // decides: a key alone marks both of its directions, which is a
            // panel saying the library is sorted two opposite ways at once.
            // UNDEFINED RATHER THAN NULL, which the descriptor's own type
            // asks for: `Action.ton` is optional, and the engine wrote `null`
            // because JavaScript let it. Both read the same at the drawing —
            // the variant tests for the tone's presence — and the oracle says
            // so at zero divergence.
            ton:
              sortKey === key && sortReversed === (direction === "inverse")
                ? "primary"
                : undefined,
            // TWO SHAPES, NOT ONE WITH AN UNDEFINED FIELD: the descriptor's
            // target is a map of DATA ATTRIBUTES, and `reversed: undefined`
            // would be an attribute the delegation reads as present. The
            // engine wrote the same two shapes for the same reason.
            target: (direction === "inverse"
              ? { setsort: key, reversed: "1" }
              : { setsort: key }) as Record<string, string>,
          })),
        ),
      },
    ],
  };
}

registerProducer("sort", { produce: sortPanel });
