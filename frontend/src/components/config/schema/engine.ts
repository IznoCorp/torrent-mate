/**
 * SchemaForm engine — pure JSON Schema inspection, resolution and validation.
 *
 * These helpers carry **no React / JSX**: they are the stateless core the
 * {@link SchemaFormRenderer} and its field kit compose over. Splitting them out
 * keeps the recursive renderer readable and lets tests exercise the schema logic
 * in isolation.
 *
 * The functions fall into five groups:
 * - type guards (``isObject`` / ``isLocArray`` / ``isRefPath`` / ``refName``),
 * - path helpers (``joinPath`` / ``flattenLocToPath``),
 * - client-side validation (``clientValidate``),
 * - ``$ref`` resolution + ``Optional`` unwrapping (``resolveRef`` /
 *   ``unwrapOptional`` / ``effectiveSchema``),
 * - schema classification (``hasProperties`` / ``hasItems`` / ``isScalarSchema`` …)
 *   and error lookup (``fieldError``).
 *
 * The human-facing display labels (``humanize`` / ``fieldLabel`` /
 * ``sectionLabel`` / ``isPathLike``) live in the sibling ``./labels`` module.
 */

// ---------------------------------------------------------------------------
// Type guards
// ---------------------------------------------------------------------------

/**
 * Narrow ``unknown`` to ``Record<string, unknown>``.
 *
 * Args:
 *   value: Any value.
 *
 * Returns:
 *   ``true`` when the value is a non-null, non-array object.
 */
export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Narrow ``unknown`` to ``(string | number)[]`` (Pydantic loc arrays).
 *
 * Args:
 *   value: Any value.
 *
 * Returns:
 *   ``true`` when every element is a string or number.
 */
export function isLocArray(value: unknown): value is (string | number)[] {
  return (
    Array.isArray(value) &&
    value.every((v) => typeof v === "string" || typeof v === "number")
  );
}

/**
 * Check whether a string looks like a JSON Schema ``$ref`` pointer.
 *
 * Args:
 *   value: Any string.
 *
 * Returns:
 *   ``true`` when the string starts with ``"#/$defs/"``.
 */
export function isRefPath(value: string): boolean {
  return value.startsWith("#/$defs/");
}

/**
 * Extract the definition name from a ``$ref`` pointer.
 *
 * Args:
 *   ref: A ``$ref`` string like ``"#/$defs/DbConfig"``.
 *
 * Returns:
 *   The definition name (``"DbConfig"``), or ``null`` when the pointer is
 *   malformed.
 */
export function refName(ref: string): string | null {
  const parts = ref.split("/");
  // "#/$defs/Name" → ["#", "$defs", "Name"]
  return parts.length === 3 && parts[0] === "#" && parts[1] === "$defs"
    ? (parts[2] ?? null)
    : null;
}

// ---------------------------------------------------------------------------
// Path helpers
// ---------------------------------------------------------------------------

/**
 * Join a parent dot-path and a child key, stripping a leading empty segment.
 *
 * Args:
 *   parent: The parent path (may be ``""``).
 *   key: The child segment (string key or numeric index).
 *
 * Returns:
 *   A dot-joined path string like ``"paths.0.data_dir"``.
 */
export function joinPath(
  parent: string | undefined,
  key: string | number,
): string {
  return parent ? `${parent}.${String(key)}` : String(key);
}

/**
 * Flatten a Pydantic ``loc`` array to the dot-path convention used by the
 * ``errors`` prop.
 *
 * Args:
 *   loc: Mixed array of strings and numbers (e.g. ``["paths", 0, "data_dir"]``).
 *
 * Returns:
 *   Dot-joined string (e.g. ``"paths.0.data_dir"``).
 *
 * Raises:
 *   TypeError: When ``loc`` is not a valid ``(string | number)[]``.
 */
export function flattenLocToPath(loc: (string | number)[]): string {
  if (!isLocArray(loc)) {
    throw new TypeError("loc must be (string | number)[]");
  }
  return loc.map(String).join(".");
}

/**
 * Derive a client-side validation error for a leaf value from its schema.
 *
 * Cheap, synchronous checks only — type coherence, ``enum`` membership, and
 * numeric ``minimum``/``maximum``/``exclusiveMinimum``/``exclusiveMaximum``
 * bounds. This is a *hint* surfaced on blur; the server 422 mapping remains the
 * source of truth (a server error for the same field always wins, see
 * {@link fieldError} precedence at the call sites).
 *
 * Args:
 *   schema: The resolved leaf schema node.
 *   value: The current value.
 *
 * Returns:
 *   A French error message, or ``null`` when the value passes the cheap checks.
 */
