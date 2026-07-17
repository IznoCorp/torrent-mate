/**
 * SchemaForm display-label helpers — the human-facing naming layer.
 *
 * These pure helpers turn schema keys / titles into the French labels rendered
 * by the field kit. Kept separate from ``./engine`` (schema resolution +
 * validation) so neither module carries the other's concerns.
 */

/**
 * Turn a ``snake_case`` identifier into a human-readable label.
 *
 * Args:
 *   key: A ``snake_case`` key (e.g. ``"staging_dir"``).
 *
 * Returns:
 *   Space-separated words with the first word capitalised
 *   (e.g. ``"Staging dir"``).
 */
export function humanize(key: string): string {
  const words = key.replace(/_/g, " ").trim();
  if (!words) return key;
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * Resolve the display label for a schema node: prefer the schema ``title`` when
 * present, else humanize the field key.
 *
 * Args:
 *   schema: The resolved schema node (may carry a ``title``).
 *   fieldKey: The property key, used as the humanized fallback.
 *
 * Returns:
 *   The human-readable label string.
 */
export function fieldLabel(
  schema: Record<string, unknown>,
  fieldKey: string,
): string {
  const title = schema.title;
  if (typeof title === "string" && title.trim() !== "") return title;
  return humanize(fieldKey);
}

/**
 * Curated French labels for the well-known config domain sections. Anything not
 * listed falls back to a humanized property key so a nested Pydantic model never
 * surfaces its raw class name (e.g. ``"ScraperConfig"``, F6).
 */
export const SECTION_LABELS: Record<string, string> = {
  scraper: "Scraper",
  ingest: "Ingestion",
  sort: "Tri",
  fuzzy_match: "Correspondance floue",
  trailers: "Bandes-annonces",
  indexer: "Indexeur",
  acquire: "Acquisition",
  paths: "Chemins",
  disks: "Disques",
  library: "Bibliothèque",
  categories: "Catégories",
  category_rules: "Règles de catégorie",
  custom_categories: "Catégories personnalisées",
  anime_rule: "Règle anime",
  genre_mapping: "Correspondance des genres",
  staging_dirs: "Dossiers de staging",
};

/**
 * Resolve a section (nested-object) heading. Prefers a curated French label,
 * then the humanized property key — never a schema ``title`` that is a bare
 * PascalCase class name (Pydantic sets a nested model's title to its class
 * name, so ``fieldLabel`` would surface ``"ScraperConfig"``; F6).
 *
 * Args:
 *   fieldKey: The section's property key (e.g. ``"fuzzy_match"``).
 *   schema: The resolved section schema node (may carry a ``title``).
 *
 * Returns:
 *   A human-readable French section heading.
 */
export function sectionLabel(
  fieldKey: string,
  schema: Record<string, unknown>,
): string {
  const mapped = SECTION_LABELS[fieldKey];
  if (mapped != null) return mapped;
  const title = schema.title;
  if (
    typeof title === "string" &&
    title.trim() !== "" &&
    !/^[A-Z][A-Za-z0-9]*$/.test(title.trim())
  ) {
    return title;
  }
  return humanize(fieldKey);
}

/**
 * Heuristic: does a string schema/key describe a filesystem path?
 *
 * Path-like fields render with a monospace class so long absolute paths stay
 * legible. Detection keys off ``format: "path"`` or common path-ish key names
 * (``dir``/``path``/``file``/``root``) — a pure display hint, never a value
 * constraint.
 *
 * Args:
 *   schema: The resolved string schema node.
 *   fieldKey: The property key.
 *
 * Returns:
 *   ``true`` when the field should render monospace.
 */
export function isPathLike(
  schema: Record<string, unknown>,
  fieldKey: string,
): boolean {
  if (schema.format === "path") return true;
  return /(^|_)(dir|path|file|root)($|_|s$)/i.test(fieldKey);
}
