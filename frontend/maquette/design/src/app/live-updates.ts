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

import type { LiveRule } from "../lib/live-rule";
import { subscribeToEvents, type RelayEvent } from "../lib/relay-events";

// ONE LINE PER FEATURE — the frame naming its features, which is what
// `router-tree.tsx` does with its pages. What each line brings is the feature's
// own; nothing here knows an event name or a query key.
import { acquisitionLiveRules } from "../features/acquisition/live";
import { arrivalsLiveRules } from "../features/arrivals/live";
import { libraryLiveRules } from "../features/library/live";
import { maintenanceLiveRules } from "../features/maintenance/live";
import { mediaLiveRules } from "../features/media/live";
import { systemLiveRules } from "../features/system/live";

// HOW MANY UNCLAIMED EVENTS ARE KEPT. The list is a diagnostic — an event
// nobody can COUNT is how a map silently stops covering its subject — and it
// used to grow for the life of the process. The events that feed it are the
// exempted ones, which include the highest-frequency in the system by design:
// `BackfillItemCompleted` fires once per item of a backfill that walks the whole
// library, and this is an installed application nobody reloads for days.
// A diagnostic bounded to nothing is a leak.
const UNMATCHED_KEPT = 200;

/** The most recent events that arrived and matched no rule. */
let unmatched: string[] = [];
/** How many have arrived in all, which is the figure a rule reads. */
let unmatchedTotal = 0;

/**
 * Reads the events nothing claimed.
 *
 * @returns Their types, in arrival order, with repeats.
 */
export function unmatchedEvents(): string[] {
  return [...unmatched];
}

/**
 * Reads how many unclaimed events have arrived in all.
 *
 * SEPARATE FROM THE LIST, because the list is capped: a count taken from its
 * length would stop rising at the cap and read as « nothing more arrived ».
 *
 * @returns The total since the boot.
 */
export function unmatchedCount(): number {
  return unmatchedTotal;
}

/**
 * Subscribes the whole application's rules to the relay, once, at boot.
 *
 * @param queryClient The cache the rules invalidate into.
 * @returns Nothing. It is installed for the document's lifetime.
 */
export function installLiveUpdates(queryClient: QueryClient): void {
  const rules: LiveRule[] = [
    ...acquisitionLiveRules,
    ...arrivalsLiveRules,
    ...libraryLiveRules,
    ...maintenanceLiveRules,
    ...mediaLiveRules,
    ...systemLiveRules,
  ];
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
      unmatchedTotal += 1;
      unmatched.push(event.type);
      if (unmatched.length > UNMATCHED_KEPT) unmatched.shift();
      return;
    }
    for (const rule of matched) {
      // A RULE MAY BE ABOUT SOME OF ITS TYPE'S EVENTS AND NOT ALL OF THEM.
      if (rule.when !== undefined && !rule.when(event.data)) continue;
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
  unmatchedTotal = 0;
}
