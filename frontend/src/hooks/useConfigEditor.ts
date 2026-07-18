/**
 * useConfigEditor — the config-editor state machine (S4 config-editor).
 *
 * Owns everything the {@link Config} page needs beyond raw presentation:
 * loading of the schema / file list / status, the per-file dirty buffer, the
 * save / validate / reload / restart flows, and the derived sub-schema for the
 * selected file. The page shell (``pages/Config.tsx``) and the presentation
 * panels (``components/config/panels/*``) consume this hook's result and render
 * it — no business logic lives in the view layer.
 *
 * Save flow:
 * - 200 → success toast + dirty cleared for that file.
 * - 412 → conflict dialog with reload button.
 * - 422 → validation errors mapped to form fields via {@link flattenLocToPath}.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import {
  getConfigStatus,
  type ConfigStatusResponse,
  type FileInfo,
  type PutFileRequest,
} from "@/api/config";
import {
  applyValidationErrors,
  extractValidationErrors,
  intersectRequired,
  isObject,
  pickProperties,
} from "@/hooks/configEditorHelpers";
import {
  useConfigFile,
  useConfigFiles,
  useConfigSchema,
  useConfigStatus,
  usePutConfigFile,
  useRestartWeb,
  useValidateConfig,
} from "@/hooks/useConfig";
import { configKeys } from "@/hooks/useConfigKeys";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Everything the config page shell + panels need to render the editor. */
export interface ConfigEditorState {
  // ---- Top-level query lifecycle ----
  /** ``true`` while the schema / files / status queries are all still loading. */
  readonly isLoading: boolean;
  /** ``true`` when any of the schema / files / status queries errored. */
  readonly isError: boolean;
  /** Refetch every top-level query (the stalled-load retry affordance). */
  readonly refetchAll: () => void;

  // ---- Status-derived flags ----
  /** The config files listing (empty until loaded). */
  readonly files: FileInfo[];
  /** Read-only instance (staging / role guard) — mutations disabled. */
  readonly readOnly: boolean;
  /** A restart is required for pending changes to take effect. */
  readonly restartRequired: boolean;
  /** The daemon is configured for a web restart (``PERSONALSCRAPER_PM2_NAME``). */
  readonly restartConfigured: boolean;
  /** Files changed since boot (surfaced in the restart banner). */
  readonly staleFiles: string[];
  /** Running on the staging role (shows the staging banner). */
  readonly isStaging: boolean;

  // ---- File selection ----
  /** Currently selected file name (URL-addressable via ``?file=``), or null. */
  readonly selectedFile: string | null;
  /** Select a file, pushing ``?file=<name>`` into the URL. */
  readonly handleSelectFile: (name: string) => void;

  // ---- Section tabs (Fichiers / Secrets) ----
  /** Active section — Fichiers or Secrets (local UI state, not URL-driven). */
  readonly leftTab: "files" | "secrets";
  /** Switch the active section (desktop tab bar — keeps ``?file=`` intact). */
  readonly setLeftTab: (tab: "files" | "secrets") => void;
  /** Switch to Secrets AND durably clear ``?file=`` (mobile selector path). */
  readonly handleSelectSecrets: () => void;
  /** Names of files with unsaved edits (bullet markers + FileList badges). */
  readonly dirtyFileNames: Set<string>;

  // ---- Selected-file editor ----
  /** ``true`` while the selected file's content query is loading. */
  readonly fileLoading: boolean;
  /** ``true`` when the selected file's content query errored. */
  readonly fileError: boolean;
  /** The sub-schema restricted to the selected file's owned keys. */
  readonly fileSchema: Record<string, unknown>;
  /** The full root schema (carries ``$defs`` for ``$ref`` resolution). */
  readonly rootSchema: Record<string, unknown> | undefined;
  /** Current form values (dirty buffer, else the loaded file values). */
  readonly currentValues: Record<string, unknown>;
  /** ``true`` when the selected file has unsaved edits. */
  readonly isDirty: boolean;
  /** Server validation errors keyed by dot-joined field path. */
  readonly formErrors: Record<string, string>;
  /** Keys shadowed by ``local.json5`` for the selected file. */
  readonly shadowedKeys: string[];
  /** Record an edit into the per-file dirty buffer. */
  readonly onFormChange: (newValues: Record<string, unknown>) => void;

  // ---- Actions ----
  /** Validate the selected file's candidate values (no write). */
  readonly handleValidate: () => Promise<void>;
  /** Persist the selected file's dirty values (PUT). */
  readonly handleSave: () => Promise<void>;
  /** ``true`` while a validate request is in flight. */
  readonly validatePending: boolean;
  /** ``true`` while a save (PUT) request is in flight. */
  readonly savePending: boolean;

