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

import { useCallback, useMemo, useState, type ReactElement } from "react";
import { toast } from "sonner";

import { ApiError, type PutFileRequest } from "@/api/client";
import { FileList } from "@/components/config/FileList";
import { SchemaForm, flattenLocToPath } from "@/components/config/SchemaForm";
import { SecretsTab } from "@/components/config/SecretsTab";
import { StagingBanner } from "@/components/StagingBanner";
import { Button } from "@/components/ui/button";
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
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
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
  const handleSelectFile = useCallback((name: string) => {
    setSelectedFile(name);
    setFormErrors({});
  }, []);

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
  const handleRestart = useCallback(async () => {
    setShowRestartConfirm(false);
    try {
      await restartWeb.mutateAsync();
      toast.success(
        "Redémarrage programmé — la connexion va se couper puis se rétablir.",
      );
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 404) {
        toast.error(
          "Redémarrage non configuré — PERSONALSCRAPER_PM2_NAME absent.",
        );
        return;
      }
      toast.error("Échec du redémarrage.");
    }
  }, [restartWeb]);

  // ---- Loading state -------------------------------------------------------
  if (schemaQ.isLoading || filesQ.isLoading || statusQ.isLoading) {
    return (
      <section className="mx-auto flex max-w-5xl flex-col gap-4">
        <h1 className="text-xl font-semibold tracking-tight">Configuration</h1>
        <p className="text-sm text-muted-foreground">Chargement…</p>
      </section>
    );
  }

  // ---- Error state ---------------------------------------------------------
  if (schemaQ.isError || filesQ.isError || statusQ.isError) {
    return (
      <section className="mx-auto flex max-w-5xl flex-col gap-4">
        <h1 className="text-xl font-semibold tracking-tight">Configuration</h1>
        <p className="text-sm text-[var(--danger)]" role="alert">
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
          className="rounded-md border border-[var(--warning)] bg-[var(--warning)]/10 px-4 py-3 text-sm"
          role="alert"
        >
          Mode lecture seule — les modifications sont désactivées sur cette
          instance.
        </div>
      )}

      {/* Restart required banner */}
      {restartRequired && (
        <div className="rounded-md border border-[var(--info)] bg-[var(--info)]/10 px-4 py-3 text-sm">
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

      {/* Two-panel layout: FileList (sidebar) + SchemaForm editor */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-[240px_1fr]">
        {/* Left panel: file list */}
        <div className="rounded-md border border-border p-2">
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
            <p className="text-sm text-[var(--danger)]" role="alert">
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

      {/* Secrets section */}
      <div className="rounded-md border border-border p-4">
        <SecretsTab readOnly={readOnly} />
      </div>

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
