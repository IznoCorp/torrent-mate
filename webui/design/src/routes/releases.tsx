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
import { ReleasesScreen } from "../features/releases/releases-screen";

// "Choose another release": the ranking's own reasoning, made inspectable.
// `$title` follows `/mediasheet/$title`'s discipline exactly — percent-encoded,
// NFC-normalised on both ends. No search param: same reason as the media
// sheet — nothing here for the address to carry.
export const releasesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/releases/$title",
  component: ReleasesScreen,
});
