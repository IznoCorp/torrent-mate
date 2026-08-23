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
// The i18n bootstrap is imported FIRST, for its side effect (initialising
// `i18next`) — every migrated screen calls `useTranslation()`, and the
// first of them can render before any other import here settles.
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
import {
  createBrowserHistory,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import React from "react";
import { flushSync } from "react-dom";
import { useTranslation } from "react-i18next";
import ReactDOM from "react-dom/client";
import { refuseBlock, type PanelDescriptor } from "../ui/panel/contract";
// The two panel blocks that belong to a domain, imported for their SIDE
// EFFECT: each declares its kind to the panel's contract and registers what
// draws it as it evaluates. Nothing else imports them — a panel is opened by
// a legacy producer through `window.__panel`, never by a component holding a
// reference to the block — so the boot is where they have to be named, and
// `app/` naming what a feature contributes at boot is exactly its job.
import "../features/media/panel-seasons";
import "../features/settings/panel-field";
import { createStore, type Store } from "./store";
import { installFocusManager } from "./focus";
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
import { installSeams } from "../engine/seams";
import {
  addressOf,
  destinationOf,
  isScreenPath,
  PANEL_PARAMETER,
  SIGN_IN_PATH,
  withoutPanel,
  withPanel,
} from "../lib/addresses";
import { go, installNavigation } from "../lib/navigate";

// The bridge's contract, stated once. The verbs are the legacy nav cluster's
// primitives, and their names are the fragment's own; the state objects
// crossing them are the legacy ones.
type Bridge = {
  record: (state: unknown, url: string) => void;
  replace: (state: unknown, url?: string) => void;
  pushLayer: (layer: string, url?: string) => void;
  back: () => void;
  // Settling SEVERAL entries at once — the door a caller uses instead of
  // saying `back()` twice in the same task. `n` counts ENTRIES, and the
  // traversal is announced to the engine before it is issued.
  rewind: (n: number) => void;
  onBack: (callback: (state: unknown) => void) => () => void;
};

// One entry per migrated screen: what a legacy call site invokes instead of
// its old `openX(...)` function. `title` crosses the bridge as a plain
// string — normalisation and encoding are this file's job, not the caller's.
type Screens = {
  profile: (title: string) => void;
  // The media sheet — the centre of the product. `title` crosses as a plain
  // string here too; the percent-encoding and the NFC normalisation are done
  // below, on write, and again by `MediaScreen` on read.
  mediaSheet: (title: string) => void;
  // The release-choice screen — same `title`-crosses-as-a-plain-string
  // contract as `mediaSheet`/`profile` above. Unlike them, it also writes
  // `state.relatedTitle` (the legacy first line of `openReleases`, still read by
  // the `data-take` click-delegation branch) BEFORE navigating.
  releases: (title: string) => void;
  // The arbitration screen — the folder crosses as a plain string, and the
  // ARGUMENT IS OPTIONAL: the legacy `openResolve()` was called with nothing
  // from two call sites and picked the first stuck folder itself, so the
  // default is resolved here rather than at each caller. `replace` is for
  // the one caller that used to close the screen and re-open it on the next
  // folder — a pop plus a push, net one entry, which a replace reproduces
  // exactly.
  resolution: (folder?: string, replace?: boolean) => void;
  // `q`/`mode` cross the bridge as plain strings, the way a legacy call site
  // already holds them (`state.addQ`, a literal like `"identify"`) — the
  // validated union lives in `/add`'s own `validateSearch`, not here.
  add: (q?: string, mode?: string) => void;
};

declare global {
  interface Window {
    __bridge: Bridge;
    __routeur: typeof router;
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
      };
    };
    // The domain hooks and the probes read the engine's state through this.
    __store: Store;
    __screens: Screens;
    // The layer-unwind bookkeeping stays ENGINE-side (the named-entry check
    // and the one-in-flight latch live with the popstate handler that consumes
    // them); the fragment publishes it so the shell's own layer can announce
    // its close the same way every legacy layer does.
    __derouler?: (layer: string) => void;
    // The same bookkeeping for a traversal of SEVERAL entries at once: the
    // shell says how many ENTRIES it settles, and the engine — which owns the
    // latch and the popstate handler reading it — turns that into the number
    // of pops it must swallow.
    __announcePops?: (entryCount: number) => void;
    // The probe R56 calls to prove the panel REFUSES a block nobody declared.
    // Published here because the constructor it exercises is a component now.
    __unknownPanel: () => void;
    // B-026's probe: raised by every write that fails silently otherwise
    // (`recordPath`, `data-navgo`, and this file's own `openPanel`),
    // declared here (`refonte.html` declares and resets it for its own two
    // sites) so this file's own catch can set it without a type error.
    __navEchec?: boolean;
  }
}

