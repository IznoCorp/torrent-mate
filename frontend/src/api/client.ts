/**
 * Typed fetch-based API client for TorrentMateUI.
 *
 * Built on the OpenAPI-generated ``paths`` types from ``./schema``.
 * Every request sends ``credentials: "include"`` so the JWT session
 * cookie is attached automatically.  401 handling is deferred to the
 * app layer (phase 5) — this module just throws on non-OK responses.
 */

import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import type {
  MethodOf,
  PathParamsOf,
  QueryParamsOf,
  RequestBodyOf,
  ResponseBodyOf,
  SuccessBody,
} from "./_schema-helpers";
import type { paths } from "./schema";

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

/** Structured error thrown by :func:`apiFetch` on a non-OK HTTP response. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  /** True for the staging read-only write guard (403 `read-only`). */
  readonly isReadOnly: boolean;

  constructor(status: number, detail: string) {
    const isReadOnly = status === 403 && detail.toLowerCase().includes("read-only");
    // The staging read-only guard is a *consultation* state, not an error the
    // operator did wrong — surface a clean French notice instead of the raw
    // "403: read-only" so a write click on the read-only staging instance reads
    // as "not available here", never a broken action.
    super(
      isReadOnly
        ? "Instance de consultation (staging) — écriture désactivée."
        : `${String(status)}: ${detail}`,
    );
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.isReadOnly = isReadOnly;
  }
}

// ---------------------------------------------------------------------------
// Error detail normalisation
// ---------------------------------------------------------------------------

/**
 * Extract a human-readable detail string from a JSON error response body.
 *
 * FastAPI 422 responses carry ``detail`` as an **array** of
 * ``{loc, msg, type}`` objects rather than a plain string.  Other
 * endpoints (or non-Pydantic errors) return a string.  This helper
 * normalises both shapes so every :class:`ApiError` carries a string
 * that downstream code can reliably ``JSON.parse`` when needed.
 *
 * Args:
 *   body: The parsed JSON body (``unknown`` — no ``any``).
 *   fallback: Value to return when ``body`` is not an object or has no
 *       ``detail`` key (typically ``response.statusText``).
 *
 * Returns:
 *   A string suitable for ``ApiError.detail``.
 */
function extractDetail(body: unknown, fallback: string): string {
  if (body !== null && typeof body === "object" && "detail" in body) {
    const detail: unknown = (body as Record<string, unknown>).detail;
    if (typeof detail === "string") return detail;
    return JSON.stringify(detail);
  }
  return fallback;
}

// ---------------------------------------------------------------------------
// Generic fetch wrapper
// ---------------------------------------------------------------------------

/**
 * Make a typed HTTP request to the TorrentMate API.
 *
 * The ``path`` and ``method`` are bound to the generated OpenAPI ``paths``
 * (DESIGN §5.3): a mistyped path or a verb the path does not declare is a
 * **compile error**, and the resolved response type is inferred from the
 * operation's 2xx ``application/json`` schema — no manual type parameter and no
 * ``any`` at any call site. Also wraps the standard ``fetch`` with:
 *
 * - Automatic ``credentials: "include"`` (sends the ``tm_session`` cookie).
 * - ``Content-Type: application/json`` set only when a body is present.
 * - An ``ApiError`` thrown on any non-OK status (401 handled in the app layer).
 *
 * Parameterized routes (R15): ``init.params.path`` carries the operation's
 * path parameters (interpolated into the ``{name}`` placeholders of the
 * literal ``paths`` key, URI-encoded) and ``init.params.query`` its query
 * parameters (serialised to a query string, ``undefined`` entries skipped).
 * Both are typed from ``paths[P][M]["parameters"]`` — passing a param the
 * operation does not declare, or omitting a required path param, is a
 * compile error.
 *
 * Type parameters:
 *   **P**: The API path — a key of the generated ``paths``.
 *   **M**: An HTTP verb the path ``P`` actually declares ({@link MethodOf}).
 *
 * Args:
 *   path: The API path (e.g. ``"/api/health"``), checked against ``paths``.
 *   init: The request method plus, for body-carrying operations, a ``body``
 *       typed to that operation's ``requestBody`` JSON shape, optional
 *       ``params`` (path/query, schema-typed), and optional extra
 *       ``headers``.
 */
