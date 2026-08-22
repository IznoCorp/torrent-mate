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
import { MediaScreen } from "../features/media/media-screen";

// The media sheet: ONE screen for every medium, reached from a poster, a
// tile, a suggestion or a panel act. `$title` follows `/profile/$title`'s
// discipline exactly — percent-encoded, NFC-normalised on both ends. NO
// search param: the legacy sheet had no open-season state either; a
// `<details open>` is computed per render and toggled natively by the finger,
// so there is nothing here for the address to carry.
export const mediaRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/mediasheet/$title",
  component: MediaScreen,
});
