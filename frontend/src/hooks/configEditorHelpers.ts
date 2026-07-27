/**
 * Pure, React-free helpers for the config-editor machine ({@link useConfigEditor}).
 *
 * Kept out of the hook module so the state machine itself stays focused on
 * wiring queries, the dirty buffer and the action handlers. These helpers shape
 * the per-file sub-schema and translate FastAPI 422 payloads into form errors.
 */

import type { Dispatch, SetStateAction } from "react";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { flattenLocToPath } from "@/components/config/SchemaForm";

/** Shape of a FastAPI 422 validation error entry (loc + msg). */
export interface ValidationErrorEntry {
  readonly loc: (string | number)[];
  readonly msg: string;
  readonly type?: string;
}

/** Narrow ``unknown`` to ``Record<string, unknown>``. */
export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

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
export function pickProperties(
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
export function intersectRequired(
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
export function extractValidationErrors(
  err: unknown,
): ValidationErrorEntry[] | null {
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

/**
 * Map an array of 422 validation errors into a field-path → message record,
 * collecting model-level errors (empty ``loc``) as an "unmatched" list, then
 * push the errors into the form and toast (the shared 422 branch of save +
 * validate; SF-14).
 *
 * Args:
 *   validationErrors: The parsed 422 detail entries.
 *   setFormErrors: Setter for the field-anchored error map.
 */
export function applyValidationErrors(
  validationErrors: ValidationErrorEntry[],
  setFormErrors: Dispatch<SetStateAction<Record<string, string>>>,
): void {
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
  // Always toast on 422 failure (SF-14 — simpler contract).
  if (unmatched.length > 0) {
    const first = unmatched[0] ?? "";
    toast.error(
      `Validation échouée — ${String(unmatched.length)} erreur(s) : ${first}`,
    );
  } else {
    toast.error("Validation échouée");
  }
}
