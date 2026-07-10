/**
 * Group provider statuses so that auth/download **sub-circuits** render under
 * their parent provider instead of as separate top-level cards.
 *
 * A provider named ``<parent>-bootstrap`` or ``<parent>-download`` is a
 * sub-circuit of ``<parent>`` — e.g. ``tvdb-bootstrap`` is the TVDB v4
 * authentication/token circuit (``api/_contracts.py`` ``TVDB_BOOTSTRAP``),
 * deliberately a separate breaker from the data circuit so auth failures trip
 * independently.  Shown as a flat twin card it looked like a duplicate
 * (operator feedback); grouping it under its parent removes the confusion.
 */

import type { ProviderStatusItem } from "@/api/registry";

/** Suffixes that mark a sub-circuit belonging to a parent provider. */
const SUB_CIRCUIT_SUFFIXES = ["-bootstrap", "-download"] as const;

/** A parent provider together with its sub-circuits. */
export interface ProviderGroup {
  readonly parent: ProviderStatusItem;
  readonly subs: readonly ProviderStatusItem[];
}

/**
 * Return the parent provider name for a sub-circuit, or ``null`` when the name
 * is not a recognised sub-circuit.
 *
 * Args:
 *   name: A provider name (e.g. ``"tvdb-bootstrap"`` or ``"tmdb"``).
 *
 * Returns:
 *   The parent stem (``"tvdb"``) for a sub-circuit, else ``null``.
 */
export function subCircuitParent(name: string): string | null {
  for (const suffix of SUB_CIRCUIT_SUFFIXES) {
    if (name.endsWith(suffix) && name.length > suffix.length) {
      return name.slice(0, -suffix.length);
    }
  }
  return null;
}

/**
 * Human label for a sub-circuit row (the parent name is already on the card).
 *
 * Args:
 *   name: The sub-circuit provider name.
 *
 * Returns:
 *   ``"Authentification"`` / ``"Téléchargement"`` for known suffixes, else the
 *   raw name.
 */
export function subCircuitLabel(name: string): string {
  if (name.endsWith("-bootstrap")) return "Authentification";
  if (name.endsWith("-download")) return "Téléchargement";
  return name;
}

/**
 * Tooltip hint explaining why a sub-circuit exists as a separate breaker.
 *
 * Args:
 *   name: The sub-circuit provider name.
 *
 * Returns:
 *   A French explanatory string for the ``title`` attribute.
 */
export function subCircuitHint(name: string): string {
  if (name.endsWith("-bootstrap")) {
    return "Circuit d'authentification / jeton — se déclenche indépendamment du circuit de données.";
  }
  if (name.endsWith("-download")) {
    return "Circuit de téléchargement (artwork/fichiers) — indépendant du circuit de métadonnées.";
  }
  return name;
}

/**
 * Group providers so sub-circuits render under their parent.
 *
 * A sub-circuit whose parent is absent from the roster is kept as its own
 * top-level group (no data loss). Parent order follows first appearance in the
 * input; sub-circuits preserve input order within a parent.
 *
 * Args:
 *   providers: The flat provider list from ``GET /api/registry/status``.
 *
 * Returns:
 *   An ordered list of {@link ProviderGroup}.
 */
export function groupProviders(
  providers: readonly ProviderStatusItem[],
): ProviderGroup[] {
  const names = new Set(providers.map((p) => p.provider_name));

  interface MutableGroup {
    parent: ProviderStatusItem;
    subs: ProviderStatusItem[];
  }
  const result: MutableGroup[] = [];
  const indexByName = new Map<string, number>();

  // First pass: one group per top-level provider (non-sub, or an orphan sub
  // whose parent is not in the roster).
  for (const p of providers) {
    const parentName = subCircuitParent(p.provider_name);
    const isAttachedSub = parentName != null && names.has(parentName);
    if (!isAttachedSub) {
      indexByName.set(p.provider_name, result.length);
      result.push({ parent: p, subs: [] });
    }
  }

  // Second pass: attach each sub-circuit to its parent group.
  for (const p of providers) {
    const parentName = subCircuitParent(p.provider_name);
    if (parentName == null || !names.has(parentName)) continue;
    const idx = indexByName.get(parentName);
    if (idx == null) continue;
    const group = result[idx];
    if (group != null) group.subs.push(p);
  }

  return result;
}
