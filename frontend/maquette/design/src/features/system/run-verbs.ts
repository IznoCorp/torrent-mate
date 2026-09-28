// What answers a tap on a passage's row.
//
// THE ROW IS A PATH, and this is where it leads. The verb registry answers the
// attribute; the address is the screen's, and the screen is what makes a run
// readable — the list says a run happened, and only its own address can say
// what happened in it.
import { registerVerb } from "../../lib/verbs";
import { go } from "../../lib/navigate";
import { countTheEntry } from "../../lib/stacked-surface";

/** The screen's address, which a tapped row pushes. */
const RUN_SCREEN = "/run/";

// THE SCREEN PUSHED AN ENTRY OF ITS OWN, so a step home counts it — or the
// landing steps back onto the screen's parent, Système, instead of the floor.
// COUNTED, not given back first: the screen's own cross-reference dies with it,
// so a replayed tap would land on nothing. Only a tapped row pushes: a cold
// load of a run's address opens the screen with no entry of its own.
const entryPosed = countTheEntry(() => location.pathname.startsWith(RUN_SCREEN));

registerVerb("run", (runUid) => {
  go({ to: "/run/$runUid", params: { runUid } });
  entryPosed();
});
