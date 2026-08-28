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
  /**
   * Which of those events this rule is about, when the type is not enough.
   *
   * A RULE WITHOUT ONE FIRES ON EVERY EVENT OF ITS TYPE, and some types are
   * not a state change at all — `ItemProgressed` fires once per item per step
   * across nine steps, which for a sixty-item run is some five hundred and
   * forty. Pointed at a list with no predicate, that is a refetch every
   * round-trip for the length of a run: a poll wearing an event's clothes, and
   * the third clause of this lot read backwards, since a `setInterval` any grep
   * can find would at least be visible.
   *
   * The payload is the event's own `data`, as the server serialised it.
   */
  when?: (data: Record<string, unknown>) => boolean;
  /**
   * What an event this rule IS about looks like.
   *
   * REQUIRED WHEREVER `when` IS, and declared beside it so the two cannot
   * drift. A predicate with no example is untestable: R91 drives every rule by
   * emitting an event of its type, and against an empty payload a predicate
   * refuses — so the rule would read as « declared and nothing moved » and the
   * measurement would be about the harness rather than the map. The example is
   * the smallest payload the predicate accepts.
   */
  sample?: Record<string, string>;
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
  /** Event types this feature sees and deliberately ignores. */
  types: readonly string[];
  /**
   * Addresses this feature READS that no event refreshes.
   *
   * THE OTHER HALF OF COMPLETENESS, and it is the half R91 cannot see. That
   * rule holds the implementation against the DECLARATION — measured, not
   * assumed: pointing an event at the wrong key leaves every per-rule hold
   * green, because the key it expects is read from the same file the mistake is
   * in. What catches a surface that has quietly stopped being refreshed is this
   * list: every address a feature's `queries.ts` reads is named by a rule or
   * named here, and `check-live-relay.py --arm map-completeness` refuses one
   * that is in neither.
   */
  keys: readonly string[];
  because: string;
};
