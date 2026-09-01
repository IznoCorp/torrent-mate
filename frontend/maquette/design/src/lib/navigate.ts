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
  }) => Promise<void> | void;
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
 *     during: Work to run inside the transition's commit, before the address
 *         changes — for whatever must be captured departing rather than
 *         already gone.

 * Raises:
 *     Error: When called before the shell's boot has handed the router over.
 *         Silence here would swallow a navigation and leave the interface on a
 *         page the URL no longer describes.
 */
export function go(
  target: {
    to: string;
    params?: Record<string, string>;
    search?: Record<string, unknown>;
    replace?: boolean;
  },
  // WORK THAT BELONGS TO THE SAME COMMIT, and the reason it cannot be done by
  // the caller before or after the call.
  //
  // A view transition captures the OLD state at the next rendering update after
  // `startViewTransition` — not synchronously at the call. So a caller that
  // dismisses something and then navigates has already dismissed it by the time
  // the snapshot is taken, and the departing thing is captured in its dismissed
  // state, or not captured at all. That is not a hypothesis: the panel's
  // departure animation had no subject for exactly this reason, and doing the
  // dismissal AFTER the call does not help either — the snapshot lands between
  // the two statements, and no timeout can be written that is reliably on the
  // right side of a frame boundary without being a number somebody guessed.
  //
  // Inside the commit the ordering is not a race: the old state is whatever was
  // on screen when the transition started, the new state is what this callback
  // leaves behind, and both are facts rather than timings.
  during?: () => void,
): void {
  if (!router || !history)
    throw new Error("navigate: go() called before installNavigation()");
  const commit = () => {
    during?.();
    const navigated = router!.navigate({
      to: target.to,
      params: target.params,
      search: target.search,
      replace: target.replace ?? false,
    });
    history!.flush();
    // THE NAVIGATION'S PROMISE IS HANDED BACK, and it is the transition that
    // needs it. A view transition captures the NEW state when the callback's
    // returned promise settles; discarded, the capture happens at the next
    // rendering opportunity whether or not the route has committed, and the
    // « new » snapshot is the page being left. That is correct today only
    // because no route has a loader or a lazy component — the day one does, the
    // arrival animates the departing page and R115 stays green, because it
    // reads the OLD side.
    //
    // The flush stays where it was, synchronous and before the return: « one
    // call, one entry » is about the router batching two writes in ONE task,
    // and awaiting after the flush changes nothing about that.
    return navigated;
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
    void commit();
    return;
  }
  // THE COMMIT RUNS INSIDE THE CALLBACK, WHICH IS WHAT THE API IS FOR — and
  // the shortcut that avoided it was measured and thrown away.
  //
  // « Ask for the capture, then commit synchronously » looked like a way to keep
  // `go()` synchronous AND get a transition. It kept the synchrony and produced
  // a DEGENERATE transition: the browser captures the old state after the
  // current task, so the commit had already run and the « old » snapshot was
  // the new page. Proved by a name that exists on ONE side —
  // `::view-transition-old(screen-banner)` was present while the library page
  // it left carries no `[data-part="hero"]` at all, which can only happen if
  // the media screen was already mounted when the snapshot was taken.
  //
  // Animations ran the whole time, so every reading that counted them was
  // green over a transition showing nothing.
  //
  // WHAT THIS COSTS, said plainly: `go()` is asynchronous again. The address
  // settles when the callback runs rather than before the next statement. The
  // flush inside it still keeps « one call, one entry » — that was always about
  // the router batching two writes in ONE task, and the callback is one task —
  // and the ladder's rules are read as this lot's gate rather than assumed.
  const transition = document.startViewTransition(commit);

  // A SUPERSEDED TRANSITION REJECTS, AND THAT IS NORMAL RATHER THAN AN ERROR.
  //
  // Starting a second view transition while one is running SKIPS the first, and
  // the skipped one rejects `ready` (and `finished`) with « Transition was
  // skipped ». Nothing is wrong: the reader navigated again before the first
  // animation finished, which is what a fast thumb does all day.
  //
  // Unhandled, those rejections reach the console as errors — measured, and it
  // is how this was found: `harness/navigation.py` drives two navigations in a
  // row and holds « no JS error during the two calls », which fell on exactly
  // this. A rejection nobody handles is also a rejection that would drown a
  // real one in the same log.
  //
  // They are swallowed HERE rather than by a global handler, because a global
  // one would swallow every other unhandled rejection with them.
  transition.ready.catch(() => undefined);
  transition.finished.catch(() => undefined);
}
