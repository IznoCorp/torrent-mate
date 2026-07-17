/**
 * OpenAPI type-extraction helpers — the single home for the generic type
 * plumbing that pulls request/response/param shapes out of the
 * openapi-typescript-generated ``schema.d.ts`` (DESIGN §5 T9a).
 *
 * Before this module the same conditional types were copy-pasted across
 * ``client.ts``, ``acquisition.ts``, ``decisions.ts`` and ``registry.ts`` (four
 * divergent copies). They now live here once; every ``api/*`` domain module
 * imports what it needs. These are **type-only** helpers — no runtime code.
 */

import type { paths } from "./schema";

// ---------------------------------------------------------------------------
// Response / request / parameter extraction
// ---------------------------------------------------------------------------

/**
 * Extract the ``application/json`` success response body from an
 * openapi-typescript response map — the ``200`` body when present, else the
 * ``202`` body (launch-and-poll endpoints), else ``never``.
 *
 * This is the most general of the previous four copies: ``registry.ts`` only
 * matched ``200``, but the ``200``-then-``202`` form is a strict superset, so a
 * ``200``-only operation resolves identically.
 *
 * Example::
 *
 *     type HealthBody = SuccessBody<
 *       paths["/api/health"]["get"]["responses"]
 *     >;
 */
export type SuccessBody<T> = T extends {
  200: {
    content: {
      "application/json": infer B;
    };
  };
}
  ? B
  : T extends {
        202: {
          content: {
            "application/json": infer B;
          };
        };
      }
    ? B
    : never;

/**
 * The ``application/json`` request body of an operation (required OR optional),
 * or ``never`` when the operation declares no body.
 *
 * openapi-typescript stamps an optional body as ``requestBody?: {...}`` (e.g. a
 * FastAPI ``Body(default_factory=…)`` param); matching ``requestBody?`` — like
 * {@link QueryParamsOf} does for ``query?`` — covers both required and optional
 * bodies, where matching only ``requestBody:`` would collapse optional bodies
 * to ``never``. This is the general form (``client.ts``'s copy); ``decisions.ts``
 * previously used the narrower ``requestBody:`` form, which resolves the same
 * for its required bodies.
 */
export type RequestBodyOf<Op> = Op extends {
  requestBody?: { content: { "application/json": infer B } };
}
  ? B
  : never;

/**
 * The **required** path parameters of an operation, or ``never`` when the
 * operation declares none (openapi-typescript stamps ``path?: never`` on
 * parameterless operations, which fails the required-property match below).
 */
export type PathParamsOf<Op> = Op extends { parameters: { path: infer P } }
  ? P
  : never;

/**
 * The optional query parameters of an operation, or ``never`` when the
 * operation declares none. Query params are always optional in the generated
 * types (``query?: {...}``), so the match strips the ``undefined`` arm.
 */
export type QueryParamsOf<Op> = Op extends { parameters: { query?: infer Q } }
  ? NonNullable<Q>
  : never;

/** The 2xx ``application/json`` response body inferred from an operation. */
export type ResponseBodyOf<Op> = Op extends { responses: infer R }
  ? SuccessBody<R>
  : never;

// ---------------------------------------------------------------------------
// Path/method binding to the generated OpenAPI `paths` (DESIGN §5.3)
// ---------------------------------------------------------------------------

/** The HTTP verbs openapi-typescript emits as keys on every path item. */
export type HttpMethod =
  | "get"
  | "put"
  | "post"
  | "delete"
  | "options"
  | "head"
  | "patch"
  | "trace";

/**
 * The verbs a path actually **defines** — the operation objects, excluding the
 * ``verb?: never`` slots openapi-typescript stamps for every absent method.
 *
 * A defined verb's value is an operation object; an absent verb's indexed value
 * collapses to ``undefined`` (optional ``never``). Passing a method a path does
 * not declare therefore fails the constraint at compile time.
 */
export type MethodOf<P extends keyof paths> = {
  [M in HttpMethod]: paths[P][M] extends undefined ? never : M;
}[HttpMethod];
