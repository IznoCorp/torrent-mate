// The strangler shell. One owner for the URL and the history: this router.
// The legacy engine keeps its navigation LOGIC (what to push, when to
// unwind) and loses only its primitives — it speaks to `window.__bridge`,
// implemented here on the router's history. `window.__go` keeps driving
// states without navigation, exactly as before.
//
// Every name reached from the legacy fragment — the window seams, their
// member names, the route paths and the `data-*` vocabulary — is the seam
// itself and stays as the fragment spells it; only what lives entirely
// inside this file is named freely.
//
// The base layer, FIRST of all, and it is a cascade decision rather than a
// stylistic one. Vite emits an imported stylesheet as a <link> in <head>,
// while the prototype fragment carries its own <style> in <body>: head before
// body is base before components, which is the order D3 asks for. A CSS import
// placed after another would reorder the emitted sheet, and the reset would
// then win against a component that had every right to override it.
// The tokens come before the base layer, and both before anything else: the
// base layer spends the scale, so the sheet that DECLARES it has to be earlier
// in the emitted stylesheet.
import "../styles/theme.css";
import "../styles/base.css";
// The residue, LAST of the three: it is hand-written CSS for markup the
// engine draws, and it must be able to win over the base layer the same way
// a component's own rule would. It dies with L13.
import "../styles/legacy.css";
// THE HARNESS, LAST, AND THE ONE IMPORT THAT DOES NOT SHIP. Phone frame,
// harness buttons, the measuring hides. It dies at switchover with the
// prototype it serves, and removing this line is the whole of its removal.
import "../styles/harness.css";
// The i18n bootstrap is the first import that RUNS, for its side effect
// (initialising `i18next`) — every migrated screen calls `useTranslation()`,
// and the first of them can render before any other import here settles. The
// stylesheet above it is emitted, not executed, so it takes no turn.
import "../i18n";
// The legacy engine, for its side effect too, and the order matters more
// here than anywhere else in this file. It used to be a classic script
// inside the fragment, evaluated while the document parsed — everything it
// declares therefore existed before this module's body ever ran, and the
// body below depends on exactly that: it reads `window.__startEngine`
// and calls it. As a module the engine keeps that guarantee for the same
// reason it had it before: a module's dependencies evaluate before its
// body, so importing it HERE is what makes it run FIRST. Moving this line
// below any other statement would not reorder anything — imports hoist —
// but writing it anywhere else would suggest otherwise.
import "../engine/legacy.js";
// The scenario table, registered with the engine as this module evaluates —
// after the engine, because it imports twenty names from it. It is the
// harness's fixture, not the product's, and the engine looks its states up
// there rather than carrying them.
import "../engine/states.js";
import { RouterProvider } from "@tanstack/react-router";
import React from "react";
import ReactDOM from "react-dom/client";
// The two panel blocks that belong to a domain, imported for their SIDE
// EFFECT: each declares its kind to the panel's contract and registers what
// draws it as it evaluates. Nothing else imports them — a panel is opened by
// a legacy producer through `window.__panel`, never by a component holding a
// reference to the block — so the boot is where they have to be named, and
// `app/` naming what a feature contributes at boot is exactly its job.
import "../features/media/panel-seasons";
import "../features/settings/panel-field";
import { createStore, type Store } from "./store";
import { publishBarHeight } from "./bar-height";
import { installFocusManager } from "./focus";
import { installMockNetwork } from "../mocks";
import { router } from "./router-tree";
import {
  history,
  installHistoryBridge,
  installScreenBridge,
} from "./history-bridge";
import { installScrollRestoration } from "./scroll-restoration";
import { installPanelHost } from "./panel-host";
import { installSeams } from "../engine/seams";
import {
  addressOf,
  destinationOf,
  HOME_PAGE,
  PANEL_PARAMETER,
  SIGN_IN_PATH,
  withoutPanel,
} from "../lib/addresses";
import { installNavigation } from "../lib/navigate";
import { QueryClientProvider } from "@tanstack/react-query";
import { createQueryClient } from "../lib/query-client";
import { installDecisionLookup } from "../features/arrivals/queries";
import { installLibraryPaging } from "../features/library/queries";
import { installEngineRedraw } from "./engine-redraw";
import {
  installFollowActions,
  installSuggestionsLookup,
} from "../features/acquisition/queries";
import { installQueueActions } from "../lib/queue";

