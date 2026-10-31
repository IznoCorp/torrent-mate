// What every handler module builds its routes with.
//
// THE RULE THAT MAKES « SEEDED FROM THE FIXTURE » CHECKABLE: a handler module
// holds no data literal. Its payload traces to an imported seed or to the
// mutable state; its own code matches, filters, pages and shapes. A number here
// is a page size or a status code, declared as a named constant, never a value
// the interface will display.
//
// Without that rule every other arm of `scripts/check-mock-seeds.py` stays
// green over a handler returning a hand-typed object.
import type { MockRequest, MockRoute } from "../router";

/**
 * Declares one route.
 *
 * @param operationId The contract's own operationId — the key a scenario names
 *   the operation by, and the name a guard cross-checks against the contract.
 * @param method The method, upper case.
 * @param template The contract's path template.
 * @param handle What it answers.
 * @returns The route.
 */
export function route(
  operationId: string,
  method: string,
  template: string,
  handle: (request: MockRequest) => unknown,
): MockRoute {
  return { operationId, method, template, handle };
}

/** The methods the contract uses, so a table cannot misspell one. */
export const GET = "GET";
export const POST = "POST";
export const PUT = "PUT";
export const PATCH = "PATCH";
export const DELETE = "DELETE";

/**
 * Reads one field of a request body without asserting the body's whole shape.
 *
 * @param body The parsed body.
 * @param name The field wanted.
 * @returns Its value, or undefined.
 */
export function field(body: unknown, name: string): unknown {
  if (typeof body !== "object" || body === null) return undefined;
  return (body as Record<string, unknown>)[name];
}

/**
 * Reads a request body field as a string.
 *
 * @param body The parsed body.
 * @param name The field wanted.
 * @returns Its value as a string, or an empty string.
 */
export function text(body: unknown, name: string): string {
  const value = field(body, name);
  return typeof value === "string" ? value : "";
}
