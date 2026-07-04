/**
 * Typed fetch-based API client for TorrentMateUI.
 *
 * Built on the OpenAPI-generated ``paths`` types from ``./schema``.
 * Every request sends ``credentials: "include"`` so the JWT session
 * cookie is attached automatically.  401 handling is deferred to the
 * app layer (phase 5) — this module just throws on non-OK responses.
 */

import { QueryClient } from "@tanstack/react-query";
import type { paths } from "./schema";

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

/** Structured error thrown by :func:`apiFetch` on a non-OK HTTP response. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(`${String(status)}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

// ---------------------------------------------------------------------------
// Unwrap the 200 application/json content type from openapi-fetch shape
// ---------------------------------------------------------------------------

/**
 * Extract the ``200 application/json`` response body from an
 * openapi-typescript response map.
 *
 * Example::
 *
 *     type HealthBody = SuccessBody<
 *       paths["/api/health"]["get"]["responses"]
 *     >;
 *     // → { [key: string]: unknown }
 */
type SuccessBody<T> = T extends {
  200: {
    content: {
      "application/json": infer B;
    };
  };
}
  ? B
  : never;

// ---------------------------------------------------------------------------
// Generic fetch wrapper
// ---------------------------------------------------------------------------

/**
 * Make a typed HTTP request to the TorrentMate API.
 *
 * Wraps the standard ``fetch`` API with:
 *
 * - Automatic ``credentials: "include"`` (sends the ``tm_session`` cookie).
 * - Typed request body (validated by the caller via Zod before reaching here).
 * - Typed response: the 200 ``application/json`` payload inferred from
 *   the OpenAPI schema.
 * - An ``ApiError`` thrown on any non-OK status (handle 401 in the app layer).
 *
 * Type parameters:
 *   **Responses**: The ``responses`` union from the generated schema.
 *
 * Args:
 *   url: The API path (e.g. ``"/api/health"``).
 *   init: Optional fetch init overrides.  ``body`` is typed to the
 *       operation's ``requestBody`` content shape (``unknown`` if no body).
 *       Omit ``body`` for GET/HEAD requests.
 */
export async function apiFetch<
  Responses extends Record<number | string, unknown>,
>(
  url: string,
  init?: { method: string; body?: unknown; headers?: Record<string, string> },
): Promise<SuccessBody<Responses>> {
  // Build headers — only set Content-Type when there is a body.
  const requestHeaders: Record<string, string> = {};
  if (init?.body !== undefined) {
    requestHeaders["Content-Type"] = "application/json";
  }
  if (init?.headers !== undefined) {
    Object.assign(requestHeaders, init.headers);
  }

  // Build the fetch init manually to avoid exactOptionalPropertyTypes
  // conflicts (spreading undefined into RequestInit properties is illegal).
  const fetchInit: RequestInit = {
    credentials: "include",
    headers: requestHeaders,
  };
  if (init?.method !== undefined) {
    fetchInit.method = init.method;
  }
  if (init?.body !== undefined) {
    fetchInit.body = JSON.stringify(init.body);
  }

  const response = await fetch(url, fetchInit);

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const json = (await response.json()) as { detail?: string };
      if (typeof json.detail === "string") {
        detail = json.detail;
      }
    } catch {
      // Body is not JSON or is empty — keep statusText.
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content — no body to parse (login / logout).
  if (response.status === 204) {
    return undefined as SuccessBody<Responses>;
  }

  return (await response.json()) as SuccessBody<Responses>;
}

// ---------------------------------------------------------------------------
// Per-endpoint typed helpers
// ---------------------------------------------------------------------------

/** Login: POST /api/auth/login.  204 on success, 401 on bad credentials. */
export async function login(
  body: paths["/api/auth/login"]["post"]["requestBody"]["content"]["application/json"],
): Promise<void> {
  await apiFetch<
    paths["/api/auth/login"]["post"]["responses"]
  >("/api/auth/login", { method: "POST", body });
}

/** Logout: POST /api/auth/logout.  Requires auth. */
export async function logout(): Promise<void> {
  await apiFetch<
    paths["/api/auth/logout"]["post"]["responses"]
  >("/api/auth/logout", { method: "POST" });
}

/** Get current user: GET /api/auth/me.  Requires auth. */
export function getMe(): Promise<
  SuccessBody<paths["/api/auth/me"]["get"]["responses"]>
> {
  return apiFetch<
    paths["/api/auth/me"]["get"]["responses"]
  >("/api/auth/me", { method: "GET" });
}

/** Health: GET /api/health.  Public. */
export function getHealth(): Promise<
  SuccessBody<paths["/api/health"]["get"]["responses"]>
> {
  return apiFetch<
    paths["/api/health"]["get"]["responses"]
  >("/api/health", { method: "GET" });
}

/** Version: GET /api/version.  Requires auth. */
export function getVersion(): Promise<
  SuccessBody<paths["/api/version"]["get"]["responses"]>
> {
  return apiFetch<
    paths["/api/version"]["get"]["responses"]
  >("/api/version", { method: "GET" });
}

// ---------------------------------------------------------------------------
// TanStack Query client
// ---------------------------------------------------------------------------

/**
 * Shared TanStack Query client.
 *
 * - ``staleTime: 5_000`` — data is fresh for 5 seconds; avoids
 *   redundant refetches on focus/remount.
 * - ``retry: 1`` — one automatic retry on failure, then surface the error.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      retry: 1,
    },
  },
});
