/**
 * Shared prop shapes for the SchemaForm field kit.
 *
 * {@link LeafProps} is consumed by the scalar leaf renderers (string / number /
 * boolean / enum); {@link CompositeFieldProps} is consumed by the recursive
 * array / card / dictionary editors. The composite shape was previously an
 * identical inline object type literal duplicated across all three composite
 * editors — collapsing it here is a byte-equivalent dedupe (P11.1).
 */

/** Props shared by all scalar leaf field renderers. */
export interface LeafProps {
  readonly schema: Record<string, unknown>;
  readonly value: unknown;
  readonly onChange: (newValue: unknown) => void;
  readonly fieldPath: string;
  readonly fieldKey: string;
  readonly errors: Record<string, string>;
  readonly readOnly: boolean;
  readonly required: boolean;
}

/**
 * Props shared by the composite (array / card list / dictionary) editors.
 *
 * All three editors recurse into {@link SchemaFormRenderer} for their children,
 * so they receive the full ``rootSchema`` for ``$ref`` resolution alongside the
 * node ``schema``, the current ``values`` and the standard error / readOnly /
 * path context.
 */
export interface CompositeFieldProps {
  readonly schema: Record<string, unknown>;
  readonly values: unknown;
  readonly onChange: (v: unknown) => void;
  readonly errors: Record<string, string>;
  readonly readOnly: boolean;
  readonly path: string;
  readonly rootSchema: Record<string, unknown>;
}
