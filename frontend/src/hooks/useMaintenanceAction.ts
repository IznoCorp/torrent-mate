/**
 * useMaintenanceAction — the run-launch machine behind {@link ActionForm}.
 *
 * Owns everything the maintenance action form needs beyond raw presentation:
 * the per-option field buffer, the dry-run switch, the launch mutation, and the
 * destructive gate that only unlocks "Appliquer" once a dry-run of the *current*
 * option values actually reaches ``outcome === "success"`` — polled from run
 * history via the shared launch-202 → poll → terminal machine
 * ({@link useRunToCompletion}), never trusting the 202 spawn.
 *
 * {@link useRunOutput} is the second poll call-site: the durable run-detail poll
 * behind the post-submit output area (badge + captured ``output_tail``). Both
 * polls share the ``pipelineKeys.historyDetail(uid)`` query key, so React Query
 * dedupes them to a single fetch while each observes the same run.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getPipelineRunDetail, pipelineKeys } from "@/api/pipeline";
import {
  runMaintenanceAction,
  type MaintenanceAction,
} from "@/api/maintenance";
import {
  isTerminalRunOutcome,
  useRunToCompletion,
} from "@/hooks/useRunToCompletion";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ActionOption = MaintenanceAction["options"][number];

/** A single form field value — string for text/number/select, boolean for switch. */
export type FieldValue = string | boolean;

/** Variables passed to the run mutation. */
interface RunVars {
  readonly dryRun: boolean;
  readonly options: Record<string, unknown>;
  readonly canonical: string;
}

/** The launched run's uid + mode (+ §6 queue hint) after a successful 202. */
export interface RunResult {
  readonly runUid: string;
  readonly dryRun: boolean;
  readonly queued: boolean;
}

