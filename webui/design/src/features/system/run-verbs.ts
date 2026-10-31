// What answers a tap on a passage's row.
//
// THE ROW IS A PATH, and this is where it leads. The verb registry answers the
// attribute; the address is the screen's, and the screen is what makes a run
// readable — the list says a run happened, and only its own address can say
// what happened in it.
import { registerVerb } from "../../lib/verbs";
import { go } from "../../lib/navigate";

registerVerb("run", (runUid) => {
  go({ to: "/run/$runUid", params: { runUid } });
});
