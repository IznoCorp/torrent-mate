// The ONE programmatic navigator.
//
// It takes a path and its parameters, knows no domain and renders nothing, so
// it lives here rather than in the shell — and that placement is what breaks a
// cycle: a screen component needs to navigate, the shell needs to render that
// screen, and while the verb lived in the shell those two needs pointed at each
// other.
//
// THE ROUTER IS HANDED IN, NEVER IMPORTED. The router instance is created in
// the shell's body, so this module cannot import it without pointing back at
// the layer that composes it. It receives it at boot instead, through the same
// live-binding shape the engine's seams already use: the shell fills the names
// once, and every call afterwards reads what was filled. A call before the boot
// handshake is a programming error and says so, rather than failing as
// `undefined is not a function` on a tap nobody tested.
//
// The immediate flush is the whole reason this is a function and not a bare
// `router.navigate`: the router library batches its commits into a microtask,
// so two writes issued in the same task would merge into ONE history entry —
// and the legacy unwinding logic COUNTS entries. Flushing keeps native
// `pushState` semantics: one call, one entry.

/** What `go()` needs of a router — the one method it calls. */
type Router = {
  navigate: (options: {
    to: string;
    params?: Record<string, string>;
    search?: Record<string, unknown>;
    replace?: boolean;
  }) => unknown;
};

/** What `go()` needs of the history — what keeps one call, one entry. */
type RouterHistory = {
  flush: () => void;
};

let router: Router | null = null;
let history: RouterHistory | null = null;

/**
 * Hands this module the router and the history the shell created.
 *
 * Called once from the shell's boot, before anything can navigate.
 *
 * Args:
 *     boundRouter: The single router instance — the only writer of the URL.
 *     boundHistory: Its history, for the flush after every write.
 */
export function installNavigation(boundRouter: Router, boundHistory: RouterHistory): void {
  router = boundRouter;
  history = boundHistory;
}

/**
 * Navigates, and flushes so the entry lands before the next statement runs.
 *
 * Args:
 *     target: The address, its path params, its search params, and whether it
 *         replaces the current entry rather than pushing one.

 * Raises:
 *     Error: When called before the shell's boot has handed the router over.
 *         Silence here would swallow a navigation and leave the interface on a
 *         page the URL no longer describes.
 */
export function go(target: {
  to: string;
  params?: Record<string, string>;
  search?: Record<string, unknown>;
  replace?: boolean;
}): void {
  if (!router || !history)
    throw new Error("navigate: go() called before installNavigation()");
  const commit = () => {
    void router!.navigate({
      to: target.to,
      params: target.params,
      search: target.search,
      replace: target.replace ?? false,
    });
    history!.flush();
  };

  // P5 — THE PAGE SWITCH IS A DECLARED TRANSITION, through the platform's own
  // View Transitions API. D9 adopts it: native, compositor-driven, zero bytes,
  // declarative — so it is measurable. A JavaScript animation library is
  // refused for this, because it buys what the platform gives and moves motion
  // out of the stylesheet (rule 1).
  //
  // THE COMMIT RUNS SYNCHRONOUSLY EITHER WAY, and that is not a detail. The
  // flush above exists because the router batches its commits into a microtask,
  // so two writes in one task would merge into ONE history entry — and the
  // dying engine's unwinding logic COUNTS entries. `startViewTransition` calls
  // its callback before yielding to the event loop, so « one call, one entry »
  // survives; the ladder's rules (R59, R65, R69, R82, R94) are read as this
  // phase's gate rather than assumed, for exactly that reason.
  //
  // NOTHING BRANCHES ON THE MOTION PREFERENCE HERE. Reduced motion is a
  // DESIGNED state and it is drawn in `styles/base.css`, where the
  // `::view-transition-*` rules live (invariant 13: motion is declared, not
  // scripted; invariant 14: the reduced state is drawn like any other). A
  // JavaScript branch on `prefers-reduced-motion` would move that decision out
  // of the stylesheet and out of the oracle's field.
  //
  // The capability check is a capability check and nothing more: a browser
  // without the API navigates exactly as before.
  if (!document.startViewTransition) {
    commit();
    return;
  }
  document.startViewTransition(commit);
}
