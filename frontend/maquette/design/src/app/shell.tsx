// The strangler shell. One owner for the URL and the history: this router.
// The legacy engine keeps its navigation LOGIC (what to push, when to
// unwind) and loses only its primitives — it speaks to the bridge door,
// implemented on the router's history. `window.__go` keeps driving
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
// body below depends on exactly that: the arrival it calls draws through
// the engine. As a module the engine keeps that guarantee for the same
// reason it had it before: a module's dependencies evaluate before its
// body, so importing it HERE is what makes it run FIRST. Moving this line
// below any other statement would not reorder anything — imports hoist —
// but writing it anywhere else would suggest otherwise.
import "../engine/legacy.js";
// The harness module — the named states, their driver, the notes toggle. Installed
// below behind the mock layer's constant, so no build without the layer has it.
import { installHarness } from "../harness";
import { RouterProvider } from "@tanstack/react-router";
import React from "react";
import ReactDOM from "react-dom/client";
// What the features contribute to the panel — blocks and producers, each
// registered by its module's own evaluation. The LIST is `panel-contributions`,
// which is a file rather than four lines here because it gains an entry per
// feature converted and this file may only lose lines.
import "./panel-contributions";
// And the FRAME's own verbs — the page a control names, the two landings, the
// drawer, a message, the surface phase and the addressed panel. They are named
// here rather than in the list above, which is what the FEATURES contribute:
// these are the shell answering for itself, and they register at evaluation.
import "./frame-verbs";
import { createStore } from "./store";
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
import { installLiveUpdates } from "./live-updates";
import { installRelay } from "../lib/relay";
import { installRelayRecovery } from "./relay-recovery";
import { installOutboxWiring } from "./outbox-wiring";
import { installUpdateDiscipline } from "./worker-registration";
import { ConnectionMark, ConnectionNotice } from "./connection-notice";
import { Frame } from "./frame";
import { installArrival } from "./arrival";
import { installSeams } from "../engine/seams";
import { installNavigation } from "../lib/navigate";
import { QueryClientProvider } from "@tanstack/react-query";
import { createQueryClient, installSharedQueryClient } from "../lib/query-client";
import { installDecisionLookup } from "../features/arrivals/queries";
import { installLibraryDelete, installLibraryPaging } from "../features/library/queries";
import { installEngineRedraw } from "./engine-redraw";
import { installEngineData } from "./engine-data";
import { installNavigationSeam } from "./navigation-seam";
import {
  installFollowActions,
  installSuggestionsLookup,
} from "../features/acquisition/queries";
import { installFeatureVerbs } from "./feature-verbs";
import { installVerbs } from "../lib/verbs";
import { installSwipeArbitration } from "../lib/swipe-arbitration";
import { installPullIndicator } from "./pull-indicator";
import { installDiscoverSwipe } from "../features/acquisition/card-gestures";
import { installQueueActions } from "../lib/queue";
import { installReleasesLookup } from "../features/releases/queries";
import { installSearchLookup } from "../features/acquisition/search-queries";
import { installStore } from "../lib/store-access";
import { bridge, panel, screens } from "../lib/shell-doors";


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
installStore(store);

// THE QUERY CACHE (invariant 4): server state lives in it, the address in the
// router, only ephemeral interface state in the store. Created in the BOOT for
// the reason the store is — one owner, one instant — and handed once to the
// callers that are not components, as the store is.
//
// IT SITS HERE, ABOVE THE PANEL HOST, and that is an ORDERING rather than a
// preference: the host takes the cache a producer reads, and `installSeams`
// two calls below reads the panel door, so the host cannot go down past the
// cache and the cache has to come up past the host. Nothing between its old
// position and this one reads it; its own installers all sit where they sat.
// Both arrive as ARGUMENTS rather than as `const`s closed over from below, so
// the dependency is stated instead of resting on when a function is called.
const queryClient = createQueryClient();
installSharedQueryClient(queryClient);
installPanelHost(store, queryClient);

// The engine reads these three by import rather than off `window` — same
// objects, so the two ways cannot disagree. Filled HERE, after all three
// exist and before the engine is started below, which is the only window in
// which they can be both real and unused.
installSeams({ bridge, screens, panel });

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

// THE NAVIGATION TABLE, PUBLISHED BEFORE THE ENGINE STARTS. The engine's own
// first render draws the tab bar from it; a seam installed afterwards would
// leave the interface opening with an empty bar until something moved.
installNavigationSeam();

installArrival(store);
if (__MOCKS_BUILT_IN__) installHarness();

// `#shell` starts, in the markup, as a static sibling of `.stage` —
// index.html knows nothing about the phone frame the fragment draws. A
// migrated screen's `.screen{position:absolute;inset:0}` resolves against
// its nearest POSITIONED ancestor, `.device` (`position:relative`) — so at
// that sibling position a React screen has no positioned ancestor at all and
// sizes to the viewport instead of the phone frame, escaping it at any width
// past the 520px breakpoint where `.device` stops filling the viewport.
//
// Moved here, once, before the first render: into `.device`, after every
// element the markup puts there — the place it has always held among them.
// `.device` becomes the mount node's positioned ancestor, so a React
// `.screen.open` resolves its `inset: 0` against the phone frame at every
// viewport width, and the frame's own markup keeps preceding it in document
// order, which is the paint order the harness (bridge.py) relies on.
// A missing `#device` (a document without the fragment injected) leaves the
// node where the markup put it rather than throwing — the same fail-soft
// posture as the rest of this boot sequence.
const mountNode = document.getElementById("shell")!;
const device = document.getElementById("device");
if (device) device.appendChild(mountNode);

