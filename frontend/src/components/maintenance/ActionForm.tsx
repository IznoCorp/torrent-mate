/**
 * ActionForm — a generated form for one maintenance action.
 *
 * Builds one control per {@link MaintenanceAction} option (text / number /
 * switch / select), validates required options client-side, and submits through
 * {@link runMaintenanceAction} with a risk-aware dry-run-first UX:
 *
 * - ``ro`` actions run immediately (``dry_run: false``, no toggle).
 * - ``write`` actions expose a dry-run switch (default on) whose state drives the
 *   submit label.
 * - ``destructive`` actions require a successful dry-run for the *current*
 *   option values before the "Appliquer" button unlocks; editing any field (or a
 *   ``428`` from the backend) re-locks it.
 *
 * On a ``202`` the dialog stays open and renders {@link RunOutput}: a status
 * badge, the run ``run_uid``, the live {@link RunLogFeed} (streamed over the
 * app-wide WebSocket, scoped to this run) and — once the run reaches a terminal
 * outcome — the durable ``output_tail`` captured by the backend.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type ReactElement } from "react";

import {
  ApiError,
  getPipelineRunDetail,
  runMaintenanceAction,
  type MaintenanceAction,
} from "@/api/client";
import { LogLine } from "@/components/ds/LogLine";
import { RunLogFeed } from "@/components/pipeline/RunLogFeed";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ActionOption = MaintenanceAction["options"][number];

/** A single form field value — string for text/number/select, boolean for switch. */
type FieldValue = string | boolean;

/** Variables passed to the run mutation. */
interface RunVars {
  readonly dryRun: boolean;
  readonly options: Record<string, unknown>;
  readonly canonical: string;
}

/** Props for {@link ActionForm}. */
export interface ActionFormProps {
  /** The selected maintenance action to render a form for. */
  readonly action: MaintenanceAction;
  /** Called when the user dismisses the form (cancel button). */
  readonly onClose: () => void;
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

/**
 * Is the given outcome terminal (the run has finished and will not change)?
 *
 * Args:
 *   outcome: The run outcome string, or null/undefined while still running.
 *
 * Returns:
 *   ``true`` for ``success``/``error``/``killed`` — the poll should stop.
 */
function isTerminalOutcome(outcome: string | null | undefined): boolean {
  return outcome === "success" || outcome === "error" || outcome === "killed";
}

// ---------------------------------------------------------------------------
// RunOutput
// ---------------------------------------------------------------------------

/** Props for {@link RunOutput}. */
interface RunOutputProps {
  /** The launched run's unique identifier. */
  readonly runUid: string;
  /** Whether the launched run was a dry-run (drives the status badge). */
  readonly dryRun: boolean;
  /** Called when the operator dismisses the output area (the run stays in history). */
  readonly onDismiss: () => void;
}

/** Poll cadence, in ms, for the durable run-detail fallback while running. */
const RUN_DETAIL_POLL_MS = 3_000;

/**
 * RunOutput — the post-submit output area for a spawned maintenance run.
 *
 * Rendered inside the {@link ActionForm} dialog after a successful ``202``:
 *
 * - A status {@link Badge} (``Dry-run démarré`` / ``Exécution démarrée``) plus
 *   the run ``run_uid``.
 * - The live {@link RunLogFeed}, scoped to this ``run_uid`` — the maintenance
 *   runner streams one ``maintenance.run_log`` envelope per output line through
 *   the same app-wide WebSocket relay S2 uses, so no WS-side change is needed.
 * - A durable fallback: once the run reaches a terminal outcome, the captured
 *   ``output_tail`` (polled from ``GET /api/pipeline/history/{run_uid}``) is
 *   rendered as a {@link LogLine} list — this survives a page reload, whereas
 *   the live feed only covers the current session.
 *
 * Args:
 *   runUid: The launched run's identifier.
 *   dryRun: Whether the run was a dry-run.
 *   onDismiss: Dismiss callback for the output area.
 *
 * Returns:
 *   The run-output element.
 */
function RunOutput({
  runUid,
  dryRun,
  onDismiss,
}: RunOutputProps): ReactElement {
  // Poll the durable run detail; stop once the run reaches a terminal outcome.
  const { data } = useQuery({
    queryKey: ["pipeline", "history", runUid] as const,
    queryFn: () => getPipelineRunDetail(runUid),
    refetchInterval: (query) =>
      isTerminalOutcome(query.state.data?.outcome) ? false : RUN_DETAIL_POLL_MS,
  });

  const outputTail = data?.output_tail;
  const showTail =
    isTerminalOutcome(data?.outcome) &&
    typeof outputTail === "string" &&
    outputTail !== "";

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border bg-muted p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone={dryRun ? "info" : "success"} dot>
            {dryRun ? "Dry-run démarré" : "Exécution démarrée"}
          </Badge>
          <span className="text-xs text-muted-foreground">
            run_uid : <span className="font-mono">{runUid}</span>
          </span>
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onDismiss}>
          Fermer la sortie
        </Button>
      </div>

      {/* Live logs over the app-wide WS stream, scoped to this run. */}
      <RunLogFeed runUid={runUid} />

