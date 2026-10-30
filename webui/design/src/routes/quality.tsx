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
import { QualityScreen } from "../features/releases/quality-screen";

// The quality-profile screen: a real route, rendering a final component
// INSIDE the React root — a surface reached directly rather than through the
// legacy fragment. `$title` is percent-encoded and
// NFC-normalised by both ends of the bridge (`go()` below on write,
// `QualityScreen` on read) so a title carrying combining characters survives
// the round trip through the URL unchanged.
export const qualityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/quality/$name",
  component: QualityScreen,
});