declare global {
  interface Window {
    // The engine's handshake: defined by refonte.html, called exactly once
    // below, once the store exists and the bridge is real. Optional because
    // a module that failed to evaluate is exactly the case this boot order
    // is built to leave visible — the startup screen, not a crash here.
    // It no longer receives an address ROOT. It used to compose every page
    // address itself against one, which is exactly the addressing the shell
    // has taken over: the engine says WHERE IT IS, `__address` says what that
    // is called. The deps object's own keys are the engine's.
    __startEngine?: (deps: { store: Store }) => void;
    // The address model, handed to the engine. `compose` turns the state it
    // holds into the address that state should be seen at; `parse` turns an
    // address back into the state it names. Both are `lib/addresses.ts` — the
    // engine reaches them through a seam rather than importing, for the same
    // reason it reaches everything else that way.
    __address: {
      /** The sign-in screen's own path, so the engine writes it by name. */
      signInPath: string;
      /** The page every other page sits on — the root of the hierarchy. The
       * engine synthesises a stack from it on a cold link and steps back onto
       * it when a tab is tapped, and neither is the engine's to name. */
      homePage: string;
      /** The name the addressed panel travels under, so the engine can ask
       * whether an address carried one at all without spelling it itself. */
      panelParameter: string;
      /** A query string with the panel parameter taken off, rest verbatim. */
      withoutPanel: (search: string) => string;
      compose: (state: Record<string, unknown>) => string;
      parse: (
        pathname: string,
        search: string,
      ) => {
        page: string;
        dials: Record<string, string>;
        notFound?: string;
        signIn?: boolean;
        panel?: string;
        screen?: boolean;
      };
    };
    // The query cache, published for the harness. It is the one place server
    // state lives (invariant 4), so a rule asking « what does this surface
    // hold, and did a mutation put it back? » asks it here.
    __queries: import("@tanstack/react-query").QueryClient;
    // The domain hooks and the probes read the engine's state through this.
    __store: Store;
  }
}

// THE BOOT ORDER, AND IT IS THE WHOLE OF WHAT THIS FILE DECIDES. Each call
// below installs one seam in the one position it can be installed in. The four
// modules it calls own WHAT they install; this file owns WHEN, and that is why
// they are functions rather than module-level assignments — a side effect on
// import would put this order at the mercy of the import list's shape.
//
// The history primitives FIRST: the panel host pushes a layer entry through
// them, and `openPanel`'s own error branch rests on the bridge being real
// before any producer can call `open`. That guarantee used to read « assigned
// at this module's top level »; it is this call now, and it is still before the
// engine, before the store's first write and before the first render.
installHistoryBridge();
installScrollRestoration();
// before anything can navigate: a verb that knows only a path and its
// parameters belongs with the domain-free helpers, and while it lived in this
// file a screen component importing it pointed back at the module that renders
// that very screen.
installNavigation(router, history);
// The screen openers, AFTER `installNavigation`: every one of them navigates
// through `go()`.
installScreenBridge();

// The store is created here, and the engine starts only once it — and the
// bridge above — are real. No queue, no replay: the engine's own boot writes
// (the arrival state, the guard entry, the back listener) now run straight
// onto the single writer, in the engine's own order, before the first
// render. A module that never evaluates simply never calls this, and the
// startup screen — already first in the frame — stays up: a visible,
// truthful failure instead of an app with mute verbs.
const store = createStore();
window.__store = store;
//
// CREATED BEFORE THE PANEL HOST, and that is the one ordering this split
// changed. The panel host receives the store as an ARGUMENT instead of closing
// over a `const` declared below its own use — the dependency is stated rather
// than resting on when a function happens to be called. Nothing between the
// two positions reads the store, and the oracle is what says so.
installPanelHost(store);

// The engine reads these three by import rather than off `window` — same
// objects, so the two ways cannot disagree. Filled HERE, after all three
// exist and before the engine is started below, which is the only window in
// which they can be both real and unused.
installSeams({
  bridge: window.__bridge,
  screens: window.__screens,
  panel: window.__panel,
});

