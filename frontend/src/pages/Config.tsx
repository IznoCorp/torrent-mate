/**
 * Config page — visual configuration editor (TorrentMateUI S4 — config-editor).
 *
 * Renders a two-panel layout: {@link FileList} sidebar on the left and a
 * {@link SchemaForm} editor on the right, with restart / staging banners and
 * a {@link SecretsTab} section below the editor.
 *
 * Save flow:
 * - 200 → success toast + dirty cleared for that file.
 * - 412 → conflict dialog with reload button.
 * - 422 → validation errors mapped to form fields via {@link flattenLocToPath}.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactElement,
} from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import {
  ApiError,
  getConfigStatus,
  type ConfigStatusResponse,
  type PutFileRequest,
} from "@/api/client";
import { FileList } from "@/components/config/FileList";
import { SchemaForm, flattenLocToPath } from "@/components/config/SchemaForm";
import { SecretsTab } from "@/components/config/SecretsTab";
import { StagingBanner } from "@/components/StagingBanner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useConfigFile,
  useConfigFiles,
  useConfigSchema,
  useConfigStatus,
  usePutConfigFile,
  useRestartWeb,
  useValidateConfig,
} from "@/hooks/useConfig";
import { useQueryClient } from "@tanstack/react-query";
import { configKeys } from "@/hooks/useConfigKeys";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape of a FastAPI 422 validation error entry (loc + msg). */
interface ValidationErrorEntry {
  readonly loc: (string | number)[];
  readonly msg: string;
  readonly type?: string;
}

// ---------------------------------------------------------------------------
// Restart-poll tuning
// ---------------------------------------------------------------------------

/**
 * Restart-outcome poll cadence. Mutable so tests can shrink the window (real
 * timers, tiny interval) instead of wrestling fake timers; prod uses the
 * defaults (~20 s window: 10 polls × 2 s).
 */
export const restartPollConfig = { attempts: 10, intervalMs: 2000 };

/** Resolve after ``ms`` milliseconds. */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Pick only the properties listed in ``keys`` from a ``properties`` object.
 *
 * Args:
 *   props: The full ``properties`` record from a JSON Schema object.
 *   keys: The subset of property names to keep.
 *
 * Returns:
 *   A new object with only the requested properties.
 */
function pickProperties(
  props: Record<string, unknown>,
  keys: string[],
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const k of keys) {
    if (k in props) out[k] = props[k];
  }
  return out;
}

/**
 * Intersect a ``required`` array with the owned keys of a file.
 *
 * Args:
 *   required: The full ``required`` array from the root schema (or undefined).
 *   ownedKeys: The keys owned by the current file.
 *
 * Returns:
 *   The intersection, or an empty array.
 */
function intersectRequired(
  required: unknown,
  ownedKeys: string[],
): string[] | undefined {
  if (!Array.isArray(required)) return undefined;
  const req = required.filter((v): v is string => typeof v === "string");
  const ownedSet = new Set(ownedKeys);
  const filtered = req.filter((k) => ownedSet.has(k));
  return filtered.length > 0 ? filtered : undefined;
}

/**
 * Try to extract a ``detail`` array of validation error entries from an API
 * error caught during PUT or validate.
 *
 * Args:
 *   err: The error thrown by the mutation.
 *
 * Returns:
 *   An array of validation errors, or ``null`` when the error is not a 422 or
 *   the detail cannot be parsed.
 */
