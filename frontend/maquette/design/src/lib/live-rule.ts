// What a live rule IS — the type, and nothing that uses it.
//
// IT LIVES HERE BECAUSE OF INVARIANT 8, and the cycle was real rather than
// theoretical. The type was declared in `app/live-updates.ts`, which imports
// each feature's table; each feature's table imported the type back, and
// `check-frontend-boundaries.py` printed the loop:
//
//     app/live-updates.ts → features/arrivals/live.ts → app/live-updates.ts
//
// A cycle makes every OTHER dependency rule unenforceable, because the cycle IS
// the violation. A type has no reason to sit with its consumer: `lib/` is where
// the application's shape lives, and « what a rule looks like » is shape.
//
// A TYPE IMPORT IS AN IMPORT. `import type` erases at build time and the module
// graph is unchanged as far as the guard — and a reader — is concerned.

/**
 * One rule: the events that refresh a set of query keys.
 *
 * A KEY IS A PREFIX into the cache, and its width is a decision. One element
 * too short covers siblings nobody listed — it compiles, its types agree, and
 * nothing but a measurement against the cache tells the difference. R91 is that
 * measurement.
 */
export type LiveRule = {
  /** The event types, spelled as the backend's own class names. */
  types: readonly string[];
  /** What to invalidate, each a prefix. */
  keys: readonly unknown[][];
  /** Why these events refresh these keys, in one line, for the next reader. */
  because: string;
};

/**
 * The event types that reach a feature and deliberately refresh nothing.
 *
 * WRITTEN DOWN RATHER THAN OMITTED. An event nobody handles is not an error; an
 * event nobody can COUNT is how a map silently stops covering its subject. Each
 * entry is a decision someone took, and `check-live-relay.py --arm
 * map-completeness` refuses a type that is in neither list.
 */
export type LiveExemptions = {
  types: readonly string[];
  because: string;
};
