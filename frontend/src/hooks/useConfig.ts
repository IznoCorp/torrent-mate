/**
 * Config editor hooks for TorrentMateUI (S4 — config-editor).
 *
 * Thin TanStack Query wrappers over the typed config API client
 * (``@/api/client``):
 *
 * - {@link useConfigSchema} — fetch JSON Schema + ownership + restart impact.
 * - {@link useConfigFiles} — fetch metadata for every config file.
 * - {@link useConfigFile} — fetch parsed contents of a single config file.
 * - {@link useConfigStatus} — fetch deployment status and stale file detection.
 * - {@link useConfigSecrets} — fetch the secret key catalog with ``is_set`` flags.
 * - {@link usePutConfigFile} — validate and atomically write a config file.
 * - {@link usePutConfigSecrets} — write secret values to ``.env``.
 * - {@link useValidateConfig} — validate a candidate config without writing.
 * - {@link useRestartWeb} — schedule a PM2 restart of the web process.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import {
  getConfigSchema,
  getConfigFiles,
  getConfigFile,
  getConfigStatus,
  getConfigSecrets,
  putConfigFile,
  putConfigSecrets,
  validateConfig,
  restartWeb,
  type ConfigSchemaResponse,
  type FilesResponse,
  type FileContent,
  type ConfigStatusResponse,
  type SecretsResponse,
  type PutFileRequest,
  type PutFileResponse,
  type SecretsPutRequest,
  type ValidateRequest,
  type ValidateResponse,
  type RestartResponse,
} from "@/api/config";
import { configKeys } from "@/hooks/useConfigKeys";

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/**
 * Fetch the JSON Schema, key ownership, and restart-impact map.
 *
 * ``staleTime: 60_000`` — the schema is computed once from ``Config`` and
 * cached on the backend, so refreshing more often is wasteful.
 */
export function useConfigSchema(): UseQueryResult<ConfigSchemaResponse> {
  return useQuery({
    queryKey: configKeys.schema,
    queryFn: getConfigSchema,
    staleTime: 60_000,
  });
}

/** Fetch metadata for every config file: ``GET /api/config/files``. */
export function useConfigFiles(): UseQueryResult<FilesResponse> {
  return useQuery({
    queryKey: configKeys.files,
    queryFn: getConfigFiles,
  });
}

/**
 * Fetch the parsed contents of a single config file.
 *
 * The query is disabled when ``name`` is falsy (no file selected).
 *
 * Args:
 *   name: Config file basename (e.g. ``"paths.json5"``).
 */
export function useConfigFile(name: string): UseQueryResult<FileContent> {
  return useQuery({
    queryKey: configKeys.file(name),
    queryFn: () => getConfigFile(name),
    enabled: !!name,
  });
}

/** Fetch deployment status and stale file detection: ``GET /api/config/status``. */
export function useConfigStatus(): UseQueryResult<ConfigStatusResponse> {
  return useQuery({
    queryKey: configKeys.status,
    queryFn: getConfigStatus,
  });
}

/**
 * Fetch the secret key catalog with ``is_set`` flags.
 *
 * ``staleTime: 30_000`` — secret state changes are infrequent, but stale data
 * is misleading for a security-related UI.
 */
export function useConfigSecrets(): UseQueryResult<SecretsResponse> {
  return useQuery({
    queryKey: configKeys.secrets,
    queryFn: getConfigSecrets,
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/**
 * Validate and atomically write a config overlay file.
 *
 * Sends ``PUT /api/config/files/{name}``. On success invalidates the file
 * list, the specific file, and the status query so the UI re-fetches stale
 * data and the restart banner updates.
 *
 * Args:
 *   name: Config file basename (e.g. ``"paths.json5"``).
 *
 * Returns:
 *   The mutation result; call ``mutateAsync(body)`` from the form.
 */
export function usePutConfigFile(
  name: string,
): UseMutationResult<PutFileResponse, Error, PutFileRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: PutFileRequest) => putConfigFile(name, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: configKeys.files });
      void queryClient.invalidateQueries({ queryKey: configKeys.file(name) });
      void queryClient.invalidateQueries({ queryKey: configKeys.status });
    },
  });
}

/**
 * Write secret values to ``.env`` via atomic upsert.
 *
 * Sends ``PUT /api/config/secrets``. On success invalidates the secrets
 * catalog and the status query so the restart banner updates.
 *
 * Returns:
 *   The mutation result; call ``mutateAsync(body)`` from the secrets form.
 */
export function usePutConfigSecrets(): UseMutationResult<
  PutFileResponse,
  Error,
  SecretsPutRequest
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SecretsPutRequest) => putConfigSecrets(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: configKeys.secrets });
      void queryClient.invalidateQueries({ queryKey: configKeys.status });
    },
  });
}

/**
 * Validate a candidate config file without writing to disk.
 *
 * Sends ``POST /api/config/validate``. This is a read-like mutation — no
 * cache invalidation on success because nothing was persisted.
 *
 * Returns:
 *   The mutation result; call ``mutateAsync(body)`` from a validate button.
 */
export function useValidateConfig(): UseMutationResult<
  ValidateResponse,
  Error,
  ValidateRequest
> {
  return useMutation({
    mutationFn: (body: ValidateRequest) => validateConfig(body),
  });
}

/**
 * Schedule a PM2 restart of the web process.
 *
 * Sends ``POST /api/config/restart-web``. No invalidation on success because
 * the backend process is about to restart — the WS connection and any active
 * queries will be re-established naturally.
 *
 * Returns:
 *   The mutation result; call ``mutateAsync()`` from the restart button.
 */
export function useRestartWeb(): UseMutationResult<
  RestartResponse,
  Error,
  void
> {
  return useMutation({
    mutationFn: () => restartWeb(),
  });
}
