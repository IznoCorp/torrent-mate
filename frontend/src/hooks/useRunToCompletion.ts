/**
 * ``useRunToCompletion`` — the one launch-202 → poll → terminal-outcome machine.
 *
 * A launched pipeline / maintenance / acquisition / decision-resolve run answers
 * ``202 {run_uid}`` immediately, then finishes asynchronously in a detached
 * subprocess. The UI must POLL the run's durable state until it reaches a
 * terminal outcome — never trust the 202 as "done". That poll loop was
 * reimplemented four times with diverging safety guards (poll interval,
 * terminal predicate, error-stop guard); this hook is the single parameterized
 * implementation the four surfaces share.
 *
 * The launch itself stays where it belongs (each surface's own ``useMutation``)
 * so the ratified per-surface UX — toasts, dialogs, French copy — is untouched;
 * this hook owns only the poll-to-terminal machine: the query key, the poll
 * cadence, the terminal predicate that stops the poll, the optional error-stop
 * guard (SF1 — a run row that never materialises must not poll a dead endpoint
 * forever), and optional fire-once ``onTerminal`` / ``onError`` callbacks that
 * let a surface react exactly once when its run settles.
 *
 * - {@link isTerminalRunOutcome} — the single definition of a terminal
 *   pipeline-run outcome (``success`` / ``error`` / ``killed``), previously
 *   pasted in three copies.
 * - {@link useRunToCompletion} — the shared poll machine.
 */

import { useEffect, useRef } from "react";
import {
  useQuery,
  type QueryKey,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query";

/** Pipeline-run outcomes that mean "finished — the run will not change again". */
const TERMINAL_RUN_OUTCOMES: ReadonlySet<string> = new Set([
  "success",
  "error",
  "killed",
]);

/**
 * Is *outcome* a terminal pipeline-run outcome?
 *
 * The ONE definition shared by every 202-run tracker (it used to live as a
 * ``TERMINAL_OUTCOMES`` set in DecisionDetail and an ``isTerminalOutcome``
 * helper in ActionForm — two copies that could drift).
 *
 * Args:
 *   outcome: The run's ``outcome`` field, or null/undefined while still running.
 *
 * Returns:
 *   ``true`` for ``success`` / ``error`` / ``killed`` — the poll should stop.
 */
export function isTerminalRunOutcome(
  outcome: string | null | undefined,
): boolean {
  return outcome != null && TERMINAL_RUN_OUTCOMES.has(outcome);
}

/** Options for {@link useRunToCompletion}. */
export interface UseRunToCompletionOptions<TData> {
  /** The full, stable query key (already including the run identifier). */
  readonly queryKey: QueryKey;
  /** Fetch the current durable run state (e.g. ``getPipelineRunDetail``). */
  readonly queryFn: () => Promise<TData>;
  /** True once *data* represents a finished run — stops the poll. */
  readonly isTerminal: (data: TData | undefined) => boolean;
  /** Poll cadence, in ms, while the run has not reached a terminal state. */
  readonly intervalMs: number;
  /** Whether the poll may fire at all (idle when false). Default: enabled. */
  readonly enabled?: boolean;
  /** react-query retry policy for a failing fetch. Default: library default. */
  readonly retry?: UseQueryOptions<TData>["retry"];
  /**
   * Stop polling once the query settles into an error state (SF1 stuck-poll
   * guard): a persistent 404 for a run row that was never written must not
   * hammer the endpoint every ``intervalMs`` forever.
   */
  readonly stopOnError?: boolean;
  /**
   * Fired exactly once when the run first reaches a terminal state, with the
   * terminal data. Shares a single latch with {@link onError} (whichever
   * settles first wins), so a run never dispatches both.
   */
  readonly onTerminal?: (data: TData) => void;
  /**
   * Fired exactly once when the poll settles into an error state (only when
   * ``stopOnError`` is set). Shares the terminal latch.
   */
  readonly onError?: () => void;
}

/**
 * Poll a launched run to its terminal outcome.
 *
 * Wraps a TanStack ``useQuery`` whose ``refetchInterval`` returns ``false`` once
 * {@link UseRunToCompletionOptions.isTerminal} holds (or, when ``stopOnError``
 * is set, once the query has settled into an error state). Optional fire-once
 * ``onTerminal`` / ``onError`` callbacks share one latch that resets when the
 * run identity (the serialized query key) changes, so a freshly-launched run is
 * tracked afresh.
 *
 * Args:
 *   options: The poll-machine configuration — see
 *     {@link UseRunToCompletionOptions}.
 *
 * Returns:
 *   The underlying {@link UseQueryResult} so callers that read ``data`` /
 *   ``isError`` directly (e.g. the maintenance run-output panel) still can.
 */
export function useRunToCompletion<TData>(
  options: UseRunToCompletionOptions<TData>,
): UseQueryResult<TData> {
  const {
    queryKey,
    queryFn,
    isTerminal,
    intervalMs,
    enabled,
    retry,
    stopOnError,
    onTerminal,
    onError,
  } = options;

  const query = useQuery<TData>({
    queryKey,
    queryFn,
    ...(enabled !== undefined ? { enabled } : {}),
    ...(retry !== undefined ? { retry } : {}),
    refetchInterval: (q) => {
      if (isTerminal(q.state.data)) {
        return false;
      }
      // SF1: once the fetch has persistently errored, stop rather than hammer a
      // dead endpoint at ``intervalMs`` indefinitely.
      if (stopOnError === true && q.state.status === "error") {
        return false;
      }
      return intervalMs;
    },
  });

  // Keep the latest callbacks in refs so the settle effect depends on the run
  // state alone, not on inline-callback identity (which changes every render).
  const onTerminalRef = useRef(onTerminal);
  const onErrorRef = useRef(onError);
  onTerminalRef.current = onTerminal;
  onErrorRef.current = onError;

  // A single fire-once latch shared by both callbacks: a run that ends AND
  // errors must dispatch only one of them (matches the former
  // ``invalidatedOnDone`` latch). Reset during render when the run identity
  // (serialized key) changes, so a new run is tracked from scratch.
  const firedRef = useRef(false);
  const keyStr = JSON.stringify(queryKey);
  const prevKeyRef = useRef(keyStr);
  if (prevKeyRef.current !== keyStr) {
    prevKeyRef.current = keyStr;
    firedRef.current = false;
  }

  const { data, isError } = query;
  useEffect(() => {
    if (firedRef.current) {
      return;
    }
    if (isTerminal(data)) {
      firedRef.current = true;
      if (data !== undefined) {
        onTerminalRef.current?.(data);
      }
      return;
    }
    if (stopOnError === true && isError) {
      firedRef.current = true;
      onErrorRef.current?.();
    }
  }, [data, isError, isTerminal, stopOnError]);

  return query;
}