// Focus follows the layers, and it is installed before the first render so the
// very first drawer an operator opens is already covered. It asks nothing of
// the engine: it watches the `data-open` attribute both worlds already emit.
installFocusManager();

// E-002 IS NOT INSTALLED HERE ANY MORE. It attached to the `#drawer` the
// engine owned, which was static markup and existed at boot; the drawer is a
// component now and its node does not exist until React commits, so the
// gesture attaches from that component's own layout effect. It is unchanged
// otherwise — still the frame's gesture, still closing through
// `closeLayers` so a swipe and a scrim tap share one path.

// THE BOTTOM BAR'S HEIGHT IS NOT PUBLISHED FROM HERE ANY MORE. It was, and it
// had to be: the bar was static markup the engine filled, so the boot was the
// first moment a real height existed. The bar is a component now
// (`app/tab-bar.tsx`) and does not exist at all until React commits, so this
// call would have measured nothing and attached its `ResizeObserver` to
// nothing. It runs in that component's own layout effect instead. R84's
// « exactly one publisher » is untouched — `app/bar-height.ts` is still it.

// The dying engine asks one question synchronously that the cache now owns
// (§13: one derivation per question). It is installed here, beside the other
// seams, and it goes with the engine at L13.
installDecisionLookup(queryClient);
installLibraryPaging(queryClient);
installLibraryDelete(queryClient);
installQueueActions(queryClient);
installSuggestionsLookup(queryClient);
installFollowActions(queryClient);
/* THE GESTURES COME BEFORE THE TAP REGISTRY, and the order is load-bearing
   rather than tidy. The swipe's guard swallows the click that ends a drag, and
   it says so with `stopImmediatePropagation` — which stops the listeners
   registered AFTER it on the same node and none before. Registered after the
   registry, the guard would let every drag's release fire the verb under the
   finger: the shape the engine's own guard had, whose `stopPropagation` stopped
   a bubble delegation that no longer exists. */
if (device) {
  installSwipeArbitration(device);
  installDiscoverSwipe(device);
}
/* AND THE PULL, on the scrollport rather than the frame: the gesture is read
   where the scrolling happens, and the indicator it draws sits above it. A
   document without the fragment has neither, and the pull is simply absent. */
const port = document.getElementById("port");
if (port) installPullIndicator(port, document.getElementById("ptr"));
// The tap registry, and the verbs registering into it — both before a panel
// can be raised, which is why they sit here and not inside a component.
installVerbs();
installFeatureVerbs(queryClient);
installReleasesLookup(queryClient);
installSearchLookup(queryClient);
// The engine draws surfaces that read the cache, and it draws them once.
installEngineRedraw(queryClient);
// And what the engine reads with no component to ask for it.
installEngineData(queryClient);
// THE LIVE RELAY, LAST OF THE CACHE'S INSTALLERS AND BEFORE THE RENDER. Two
// things fix its place and neither is a preference:
//
//   AFTER the query client, because it invalidates into it and receives it as
//   an argument — the same reason `installPanelHost(store)` sits after
//   `createStore()`.
//   BEFORE the render, because the first event may arrive before React has
//   committed anything, and a subscription installed inside a component would
//   be a subscription that misses it. It is installed for the document's
//   lifetime, never mounted with a surface: `staleTime: Infinity` with no focus
//   and no reconnect refetch means a query that misses its invalidation is
//   stale for the life of the process (B-154), so a subscription that comes and
//   goes with a page is a subscription that loses data permanently.
installLiveUpdates(queryClient);
installRelay();
// AFTER the relay, because it reconnects one — and it subscribes to the same
// history instance the scroll restoration does, so it inherits that step's own
// ordering constraint.
installRelayRecovery();
// THE UPDATE DISCIPLINE, after everything it could disturb: nothing depends on
// it, so a host it cannot reach takes no other step with it. It does not
// REGISTER the worker — the envelope's inline script does, and why is written
// where that is decided.
installUpdateDiscipline();
// THE OUTBOX, LAST. It reads what survived the previous run and sends it, so it
// must come after everything a departure could touch.
// THE OUTBOX'S FOUR JOINS — the cache, the relay, the harness seam and the mock
// layer's reset. Each names something the queue is forbidden to know, and the
// boot is where facts cross; `outbox-wiring.ts` owns WHAT crosses, this file
// owns WHEN.
installOutboxWiring(queryClient);

ReactDOM.createRoot(mountNode).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* The connection, FIRST, and outside the router on purpose: what the
          interface says about its own liveness is true of every page, and a
          notice mounted per route would come and go with a navigation. */}
      <ConnectionMark />
      <ConnectionNotice />
      <RouterProvider router={router} />
      {/* The frame LAST, so its layers sit after the router's screens in
          document order — which is the order the stacking already assumed when
          the engine drew them after `#shell`. */}
      <Frame />
    </QueryClientProvider>
  </React.StrictMode>,
);
