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

// The media sheet: ONE screen for every medium, reached from a poster, a tile,
// a suggestion or a panel act.
//
// THE ADDRESS IS THE ONE THE CONSTITUTION WRITES. DOIT-11 says the sheet « est
// atteignable par un lien stable (`/media/:provider/:id`) », and production
// already serves exactly that. It used to be `/mediasheet/$title` here — while
// the screen DISPLAYED `/media/tvdb/<id>` in its own bar, showing a stable link
// it did not honour. A title is what the catalogue is keyed by, not what a
// medium IS: two works can share one, and a rename breaks every link to it.
//
// A medium with no provider id has no address here, and that is §11's single
// explicit exception rather than a gap: the surface must lead to the
// resolution, never to a dead link.
//
// NO search param: the legacy sheet had no open-season state either; a
// `<details open>` is computed per render and toggled natively by the finger,
// so there is nothing here for the address to carry.
export const mediaRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/media/$provider/$id",
  component: MediaScreen,
});