export function clientValidate(
  schema: Record<string, unknown>,
  value: unknown,
): string | null {
  // Empty/undefined values are left to the server (required-ness lives there).
  if (value === undefined || value === null || value === "") return null;

  const type = typeof schema.type === "string" ? schema.type : undefined;

  // enum membership (only meaningful for primitive values).
  if (
    Array.isArray(schema.enum) &&
    (typeof value === "string" ||
      typeof value === "number" ||
      typeof value === "boolean")
  ) {
    const opts = (schema.enum as unknown[]).map((o) => String(o));
    if (!opts.includes(String(value))) {
      return `Valeur invalide — attendu : ${opts.join(", ")}`;
    }
    return null;
  }

  if (type === "integer" || type === "number") {
    const n = typeof value === "number" ? value : Number(value);
    if (Number.isNaN(n)) return "Doit être un nombre.";
    if (type === "integer" && !Number.isInteger(n)) {
      return "Doit être un entier.";
    }
    if (typeof schema.minimum === "number" && n < schema.minimum) {
      return `Doit être ≥ ${String(schema.minimum)}.`;
    }
    if (typeof schema.maximum === "number" && n > schema.maximum) {
      return `Doit être ≤ ${String(schema.maximum)}.`;
    }
    if (
      typeof schema.exclusiveMinimum === "number" &&
      n <= schema.exclusiveMinimum
    ) {
      return `Doit être > ${String(schema.exclusiveMinimum)}.`;
    }
    if (
      typeof schema.exclusiveMaximum === "number" &&
      n >= schema.exclusiveMaximum
    ) {
      return `Doit être < ${String(schema.exclusiveMaximum)}.`;
    }
  }

  return null;
}

// ---------------------------------------------------------------------------
// $ref resolution
// ---------------------------------------------------------------------------

/**
 * Resolve a ``$ref`` pointer against ``rootSchema.$defs``.
 *
 * Args:
 *   schema: A schema node that may carry a ``$ref`` key.
 *   rootSchema: The root schema whose ``$defs`` section holds the definitions.
 *
 * Returns:
 *   The resolved definition, or the original schema when there is no ``$ref``
 *   or the pointer cannot be resolved (broken ref → fallback path).
 */
export function resolveRef(
  schema: Record<string, unknown>,
  rootSchema: Record<string, unknown>,
): Record<string, unknown> {
  const ref = schema.$ref;
  if (typeof ref !== "string" || !isRefPath(ref)) return schema;

  const name = refName(ref);
  if (name === null) return schema;

  const defs = rootSchema.$defs;
  if (!isObject(defs)) return schema;

  const def = defs[name];
  return isObject(def) ? def : schema;
}

// ---------------------------------------------------------------------------
// Optional (anyOf [X, null]) unwrapping
// ---------------------------------------------------------------------------

/**
 * Detect Pydantic ``Optional[X]`` → ``anyOf: [X, {"type": "null"}]`` and
 * unwrap to just ``X``.
 *
 * Args:
 *   schema: A resolved schema node.
 *
 * Returns:
 *   The inner non-null schema when the pattern matches, otherwise the original
 *   schema.
 */
export function unwrapOptional(
  schema: Record<string, unknown>,
): Record<string, unknown> {
  const anyOf = schema.anyOf;
  if (!Array.isArray(anyOf) || anyOf.length !== 2) return schema;

  const [a, b] = anyOf as [unknown, unknown];

  if (isObject(a) && isObject(b)) {
    if (b.type === "null") return a;
    if (a.type === "null") return b;
  }

  return schema;
}

/**
 * Fully resolve a schema node: ``$ref`` → definition, then unwrap
 * ``Optional``.
 *
 * Args:
 *   schema: The raw (possibly ``$ref``-carrying) schema node.
 *   rootSchema: The schema carrying ``$defs``.
 *
 * Returns:
 *   A fully-resolved, non-optional schema node ready for rendering.
 */
export function effectiveSchema(
  schema: Record<string, unknown>,
  rootSchema: Record<string, unknown>,
): Record<string, unknown> {
  return unwrapOptional(resolveRef(schema, rootSchema));
}

// ---------------------------------------------------------------------------
// Schema inspection helpers
// ---------------------------------------------------------------------------

/** Schema node type as a string constant. */
export type SchemaType = string | undefined;

/** Predicate: does the schema declare an ``enum`` constraint? */
export function hasEnum(schema: Record<string, unknown>): boolean {
  return Array.isArray(schema.enum);
}

