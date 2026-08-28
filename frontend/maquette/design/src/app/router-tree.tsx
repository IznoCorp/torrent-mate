// The route tree, and the failure a thrown screen renders instead of nothing.
//
// It is the shell's, and it is not the shell: the boot decides WHEN things
// happen, this file decides WHICH addresses exist. `router` is a module
// constant because the `Register` declaration below is typed off it — a
// function returning one could not be named in a type.
import { createRouter } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { history } from "./history-bridge";
import { rootRoute } from "./root-route";
import { accountRoute } from "../routes/account";
import { acquisitionRoute } from "../routes/acquisition";
import { addRoute } from "../routes/add";
import { arrivalsRoute } from "../routes/arrivals";
import { rootAddressRoute } from "../routes/index";
import { libraryRoute } from "../routes/library";
import { maintenanceRoute } from "../routes/maintenance";
import { settingsRoute } from "../routes/settings";
import { systemRoute } from "../routes/system";
import { mediaRoute } from "../routes/media-sheet";
import { qualityRoute } from "../routes/quality";
import { releasesRoute } from "../routes/releases";
import { resolutionRoute } from "../routes/resolution";

declare global {
  interface Window {
    __routeur: typeof router;
  }
}

// A thrown component used to fail into a bare `null` — the exact failure
// shape this whole architecture exists to kill: a blank phone frame with
// nothing on screen saying why, and nothing in the console pointing at it
// either, since React only reports past an error boundary. This one is a
// VISIBLE failure instead, styled with the document's own tokens rather
// than an inline guess, so it reads as part of the interface it failed
// inside rather than as an unstyled crash page.
function ScreenError({ error }: { error: unknown }) {
  console.error(error);
  const { t } = useTranslation();
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        textAlign: "center",
        background: "var(--color-background)",
        color: "var(--color-danger)",
      }}
    >
      {t("screens.error.message")}
    </div>
  );
}

export const router = createRouter({
  routeTree: rootRoute.addChildren([
    // The pages, one address each. Their components render nothing: a page's
    // markup lands in the legacy `#view` through the page host, and declaring
    // the route is what makes the address KNOWN rather than nobody's.
    rootAddressRoute,
    acquisitionRoute,
    libraryRoute,
    arrivalsRoute,
    systemRoute,
    maintenanceRoute,
    settingsRoute,
    accountRoute,
    // The screens, which do render.
    qualityRoute,
    addRoute,
    mediaRoute,
    releasesRoute,
    resolutionRoute,
  ]),
  history,
  // The document is also read under other paths than `/` — the rule harness
  // serves it as `wrapped.html`. The router's built-in not-found fallback
  // would print « Not Found » into the mount node; the fallback DOCUMENT
  // already serves any unknown path (see serve.py), so a second one here
  // would only duplicate it — silenced rather than left to a default. A
  // thrown error is a different failure and gets a different answer: see
  // `ScreenError` above.
  defaultNotFoundComponent: () => null,
  defaultErrorComponent: ScreenError,
});
// Registers `router` as THE router for every `useParams`/`useNavigate` call
// in the tree, so a screen component (in its own file, importing neither
// `router` nor `rootRoute` — that would cycle back to this module) still gets
// fully typed params from a bare path literal like `/quality/$name`.
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

// Published at this module's evaluation rather than from the boot, because it
// is the publication of a constant this module owns and nothing reads it while
// the application starts. The harness drives through it.
window.__routeur = router;
