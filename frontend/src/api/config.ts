/**
 * Typed fetch wrappers for the config editor API (S4 — config-editor).
 *
 * Every helper binds through {@link apiFetch} so path, method, request body and
 * path params are all checked against the OpenAPI-generated ``schema.d.ts`` —
 * no ``any`` at any call site. Mutating endpoints carry the ``X-Requested-With``
 * header (``XRW_HEADERS`` from client.ts); reads are header-free.
 */

import type { SuccessBody } from "./_schema-helpers";
import type { components, paths } from "./schema";
import { XRW_HEADERS, apiFetch } from "./client";

// ---------------------------------------------------------------------------
// Response / component types
// ---------------------------------------------------------------------------

/** Response type for ``GET /api/config/schema``. */
export type ConfigSchemaResponse = SuccessBody<
  paths["/api/config/schema"]["get"]["responses"]
>;

/** Response type for ``GET /api/config/files``. */
export type FilesResponse = SuccessBody<
  paths["/api/config/files"]["get"]["responses"]
>;

/** Response type for ``GET /api/config/files/{name}``. */
export type FileContent = SuccessBody<
  paths["/api/config/files/{name}"]["get"]["responses"]
>;

/** Response type for ``GET /api/config/status``. */
export type ConfigStatusResponse = SuccessBody<
  paths["/api/config/status"]["get"]["responses"]
>;

/** Response type for ``GET /api/config/secrets``. */
export type SecretsResponse = SuccessBody<
  paths["/api/config/secrets"]["get"]["responses"]
>;

/** A single file entry in the config files listing. */
export type FileInfo = components["schemas"]["FileInfo"];

/** A single secret key entry from the catalog. */
export type SecretEntry = components["schemas"]["SecretEntry"];

/** Request body for ``PUT /api/config/files/{name}``. */
export type PutFileRequest = components["schemas"]["PutFileRequest"];

/** Response body for ``PUT /api/config/files/{name}`` and ``PUT /api/config/secrets``. */
export type PutFileResponse = components["schemas"]["PutFileResponse"];

/** Request body for ``PUT /api/config/secrets``. */
export type SecretsPutRequest = components["schemas"]["SecretsPutRequest"];

/** Request body for ``POST /api/config/validate``. */
export type ValidateRequest = components["schemas"]["ValidateRequest"];

/** Response body for ``POST /api/config/validate``. */
export type ValidateResponse = components["schemas"]["ValidateResponse"];

/** Response body for ``POST /api/config/restart-web``. */
export type RestartResponse = components["schemas"]["RestartResponse"];

// ---------------------------------------------------------------------------
// Read endpoints
// ---------------------------------------------------------------------------

/** Fetch the JSON Schema, key ownership, and restart-impact map: GET /api/config/schema. */
export function getConfigSchema(): Promise<ConfigSchemaResponse> {
  return apiFetch("/api/config/schema", { method: "get" });
}

/** Fetch metadata for every config file: GET /api/config/files. */
export function getConfigFiles(): Promise<FilesResponse> {
  return apiFetch("/api/config/files", { method: "get" });
}

/**
 * Fetch the parsed contents of a single config file.
 *
 * Sends ``GET /api/config/files/{name}`` through the typed {@link apiFetch}
 * (R15 — ``name`` is a schema-typed path param).
 *
 * Args:
 *   name: Config file basename (e.g. ``"paths.json5"``).
 *
 * Returns:
 *   A {@link FileContent} with parsed values, SHA-256, and shadowed keys.
 *
 * Raises:
 *   ApiError: 404 if *name* is not a recognised config file.
 */
export function getConfigFile(name: string): Promise<FileContent> {
  return apiFetch("/api/config/files/{name}", {
    method: "get",
    params: { path: { name } },
  });
}

/** Fetch deployment status and stale file detection: GET /api/config/status. */
export function getConfigStatus(): Promise<ConfigStatusResponse> {
  return apiFetch("/api/config/status", { method: "get" });
}

/** Fetch the secret key catalog with ``is_set`` flags: GET /api/config/secrets. */
export function getConfigSecrets(): Promise<SecretsResponse> {
  return apiFetch("/api/config/secrets", { method: "get" });
}

// ---------------------------------------------------------------------------
// Mutating endpoints
// ---------------------------------------------------------------------------

/**
 * Validate and atomically write a config overlay file.
 *
 * Sends ``PUT /api/config/files/{name}`` with the ``X-Requested-With`` header
 * through the typed {@link apiFetch} (R15 — ``name`` is a schema-typed path
 * param).
 *
 * Args:
 *   name: Config file basename (e.g. ``"paths.json5"``).
 *   body: The request payload with ``values`` and ``base_sha256``.
 *
 * Returns:
 *   A {@link PutFileResponse} with warnings and restart_required flag.
 *
 * Raises:
 *   ApiError: 403 (staging read-only), 404 (not a writable file),
 *     412 (SHA-256 mismatch), or 422 (validation failure).
 */
export function putConfigFile(
  name: string,
  body: PutFileRequest,
): Promise<PutFileResponse> {
  return apiFetch("/api/config/files/{name}", {
    method: "put",
    body,
    headers: XRW_HEADERS,
    params: { path: { name } },
  });
}

/**
 * Write secret values to ``.env`` via atomic upsert.
 *
 * Sends ``PUT /api/config/secrets`` with the ``X-Requested-With`` header.
 *
 * Args:
 *   body: Mapping of ``{KEY: value, ...}`` to upsert into ``.env``.
 *
 * Returns:
 *   A {@link PutFileResponse} with ``restart_required=True``.
 *
 * Raises:
 *   ApiError: 403 (staging read-only) or 422 (unknown key).
 */
export function putConfigSecrets(
  body: SecretsPutRequest,
): Promise<PutFileResponse> {
  return apiFetch("/api/config/secrets", {
    method: "put",
    body,
    headers: XRW_HEADERS,
  });
}

/**
 * Validate a candidate config file without writing to disk.
 *
 * Sends ``POST /api/config/validate`` with the ``X-Requested-With`` header.
 *
 * Args:
 *   body: The file name and candidate values to validate.
 *
 * Returns:
 *   A {@link ValidateResponse} with validation warnings.
 *
 * Raises:
 *   ApiError: 422 if the candidate fails Pydantic validation.
 */
export function validateConfig(
  body: ValidateRequest,
): Promise<ValidateResponse> {
  return apiFetch("/api/config/validate", {
    method: "post",
    body,
    headers: XRW_HEADERS,
  });
}

/**
 * Schedule a PM2 restart of the web process.
 *
 * Sends ``POST /api/config/restart-web`` with the ``X-Requested-With`` header.
 * The restart is handed off to a detached subprocess; the 202 response confirms
 * scheduling only.
 *
 * Returns:
 *   A {@link RestartResponse} with ``status: "scheduled"``.
 *
 * Raises:
 *   ApiError: 403 (staging) or 404 (PM2 name not configured).
 */
export function restartWeb(): Promise<RestartResponse> {
  return apiFetch("/api/config/restart-web", {
    method: "post",
    headers: XRW_HEADERS,
  });
}
