// The navigation seam: the history primitives the legacy nav cluster calls,
// and the screen openers a migrated call site invokes instead of its old
// `openX(...)`.
//
// One subject, two halves, and they belong together: both answer « how does
// the engine move the address ». What decides WHEN they are installed is the
// boot, which is why each half is a function rather than a module-level
// assignment — the order relative to `window.__startEngine` is load-bearing
// and it stays legible in one place.
import {
  carryingState,
  layerEntry,
  type CarriedIdentity,
  type LayerRecord,
} from "../lib/navigation-entry";
import { heldIdentity, providerAddress } from "../lib/held-identity";
import { createBrowserHistory } from "@tanstack/react-router";
import { go } from "../lib/navigate";
import { firstStuckFolder } from "../lib/queue";
import { fillBridgeDoor, fillScreensDoor, panel, screens } from "../lib/shell-doors";
import { store } from "../lib/store-access";
import { announceEntries } from "./layers";

// The bridge's contract, stated once. The verbs are the legacy nav cluster's
// primitives, and their names are the fragment's own; the state objects
// crossing them are the legacy ones.
type Bridge = {
  record: (state: unknown, url: string) => void;
  replace: (state: unknown, url?: string) => void;
  pushLayer: (layer: string, url?: string, record?: LayerRecord) => void;
  back: () => void;
  // Settling SEVERAL entries at once — the door a caller uses instead of
  // saying `back()` twice in the same task. `n` counts ENTRIES, and the
  // traversal is announced to the engine before it is issued.
  rewind: (n: number) => void;
  // The callback is handed the entry's state AND the direction the
  // traversal came from: the same entry means opposite things stepped onto
  // forwards and stepped back onto, and only the caller of `subscribe` can
  // tell them apart.
  onBack: (
    callback: (state: unknown, direction: "BACK" | "FORWARD" | "GO") => void,
  ) => () => void;
};

// One entry per migrated screen: what a legacy call site invokes instead of
// its old `openX(...)` function. `title` crosses the bridge as a plain
// string — normalisation and encoding are this file's job, not the caller's.
type Screens = {
  profile: (title: string, replace?: boolean) => void;
  // The media sheet — the centre of the product. `title` crosses as a plain
  // string here too; `carried` is what the caller knows of the item when it
  // knows it, and the cache is asked otherwise.
  mediaSheet: (title: string, carried?: CarriedIdentity) => void;
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
  // `q`/`mode` cross the bridge as plain strings (a literal like `"identify"`)
  // — the validated union lives in `/add`'s own `validateSearch`, not here.
  add: (q?: string, mode?: string, replace?: boolean) => void;
  // One passage, by its identifier — an arrival from the passages' list.
  run: (runUid: string) => void;
};

