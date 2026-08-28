// What a server event refreshes — composed, never declared here.
//
// THE SHAPE OF THIS FILE IS INVARIANT 10 READ LITERALLY. Which events refresh
// which data is DOMAIN knowledge, so it lives with each domain
// (`features/<domain>/live.ts`). The transport is the application's SHAPE, so
// it lives in `lib/relay.ts`. What is left — naming the features and handing
// their tables to the relay — is the same species as `router-tree.tsx`, which
// is one import per page: the frame naming its pages, which every framework has
// somewhere and which invariant 10 blesses by name.
//
// So the count that matters is what this file names. It names FEATURES. It
// does not name an event, a query key or a domain object, and a table that
// started doing so would be the central map this arrangement exists to refuse
// — production has one, and it carries forty event names and twenty keys in a
// file that belongs to no domain at all.
//
// WHY THE INVALIDATION IS APPLIED HERE AND NOT IN `lib/relay.ts`. A relay that
// knew what a query key was would be a relay coupled to the cache library. It
// hands out events; this decides what they mean.
import type { QueryClient } from "@tanstack/react-query";

import { subscribeToEvents, type RelayEvent } from "../lib/relay";

// ONE LINE PER FEATURE — the frame naming its features, which is what
// `router-tree.tsx` does with its pages. What each line brings is the feature's
// own; nothing here knows an event name or a query key.
import { arrivalsLiveRules } from "../features/arrivals/live";

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
 * The event types that reach the interface and deliberately refresh nothing.
 *
 * WRITTEN DOWN RATHER THAN OMITTED. An event nobody handles is not an error; an
 * event nobody can COUNT is how a map silently stops covering its subject. Each
 * entry here is a decision someone took, and `check-live-relay.py --arm
 * map-completeness` refuses a type that is in neither list.
 */
export type LiveExemptions = {
  types: readonly string[];
  because: string;
};

/** Every event that arrived and matched no rule, since the boot. */
let unmatched: string[] = [];

/**
 * Reads the events nothing claimed.
 *
 * @returns Their types, in arrival order, with repeats.
 */
export function unmatchedEvents(): string[] {
  return [...unmatched];
}

/**
 * Subscribes the whole application's rules to the relay, once, at boot.
 *
 * @param queryClient The cache the rules invalidate into.
 * @returns Nothing. It is installed for the document's lifetime.
 */
export function installLiveUpdates(queryClient: QueryClient): void {
  const rules: LiveRule[] = [...arrivalsLiveRules];
  // Built once, not per event: a lookup rebuilt on every frame would turn a
  // replay burst into N table constructions.
  const byType = new Map<string, LiveRule[]>();
  for (const rule of rules) {
    for (const type of rule.types) {
      const found = byType.get(type);
      if (found === undefined) byType.set(type, [rule]);
      else found.push(rule);
    }
  }

  subscribeToEvents((event: RelayEvent) => {
    const matched = byType.get(event.type);
    if (matched === undefined) {
      unmatched.push(event.type);
      return;
    }
    for (const rule of matched) {
      for (const key of rule.keys) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
    }
  });
}

/**
 * Forgets what arrived, so a named state starts from a known count.
 */
export function resetLiveUpdates(): void {
  unmatched = [];
}