function extractValidationErrors(err: unknown): ValidationErrorEntry[] | null {
  if (!(err instanceof ApiError) || err.status !== 422) return null;
  try {
    const parsed: unknown = JSON.parse(err.detail);
    if (Array.isArray(parsed)) {
      // Each element should have at least a `loc` field.
      return parsed.filter(
        (v): v is ValidationErrorEntry =>
          typeof v === "object" &&
          v !== null &&
          Array.isArray((v as Record<string, unknown>).loc),
      );
    }
    return null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

/**
 * Config — the authenticated config editor route (``/config``).
 *
 * Returns:
 *   The config page element.
 */
export default function Config(): ReactElement {
  // ---- Queries -------------------------------------------------------------
  const schemaQ = useConfigSchema();
  const filesQ = useConfigFiles();
  const statusQ = useConfigStatus();

  // ---- Local state ---------------------------------------------------------
  // The selected file is URL-addressable (?file=<name>) — DOIT-10: a shareable
  // deep-link to a specific config file, and Back returns to the file list.
  // Derived from the URL (single source of truth); no param = no file selected.
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedFile = searchParams.get("file");
  // Dirty values per file: Map<filename, {owned_key: value}>
  const [dirtyValues, setDirtyValues] = useState<
    Map<string, Record<string, unknown>>
  >(new Map());
  // Server validation errors to pass to SchemaForm.
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  // Conflict dialog visibility.
  const [showConflict, setShowConflict] = useState(false);
  // Restart confirmation dialog visibility.
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);
  // Left sidebar tab — Fichiers or Secrets (local UI state, not URL-driven).
  const [leftTab, setLeftTab] = useState<"files" | "secrets">("files");

  const queryClient = useQueryClient();

  // ---- Derived state -------------------------------------------------------
  const dirtyFileNames = new Set(dirtyValues.keys());
  const readOnly = statusQ.data?.read_only === true;
  const restartRequired = statusQ.data?.restart_required === true;
  const restartConfigured = statusQ.data?.restart_configured === true;
  const staleFiles = statusQ.data?.stale_files ?? [];
  const isStaging = statusQ.data?.role === "staging";

  // ---- Selected file query -------------------------------------------------
  const fileQ = useConfigFile(selectedFile ?? "");
  const putFile = usePutConfigFile(selectedFile ?? "");
  const restartWeb = useRestartWeb();
  const validate = useValidateConfig();

  // ---- File selection handler ----------------------------------------------
  // Push the selection into the URL (?file=<name>) so it is shareable and Back
  // returns to the previous file / the list. Per-file dirty values persist in
  // `dirtyValues` (keyed by name), so switching never loses unsaved edits.
  const handleSelectFile = useCallback(
    (name: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("file", name);
          return next;
        },
        { replace: false },
      );
      setFormErrors({});
    },
    [setSearchParams],
  );

  // ---- Auto-select first file on initial load (G2) --------------------------
  // When no file is addressed in the URL, select the first available file so
  // the user never sees the empty "Sélectionnez un fichier" dead start.  Deep-
  // links (?file=...) are NOT overridden — the guard `selectedFile === null`
  // preserves the URL-addressable file selection from D3/DOIT-10.  If the
  // user clears the param (Back), auto-select fires again.
  useEffect(() => {
    if (selectedFile === null && filesQ.data && filesQ.data.files.length > 0) {
      const first = filesQ.data.files[0];
      if (first) {
        setSearchParams(
          (prev) => {
            const next = new URLSearchParams(prev);
            next.set("file", first.name);
            return next;
          },
          { replace: true },
        );
      }
    }
  }, [selectedFile, filesQ.data, setSearchParams]);

  // ---- Get current values for the selected file ----------------------------
  const currentValues = useMemo<Record<string, unknown>>(
    () =>
      dirtyValues.get(selectedFile ?? "") ??
      (fileQ.data?.values as Record<string, unknown> | undefined) ??
      {},
    [dirtyValues, selectedFile, fileQ.data?.values],
  );

  // ---- Dirty check ---------------------------------------------------------
  const isDirty = dirtyValues.has(selectedFile ?? "");

  // ---- Build the sub-schema for the selected file --------------------------
  const rootSchema = schemaQ.data?.json_schema as
    Record<string, unknown> | undefined;
  const fileInfo = filesQ.data?.files.find((f) => f.name === selectedFile);
  const ownedKeys = fileInfo?.owned_keys ?? [];

  let fileSchema: Record<string, unknown> = { type: "object" };
  if (rootSchema && ownedKeys.length > 0) {
    const props = isObject(rootSchema.properties) ? rootSchema.properties : {};
    fileSchema = {
      type: "object",
      properties: pickProperties(props, ownedKeys),
      ...(intersectRequired(rootSchema.required, ownedKeys) !== undefined
        ? { required: intersectRequired(rootSchema.required, ownedKeys) }
        : {}),
    };
  }

  // ---- Save handler --------------------------------------------------------
  const handleSave = useCallback(async () => {
    if (!selectedFile) return;
    const values = dirtyValues.get(selectedFile);
    if (!values) return;

    const baseSha256 = fileQ.data?.sha256 ?? "";
    const body: PutFileRequest = { values, base_sha256: baseSha256 };

    try {
      const result = await putFile.mutateAsync(body);
      // 200 — success.
      // Surface warnings from validate_candidate.
      if (result.warnings.length > 0) {
        toast.warning(result.warnings.join("\n"));
      }
      // Surface restart hint (status invalidation covers the banner).
      if (result.restart_required) {
        toast.warning("Redémarrage requis pour appliquer.");
      }
      toast.success(`Fichier "${selectedFile}" enregistré.`);
      setDirtyValues((prev) => {
        const next = new Map(prev);
        next.delete(selectedFile);
        return next;
      });
      setFormErrors({});
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 412) {
          setShowConflict(true);
          return;
        }
        if (err.status === 422) {
          const validationErrors = extractValidationErrors(err);
          if (validationErrors) {
            const mapped: Record<string, string> = {};
            const unmatched: string[] = [];
            for (const ve of validationErrors) {
              const path = flattenLocToPath(ve.loc);
              if (path === "") {
                // Model-level error (loc: []) — no field to anchor to.
                unmatched.push(ve.msg);
              } else {
                mapped[path] = ve.msg;
              }
            }
            setFormErrors(mapped);
            // Always toast on 422 save failure (SF-14 — simpler contract).
            if (unmatched.length > 0) {
              const first = unmatched[0] ?? "";
              toast.error(
                `Validation échouée — ${String(unmatched.length)} erreur(s) : ${first}`,
              );
            } else {
              toast.error("Validation échouée");
            }
            return;
          }
        }
      }
      toast.error(
        err instanceof ApiError && err.detail
          ? err.detail
          : "Échec de l'enregistrement.",
      );
    }
  }, [selectedFile, dirtyValues, fileQ.data?.sha256, putFile]);

  // ---- Validate handler ----------------------------------------------------
  const handleValidate = useCallback(async () => {
    if (!selectedFile) return;
    const values = dirtyValues.get(selectedFile) ?? currentValues;
    if (Object.keys(values).length === 0) return;

    try {
      const result = await validate.mutateAsync({
        file_name: selectedFile,
        values,
      });
      if (result.warnings.length > 0) {
        toast.warning(result.warnings.join("\n"));
      } else {
        toast.success("Validation réussie — aucune alerte.");
      }
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 422) {
        const validationErrors = extractValidationErrors(err);
        if (validationErrors) {
          const mapped: Record<string, string> = {};
          const unmatched: string[] = [];
          for (const ve of validationErrors) {
            const path = flattenLocToPath(ve.loc);
            if (path === "") {
              unmatched.push(ve.msg);
            } else {
              mapped[path] = ve.msg;
            }
          }
          setFormErrors(mapped);
          if (unmatched.length > 0) {
            const first = unmatched[0] ?? "";
            toast.error(
              `Validation échouée — ${String(unmatched.length)} erreur(s) : ${first}`,
            );
          } else {
            toast.error("Validation échouée");
          }
          return;
        }
      }
      if (err instanceof ApiError && err.status === 409) {
        // R20 — a declared dependency overlay is missing on disk: the
        // composed config cannot be built, so validation is BLOCKED (the
        // candidate itself was never evaluated — distinct from a 422).
        toast.error(`Validation impossible — ${err.detail}`);
        return;
      }
      toast.error(
        err instanceof ApiError && err.detail
          ? err.detail
          : "Échec de la validation.",
      );
    }
  }, [selectedFile, dirtyValues, currentValues, validate]);

  // ---- Reload after conflict -----------------------------------------------
  const handleReloadFile = useCallback(() => {
    setShowConflict(false);
    setDirtyValues((prev) => {
      const next = new Map(prev);
      next.delete(selectedFile ?? "");
      return next;
    });
    setFormErrors({});
    // Invalidate the file query to force a re-fetch with the latest SHA.
    if (selectedFile) {
      void queryClient.invalidateQueries({
        queryKey: configKeys.file(selectedFile),
      });
    }
  }, [selectedFile, queryClient]);

  // ---- Restart handler -----------------------------------------------------
  // After the 202 (restart is scheduled, not confirmed — the endpoint answers
  // before the detached pm2 restart runs), poll /status to detect whether the
  // daemon actually restarted. A real restart re-captures the boot-hash snapshot
  // from the now-current config, so `restart_required` flips to false. If it
  // stays true past the window, the async restart silently failed (pm2 not on
  // PATH, wrong name, daemon down) — surface it instead of a false "scheduled".
  const pollRestartOutcome = useCallback(async () => {
    for (let attempt = 0; attempt < restartPollConfig.attempts; attempt++) {
      await sleep(restartPollConfig.intervalMs);
      let status: ConfigStatusResponse | null = null;
      try {
        status = await getConfigStatus();
      } catch {
        // Connection dropped mid-restart is expected — keep polling.
        continue;
      }
      void queryClient.invalidateQueries({ queryKey: configKeys.status });
      if (!status.restart_required) {
        toast.success("Redémarrage effectué — configuration appliquée.");
        return;
      }
    }
    toast.warning(
      "Le redémarrage ne semble pas avoir eu lieu — vérifiez le daemon (logs pm2).",
    );
  }, [queryClient]);

  const handleRestart = useCallback(async () => {
    setShowRestartConfirm(false);
    try {
      await restartWeb.mutateAsync();
      toast.success(
        "Redémarrage programmé — la connexion va se couper puis se rétablir.",
      );
      void pollRestartOutcome();
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 404) {
        toast.error(
          "Redémarrage non configuré — PERSONALSCRAPER_PM2_NAME absent.",
        );
        return;
      }
      toast.error("Échec du redémarrage.");
    }
  }, [restartWeb, pollRestartOutcome]);

  // ---- Loading state -------------------------------------------------------
  if (schemaQ.isLoading || filesQ.isLoading || statusQ.isLoading) {
    return (
      <section className="mx-auto flex max-w-5xl flex-col gap-4">
        <h1 className="text-xl font-semibold tracking-tight">Configuration</h1>
        <p className="text-sm text-muted-foreground">Chargement…</p>
        <StalledLoadRetry
          onRetry={() => {
            void schemaQ.refetch();
            void filesQ.refetch();
            void statusQ.refetch();
          }}
        />
      </section>
    );
  }

  // ---- Error state ---------------------------------------------------------
  if (schemaQ.isError || filesQ.isError || statusQ.isError) {
    return (
      <section className="mx-auto flex max-w-5xl flex-col gap-4">
        <h1 className="text-xl font-semibold tracking-tight">Configuration</h1>
        <p className="text-sm text-danger" role="alert">
          Impossible de charger la configuration. Vérifiez que le backend est
          accessible.
        </p>
      </section>
    );
  }

  // ---- Render --------------------------------------------------------------
  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Configuration</h1>

      {/* Staging read-only banner */}
      {isStaging && <StagingBanner />}
      {readOnly && (
        <div
          className="rounded-md border border-warning bg-warning/10 px-4 py-3 text-sm"
          role="alert"
        >
          Mode lecture seule — les modifications sont désactivées sur cette
          instance.
        </div>
      )}

      {/* Restart required banner */}
      {restartRequired && (
        <div className="rounded-md border border-info bg-info/10 px-4 py-3 text-sm">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <p className="font-medium">Redémarrage requis</p>
              <p className="text-muted-foreground text-xs mt-0.5">
                Fichiers modifiés : {staleFiles.join(", ")}
              </p>
            </div>
            {!readOnly && restartConfigured && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={restartWeb.isPending}
                onClick={() => {
                  setShowRestartConfirm(true);
                }}
              >
                Redémarrer le daemon
              </Button>
            )}
            {!readOnly && !restartConfigured && (
              <p className="text-xs text-muted-foreground">
                Redémarrage requis — non configuré sur ce daemon
                (PERSONALSCRAPER_PM2_NAME).
              </p>
            )}
          </div>
        </div>
      )}

      {/* Mobile-only file / Secrets selector — the 240px sidebar is hidden
          < md, so a top dropdown keeps both surfaces usable at 375px. */}
      <div className="flex flex-col gap-1.5 md:hidden">
        <Label htmlFor="config-file-mobile-select">
          {leftTab === "secrets" ? "Secrets" : "Fichier"}
        </Label>
        <Select
          {...(selectedFile !== null && leftTab === "files"
            ? { value: selectedFile }
            : {})}
          onValueChange={(value: string) => {
            if (value === "__secrets__") {
              // Clear file selection and switch to Secrets tab.
              setSearchParams(
                (prev) => {
                  const next = new URLSearchParams(prev);
                  next.delete("file");
                  return next;
                },
                { replace: true },
              );
              setLeftTab("secrets");
            } else {
              setLeftTab("files");
              handleSelectFile(value);
            }
          }}
        >
          <SelectTrigger id="config-file-mobile-select" aria-label="Section">
            <SelectValue
              placeholder={
                leftTab === "secrets" ? "Secrets" : "Sélectionner un fichier…"
              }
            />
          </SelectTrigger>
          <SelectContent>
            {(filesQ.data?.files ?? []).map((f) => (
              <SelectItem key={f.name} value={f.name}>
                {f.name}
                {dirtyFileNames.has(f.name) ? " •" : ""}
              </SelectItem>
            ))}
            <SelectItem
              value="__secrets__"
              className="border-t border-border mt-1 pt-1"
            >
              Secrets
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Desktop tab bar — visible only on md+; mobile uses the dropdown above. */}
      <div
        className="hidden md:flex gap-0.5 rounded-lg bg-muted p-1 w-fit"
        role="tablist"
        aria-label="Section"
      >
        <button
          role="tab"
          aria-selected={leftTab === "files"}
          type="button"
          onClick={() => {
            setLeftTab("files");
          }}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            leftTab === "files"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Fichiers
        </button>
        <button
          role="tab"
          aria-selected={leftTab === "secrets"}
          type="button"
          onClick={() => {
            setLeftTab("secrets");
          }}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            leftTab === "secrets"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Secrets
        </button>
      </div>

      {/* Files tab: two-panel layout (FileList sidebar + SchemaForm editor). */}
      {leftTab === "files" && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-[240px_1fr]">
          {/* Left panel: file list (hidden < md — replaced by the mobile Select). */}
          <div className="hidden rounded-md border border-border p-2 md:block">
            <FileList
              dirtyFiles={dirtyFileNames}
              selected={selectedFile}
              onSelect={handleSelectFile}
            />
          </div>

          {/* Right panel: form or placeholder */}
          <div className="rounded-md border border-border p-4">
            {selectedFile === null ? (
              <p className="text-sm text-muted-foreground">
                Sélectionnez un fichier dans la liste pour l&apos;éditer.
              </p>
            ) : fileQ.isLoading ? (
              <p className="text-sm text-muted-foreground">
                Chargement du fichier…
              </p>
            ) : fileQ.isError ? (
              <p className="text-sm text-danger" role="alert">
                Erreur lors du chargement de &quot;{selectedFile}&quot;.
              </p>
            ) : (
              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold">{selectedFile}</h2>

                  {/* Action buttons */}
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={readOnly || validate.isPending}
                      onClick={() => {
                        void handleValidate();
                      }}
                    >
                      Valider
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      disabled={readOnly || !isDirty || putFile.isPending}
                      onClick={() => {
                        void handleSave();
                      }}
                    >
                      {putFile.isPending ? "Enregistrement…" : "Enregistrer"}
                    </Button>
                  </div>
                </div>

                {/* SchemaForm */}
                <SchemaForm
                  schema={fileSchema}
                  rootSchema={rootSchema ?? fileSchema}
                  values={currentValues}
                  onChange={(newValues) => {
                    setDirtyValues((prev) => {
                      const next = new Map(prev);
                      next.set(selectedFile, newValues);
                      return next;
                    });
                  }}
                  errors={formErrors}
                  readOnly={readOnly}
                  shadowedKeys={fileQ.data?.shadowed_keys ?? []}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Secrets tab (sibling of the file list — no more scroll-to-find, G2/E3) */}
      {leftTab === "secrets" && (
        <div className="rounded-md border border-border p-4">
          <SecretsTab readOnly={readOnly} />
        </div>
      )}

      {/* Conflict dialog */}
      <Dialog
        open={showConflict}
        onOpenChange={(open) => {
          if (!open) setShowConflict(false);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Conflit de version</DialogTitle>
            <DialogDescription>
              Le fichier a été modifié par ailleurs depuis son chargement.
              Voulez-vous recharger la version actuelle ? Vos modifications
              locales seront perdues.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setShowConflict(false);
              }}
            >
              Annuler
            </Button>
            <Button type="button" onClick={handleReloadFile}>
              Recharger
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Restart confirmation dialog */}
      <Dialog
        open={showRestartConfirm}
        onOpenChange={(open) => {
          if (!open) setShowRestartConfirm(false);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Redémarrer le daemon ?</DialogTitle>
            <DialogDescription>
              Cette action va redémarrer le processus web via PM2. La connexion
              va se couper puis se rétablir.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setShowRestartConfirm(false);
              }}
            >
              Annuler
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => {
                void handleRestart();
              }}
            >
              Redémarrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Helpers (module-level)
