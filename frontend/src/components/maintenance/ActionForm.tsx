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
 * - ``destructive`` actions require the launched dry-run to actually reach
 *   ``outcome === "success"`` — polled from run history, *not* merely the
 *   ``202`` spawn — for the *current* option values before the "Appliquer"
 *   button unlocks; editing any field, a failed/killed dry-run, or a ``428``
 *   from the backend re-locks it.
 *
 * On a ``202`` the dialog stays open and renders {@link RunOutput}: a status
 * badge, the run ``run_uid``, the live {@link RunLogFeed} (streamed over the
 * app-wide WebSocket, scoped to this run) and — once the run reaches a terminal
 * outcome — the durable ``output_tail`` captured by the backend.
 *
 * All data logic — the field buffer, the launch mutation, the destructive gate,
 * and the two run-detail polls — lives in {@link useMaintenanceAction} /
 * {@link useRunOutput}; this component is pure presentation over those machines.
 */

import { type ReactElement } from "react";

import { type MaintenanceAction } from "@/api/maintenance";
import {
  useMaintenanceAction,
  useRunOutput,
} from "@/hooks/useMaintenanceAction";
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

/** Props for {@link ActionForm}. */
export interface ActionFormProps {
  /** The selected maintenance action to render a form for. */
  readonly action: MaintenanceAction;
  /** Called when the user dismisses the form (cancel button). */
  readonly onClose: () => void;
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
  /** Whether the 202 said the runner starts in the visible queue (§6). */
  readonly queued: boolean;
  /** Called when the operator dismisses the output area (the run stays in history). */
  readonly onDismiss: () => void;
}

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
 *   ``output_tail`` (polled from ``GET /api/pipeline/history/{run_uid}`` via
 *   {@link useRunOutput}) is rendered as a {@link LogLine} list — this survives
 *   a page reload, whereas the live feed only covers the current session.
 *
 * Args:
 *   runUid: The launched run's identifier.
 *   dryRun: Whether the run was a dry-run.
 *   queued: Whether the 202 said the runner starts in the visible queue (§6).
 *   onDismiss: Dismiss callback for the output area.
 *
 * Returns:
 *   The run-output element.
 */
function RunOutput({
  runUid,
  dryRun,
  queued,
  onDismiss,
}: RunOutputProps): ReactElement {
  const { waitingInQueue, outputTailLines } = useRunOutput(runUid, queued);

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border bg-muted p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge
            tone={waitingInQueue ? "info" : dryRun ? "info" : "success"}
            dot
          >
            {waitingInQueue
              ? "En file"
              : dryRun
                ? "Dry-run démarré"
                : "Exécution démarrée"}
          </Badge>
          <span className="text-xs text-muted-foreground">
            run_uid : <span className="font-mono">{runUid}</span>
          </span>
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onDismiss}>
          Fermer la sortie
        </Button>
      </div>

      {waitingInQueue && (
        <p className="rounded-md border border-border bg-card px-3 py-2 text-xs text-muted-foreground">
          En file d'attente — un autre run tient le verrou du pipeline ;
          l'action démarrera automatiquement à sa libération.
        </p>
      )}

      {/* Live logs over the app-wide WS stream, scoped to this run. */}
      <RunLogFeed runUid={runUid} />

      {/* Durable fallback once the run has finished (survives a reload). */}
      {outputTailLines != null && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium text-muted-foreground">
            Sortie capturée
          </p>
          <div className="max-h-48 overflow-auto rounded-md border border-border bg-card p-2">
            {outputTailLines.map((textLine, index) => (
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
  const {
    values,
    setValue,
    dryRunEnabled,
    setDryRunEnabled,
    errorDetail,
    runResult,
    clearRunResult,
    pending,
    applyDisabled,
    submit,
  } = useMaintenanceAction(action);

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
        <div className="rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
          {errorDetail}
        </div>
      )}

      {/* Live output area for the spawned run (status + WS feed + fallback). */}
      {runResult != null && (
        <RunOutput
          runUid={runResult.runUid}
          dryRun={runResult.dryRun}
          queued={runResult.queued}
          onDismiss={clearRunResult}
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
