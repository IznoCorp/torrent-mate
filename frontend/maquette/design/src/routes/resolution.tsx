// One address, one file.
//
// A route is THIN: it names its path and composes what renders there. Anything
// it would otherwise decide belongs to the feature it renders. The six of them
// lived inside the shell, which is how a file that boots the application also
// came to hold the address table.
//
// The parent is imported from `app/root-route`, never from the shell: the
// shell imports the assembled tree, so a route reaching back into it would
// close a cycle.

import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "../app/root-route";
import { ResolutionScreen } from "../features/arrivals/resolution-screen";

// The arbitration screen: what is stuck, and which medium it is. `$folder` is
// the FOLDER as it is on disk — not a media title, which is precisely what is
// missing — percent-encoded and NFC-normalised on both ends like every other
// `$` param here. No search param: the screen carries no state of its own, and
// an answer changes the queue rather than the address.
export const resolutionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/resolution/$folder",
  component: ResolutionScreen,
});