export async function apiFetch<P extends keyof paths, M extends MethodOf<P>>(
  path: P,
  init: {
    method: M;
    body?: RequestBodyOf<paths[P][M]>;
    headers?: Record<string, string>;
    params?: {
      path?: PathParamsOf<paths[P][M]>;
      query?: QueryParamsOf<paths[P][M]>;
    };
  },
): Promise<ResponseBodyOf<paths[P][M]>> {
  // Build headers — only set Content-Type when there is a body.
  const requestHeaders: Record<string, string> = {};
  if (init.body !== undefined) {
    requestHeaders["Content-Type"] = "application/json";
  }
  if (init.headers !== undefined) {
    Object.assign(requestHeaders, init.headers);
  }

  // Build the fetch init manually to avoid exactOptionalPropertyTypes
  // conflicts (spreading undefined into RequestInit properties is illegal).
  // The schema verb keys are lowercase; `fetch` wants the canonical uppercase.
  const fetchInit: RequestInit = {
    method: init.method.toUpperCase(),
    credentials: "include",
    headers: requestHeaders,
  };
  if (init.body !== undefined) {
    fetchInit.body = JSON.stringify(init.body);
  }

  // Resolve the concrete URL: interpolate {name} path params, append query.
  let url: string = path;
  const pathParams = init.params?.path;
  if (pathParams !== undefined) {
    for (const [key, value] of Object.entries(
      pathParams as Record<string, string | number>,
    )) {
      url = url.replace(`{${key}}`, encodeURIComponent(String(value)));
    }
  }
  const queryParams = init.params?.query;
  if (queryParams !== undefined) {
    const sp = new URLSearchParams();
    for (const [key, value] of Object.entries(
      queryParams as Record<string, string | number | boolean | undefined>,
    )) {
      if (value !== undefined) sp.set(key, String(value));
    }
    const qs = sp.toString();
    if (qs) url = `${url}?${qs}`;
  }

  const response = await fetch(url, fetchInit);

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body: unknown = await response.json();
      detail = extractDetail(body, response.statusText);
    } catch {
      // Body is not JSON or is empty — keep statusText.
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content — no body to parse (login / logout). The cast is forced: the
  // schema types the body, but a 204 carries none.
  if (response.status === 204) {
    return undefined as ResponseBodyOf<paths[P][M]>;
  }

  // `Response.json()` is untyped (`Promise<any>`); assert the schema-derived
  // body — the only cast the generated types force on us.
  return (await response.json()) as ResponseBodyOf<paths[P][M]>;
}

// ---------------------------------------------------------------------------
// Shared mutating-request header
// ---------------------------------------------------------------------------

/**
 * Shared header required by EVERY mutating endpoint (the backend's
 * `require_x_requested_with` guard returns 400 without it). Exported so every
 * per-domain module (pipeline / staging / maintenance / config / acquisition /
 * decisions) reuses the exact same value (coherence study F00).
 */
export const XRW_HEADERS: Record<string, string> = {
  "X-Requested-With": "TorrentMate",
};

// ---------------------------------------------------------------------------
// Auth + system endpoints
// ---------------------------------------------------------------------------

/** Login: POST /api/auth/login.  204 on success, 401 on bad credentials. */
export async function login(
  body: paths["/api/auth/login"]["post"]["requestBody"]["content"]["application/json"],
): Promise<void> {
  await apiFetch("/api/auth/login", { method: "post", body });
}

/** Logout: POST /api/auth/logout.  Requires auth. */
export async function logout(): Promise<void> {
  await apiFetch("/api/auth/logout", { method: "post" });
}

/** Get current user: GET /api/auth/me.  Requires auth. */
export function getMe(): Promise<
  SuccessBody<paths["/api/auth/me"]["get"]["responses"]>
> {
  return apiFetch("/api/auth/me", { method: "get" });
}

/** Health: GET /api/health.  Public. */
export function getHealth(): Promise<
  SuccessBody<paths["/api/health"]["get"]["responses"]>
> {
  return apiFetch("/api/health", { method: "get" });
}

