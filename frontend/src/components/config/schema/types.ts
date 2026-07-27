/**
 * Public prop surface for the SchemaForm renderer.
 *
 * Kept in its own module so {@link SchemaFormRenderer} (``./Renderer``) and the
 * thin ``SchemaForm`` re-export (``../SchemaForm``) share one authoritative
 * definition without either file owning it.
 */

/** Props for the recursive schema renderer (and its ``SchemaForm`` re-export). */
export interface SchemaFormProps {
  /** JSON Schema node to render (root or resolved ``$def`` entry). */
  readonly schema: Record<string, unknown>;
  /**
   * Root schema carrying ``$defs`` for ``$ref`` resolution.
   *
   * When omitted the component falls back to ``schema`` itself — this works
   * for top-level schemas that embed ``$defs`` at their own root.
   */
  readonly rootSchema?: Record<string, unknown>;
  /** Current values for the form node being rendered. */
  readonly values: Record<string, unknown>;
  /**
   * Called with a new values object whenever any field is edited.
   *
   * The new object is an immutable shallow copy with the changed key set.
   * Nested paths are handled by recursive composition — each level rebuilds
   * its own object.
   */
  readonly onChange: (values: Record<string, unknown>) => void;
  /**
   * Server 422 validation errors keyed by dot-joined field path
   * (e.g. ``"paths.0.data_dir"`` → ``"Path does not exist"``).
   */
  readonly errors?: Record<string, string>;
  /** When ``true`` all controls are disabled. */
  readonly readOnly?: boolean;
  /**
   * Keys in the current file that are overridden by ``local.json5``.
   *
   * Top-level property fields whose key is in this set render a warning chip
   * ("écrasée par local.json5 — modification sans effet").  Only checked at
   * path depth 0 (the file root).
   */
  readonly shadowedKeys?: readonly string[];
  /**
   * Whether this field is required by its parent object schema.
   *
   * When ``true`` the label is marked with ``*`` and ``aria-required``.
   * @default false
   */
  readonly required?: boolean;
  /**
   * Dot-joined field path used for error lookup and ``id`` generation.
   * @default ""
   */
  readonly path?: string;
}