// The address model, published for the engine. It reads `state.page` and the
// dial fields straight off the object the engine hands over — the engine's own
// vocabulary, so nothing translates on the way across.
window.__address = {
  signInPath: SIGN_IN_PATH,
  homePage: HOME_PAGE,
  panelParameter: PANEL_PARAMETER,
  withoutPanel: withoutPanel,
  compose: (state) => addressOf(String(state.page ?? ""), state),
  parse: destinationOf,
};
// No address BASE is computed any more, and its disappearance is the
// subtraction this lot exists for. It answered « what does this engine
// compose its page addresses against? », a question that only had to be asked
// because the engine composed them at all. It does not: a page has a real
// path, `lib/addresses.ts` holds which, and the harness's own host serves
// every one of them off `/` like any single-page host.
// THE MOCK LAYER, INSTALLED BEFORE ANYTHING FETCHES (L08).
//
// Synchronously, and before the engine starts: the seam replaces `fetch`, and a
// replacement that arrived after the first request would be a race no rule
// could reproduce. This is also why the layer is not a service worker — a
// worker's registration is asynchronous, and the oracle measures at first
// paint.
//
// Behind a build-time constant, so the switchover removes it by editing one
// value. `__MOCKS_BUILT_IN__` is replaced at build time, so the branch below is dead
// code when it is false and the bundler drops the import with it.
if (__MOCKS_BUILT_IN__) installMockNetwork();

const start = window.__startEngine;
if (typeof start === "function") start({ store: store });

// `#shell` starts, in the markup, as a static sibling of `.stage` —
// index.html knows nothing about the phone frame the fragment draws. A
// migrated screen's `.screen{position:absolute;inset:0}` resolves against
// its nearest POSITIONED ancestor, which for the legacy `#screen` is
// `.device` (`position:relative`) — so at that sibling position a React
// screen has no positioned ancestor at all and sizes to the viewport
// instead of the phone frame, escaping it at any width past the 520px
// breakpoint where `.device` stops filling the viewport.
//
// Moved here, once, before the first render: into `.device`, immediately
// before the legacy `#screen`. Two things this placement is chosen to keep:
//   - containment — `.device` becomes the mount node's positioned ancestor
//     too, so a React `.screen.open` resolves its `inset: 0` the same way
//     the legacy one already does, at every viewport width.
//   - paint order — `insertBefore` keeps the mount node exactly where it
//     already was relative to `#screen` (earlier in document order, simply
//     re-parented), so a React screen still sits BEHIND the legacy one in
//     the stacking order the harness (screens.py, bridge.py) already relies on:
//     when both carry `.open` at once (a legacy mediaSheet opened over a migrated
//     results screen), `#screen` — later in the DOM — paints on top, and
//     `document.querySelector('.screen.open')` still resolves the React
//     screen first.
// A missing `#device`/`#screen` (a document without the fragment injected)
// leaves the node where the markup put it rather than throwing — the same
// fail-soft posture as the rest of this boot sequence.
const mountNode = document.getElementById("shell")!;
const device = document.getElementById("device");
const legacyScreen = document.getElementById("screen");
if (device && legacyScreen) device.insertBefore(mountNode, legacyScreen);

// Focus follows the layers, and it is installed before the first render so the
// very first drawer an operator opens is already covered. It asks nothing of
// the engine: it watches the `data-open` attribute both worlds already emit.
installFocusManager();

// The bottom bar's real height, published for everything that must sit above
// it. Here rather than in the engine, which no longer carries a copy: the
// measurement has to outlive the engine, and the day it goes is the wrong day
// to move it.
//
// AFTER the engine has started, and that ordering is the whole of the placement.
// The bar's node is static markup, so it exists long before this line — but it
// is EMPTY until `renderNav` fills it, and a measurement taken then publishes
// the height of an empty bar. The `ResizeObserver` would correct it on the next
// layout; publishing the right value the first time saves the frame in which
// everything above the bar sits on `0px`.
publishBarHeight();

// THE QUERY CACHE, created here and wrapped around the router (invariant 4).
// Server state lives in it; the address lives in the router; only ephemeral
// interface state lives in the store. It is created in the BOOT rather than at
// its module's evaluation for the same reason the store is — one owner, one
// instant, named in the order everything else is named in.
//
// Published for the harness beside the other seams: a rule that has to reach
// inside a module to ask what the cache holds is a rule coupled to how the
// module is built, which is the arrangement `__store` and `__mocks` refuse.
const queryClient = createQueryClient();
window.__queries = queryClient;
// The dying engine asks one question synchronously that the cache now owns
// (§13: one derivation per question). It is installed here, beside the other
// seams, and it goes with the engine at L13.
installDecisionLookup(queryClient);
installLibraryPaging(queryClient);
installQueueActions(queryClient);
installSuggestionsLookup(queryClient);
installFollowActions(queryClient);
// The engine draws surfaces that read the cache, and it draws them once.
installEngineRedraw(queryClient);

ReactDOM.createRoot(mountNode).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