/** Version: GET /api/version.  Requires auth. */
export function getVersion(): Promise<
  SuccessBody<paths["/api/version"]["get"]["responses"]>
> {
  return apiFetch("/api/version", { method: "get" });
}

// ---------------------------------------------------------------------------
// Global 401 policy seam
// ---------------------------------------------------------------------------

/**
 * Handler invoked when the API answers ``401 Unauthorized`` on any query or
 * mutation (except mutations that opt out via {@link SKIP_AUTH_REDIRECT}).
 *
 * Deliberately injectable: sub-phase 5.3 (auth guard) replaces the default
 * hard redirect with a router-aware navigation that preserves the target path
 * (``?redirect=<current>``) via {@link setUnauthorizedHandler}.
 */
export type UnauthorizedHandler = () => void;

/**
 * Mutation ``meta`` flag opting a mutation out of the global 401 → redirect
 * policy.  The login mutation sets it: a 401 there means "bad credentials",
 * which must surface inline on the login form, not trigger a redirect loop.
 */
export const SKIP_AUTH_REDIRECT = "skipAuthRedirect";

// Current handler.  Assigned its real default once ``queryClient`` exists (see
// below) so the default can close over it; swapped at runtime by phase 5.3.
let unauthorizedHandler: UnauthorizedHandler | null = null;

/** True when ``error`` is an :class:`ApiError` carrying HTTP 401. */
function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

/**
 * True when ``query`` is the ``me`` identity query (``['auth', 'me']``).
 *
 * Mirrors ``authKeys.me`` in ``hooks/useAuth.ts`` — kept as a structural check
 * here to avoid a ``client`` ↔ ``useAuth`` import cycle.
 */
function isMeQuery(query: { readonly queryKey: readonly unknown[] }): boolean {
  const key = query.queryKey;
  return key.length === 2 && key[0] === "auth" && key[1] === "me";
}

/** Invoke the currently-registered unauthorized handler, if any. */
function runUnauthorizedHandler(): void {
  unauthorizedHandler?.();
}

/**
 * Register a custom unauthorized handler, replacing the default hard redirect.
 *
 * Sub-phase 5.3 (auth guard) calls this at app boot to swap in a router-aware
 * redirect. Idempotent — the last registered handler wins.
 *
 * Args:
 *   handler: The replacement handler invoked on any unhandled 401.
 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  unauthorizedHandler = handler;
}

// ---------------------------------------------------------------------------
// TanStack Query client
// ---------------------------------------------------------------------------

/**
 * Shared TanStack Query client.
 *
 * - ``staleTime: 5_000`` — data is fresh for 5 seconds; avoids redundant
 *   refetches on focus/remount.
 * - ``retry: 1`` — one automatic retry on failure, then surface the error.
 * - **Global 401 policy**: the query cache and mutation cache both invoke
 *   {@link runUnauthorizedHandler} on an :class:`ApiError` with status 401.
 *   Mutations carrying the {@link SKIP_AUTH_REDIRECT} ``meta`` flag (the login
 *   mutation) are exempt so bad-credential 401s stay on the login form.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      retry: 1,
    },
  },
  queryCache: new QueryCache({
    onError: (error, query) => {
      // The `me` query's own 401 is the canonical "not authenticated" signal —
      // AuthProvider + ProtectedRoute react to its error directly. Routing it
      // through the redirect handler would, once the handler clears `me` and its
      // observer refetches, re-enter on the refetch's 401 and loop forever, so
      // exempt it (pairs with RouterBridge clearing the `me` cache on 401).
      if (isUnauthorized(error) && !isMeQuery(query)) {
        runUnauthorizedHandler();
      }
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _variables, _onMutateResult, mutation) => {
      if (mutation.meta?.[SKIP_AUTH_REDIRECT] === true) {
        return;
      }
      if (isUnauthorized(error)) {
        runUnauthorizedHandler();
      }
    },
  }),
});

// Default handler: drop all cached data and hard-redirect to the login page.
// Assigned here (not at declaration) so it can close over ``queryClient``.
unauthorizedHandler = () => {
  queryClient.clear();
  window.location.assign("/login");
};
