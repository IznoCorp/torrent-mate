// A REFUSAL, SAID IN THE INTERFACE'S OWN WORDS — read from `fr.json` by the
// code the server refused with (X4; gap G-1). The wire carries no sentence the
// interface shows: `title` and `detail` are English, for logs; `code` is the
// closed reason and `params` the values its words name.
//
// A REFUSAL WITHOUT A CODE — an operation whose lot has not landed its codes
// yet, a proxy's 502 — falls back to the words the surface gives for its own
// act, never to the wire's text.
import i18next from "i18next";

import type { Schemas } from "./contract-schemas";

/** One closed refusal reason, in the contract's own names. */
export type RefusalCode = Schemas["RefusalCode"];

/** Where every code's words live in `fr.json`. */
const NAMESPACE = "refusals";

/**
 * The code a failed answer carries, if it carries one.
 *
 * @param body What the server answered — a problem body, or anything else.
 * @returns The code, or undefined.
 */
export function refusalCode(body: unknown): RefusalCode | undefined {
  if (typeof body !== "object" || body === null) return undefined;
  const code = (body as { code?: unknown }).code;
  return typeof code === "string" ? (code as RefusalCode) : undefined;
}

/**
 * The words one code is said with — the key every code owns in `fr.json`.
 *
 * @param code The code.
 * @returns Its translation key.
 */
export function refusalKey(code: RefusalCode): string {
  return `${NAMESPACE}.${code}`;
}

/**
 * Says why a request was refused.
 *
 * @param body What the server answered.
 * @param fallback The surface's own words for a refusal that carries no code
 *     the interface knows.
 * @returns The sentence to show.
 */
export function refusalWords(body: unknown, fallback: string): string {
  const code = refusalCode(body);
  if (code === undefined || !i18next.exists(refusalKey(code))) return i18next.t(fallback);
  const params = (body as { params?: Record<string, string | number> }).params ?? {};
  return i18next.t(refusalKey(code), params);
}
