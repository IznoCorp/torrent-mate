// The navigation seam: the history primitives the legacy nav cluster calls,
// and the screen openers a migrated call site invokes instead of its old
// `openX(...)`.
//
// One subject, two halves, and they belong together: both answer « how does
// the engine move the address ». What decides WHEN they are installed is the
// boot, which is why each half is a function rather than a module-level
// assignment — the order relative to `window.__startEngine` is load-bearing
// and it stays legible in one place.
import { createBrowserHistory } from "@tanstack/react-router";
import { go } from "../lib/navigate";
import { firstStuckFolder } from "../lib/queue";

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
};
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
    // NOT popped, because the media screen is pushed ON TOP of it: Back then
    // returns to the panel over the list, which is what §16 asks for and what
    // the reversed departure animation is drawn for. The old shape popped the
    // panel's entry and pushed the screen's, so Back landed on the bare list
    // and the return animation had nothing to return to.
    go(
      { to: "/media/$provider/$id", params: ids },
      () => {
        if (window.__panel.isOpen()) window.__panel.close(true);
      },
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
    // FROM THE CACHE, since L09 — the same three lists every surface reads.
    // A default subject read off a fixture the engine no longer holds would be
    // a door opening onto nothing.
    const first = firstStuckFolder();
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
}
