/**
 * ``useWsInvalidation`` — the one WS-event → query-invalidation map.
 *
 * Live domain events on the app-wide WebSocket must invalidate the caches they
 * affect so the UI reflects new state before the next poll tick. That mapping
 * was implemented in two divergent idioms across five-plus sites
 * (FRONTEND-DATA-03): a "newest-event-only" idiom in three hooks (which drops a
 * relevant event buried in a batched replay burst) and the correct "fresh-slice
 * ref" idiom in the shell. This hook is the single implementation, built on the
 * correct fresh-slice pattern, driven by a declarative list of rules.
 *
 * Each rule maps a set of event ``type`` values → the query keys to invalidate.
 * The event-name sets live once in ``@/api/events`` (e.g.
 * {@link PIPELINE_LIFECYCLE_EVENT_TYPES}), so no site re-declares them.
 *
 * - {@link WsInvalidationRule} — one ``{types, keys}`` rule.
 * - {@link useWsInvalidation} — subscribe + invalidate on matching events.
 */

import { useEffect, useRef } from "react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";

import { isEvent } from "@/api/events";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";

/** A single WS-event → invalidation rule. */
export interface WsInvalidationRule {
  /** Event ``type`` values that trigger this rule. */
  readonly types: ReadonlySet<string>;
  /** The query keys to invalidate when a matching event arrives. */
  readonly keys: readonly QueryKey[];
}

/**
 * Invalidate the mapped query keys whenever a fresh WS event matches a rule.
 *
 * Reads the app-wide event ring via {@link useEventStreamContext} and, on every
 * render where new events arrived, inspects EVERY event appended since the last
 * render — not just the newest one. ``useEventStream`` coalesces a synchronous
 * replay burst (a reconnect, or several items in one scrape tick) into ONE
 * re-render, so inspecting only ``events[length-1]`` would silently drop a
 * relevant event buried in the batch (the bug in the retired newest-only
 * idiom). A monotonic ``lastProcessedRef`` cursor makes each event count once.
 *
 * Args:
 *   rules: The declarative event-type → query-key invalidation rules. Read from
 *     a ref so the effect depends only on the event ring, never on inline-rule
 *     identity (which changes every render).
 */
export function useWsInvalidation(rules: readonly WsInvalidationRule[]): void {
  const queryClient = useQueryClient();
  const { events } = useEventStreamContext();

  // Highest event index already processed, so a batched re-render never
  // re-invalidates for events seen on a previous render.
  const lastProcessedRef = useRef(0);
  // Keep the latest rules in a ref so the effect fires on event changes alone.
  const rulesRef = useRef(rules);
  rulesRef.current = rules;

  useEffect(() => {
    // Guard against the ring shrinking (eviction past the cap) with Math.min.
    const start = Math.min(lastProcessedRef.current, events.length);
    const fresh = events.slice(start);
    lastProcessedRef.current = events.length;
    if (fresh.length === 0) {
      return;
    }
    for (const rule of rulesRef.current) {
      const matched = fresh.some(
        (event) => isEvent(event) && rule.types.has(event.type),
      );
      if (!matched) {
        continue;
      }
      for (const key of rule.keys) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
    }
  }, [events, queryClient]);
}