      {/* Durable fallback once the run has finished (survives a reload). */}
      {showTail && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium text-muted-foreground">
            Sortie capturée
          </p>
          <div className="max-h-48 overflow-auto rounded-md border border-border bg-card p-2">
            {outputTail.split("\n").map((textLine, index) => (
              <LogLine key={`tail-${String(index)}`} level="info">
                {textLine}
              </LogLine>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * ActionForm — the generated per-action form rendered inside the catalog dialog.
 *
 * Args:
 *   action: The selected maintenance action.
 *   onClose: Dismiss callback.
 *
 * Returns:
 *   The action-form element.
 */
export function ActionForm({ action, onClose }: ActionFormProps): ReactElement {
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
  // The launched run's uid + mode after a successful 202.
  const [runResult, setRunResult] = useState<{
    runUid: string;
    dryRun: boolean;
  } | null>(null);
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

  const mutation = useMutation<{ run_uid: string }, Error, RunVars>({
    mutationFn: (vars) =>
      runMaintenanceAction(action.id, {
        options: vars.options,
        dry_run: vars.dryRun,
      }),
    onSuccess: (data, vars) => {
      setErrorDetail(null);
      setRunResult({ runUid: data.run_uid, dryRun: vars.dryRun });
      if (action.risk === "destructive" && vars.dryRun) {
        setDryRunOkFor(vars.canonical);
      }
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setErrorDetail(error.detail);
        // A 428 means the recent-dry-run precondition is not satisfied — re-lock.
        if (error.status === 428) setDryRunOkFor(null);
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

  return (
    <div className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{action.title}</DialogTitle>
        <DialogDescription>{action.description}</DialogDescription>
      </DialogHeader>

      {/* Generated fields */}
      {action.options.length > 0 && (
        <div className="flex flex-col gap-4">
          {action.options.map((option) => {
            const fieldId = `field-${option.name}`;
            const value = values[option.name];
            return (
              <div key={option.name} className="flex flex-col gap-1.5">
                {option.type === "bool" ? (
                  <div className="flex items-center justify-between gap-2">
                    <Label htmlFor={fieldId}>
                      {option.label}
                      {option.required && <span aria-hidden="true"> *</span>}
                    </Label>
                    <Switch
                      id={fieldId}
                      aria-label={option.label}
                      checked={value === true}
                      onCheckedChange={(checked) => {
                        setValue(option.name, checked);
                      }}
                    />
                  </div>
                ) : (
                  <>
                    <Label htmlFor={fieldId}>
                      {option.label}
                      {option.required && <span aria-hidden="true"> *</span>}
                    </Label>
                    {option.type === "enum" && option.enum_values != null ? (
                      <Select
                        // Radix rejects an empty value; omit the prop entirely
                        // (uncontrolled placeholder) until a choice is made.
                        {...(typeof value === "string" && value !== ""
                          ? { value }
                          : {})}
                        onValueChange={(next) => {
                          setValue(option.name, next);
                        }}
                      >
                        <SelectTrigger id={fieldId} aria-label={option.label}>
                          <SelectValue placeholder="Choisir…" />
                        </SelectTrigger>
                        <SelectContent>
                          {option.enum_values.map((choice) => (
                            <SelectItem key={choice} value={choice}>
                              {choice}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input
                        id={fieldId}
                        type={option.type === "int" ? "number" : "text"}
                        value={typeof value === "string" ? value : ""}
                        onChange={(event) => {
                          setValue(option.name, event.target.value);
                        }}
                      />
                    )}
                  </>
                )}
                <p className="text-xs text-muted-foreground">{option.help}</p>
              </div>
            );
          })}
        </div>
      )}

      {/* Error block (validation or backend 409/422/428) */}
      {errorDetail != null && (
        <div className="rounded-md border border-[color-mix(in_oklch,var(--danger)_34%,transparent)] bg-[color-mix(in_oklch,var(--danger)_12%,transparent)] p-3 text-sm text-[var(--danger)]">
          {errorDetail}
        </div>
      )}

      {/* Live output area for the spawned run (status + WS feed + fallback). */}
      {runResult != null && (
        <RunOutput
          runUid={runResult.runUid}
          dryRun={runResult.dryRun}
          onDismiss={() => {
            setRunResult(null);
          }}
        />
      )}

      {/* Action buttons — layout depends on risk. */}
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onClose}>
          Fermer
        </Button>

        {action.risk === "ro" && (
          <Button
            type="button"
            disabled={pending}
            onClick={() => {
              submit(false);
            }}
          >
            Exécuter
          </Button>
        )}

        {action.risk === "write" &&
          (action.dry_run === "supported" ? (
            <>
              <div className="mr-auto flex items-center gap-2">
                <Label htmlFor="action-dry-run">Dry-run</Label>
                <Switch
                  id="action-dry-run"
                  aria-label="Dry-run"
                  checked={dryRunEnabled}
                  onCheckedChange={setDryRunEnabled}
                />
              </div>
              <Button
                type="button"
                disabled={pending}
                onClick={() => {
                  submit(dryRunEnabled);
                }}
              >
                {dryRunEnabled ? "Exécuter (dry-run)" : "Exécuter"}
              </Button>
            </>
          ) : (
            <Button
              type="button"
              disabled={pending}
              onClick={() => {
                submit(false);
              }}
            >
              Exécuter
            </Button>
          ))}

        {action.risk === "destructive" && (
          <>
            <Button
              type="button"
              variant="outline"
              disabled={pending}
              onClick={() => {
                submit(true);
              }}
            >
              Dry-run
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={applyDisabled}
              onClick={() => {
                submit(false);
              }}
            >
              Appliquer
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