declare global {
  interface Window {
    __bridge: Bridge;
    __screens: Screens;
    // B-026's probe: raised by every write that fails silently otherwise
    // (`recordPath`, `data-navgo`, and this file's own `openPanel`),
    // declared here (`refonte.html@60530dbd8` declares and resets it for its own two
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
export const history = createBrowserHistory();

/**
 * Installs the history primitives the legacy nav cluster calls.
 *
 * Called from the boot BEFORE the engine starts and before anything can open a
 * panel, which is the guarantee `panel-host.ts` leans on.
 */
export function installHistoryBridge(): void {
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
fillBridgeDoor({
  record: (state: unknown, url: string) => {
    history.push(url, state);
    history.flush();
  },
  replace: (state: unknown, url?: string) => {
    history.replace(url ?? history.location.href, state);
    history.flush();
  },
  pushLayer: (layer: string, url?: string, record?: LayerRecord) => {
    // A layer that carries an ADDRESS pushes it; one that does not keeps the
    // address it opened over. That is D1's tier split, expressed in one
    // argument: tier 2 is addressable and reopens on a reload, tier 3 is
    // transient and Back still closes it. The RECORD is what reopens either
    // one when a Back lands on its entry after an arrival closed it.
    history.push(url ?? history.location.href, layerEntry(layer, record));
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
    announceEntries(n);
    history.go(-n);
  },
  onBack: (
    callback: (state: unknown, direction: "BACK" | "FORWARD" | "GO") => void,
  ) =>
    history.subscribe(({ action, location }) => {
      if (
        action.type === "BACK" ||
        action.type === "FORWARD" ||
        action.type === "GO"
      )
        callback(location.state, action.type);
    }),
});
}

/**
 * Installs the screen openers a migrated legacy call site invokes.
 *
 * Called from the boot after `installNavigation`, because every opener below
 * navigates through `go()`.
 */
export function installScreenBridge(): void {
// NFC-normalised here, once, on write — `QualityScreen` normalises again on
// read so an entry arriving by direct URL (not through this bridge) is
// covered too.
/* A LAYER LEFT FOR AN ARRIVAL KEEPS ITS ENTRY. Every screen below closes an open
   panel inside the navigation's own commit and WITHOUT unwinding it —
   `close(true)` — so the screen's entry lands on top of the panel's, and a Back
   from the screen comes back to the panel's entry, which reopens it. A verb
   that closed the panel first and navigated a beat later popped that entry,
   and no timer could say how long « a beat » was. */
const leavePanel = () => {
  if (panel.isOpen()) panel.close(true);
};

fillScreensDoor({
  // REPLACE when one screen leaves for another at the same depth: the release
  // screen's own « profile » takes that screen's place on the ladder.
  profile: (title: string, replace?: boolean) =>
    go(
      { to: "/quality/$name", params: { name: title.normalize("NFC") }, replace },
      leavePanel,
    ),
  // The sheet is addressed by PROVIDER ID (DOIT-11), and a tap holds a title,
  // so the crossing happens here — the seam, which is where every other
  // title-to-address translation already happens. WHAT THE TAP KNEW is the
  // item the card was drawn from, and the cache holds it: its identity gives
  // the address, and its title, poster and identity travel on the entry, so the
  // screen draws them on its first frame while its own read is out.
  //
  // §11's single exception is honoured rather than worked around: a medium with
  // no provider id has NO sheet, and the surface must lead to the resolution
  // instead of to a dead link.
  mediaSheet: (title: string, carried?: CarriedIdentity) => {
    const known = carried ?? heldIdentity(title.normalize("NFC"));
    const ids = providerAddress(known?.ids);
    if (!known || !ids) return screens.resolution();
    // THE PANEL LEAVES INSIDE THE COMMIT, so the transition captures it OPEN
    // and its departure has something to draw.
    //
    // The engine used to close the panel and wait 260ms before opening the
    // screen, because an open panel sits above a screen and opening the screen
    // underneath left it invisible. The transition answers that without a
    // delay: the panel's old snapshot slides down over the arriving screen,
    // which is the gesture the delay was standing in for.
    //
    // CLOSED WITHOUT UNWINDING — `close(true)`. The panel's history entry is
    // NOT popped here, because the media screen is pushed on top of it.
    //
    // WHAT BACK DOES: the panel's entry is still there, under the screen's, and
    // it records the panel's kind and subject — so a Back from the screen lands
    // on it and the ladder's handler REOPENS the panel, and a second Back
    // leaves for the list. R188 counts it, for this opener and its siblings.
    go(
      { to: "/media/$provider/$id", params: ids, state: carryingState(known) },
      leavePanel,
    );
  },
  // The legacy `openReleases`'s own first line, transplanted here rather than
  // into the component: `state.relatedTitle` is what the `data-take`
  // click-delegation branch reads once the operator picks a candidate, and it
  // must be current BEFORE the route renders, exactly as the legacy function
  // wrote it before drawing the screen. This file is SHELL code — the seam
  // itself — so it writes the store directly rather than through
  // `data.ts`'s `writeUiState` component door.
  releases: (title: string) => {
    store.write({ relatedTitle: title });
    go(
      {
        to: "/releases/$title",
        params: { title: title.normalize("NFC") },
      },
      leavePanel,
    );
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
    // FROM THE CACHE, since L09 — the same three lists every surface reads.
    // A default subject read off a fixture the engine no longer holds would be
    // a door opening onto nothing.
    const first = firstStuckFolder();
    const target = folder ?? (typeof first === "string" ? first : null);
    store.write({ resolveTarget: target });
    go(
      {
        to: "/resolution/$folder",
        // An address that changed with the interface language would no longer
        // identify anything — see the note above this function.
        // french-ok: a route PARAMETER, not interface copy
        params: { folder: (target ?? "élément inconnu").normalize("NFC") },
        replace,
      },
      leavePanel,
    );
  },
  // THE ROUTER CARRIES BOTH: the query and the mode travel in the address, and
  // nothing is copied into the store — a copy there outlived the screen and
  // handed « + » the previous visit's query (B-340).
  add: (q?: string, mode?: string, replace?: boolean) => {
    const validMode = mode === "identify" ? "identify" : "follow";
    go(
      {
        to: "/add",
        search: {
          q: q || undefined,
          mode: validMode === "identify" ? "identify" : undefined,
        },
        replace,
      },
      leavePanel,
    );
  },
  run: (runUid: string) => go({ to: "/run/$runUid", params: { runUid } }),
});
}