/** Everything {@link ActionForm} needs to render + drive the form. */
export interface MaintenanceActionMachine {
  /** Current per-option field values, keyed by option name. */
  readonly values: Record<string, FieldValue>;
  /** Set one field's value. */
  readonly setValue: (name: string, value: FieldValue) => void;
  /** Dry-run switch state for ``write`` actions (default on for safety). */
  readonly dryRunEnabled: boolean;
  /** Toggle the dry-run switch (bound directly to the Switch). */
  readonly setDryRunEnabled: (value: boolean) => void;
  /** Inline error detail (validation or backend 409/422/428), or ``null``. */
  readonly errorDetail: string | null;
  /** The launched run's result after a successful 202, or ``null``. */
  readonly runResult: RunResult | null;
  /** Dismiss the output area (the run stays in history). */
  readonly clearRunResult: () => void;
  /** ``true`` while the launch mutation is in flight. */
  readonly pending: boolean;
  /**
   * Whether the destructive "Appliquer" button is disabled — unlocks only when a
   * dry-run succeeded for the exact current option values.
   */
  readonly applyDisabled: boolean;
  /** Validate required fields then launch the run in the given mode. */
  readonly submit: (dryRun: boolean) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Compute the initial field value for one option from its declared default.
 *
 * Args:
 *   option: The option descriptor.
 *
 * Returns:
 *   A boolean for ``bool`` options, otherwise the stringified default (empty
 *   string when there is no default).
 */
function initialValue(option: ActionOption): FieldValue {
  if (option.type === "bool") {
    return option.default === true;
  }
  return option.default != null ? String(option.default) : "";
}

/** One persisted ``steps_json`` entry, as served by the run-detail endpoint. */
interface StepEntryLike {
  readonly name?: string | null;
  readonly status?: string | null;
}

/**
 * Return the LAST ``queue`` step of a run, if any.
 *
 * The runner appends one ``queue`` entry when it starts waiting for
 * ``pipeline.lock`` (status ``waiting_pipeline_lock``) and another when the
 * wait ends (status ``done``) — the last one carries the current truth.
 *
 * Args:
 *   steps: The run's persisted step entries (may be undefined while loading).
 *
 * Returns:
 *   The last queue entry, or null when the run never queued.
 */
function lastQueueStep(
  steps: readonly StepEntryLike[] | undefined,
): StepEntryLike | null {
  if (steps === undefined) return null;
  for (let i = steps.length - 1; i >= 0; i -= 1) {
    if (steps[i]?.name === "queue") return steps[i] ?? null;
  }
  return null;
}

/** Poll cadence, in ms, for the durable run-detail fallback while running. */
const RUN_DETAIL_POLL_MS = 3_000;

// ---------------------------------------------------------------------------
// useRunOutput — the post-submit output-area poll (RunOutput presentation)
// ---------------------------------------------------------------------------

/** Derived display state for the {@link ActionForm} post-submit output area. */
export interface RunOutputState {
  /**
   * §6 visible queue — the run is waiting for ``pipeline.lock`` (waiting is a
   * STATE the operator sees, never a refusal).
   */
  readonly waitingInQueue: boolean;
  /**
   * The durable captured ``output_tail`` split into lines, or ``null`` while the
   * run is still running / captured nothing yet.
   */
  readonly outputTailLines: readonly string[] | null;
}

/**
 * Poll a launched maintenance run for its durable output area (RunOutput).
 *
 * Wraps the shared launch-202 → poll → terminal machine; stops once the run
 * reaches a terminal outcome. Derives the sticky « En file » badge state and the
 * captured ``output_tail`` for the durable fallback.
 *
 * Args:
 *   runUid: The launched run's identifier.
 *   queued: Whether the 202 said the runner starts in the visible queue (§6).
 *
 * Returns:
 *   A {@link RunOutputState} the RunOutput presentation renders.
 */
export function useRunOutput(runUid: string, queued: boolean): RunOutputState {
  // Poll the durable run detail; stop once the run reaches a terminal outcome
  // (the shared launch-202 → poll → terminal machine).
  const { data } = useRunToCompletion({
    queryKey: pipelineKeys.historyDetail(runUid),
    queryFn: () => getPipelineRunDetail(runUid),
    isTerminal: (d) => isTerminalRunOutcome(d?.outcome),
    intervalMs: RUN_DETAIL_POLL_MS,
  });

  const outputTail = data?.output_tail;
  const showTail =
    isTerminalRunOutcome(data?.outcome) &&
    typeof outputTail === "string" &&
    outputTail !== "";

  // §6 visible queue — waiting is a STATE the operator sees, never a refusal.
  // The badge is STICKY on the 202 `queued` hint: the runner writes its
  // ``queue`` step ~1 s after spawn, so the first run-detail poll can land
  // before it exists (empty steps) — relying on the waiting step alone would
  // wrongly drop « En file » in that window (observed live 2026-07-15). We
  // therefore hold « En file » until the run POSITIVELY leaves the queue: a
  // ``queue``/``done`` step, or a terminal outcome.
  const queueStep = lastQueueStep(data?.steps);
  const waitingInQueue = isTerminalRunOutcome(data?.outcome)
    ? false
    : queueStep?.status === "done"
      ? false
      : queueStep?.status === "waiting_pipeline_lock"
        ? true
        : queued;

  return {
    waitingInQueue,
    outputTailLines: showTail ? outputTail.split("\n") : null,
  };
}

// ---------------------------------------------------------------------------
// useMaintenanceAction — the form's run-launch machine
// ---------------------------------------------------------------------------

/**
 * Drive one maintenance action's form: field buffer, dry-run switch, launch
 * mutation, and destructive gate.
 *
 * Args:
 *   action: The selected maintenance action.
 *
 * Returns:
 *   A {@link MaintenanceActionMachine} the presentation renders.
 */
export function useMaintenanceAction(
  action: MaintenanceAction,
): MaintenanceActionMachine {
  const queryClient = useQueryClient();
  const [values, setValues] = useState<Record<string, FieldValue>>(() => {
    const init: Record<string, FieldValue> = {};
    for (const option of action.options) {
      init[option.name] = initialValue(option);
    }
    return init;
  });

  // Dry-run switch state for `write` actions (default on for safety).
  const [dryRunEnabled, setDryRunEnabled] = useState(true);
  // Canonical options string for which a dry-run succeeded (destructive gate).
  const [dryRunOkFor, setDryRunOkFor] = useState<string | null>(null);
  // The dry-run being tracked for the destructive gate: its run_uid plus the
  // canonical options captured at launch. Set on the dry-run's 202 (spawn), then
  // polled — the gate only unlocks once this run reaches outcome === "success".
  const [dryRunTracking, setDryRunTracking] = useState<{
    runUid: string;
    canonical: string;
  } | null>(null);
  // The launched run's uid + mode (+ §6 queue hint) after a successful 202.
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  // Inline error detail (validation or backend 409/422/428).
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  /** Set one field's value. */
  function setValue(name: string, value: FieldValue): void {
    setValues((prev) => ({ ...prev, [name]: value }));
  }

  /** Build the typed options payload keyed by option name. */
  function buildOptions(): Record<string, unknown> {
    const options: Record<string, unknown> = {};
    for (const option of action.options) {
      const value = values[option.name];
      if (option.type === "bool") {
        options[option.name] = value === true;
      } else if (typeof value === "string" && value !== "") {
        options[option.name] = option.type === "int" ? Number(value) : value;
      }
    }
    return options;
  }

  /** Return the required options that are still empty / invalid. */
  function missingRequired(): ActionOption[] {
    return action.options.filter((option) => {
      if (!option.required || option.type === "bool") return false;
      const value = values[option.name];
      if (typeof value !== "string" || value === "") return true;
      return option.type === "int" && Number.isNaN(Number(value));
    });
  }

  const canonical = JSON.stringify(buildOptions());

  // Poll the tracked dry-run so the destructive gate reacts to its REAL outcome
  // rather than the 202 spawn. Reuses the same ``pipelineKeys.historyDetail(uid)``
  // queryKey as RunOutput, so React Query dedupes to a single fetch while both
  // observe the same run; the poll stops once the run reaches a terminal outcome.
  const trackedUid = dryRunTracking?.runUid ?? null;
  const { data: trackedDetail } = useRunToCompletion({
    queryKey: pipelineKeys.historyDetail(trackedUid),
    queryFn: () => getPipelineRunDetail(trackedUid ?? ""),
    enabled: trackedUid !== null,
    isTerminal: (d) => isTerminalRunOutcome(d?.outcome),
    intervalMs: RUN_DETAIL_POLL_MS,
  });

  // Drive the destructive gate off the POLLED dry-run outcome (not the 202):
  // unlock only when the tracked dry-run reaches ``success`` AND its captured
  // options still equal the current form values; re-lock when it ends in
  // ``error``/``killed``. Editing a field re-locks via the ``applyDisabled``
  // canonical comparison below; a backend ``428`` re-locks in ``onError``.
  useEffect(() => {
    if (dryRunTracking === null) return;
    const outcome = trackedDetail?.outcome;
    if (outcome === "success") {
      if (dryRunTracking.canonical === canonical) {
        setDryRunOkFor(dryRunTracking.canonical);
      }
    } else if (outcome === "error" || outcome === "killed") {
      setDryRunOkFor(null);
    }
  }, [trackedDetail, dryRunTracking, canonical]);

  const mutation = useMutation<
    { run_uid: string; queued?: boolean },
    Error,
    RunVars
  >({
    mutationFn: (vars) =>
      runMaintenanceAction(action.id, {
        options: vars.options,
        dry_run: vars.dryRun,
      }),
    onSuccess: (data, vars) => {
      setErrorDetail(null);
      setRunResult({
        runUid: data.run_uid,
        dryRun: vars.dryRun,
        queued: data.queued === true,
      });
      // R21 — the 202 reserved a fresh pipeline_run row (kind='maintenance'):
      // refresh every history-table query so the new run appears without a
      // manual re-sort/paginate/reload.
      void queryClient.invalidateQueries({ queryKey: pipelineKeys.history });
      // Destructive gate: record the launched dry-run so the poll above can
      // track its real outcome. Do NOT unlock here — a 202 only means "spawn
      // accepted", not "dry-run succeeded" (finding G). Re-lock until the poll
      // observes ``success``.
      if (action.risk === "destructive" && vars.dryRun) {
        setDryRunTracking({ runUid: data.run_uid, canonical: vars.canonical });
        setDryRunOkFor(null);
      }
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setErrorDetail(error.detail);
        // A 428 means the recent-dry-run precondition is not satisfied — re-lock
        // and forget the tracked dry-run so the poll cannot re-unlock Apply.
        if (error.status === 428) {
          setDryRunOkFor(null);
          setDryRunTracking(null);
        }
      } else {
        setErrorDetail("Erreur inattendue.");
      }
    },
  });

  /** Validate required fields then launch the run in the given mode. */
  function submit(dryRun: boolean): void {
    const missing = missingRequired();
    if (missing.length > 0) {
      const labels = missing.map((option) => option.label).join(", ");
      setErrorDetail(`Champs requis manquants : ${labels}`);
      return;
    }
    const options = buildOptions();
    mutation.mutate({ dryRun, options, canonical: JSON.stringify(options) });
  }

  const pending = mutation.isPending;
  // Destructive "Appliquer" unlocks only when a dry-run succeeded for the
  // exact current option values.
  const applyDisabled =
    pending || dryRunOkFor === null || dryRunOkFor !== canonical;

  return {
    values,
    setValue,
    dryRunEnabled,
    setDryRunEnabled,
    errorDetail,
    runResult,
    clearRunResult: () => {
      setRunResult(null);
    },
    pending,
    applyDisabled,
    submit,
  };
}