// The history instance is created here rather than left to the router's
// default, so the single writer is a named object this file owns: the bridge
// below and the router share it, and no future default can silently split it
// in two.
//
// Creating it stamps the current entry with the library's own bookkeeping
// keys. Nothing is preserved across that stamp on purpose: the engine no
// longer writes the entry itself — its boot writes go straight onto this
// instance BELOW, once window.__startEngine is called, so the entry the
// shell mounts on is written once, by the single writer, in the right order.
const history = createBrowserHistory();

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
        background: "var(--background)",
        color: "var(--danger)",
      }}
    >
      {t("screens.error.message")}
    </div>
  );
}

const router = createRouter({
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

// The bridge: the same verbs the legacy cluster used, one writer underneath.
// `layer` entries and the guard entry keep their exact state shapes — the
// legacy popstate logic still reads them.
//
// Two adaptations to the router's history, both to keep the NATIVE semantics
// the legacy engine was written against:
//   - writes are flushed immediately. The library batches pushes into a
//     microtask, which would merge two writes issued in the same task into a
//     single entry; native `pushState` creates one entry per call, and the
//     unwinding logic counts entries.
//   - a pop is reported as BACK / FORWARD / GO, never as a « POP » type: the
//     three together are what the `popstate` event used to signal.
//
// EVERY pop is forwarded to the engine callback, unfiltered. Ownership of an
// entry is not decided here by matching the address against a list of
// routes — it is already encoded in the entry's own SHAPE, and the engine
// callback reads that shape itself: a `layer` entry and a `tm: "nav"` entry
// keep their exact existing handling, and an entry written by the router
// carries neither key, so the callback's own checks fall through it
// harmlessly — the router has already re-rendered by the new URL before this
// runs, and the callback simply has nothing left to do. Filtering pops by
// pathname here was tried and withdrawn: a layer opened OVER a screen route
// (via `pushLayer`, still a `layer` entry) needs the SAME forwarding a layer
// opened anywhere else gets, or its own unwind guard never runs and closing
// it silently stops working.
window.__bridge = {
  record: (state: unknown, url: string) => {
    history.push(url, state);
    history.flush();
  },
  replace: (state: unknown, url?: string) => {
    history.replace(url ?? history.location.href, state);
    history.flush();
  },
  pushLayer: (layer: string, url?: string) => {
    // A layer that carries an ADDRESS pushes it; one that does not keeps the
    // address it opened over. That is D1's tier split, expressed in one
    // argument: tier 2 is addressable and reopens on a reload, tier 3 is
    // transient and Back still closes it.
    history.push(url ?? history.location.href, { layer });
    history.flush();
  },
  back: () => history.back(),
  /* One logical navigation, ONE history operation — R76's rule read on the way
     BACK. A caller leaving several entries behind used to say `back()` twice
     in the same task: two backs, two pops, and the engine's latch had only
     ever been told about one of them, so the surplus pop was read as the
     operator's own Back gesture (M11). Here the traversal is asked for once.

     Order matters twice over. Pending writes are flushed FIRST, for the same
     reason every write verb above flushes: a push still queued in this task
     would otherwise land after the traversal, on the entry just returned to.
     The announcement comes SECOND, before the traversal is issued, exactly as
     a layer announces its own unwind before popping — a pop that lands before
     its announcement is a pop nobody expected. `n` counts ENTRIES; how many
     popstate events a traversal of n entries costs is knowledge that belongs
     with the handler consuming them, and it is the announcer's to apply. */
  rewind: (n: number) => {
    if (n <= 0) return;
    history.flush();
    window.__announcePops?.(n);
    history.go(-n);
  },
  onBack: (callback: (state: unknown) => void) =>
    history.subscribe(({ action, location }) => {
      if (
        action.type === "BACK" ||
        action.type === "FORWARD" ||
        action.type === "GO"
      )
        callback(location.state);
    }),
};
window.__routeur = router;

/* ── SCROLL FOLLOWS THE HISTORY ENTRY ─────────────────────────────────────
   A screen opened OVER another one used to be the same LAYER replacing its
   own content, and the legacy layer restored the covered screen's scroll
   itself when it unwound (`closeScreen`). Router-owned screens replace each
   other by UNMOUNTING instead: the covered screen's DOM — and its scroll
   offset with it — is gone by the time one comes back to it, and the
   operator lands at the top of the list they had walked down.

   The memory is kept HERE, in the shell, and keyed per HISTORY ENTRY (the
   library stamps every entry with its own `key`), never per address: the
   same `/add?q=lucky` reached twice is two entries and two positions.
   Components stay unaware — nothing below is a prop, a hook or a context.

   Reading happens in the history subscription, which runs BEFORE React
   commits the new route: the outgoing screen is still in the DOM at that
   instant, which is the only moment its position can still be read.
   `.screen.open .port` resolves the React screen first (`#shell` precedes
   the legacy `#screen` in document order), which is exactly the one that is
   about to be unmounted; a legacy screen above it keeps its own restoration.

   Restoring mirrors the legacy re-apply: once as soon as the port exists,
   then once more when the late-loading posters have settled — the restored
   list is briefly too short and the browser clamps the offset back to 0. */
const scrollPositions = new Map<string, number>();
// A navigation that lands while a restoration is still waiting for its frames
// or its images invalidates it: the position belonged to the entry one has
// just left.
let restoreToken = 0;

function entryKey(state: unknown): string | null {
  const stamped = state as { key?: string; __TSR_key?: string } | undefined;
  return stamped?.key ?? stamped?.__TSR_key ?? null;
}

function activePort(): HTMLElement | null {
  return document.querySelector<HTMLElement>(".screen.open .port");
}

function restoreScroll(y: number, token: number): void {
  // The router commits its re-render on its own schedule, so the port of the
  // screen being restored does not exist yet at subscription time. A bounded
  // retry over a few frames is what waits for it without polling forever.
  let framesLeft = 5;
  const attempt = () => {
    if (token !== restoreToken) return;
    const port = activePort();
    if (!port) {
      if (--framesLeft > 0) requestAnimationFrame(attempt);
      return;
    }
    port.scrollTop = y;
    const images = [...port.querySelectorAll("img")].filter(
      (image) => !image.complete,
    );
    let pending = images.length;
    images.forEach((image) =>
      image.addEventListener(
        "load",
        () => {
          if (--pending <= 0 && token === restoreToken) port.scrollTop = y;
        },
        { once: true },
      ),
    );
  };
  requestAnimationFrame(attempt);
}

let currentKey = entryKey(history.location.state);
history.subscribe(({ action, location }) => {
  const port = activePort();
  if (currentKey && port) scrollPositions.set(currentKey, port.scrollTop);
  currentKey = entryKey(location.state);
  restoreToken += 1;
  // Only a RETURN restores: arriving forward on an address one has seen
  // before is a new visit, and it starts where a new visit starts.
  if (
    action.type !== "BACK" &&
    action.type !== "FORWARD" &&
    action.type !== "GO"
  )
    return;
  const remembered = currentKey ? scrollPositions.get(currentKey) : undefined;
  if (remembered) restoreScroll(remembered, restoreToken);
});

// `go()` — the ONLY programmatic navigator in `src/` — lives in
// `lib/navigate.ts`. It is handed the router and the history here, once,
// before anything can navigate: a verb that knows only a path and its
// parameters belongs with the domain-free helpers, and while it lived in this
// file a screen component importing it pointed back at the module that renders
// that very screen.
installNavigation(router, history);
// What a migrated legacy call site invokes instead of its old `openX(...)`.
// NFC-normalised here, once, on write — `QualityScreen` normalises again on
// read so an entry arriving by direct URL (not through this bridge) is
// covered too.
window.__screens = {
  profile: (title: string) =>
    go({ to: "/quality/$name", params: { name: title.normalize("NFC") } }),
  // The sheet is addressed by PROVIDER ID (DOIT-11), and callers hold a title,
  // so the crossing happens here — the seam, which is where every other
  // title-to-address translation already happens.
  //
  // §11's single exception is honoured rather than worked around: a medium with
  // no provider id has NO sheet, and the surface must lead to the resolution
  // instead of to a dead link. Measured on the fixture the day this landed, all
  // 259 sheets carry ids, so this branch is unreachable today — it is here
  // because the rule is, not because a case demanded it.
  mediaSheet: (title: string) => {
    const ids = window.__referentiel.addressIdsFor(title.normalize("NFC"));
    if (!ids) return window.__screens.resolution();
    go({ to: "/media/$provider/$id", params: ids });
  },
  // The legacy `openReleases`'s own first line, transplanted here rather than
  // into the component: `state.relatedTitle` is what the `data-take`
  // click-delegation branch reads once the operator picks a candidate, and it
  // must be current BEFORE the route renders, exactly as the legacy function
  // wrote it before drawing the screen. This file is SHELL code — the seam
  // itself — so it writes the store directly rather than through
  // `data.ts`'s `writeUiState` component door.
  releases: (title: string) => {
    window.__store.write({ relatedTitle: title });
    go({
      to: "/releases/$title",
      params: { title: title.normalize("NFC") },
    });
  },
  // The legacy `openResolve`'s own first two lines, transplanted here rather
  // than into the component. Two things happen before the address changes,
  // and both are the shell's business:
  //   - the DEFAULT subject is resolved. `openResolve()` was called with no
  //     argument from the deck's own state and from the « Résoudre → » act,
  //     and answered with the first stuck folder. That fallback stays one
  //     expression, read through the référentiel's live arrow, instead of
  //     being re-derived at each call site.
  //   - `state.resolveTarget` is written. It is what the `data-resolve` and
  //     `data-leave` click-delegation branches read as THE FOLDER (the
  //     attribute they carry is the choice, not the subject), so it must be
  //     current before the route renders — exactly as the legacy function
  //     wrote it before drawing the screen. Same accepted debt as `/add` and
  //     `/releases`: an entry reached by a typed URL never crossed this door,
  //     so those branches would act on a stale target until the legacy
  //     dispatcher itself goes.
  // A subject that resolves to nothing at all keeps the legacy's own last
  // resort — the screen said « élément inconnu » and offered its three ways
  // out on that name — expressed here as the address, since the address is the
  // identity now. That makes it the ONE French string in this file that stays
  // out of `fr.json`: it is a route parameter, and an address that changed
  // with the interface language would no longer identify anything.
  resolution: (folder?: string, replace?: boolean) => {
    const first = window.__referentiel.derivedStuck()[0]?.t;
    const target = folder ?? (typeof first === "string" ? first : null);
    window.__store.write({ resolveTarget: target });
    go({
      to: "/resolution/$folder",
      // An address that changed with the interface language would no longer
      // identify anything — see the note above this function.
      // french-ok: a route PARAMETER, not interface copy
      params: { folder: (target ?? "élément inconnu").normalize("NFC") },
      replace,
    });
  },
  // Kept in sync in `window.__store.write` BEFORE navigating: `state.addMode` is
  // still read by the untouched cross-world "add:N" panel act (it decides
  // ASSOCIATE vs regular add — see refonte.html) and by `addVerb`, and
  // `state.addQ` still seeds the FAB's next open. Neither is written again
  // after this call — typing on `/add` updates the ROUTER's search params
  // only, through `go()` directly, not through this bridge — so a value
  // read off `state.addQ`/`state.addMode` after the operator has typed
  // reflects the screen's ENTRY query, not its live one. That staleness is
  // the accepted cost of the ownership flip: the router is the only thing
  // that stays current for as long as the address reads `/add`.
  add: (q?: string, mode?: string) => {
    const validMode = mode === "identify" ? "identify" : "follow";
    // This file is SHELL code, not a component — it is the seam itself, so
    // it writes the store directly rather than through data.ts's
    // `writeUiState` write door (components must use that one; see its own
    // doc comment).
    window.__store.write({ addQ: q ?? "", addMode: validMode });
    go({
      to: "/add",
      search: {
        q: q || undefined,
        mode: validMode === "identify" ? "identify" : undefined,
      },
    });
  },
};

/* The bottom panel, as the shell's verbs — what every legacy producer calls
   instead of the dead `openSheet(html)`. The descriptor of FACTS crosses
   untouched; the markup is `PanelContent`'s business.

   The store write is flushed SYNCHRONOUSLY, and that is the whole subtlety of
   moving this layer. React commits a frame later by default, while the legacy
   layer's callers were written against a DOM that was already updated when
   `openSheet`/`closeSheet` returned: `data-del` closes the sheet and opens a
   dialog on the next line, and the dialog raises the SAME shared `#scrim` — a
   commit landing after that line would clear the scrim out from under the
   dialog. Flushing keeps the ordering every caller already relies on, and the
   panel's own content changes in the same task as the class that reveals it,
   so the sheet never slides in showing the previous panel for a frame. */
/* The address an addressed panel travels at — D1 read literally. The query
   says how THIS surface is being looked at, and under a screen the surface IS
   the screen: the panel hangs off the path one is already on, with whatever
   else that address carries kept verbatim.

   Composing it from `state.page` instead is not a cosmetic difference. A
   screen is a ROUTE, mounted by the router, so pushing the page's own path
   stops the route matching and the screen the operator linked to unmounts
   behind the panel — measured on `/media/$provider/$id`, which is the wave's
   headline surface. Off a screen, the page composes its address as it always
   did: the page IS the surface there. */
function panelAddress(address: string): string {
  if (isScreenPath(window.location.pathname))
    return (
      window.location.pathname + withPanel(window.location.search, address)
    );
  const { state } = window.__store.read();
  return addressOf(String(state.page ?? ""), state, address);
}

/* Raised while a panel is being put back onto the entry that ALREADY records
   it. It is the one case where a panel opens and history must not move: a
   Forward lands on the layer entry the first open pushed, and that entry is
   already there, already `{ layer: "sheet" }`, already carrying the panel's own
   address. Pushing a second one would leave a duplicate the next Back spends
   without taking the panel's address off. */
let onCurrentEntry = false;

/**
 * Runs a producer's open with the history write suppressed.
 *
 * The producer is called through this door rather than handed an argument,
 * because the argument would have to travel through every producer that opens
 * a panel — and they open it by describing FACTS, which is the whole of what
 * they are meant to know.
 *
 * Args:
 *     open: The producer call that opens the panel.
 */
function openPanelOnCurrentEntry(open: () => void): void {
  onCurrentEntry = true;
  try {
    open();
  } finally {
    onCurrentEntry = false;
  }
}

function openPanel(descriptor: PanelDescriptor): void {
  // Same order as the legacy `openSheet`: the layer first, the history entry
  // second. This file is SHELL code — the seam itself — so it writes the store
  // directly rather than through data.ts's `writeUiState` component door.
  flushSync(() =>
    store.write({ panelDescriptor: descriptor, panelOpen: true }),
  );
  if (onCurrentEntry) return;
  try {
    // D1's second tier: a panel whose subject is stable travels in the query,
    // so a reload reopens it. One with no `address` is transient and keeps the
    // address it opened over.
    window.__bridge.pushLayer(
      "sheet",
      descriptor.address ? panelAddress(descriptor.address) : undefined,
    );
  } catch (error) {
    // B-026's own residual: `window.__bridge` is assigned synchronously at this
    // module's top level, before any producer can call `open` — so unlike
    // the legacy `openSheet` swallow this copies, there is no boot-time
    // window where the bridge is genuinely absent. A throw here means the
    // write itself failed, and the store above already flushed the panel
    // open: silence would leave the interface showing the panel with no
    // history entry recording it, the exact URL/UI disagreement DOIT-10
    // forbids. Same wiring as `recordPath`'s and `data-navgo`'s own
    // tails.
    // ENGLISH, and not in `fr.json`: a console message is a tool message,
    // read by a developer, never by a reader of the interface.
    console.error("openPanel: navigation write failed", error);
    window.__navEchec = true;
  }
}

function closePanel(pop?: boolean): void {
  // Guarded per LAYER, exactly as `closeSheet` was: closing an already-closed
  // sheet would consume a history entry that belongs to someone else.
  if (!isPanelOpen()) return;
  flushSync(() => store.write({ panelOpen: false }));
  // `pop` means the entry is already being popped by the gesture that got us
  // here; otherwise the layer unwinds its own, through the engine's latch.
  if (!pop) window.__derouler?.("sheet");
}

// The STORE answers, never the DOM: a legacy caller asks in the middle of its
// own task ("is a layer up before I open a screen?"), and the store is right
// at that instant whatever React has painted.
function isPanelOpen(): boolean {
  return store.read().state.panelOpen === true;
}

window.__panel = {
  open: openPanel,
  close: closePanel,
  isOpen: isPanelOpen,
  openOnCurrentEntry: openPanelOnCurrentEntry,
};

// The engine reads these three by import rather than off `window` — same
// objects, so the two ways cannot disagree. Filled HERE, after all three
// exist and before the engine is started below, which is the only window in
// which they can be both real and unused.
installSeams({
  bridge: window.__bridge,
  screens: window.__screens,
  panel: window.__panel,
});

/* Lets the contract check prove the refusal rather than trust the comment on
   it: a block type nobody declared must raise, not draw nothing. Called as a
   plain function, not rendered — the dispatcher refuses before it reads
   anything else, which is what makes the refusal provable from outside. */
window.__unknownPanel = () => refuseBlock({ type: "ceci-n-existe-pas" });

// The store is created here, and the engine starts only once it — and the
// bridge above — are real. No queue, no replay: the engine's own boot writes
// (the arrival state, the guard entry, the back listener) now run straight
// onto the single writer, in the engine's own order, before the first
// render. A module that never evaluates simply never calls this, and the
// startup screen — already first in the frame — stays up: a visible,
// truthful failure instead of an app with mute verbs.
const store = createStore();
window.__store = store;
// The address model, published for the engine. It reads `state.page` and the
// dial fields straight off the object the engine hands over — the engine's own
// vocabulary, so nothing translates on the way across.
window.__address = {
  signInPath: SIGN_IN_PATH,
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

ReactDOM.createRoot(mountNode).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
