// the engine's derived read model over the staging queue
//
// The slice of `window.__referentiel` this layer reads, and nothing else.
//
// The engine publishes ONE object; what it publishes is not one subject. A
// single 340-line declaration of all of it made every module that needed two
// members depend on all hundred and eight, and seventeen of twenty-five
// modules did. Each slice is declared where its subject lives instead, and the
// global's own type is their intersection (app/reference.d.ts) — so a
// reader imports nothing to be typed, and a member nobody's subject claims has
// nowhere to be written down.

// A queue card exactly as `BLOCKED` / `STUCK` / `STUCK_REAL` shape one — the
// source carries more fields (`s`, `chip`, `strip`, `noposter`…) than any one
// reader needs, so this stays the same loose index shape as `MediaSheet`
// rather than a speculative closed type: a caller narrows the fields it
// actually reads, starting with `t` to match against a decision's `d`.
export type QueueCard = Record<string, unknown>;

export type EngineQueue = {
  // Thin arrows over `derived.blocked` / `derived.stuck`, published so the
  // FUNCTION REFERENCE stays stable across renders while the value each call
  // returns stays live — a component can pass these to a hook that expects a
  // stable selector without ever seeing a stale snapshot.
  derivedBlocked: () => QueueCard[];
  derivedStuck: () => QueueCard[];
  derivedMoving: () => QueueCard[];
  derivedSettled: () => QueueCard[];
  derivedTakeable: () => QueueCard[];
  derivedInflight: () => QueueCard[];
  derivedNotfound: () => QueueCard[];
  derivedDoneToday: () => QueueCard[];
  // Agreeing with the machine (`actionLeave`) or with a candidate
  // (`actionResolve`, `choice` the chosen title when the operator picked
  // one) both remove the folder from wherever it is queued and hand it back
  // to the pipeline; `actionTake` restarts a takeable item instead.
  // Each toasts and re-renders on success; `actionLeave` also reports
  // whether the folder was found at all.
  actionResolve: (title: string, choice?: string) => void;
  actionLeave: (title: string) => boolean;
  actionTake: (title: string) => void;
};
