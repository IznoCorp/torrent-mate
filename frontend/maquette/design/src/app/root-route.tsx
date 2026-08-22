// The root of the route tree, and the two layers that belong to no route.
//
// It lives apart from the shell because the six address files name it as their
// parent while the shell imports the ASSEMBLED tree: had it stayed in the
// shell, every route would have pointed back at the module that boots the
// application.
//
// The sheet closes through the published seam rather than through the shell's
// own function — the same object either way (`window.__panel.close` IS that
// function, assigned at the shell's module evaluation, long before this
// component can render), and it is what lets this file import no shell.
import { createRootRoute, Outlet } from "@tanstack/react-router";
import { PageHost } from "./page-host";
import { Sheet } from "../ui/sheet";

// The root renders the matched route, the bottom-sheet layer and the PAGE host
// — the last two belong to no route. The sheet opens over whatever is on screen
// (a React route, a legacy `#screen`, a plain page), so it is mounted once and
// its visibility is a class rather than a mount. The page host is mounted for
// the same reason from the other side: a PAGE has no address of its own, it is
// a value of `state.page`, so nothing in the route table can select it — see
// `app/page-host.tsx` for why it portals into the legacy `#view`.
export const rootRoute = createRootRoute({
  component: () => (
    <>
      <Outlet />
      <PageHost />
      <Sheet close={(pop) => window.__panel.close(pop)} />
    </>
  ),
});

