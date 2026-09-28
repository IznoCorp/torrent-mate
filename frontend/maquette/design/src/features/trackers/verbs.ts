// THE « TRACKERS » PAGE'S VERBS, declared to the tap registry.
//
// THE DECLARATION RUNS AT MODULE EVALUATION, named once in
// `app/panel-contributions.ts`, like its neighbours.
import { registerVerb } from "../../lib/verbs";
import { redraw, replaceAddress } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";

/* A TAB IS A SETTING OF THE PAGE, never an arrival: its address REPLACES the
   entry it is on, so a back leaves the page rather than stepping between tabs,
   and the list starts again from the top. */
registerVerb("trackers-tab", (tab) => {
  store.write({ trackersTab: tab });
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
  redraw();
  replaceAddress?.();
});