  // ---- Conflict dialog (412) ----
  /** Conflict dialog visibility. */
  readonly showConflict: boolean;
  /** Dismiss the conflict dialog without reloading. */
  readonly closeConflict: () => void;
  /** Discard local edits and re-fetch the file at the latest SHA. */
  readonly handleReloadFile: () => void;

  // ---- Restart flow ----
  /** ``true`` while the restart POST is in flight. */
  readonly restartPending: boolean;
  /** Restart confirmation dialog visibility. */
  readonly showRestartConfirm: boolean;
  /** Open the restart confirmation dialog. */
  readonly openRestartConfirm: () => void;
  /** Dismiss the restart confirmation dialog. */
  readonly closeRestartConfirm: () => void;
  /** Trigger the web restart and poll for its outcome. */
  readonly handleRestart: () => Promise<void>;
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
// Hook
// ---------------------------------------------------------------------------

/**
 * useConfigEditor — compose the config-editor queries, dirty buffer and action
 * handlers into a single machine consumed by the config page.
 *
 * Returns:
 *   The {@link ConfigEditorState} for the page shell + panels.
 */
export function useConfigEditor(): ConfigEditorState {
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
  // Active section — Fichiers or Secrets (local UI state, not URL-driven).
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
      // Selecting a file always lands on the Files section (the mobile
      // dropdown can pick a file while the Secrets section is showing).
      setLeftTab("files");
    },
    [setSearchParams],
  );

  // ---- Switch to Secrets (mobile selector path) ----------------------------
  // Removes ?file= with replace:true so Back does not resurrect it. The clear
  // is durable: the G2 auto-select below is gated on leftTab === "files".
  const handleSelectSecrets = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("file");
        return next;
      },
      { replace: true },
    );
    setLeftTab("secrets");
  }, [setSearchParams]);

  // ---- Auto-select first file on initial load (G2) --------------------------
  // When no file is addressed in the URL, select the first available file so
  // the user never sees the empty "Sélectionnez un fichier" dead start.  Deep-
  // links (?file=...) are NOT overridden — the guard `leftTab === "files" &&
  // selectedFile === null` preserves the URL-addressable file selection from
  // D3/DOIT-10.  If the user clears the param (Back), auto-select fires again.
  // Gating on `leftTab` keeps the Secrets-path ?file= clear durable (see
  // handleSelectSecrets).
  useEffect(() => {
    if (
      leftTab === "files" &&
      selectedFile === null &&
      filesQ.data &&
      filesQ.data.files.length > 0
    ) {
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
  }, [leftTab, selectedFile, filesQ.data, setSearchParams]);

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
    | Record<string, unknown>
    | undefined;
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

  // ---- Form edit handler ---------------------------------------------------
  const onFormChange = useCallback(
    (newValues: Record<string, unknown>) => {
      if (selectedFile === null) return;
      setDirtyValues((prev) => {
        const next = new Map(prev);
        next.set(selectedFile, newValues);
        return next;
      });
    },
    [selectedFile],
  );

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
            applyValidationErrors(validationErrors, setFormErrors);
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
          applyValidationErrors(validationErrors, setFormErrors);
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

  // ---- Dialog visibility actions -------------------------------------------
  const closeConflict = useCallback(() => {
    setShowConflict(false);
  }, []);
  const openRestartConfirm = useCallback(() => {
    setShowRestartConfirm(true);
  }, []);
  const closeRestartConfirm = useCallback(() => {
    setShowRestartConfirm(false);
  }, []);

  // ---- Stalled-load retry --------------------------------------------------
  const refetchAll = useCallback(() => {
    void schemaQ.refetch();
    void filesQ.refetch();
    void statusQ.refetch();
  }, [schemaQ, filesQ, statusQ]);

  return {
    isLoading: schemaQ.isLoading || filesQ.isLoading || statusQ.isLoading,
    isError: schemaQ.isError || filesQ.isError || statusQ.isError,
    refetchAll,
    files: filesQ.data?.files ?? [],
    readOnly,
    restartRequired,
    restartConfigured,
    staleFiles,
    isStaging,
    selectedFile,
    handleSelectFile,
    leftTab,
    setLeftTab,
    handleSelectSecrets,
    dirtyFileNames,
    fileLoading: fileQ.isLoading,
    fileError: fileQ.isError,
    fileSchema,
    rootSchema,
    currentValues,
    isDirty,
    formErrors,
    shadowedKeys: fileQ.data?.shadowed_keys ?? [],
    onFormChange,
    handleValidate,
    handleSave,
    validatePending: validate.isPending,
    savePending: putFile.isPending,
    showConflict,
    closeConflict,
    handleReloadFile,
    restartPending: restartWeb.isPending,
    showRestartConfirm,
    openRestartConfirm,
    closeRestartConfirm,
    handleRestart,
  };
}