// ---------------------------------------------------------------------------

/** Narrow ``unknown`` to ``Record<string, unknown>``. */
function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Props for {@link StalledLoadRetry}. */
interface StalledLoadRetryProps {
  /** Refetch every stalled query. */
  readonly onRetry: () => void;
}

/**
 * StalledLoadRetry — an exit from an eternal « Chargement… ».
 *
 * On mobile/PWA a flaky network at mount can leave the initial queries
 * pending forever (paused networkMode), stranding the page on the loading
 * text with no recourse (operator report 2026-07-15). After a short grace
 * period this surfaces an explicit retry button that refetches the stalled
 * queries.
 *
 * Args:
 *   props: {@link StalledLoadRetryProps}.
 *
 * Returns:
 *   The retry affordance, or null during the grace period.
 */
function StalledLoadRetry({
  onRetry,
}: StalledLoadRetryProps): ReactElement | null {
  const [stalled, setStalled] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setStalled(true);
    }, 8_000);
    return () => {
      window.clearTimeout(timer);
    };
  }, []);
  if (!stalled) return null;
  return (
    <div className="flex flex-col items-start gap-2">
      <p className="text-sm text-muted-foreground">
        Le chargement prend plus de temps que prévu.
      </p>
      <Button type="button" variant="outline" size="sm" onClick={onRetry}>
        Recharger
      </Button>
    </div>
  );
}