/** Predicate: is this an object schema with explicit ``properties``? */
export function hasProperties(schema: Record<string, unknown>): boolean {
  return schema.type === "object" && isObject(schema.properties);
}

/** Predicate: is this an object schema with ``additionalProperties``? */
export function hasAdditionalProperties(
  schema: Record<string, unknown>,
): boolean {
  return (
    schema.type === "object" &&
    isObject(schema.additionalProperties) &&
    !isObject(schema.properties)
  );
}

/** Predicate: is this an array schema with ``items``? */
export function hasItems(schema: Record<string, unknown>): boolean {
  return schema.type === "array" && isObject(schema.items);
}

/**
 * Determine whether array items reference a ``$def`` entry (so they are
 * objects rendered as cards rather than primitive rows).
 */
export function itemsAreObjects(
  items: Record<string, unknown>,
  rootSchema: Record<string, unknown>,
): boolean {
  // Direct $ref to a definition → object.
  if (typeof items.$ref === "string" && isRefPath(items.$ref)) return true;
  // Inline object with properties → object.
  if (items.type === "object" && isObject(items.properties)) return true;
  // $ref after unwrapping anyOf (Optional[Def]) → object.
  const resolved = resolveRef(items, rootSchema);
  if (resolved !== items) {
    return (
      resolved.type === "object" ||
      (typeof resolved.$ref === "string" && isRefPath(resolved.$ref))
    );
  }
  return false;
}

/**
 * Read the ``required`` array from a parent object schema, if present.
 *
 * Returns:
 *   A set of required property names, or ``null`` when no ``required`` is
 *   declared.
 */
export function requiredSet(
  schema: Record<string, unknown>,
): Set<string> | null {
  if (Array.isArray(schema.required)) {
    const req = schema.required as unknown[];
    return new Set(req.filter((v): v is string => typeof v === "string"));
  }
  return null;
}

/**
 * Classify a property schema as a "scalar" leaf (string / number / boolean /
 * enum) versus a composite (object / array / dict / fallback).
 *
 * Scalars are laid out in a responsive 2-column grid (they are short, single-
 * line controls); composites always take the full row so their nested editors
 * have room. Detection resolves ``$ref`` + unwraps ``Optional`` first.
 *
 * Args:
 *   schema: The raw (possibly ``$ref``-carrying) child schema.
 *   rootSchema: The schema carrying ``$defs``.
 *
 * Returns:
 *   ``true`` when the child renders as a single scalar control.
 */
export function isScalarSchema(
  schema: Record<string, unknown>,
  rootSchema: Record<string, unknown>,
): boolean {
  const eff = effectiveSchema(schema, rootSchema);
  if (hasProperties(eff) || hasAdditionalProperties(eff) || hasItems(eff)) {
    return false;
  }
  const type = eff.type;
  return (
    type === "string" ||
    type === "integer" ||
    type === "number" ||
    type === "boolean"
  );
}

// ---------------------------------------------------------------------------
// Error lookup
// ---------------------------------------------------------------------------

/**
 * Get the error message for a given field path, if any.
 *
 * Args:
 *   errors: The error map.
 *   path: Dot-joined field path.
 *
 * Returns:
 *   The error string, or ``null``.
 */
export function fieldError(
  errors: Record<string, string>,
  path: string,
): string | null {
  return errors[path] ?? null;
}

// ---------------------------------------------------------------------------
// Immutable array helpers (shared by the array/card list editors)
// ---------------------------------------------------------------------------

/**
 * Return a shallow copy of ``arr`` with ``index`` set to ``newValue``.
 *
 * Hoisted here because {@link PrimitiveArrayField} and {@link ObjectArrayField}
 * carried a byte-identical ``replaceAt`` closure each; sharing the pure helper
 * keeps the two editors in lock-step without altering their output.
 *
 * Args:
 *   arr: The source array.
 *   index: The index to replace.
 *   newValue: The value to set at ``index``.
 *
 * Returns:
 *   A new array with the single element replaced.
 */
export function replaceAtIndex(
  arr: unknown[],
  index: number,
  newValue: unknown,
): unknown[] {
  const next = [...arr];
  next[index] = newValue;
  return next;
}

/**
 * Return a shallow copy of ``arr`` with the element at ``index`` removed.
 *
 * Shared by the array/card editors (identical ``removeAt`` closures before the
 * P11.1 split).
 *
 * Args:
 *   arr: The source array.
 *   index: The index to drop.
 *
 * Returns:
 *   A new array without the element at ``index``.
 */
export function removeAtIndex(arr: unknown[], index: number): unknown[] {
  return arr.filter((_, i) => i !== index);
}
