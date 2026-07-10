/**
 * SchemaForm — recursive JSON Schema → shadcn form control renderer.
 *
 * Renders a Pydantic v2 ``model_json_schema()`` node (with ``$defs``/``$ref``) as
 * a controlled form.  Each schema ``type`` maps to a specific shadcn control;
 * nested objects and arrays recurse into child {@link SchemaForm} instances.
 *
 * The component is **stateless** — every edit produces a NEW values object via
 * ``onChange`` so the parent owns the truth.
 */

/* eslint-disable react-refresh/only-export-components */

import { Plus, X } from "lucide-react";
import { useId, useState, type ReactElement, type ChangeEvent } from "react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Props for {@link SchemaForm}. */
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
function isObject(value: unknown): value is Record<string, unknown> {
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
function isLocArray(value: unknown): value is (string | number)[] {
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
function isRefPath(value: string): boolean {
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
function refName(ref: string): string | null {
  const parts = ref.split("/");
  // "#/$defs/Name" → ["#", "$defs", "Name"]
  return parts.length === 3 && parts[0] === "#" && parts[1] === "$defs"
    ? (parts[2] ?? null)
    : null;
}

// ---------------------------------------------------------------------------
// Path & label helpers
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
function joinPath(parent: string | undefined, key: string | number): string {
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
 * Turn a ``snake_case`` identifier into a human-readable label.
 *
 * Args:
 *   key: A ``snake_case`` key (e.g. ``"staging_dir"``).
 *
 * Returns:
 *   Space-separated words with the first word capitalised
 *   (e.g. ``"Staging dir"``).
 */
function humanize(key: string): string {
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
function fieldLabel(schema: Record<string, unknown>, fieldKey: string): string {
  const title = schema.title;
  if (typeof title === "string" && title.trim() !== "") return title;
  return humanize(fieldKey);
}

/**
 * Curated French labels for the well-known config domain sections. Anything not
 * listed falls back to a humanized property key so a nested Pydantic model never
 * surfaces its raw class name (e.g. ``"ScraperConfig"``, F6).
 */
const SECTION_LABELS: Record<string, string> = {
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
function sectionLabel(
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
 * SectionDescription — a section docstring truncated to its first sentence with
 * an "En savoir plus" toggle. Full Pydantic docstrings ("… Attributes: language:
 * …") are a wall of text; the first sentence is the useful summary and the
 * per-field help text covers the rest (F7).
 *
 * Args:
 *   text: The full section description string.
 *
 * Returns:
 *   The collapsible description element.
 */
function SectionDescription({ text }: { text: string }): ReactElement {
  const [expanded, setExpanded] = useState(false);
  const sep = text.indexOf(". ");
  const summary = sep === -1 ? text : `${text.slice(0, sep)}.`;
  const isLong = summary.length < text.length;
  return (
    <div className="flex flex-col items-start gap-0.5">
      <p className="text-xs text-muted-foreground">
        {expanded || !isLong ? text : summary}
      </p>
      {isLong && (
        <button
          type="button"
          onClick={() => {
            setExpanded((v) => !v);
          }}
          className="text-xs font-medium text-primary hover:underline"
        >
          {expanded ? "Réduire" : "En savoir plus"}
        </button>
      )}
    </div>
  );
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
function isPathLike(
  schema: Record<string, unknown>,
  fieldKey: string,
): boolean {
  if (schema.format === "path") return true;
  return /(^|_)(dir|path|file|root)($|_|s$)/i.test(fieldKey);
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
function clientValidate(
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
function resolveRef(
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
function unwrapOptional(
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
function effectiveSchema(
  schema: Record<string, unknown>,
  rootSchema: Record<string, unknown>,
): Record<string, unknown> {
  return unwrapOptional(resolveRef(schema, rootSchema));
}

// ---------------------------------------------------------------------------
// Schema inspection helpers
// ---------------------------------------------------------------------------

/** Schema node type as a string constant. */
type SchemaType = string | undefined;

/** Predicate: does the schema declare an ``enum`` constraint? */
function hasEnum(schema: Record<string, unknown>): boolean {
  return Array.isArray(schema.enum);
}

/** Predicate: is this an object schema with explicit ``properties``? */
function hasProperties(schema: Record<string, unknown>): boolean {
  return schema.type === "object" && isObject(schema.properties);
}

/** Predicate: is this an object schema with ``additionalProperties``? */
function hasAdditionalProperties(schema: Record<string, unknown>): boolean {
  return (
    schema.type === "object" &&
    isObject(schema.additionalProperties) &&
    !isObject(schema.properties)
  );
}

/** Predicate: is this an array schema with ``items``? */
function hasItems(schema: Record<string, unknown>): boolean {
  return schema.type === "array" && isObject(schema.items);
}

/**
 * Determine whether array items reference a ``$def`` entry (so they are
 * objects rendered as cards rather than primitive rows).
 */
function itemsAreObjects(
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
function requiredSet(schema: Record<string, unknown>): Set<string> | null {
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
function isScalarSchema(
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
function fieldError(
  errors: Record<string, string>,
  path: string,
): string | null {
  return errors[path] ?? null;
}

// ---------------------------------------------------------------------------
// Leaf field renderers
// ---------------------------------------------------------------------------

/** Props shared by all leaf field renderers. */
interface LeafProps {
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
 * Render a ``string`` field as a text ``<Input>``.
 *
 * Args:
 *   props: {@link LeafProps}.
 *
 * Returns:
 *   The input element.
 */
function StringField({
  schema,
  value,
  onChange,
  fieldPath,
  fieldKey,
  errors,
  readOnly,
  required,
}: LeafProps): ReactElement {
  const id = useId();
  const serverErr = fieldError(errors, fieldPath);
  const [clientErr, setClientErr] = useState<string | null>(null);
  // Server 422 wins over the cheap client hint (server is the authority).
  const er = serverErr ?? clientErr;
  const description =
    typeof schema.description === "string" ? schema.description : null;
  const mono = isPathLike(schema, fieldKey);

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>
        {fieldLabel(schema, fieldKey)}
        {required && <span aria-hidden="true"> *</span>}
      </Label>
      {description !== null && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      <Input
        id={id}
        type="text"
        aria-required={required}
        aria-invalid={er !== null ? true : undefined}
        disabled={readOnly}
        className={cn(mono && "font-mono")}
        value={typeof value === "string" ? value : ""}
        onChange={(e) => {
          if (clientErr !== null) setClientErr(null);
          onChange(e.target.value);
        }}
        onBlur={(e) => {
          setClientErr(clientValidate(schema, e.target.value));
        }}
      />
      {er !== null && (
        <p className="text-sm text-danger" role="alert">
          {er}
        </p>
      )}
    </div>
  );
}

/**
 * Render an ``integer`` or ``number`` field as ``<Input type="number">``.
 *
 * Coerces ``onChange`` to a number; empty string → ``undefined``.
 *
 * Args:
 *   props: {@link LeafProps}.
 *
 * Returns:
 *   The number input element.
 */
function NumberField({
  schema,
  value,
  onChange,
  fieldPath,
  fieldKey,
  errors,
  readOnly,
  required,
}: LeafProps): ReactElement {
  const id = useId();
  const serverErr = fieldError(errors, fieldPath);
  const [clientErr, setClientErr] = useState<string | null>(null);
  // Server 422 wins over the cheap client hint (server is the authority).
  const er = serverErr ?? clientErr;
  const description =
    typeof schema.description === "string" ? schema.description : null;

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>
        {fieldLabel(schema, fieldKey)}
        {required && <span aria-hidden="true"> *</span>}
      </Label>
      {description !== null && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      <Input
        id={id}
        type="number"
        aria-required={required}
        aria-invalid={er !== null ? true : undefined}
        disabled={readOnly}
        value={
          typeof value === "number" && !Number.isNaN(value) ? String(value) : ""
        }
        onChange={(e) => {
          if (clientErr !== null) setClientErr(null);
          const raw = e.target.value;
          if (raw === "") {
            onChange(undefined);
            return;
          }
          const n = Number(raw);
          if (!Number.isNaN(n)) onChange(n);
        }}
        onBlur={(e) => {
          const raw = e.target.value;
          setClientErr(raw === "" ? null : clientValidate(schema, Number(raw)));
        }}
      />
      {er !== null && (
        <p className="text-sm text-danger" role="alert">
          {er}
        </p>
      )}
    </div>
  );
}

/**
 * Render a ``boolean`` field as a ``<Switch>``.
 *
 * Args:
 *   props: {@link LeafProps}.
 *
 * Returns:
 *   The switch element.
 */
function BooleanField({
  schema,
  value,
  onChange,
  fieldPath,
  fieldKey,
  errors,
  readOnly,
  required,
}: LeafProps): ReactElement {
  const id = useId();
  const er = fieldError(errors, fieldPath);
  const description =
    typeof schema.description === "string" ? schema.description : null;

  return (
    <div className="flex flex-col gap-1.5">
      {description !== null && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      <div className="flex items-center justify-between gap-2">
        <Label htmlFor={id}>
          {fieldLabel(schema, fieldKey)}
          {required && <span aria-hidden="true"> *</span>}
        </Label>
        <Switch
          id={id}
          aria-label={fieldLabel(schema, fieldKey)}
          aria-required={required}
          checked={value === true}
          disabled={readOnly}
          onCheckedChange={(checked) => {
            onChange(checked);
          }}
        />
      </div>
      {er !== null && (
        <p className="text-sm text-danger" role="alert">
          {er}
        </p>
      )}
    </div>
  );
}

/**
 * Render a ``string`` + ``enum`` field as a ``<Select>``.
 *
 * Args:
 *   props: {@link LeafProps}.
 *
 * Returns:
 *   The select element.
 */
function EnumField({
  schema,
  value,
  onChange,
  fieldPath,
  fieldKey,
  errors,
  readOnly,
  required,
}: LeafProps): ReactElement {
  const id = useId();
  const er = fieldError(errors, fieldPath);
  const options: unknown[] = Array.isArray(schema.enum)
    ? (schema.enum as unknown[])
    : [];
  const description =
    typeof schema.description === "string" ? schema.description : null;

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>
        {fieldLabel(schema, fieldKey)}
        {required && <span aria-hidden="true"> *</span>}
      </Label>
      {description !== null && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      <Select
        disabled={readOnly}
        {...(typeof value === "string" && value !== "" ? { value } : {})}
        onValueChange={(next) => {
          onChange(next);
        }}
      >
        <SelectTrigger
          id={id}
          aria-label={fieldLabel(schema, fieldKey)}
          aria-required={required}
          aria-invalid={er !== null ? true : undefined}
        >
          <SelectValue placeholder="Choisir…" />
        </SelectTrigger>
        <SelectContent>
          {options.map((opt) => (
            <SelectItem key={String(opt)} value={String(opt)}>
              {String(opt)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {er !== null && (
        <p className="text-sm text-danger" role="alert">
          {er}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Array renderers
// ---------------------------------------------------------------------------

/**
 * Render an array of primitives as a list of rows, each with a remove button
 * plus an add button at the bottom.
 *
 * Args:
 *   schema: The array schema node (must have ``items``).
 *   values: The current array value (treated as ``unknown[]``).
 *   onChange: Called with a new array.
 *   All other props: Forwarded from parent {@link SchemaForm}.
 *
 * Returns:
 *   The list editor element.
 */
function PrimitiveArrayField({
  schema,
  values,
  onChange,
  errors,
  readOnly,
  path,
  rootSchema,
}: {
  readonly schema: Record<string, unknown>;
  readonly values: unknown;
  readonly onChange: (v: unknown) => void;
  readonly errors: Record<string, string>;
  readonly readOnly: boolean;
  readonly path: string;
  readonly rootSchema: Record<string, unknown>;
}): ReactElement {
  const arr: unknown[] = Array.isArray(values) ? values : [];
  const items = schema.items as Record<string, unknown>;
  const label = fieldLabel(schema, path.split(".").pop() ?? "items");

  function replaceAt(index: number, newValue: unknown): void {
    const next = [...arr];
    next[index] = newValue;
    onChange(next);
  }

  function removeAt(index: number): void {
    onChange(arr.filter((_, i) => i !== index));
  }

  function addItem(): void {
    onChange([...arr, ""]);
  }

  return (
    <fieldset className="flex flex-col gap-2 rounded-md border border-border p-3">
      <legend className="px-1 text-sm font-medium">{label}</legend>

      {arr.map((item, i) => {
        const itemPath = joinPath(path, i);
        return (
          <div key={itemPath} className="flex items-center gap-2">
            <SchemaForm
              schema={items}
              rootSchema={rootSchema}
              // Wrap the primitive value in a record keyed by the index so the
              // internal leaf renderer can read it via fieldKey resolution.
              values={{ [String(i)]: item }}
              onChange={(v) => {
                replaceAt(i, v[String(i)]);
              }}
              errors={errors}
              readOnly={readOnly}
              path={itemPath}
            />
            {!readOnly && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Supprimer l'élément ${String(i)}`}
                className="mt-5 shrink-0"
                onClick={() => {
                  removeAt(i);
                }}
              >
                <X className="size-4" aria-hidden="true" />
              </Button>
            )}
          </div>
        );
      })}

      {!readOnly && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="self-start"
          aria-label="Ajouter un élément"
          onClick={addItem}
        >
          <Plus className="size-4" aria-hidden="true" />
          Ajouter
        </Button>
      )}
    </fieldset>
  );
}

/**
 * Render an array of objects (``$ref`` or inline) as a card list.
 *
 * Each card renders a recursive {@link SchemaForm} for the object, plus
 * per-card remove.  An add button prepends a new empty object.
 *
 * Args:
 *   schema: The array schema node (must have ``items``).
 *   values: The current array value.
 *   onChange: Called with a new array.
 *   All other props: Forwarded from parent {@link SchemaForm}.
 *
 * Returns:
 *   The card-list element.
 */
function ObjectArrayField({
  schema,
  values,
  onChange,
  errors,
  readOnly,
  path,
  rootSchema,
}: {
  readonly schema: Record<string, unknown>;
  readonly values: unknown;
  readonly onChange: (v: unknown) => void;
  readonly errors: Record<string, string>;
  readonly readOnly: boolean;
  readonly path: string;
  readonly rootSchema: Record<string, unknown>;
}): ReactElement {
  const arr: unknown[] = Array.isArray(values) ? values : [];
  const items = schema.items as Record<string, unknown>;
  const resolvedItems = effectiveSchema(items, rootSchema);
  const label = fieldLabel(schema, path.split(".").pop() ?? "items");

  function replaceAt(index: number, newValue: unknown): void {
    const next = [...arr];
    next[index] = newValue;
    onChange(next);
  }

  function removeAt(index: number): void {
    onChange(arr.filter((_, i) => i !== index));
  }

  function addItem(): void {
    onChange([...arr, {}]);
  }

  return (
    <fieldset className="flex flex-col gap-3 rounded-md border border-border p-3">
      <legend className="px-1 text-sm font-medium">{label}</legend>

      {arr.map((item, i) => {
        const itemPath = joinPath(path, i);
        return (
          <Card key={itemPath}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm">
                {label} {String(i + 1)}
              </CardTitle>
              {!readOnly && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label={`Supprimer ${label} ${String(i + 1)}`}
                  onClick={() => {
                    removeAt(i);
                  }}
                >
                  <X className="size-4" aria-hidden="true" />
                </Button>
              )}
            </CardHeader>
            <CardContent>
              <SchemaForm
                schema={resolvedItems}
                rootSchema={rootSchema}
                values={{ [String(i)]: isObject(item) ? item : {} }}
                onChange={(newItem) => {
                  replaceAt(i, newItem[String(i)]);
                }}
                errors={errors}
                readOnly={readOnly}
                path={itemPath}
              />
            </CardContent>
          </Card>
        );
      })}

      {!readOnly && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="self-start"
          aria-label={`Ajouter ${label}`}
          onClick={addItem}
        >
          <Plus className="size-4" aria-hidden="true" />
          Ajouter
        </Button>
      )}
    </fieldset>
  );
}

// ---------------------------------------------------------------------------
// Object with additionalProperties (key/value row editor)
// ---------------------------------------------------------------------------

/**
 * Render an object with ``additionalProperties`` as a key/value row editor.
 *
 * Each row has a text input for the key and a control for the value (recursive
 * when the ``additionalProperties`` schema is an object, otherwise a plain
 * ``Input``).  Add/remove buttons let the user grow or shrink the dict.
 *
 * Args:
 *   schema: The object schema with ``additionalProperties``.
 *   values: The current object value.
 *   onChange: Called with a new object.
 *   All other props: Forwarded from parent {@link SchemaForm}.
 *
 * Returns:
 *   The key/value editor element.
 */
function AdditionalPropertiesField({
  schema,
  values,
  onChange,
  errors,
  readOnly,
  path,
  rootSchema,
}: {
  readonly schema: Record<string, unknown>;
  readonly values: unknown;
  readonly onChange: (v: unknown) => void;
  readonly errors: Record<string, string>;
  readonly readOnly: boolean;
  readonly path: string;
  readonly rootSchema: Record<string, unknown>;
}): ReactElement {
  const obj: Record<string, unknown> = isObject(values) ? values : {};
  const entries = Object.entries(obj);
  const addSchema = schema.additionalProperties as Record<string, unknown>;
  const label = fieldLabel(schema, path.split(".").pop() ?? "entries");

  function setEntry(key: string, newValue: unknown): void {
    onChange({ ...obj, [key]: newValue });
  }

  function removeEntry(key: string): void {
    const next = { ...obj };
    // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
    delete next[key];
    onChange(next);
  }

  function addEntry(): void {
    // Generate a unique key for the new entry.
    let newKey = "new_key";
    let counter = 1;
    while (newKey in obj) {
      newKey = `new_key_${String(counter)}`;
      counter++;
    }
    onChange({ ...obj, [newKey]: "" });
  }

  return (
    <fieldset className="flex flex-col gap-2 rounded-md border border-border p-3">
      <legend className="px-1 text-sm font-medium">{label}</legend>

      {entries.map(([k, v]) => {
        const rowPath = joinPath(path, k);
        return (
          <div key={k} className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <Label className="text-xs text-muted-foreground">{k}</Label>
              {isObject(addSchema) &&
              addSchema.type === "object" &&
              isObject(addSchema.properties) ? (
                <SchemaForm
                  schema={addSchema}
                  rootSchema={rootSchema}
                  values={{ [k]: isObject(v) ? v : {} }}
                  onChange={(newV) => {
                    setEntry(k, newV[k]);
                  }}
                  errors={errors}
                  readOnly={readOnly}
                  path={rowPath}
                />
              ) : (
                <Input
                  type="text"
                  aria-label={`Valeur pour ${k}`}
                  disabled={readOnly}
                  value={typeof v === "string" ? v : JSON.stringify(v)}
                  onChange={(e) => {
                    setEntry(k, e.target.value);
                  }}
                />
              )}
              {(() => {
                const er = fieldError(errors, rowPath);
                return er !== null ? (
                  <p className="text-sm text-danger" role="alert">
                    {er}
                  </p>
                ) : null;
              })()}
            </div>
            {!readOnly && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Supprimer la clé ${k}`}
                className="mt-5 shrink-0"
                onClick={() => {
                  removeEntry(k);
                }}
              >
                <X className="size-4" aria-hidden="true" />
              </Button>
            )}
          </div>
        );
      })}

      {!readOnly && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="self-start"
          aria-label="Ajouter une entrée"
          onClick={addEntry}
        >
          <Plus className="size-4" aria-hidden="true" />
          Ajouter
        </Button>
      )}
    </fieldset>
  );
}

// ---------------------------------------------------------------------------
// JSON textarea fallback
// ---------------------------------------------------------------------------

/**
 * Fallback renderer for unresolvable schemas (unknown ``$ref``, complex
 * unions, free-form dicts).
 *
 * Renders a ``<textarea>`` with ``JSON.parse`` validation on blur:
 * - Invalid JSON → inline error shown, ``onChange`` is NOT called.
 * - Valid JSON → ``onChange`` is called with the parsed value.
 *
 * This is the **only** place in the component tree allowed to hold raw
 * ``unknown`` values — the textarea draft is local state, not pushed upward
 * until it is valid JSON.
 *
 * Args:
 *   value: The current value (rendered as pretty-printed JSON).
 *   onChange: Called with the parsed value on successful blur validation.
 *   fieldPath: Dot-joined field path for error lookup.
 *   errors: Server error map.
 *   readOnly: Whether the textarea is disabled.
 *
 * Returns:
 *   The textarea element.
 */
function JsonFallback({
  value,
  onChange,
  fieldPath,
  errors,
  readOnly,
}: {
  readonly value: unknown;
  readonly onChange: (v: unknown) => void;
  readonly fieldPath: string;
  readonly errors: Record<string, string>;
  readonly readOnly: boolean;
}): ReactElement {
  const id = useId();
  const text =
    value !== undefined && value !== null ? JSON.stringify(value, null, 2) : "";
  const [draft, setDraft] = useState(text);
  const [parseErr, setParseErr] = useState<string | null>(null);
  const er = fieldError(errors, fieldPath);

  function handleBlur(): void {
    if (draft.trim() === "") {
      setParseErr(null);
      onChange(undefined);
      return;
    }
    try {
      const parsed: unknown = JSON.parse(draft);
      setParseErr(null);
      onChange(parsed);
    } catch (e: unknown) {
      setParseErr(e instanceof Error ? e.message : "JSON invalide");
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>JSON</Label>
      <textarea
        id={id}
        className={cn(
          "border-input placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 flex min-h-[120px] w-full rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50 font-mono",
          (er !== null || parseErr !== null) && "border-destructive",
        )}
        aria-invalid={er !== null || parseErr !== null ? true : undefined}
        disabled={readOnly}
        value={draft}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => {
          setDraft(e.target.value);
          // Clear parse error while the user is editing.
          if (parseErr !== null) setParseErr(null);
        }}
        onBlur={handleBlur}
        rows={6}
        spellCheck={false}
      />
      {parseErr !== null && (
        <p className="text-sm text-danger" role="alert">
          {parseErr}
        </p>
      )}
      {er !== null && (
        <p className="text-sm text-danger" role="alert">
          {er}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SchemaForm — main component
// ---------------------------------------------------------------------------

/**
 * SchemaForm — recursive JSON Schema → form control renderer.
 *
 * Renders a JSON Schema node as shadcn form controls.  The component
 * dispatches to the appropriate renderer based on the schema ``type``:
 *
 * - ``string`` → ``<Input type="text">``
 * - ``integer`` / ``number`` → ``<Input type="number">``
 * - ``boolean`` → ``<Switch>``
 * - ``string`` + ``enum`` → ``<Select>``
 * - ``array`` of primitives → list editor with add/remove
 * - ``array`` of ``$ref`` / objects → card list
 * - ``object`` with ``properties`` → collapsible ``<details>`` section
 * - ``object`` with ``additionalProperties`` → key/value row editor
 * - unresolvable → JSON ``<textarea>`` fallback
 *
 * ``anyOf [X, null]`` (Pydantic ``Optional``) is unwrapped to ``X``.
 *
 * Args:
 *   props: {@link SchemaFormProps}.
 *
 * Returns:
 *   The rendered form fragment.
 */
export function SchemaForm({
  schema,
  rootSchema,
  values,
  onChange,
  errors = {},
  readOnly = false,
  required = false,
  path = "",
  shadowedKeys,
}: SchemaFormProps): ReactElement {
  const fullRoot = rootSchema ?? schema;

  // 1. Resolve $ref + unwrap Optional.
  const effective = effectiveSchema(schema, fullRoot);

  const schemaType: SchemaType =
    typeof effective.type === "string" ? effective.type : undefined;

  // Generate a fallback label from the last path segment.
  const fieldKey = path.split(".").pop() ?? "";

  // ------------------------------------------------------------------
  // Fallback: unresolvable
  // ------------------------------------------------------------------
  if (
    typeof schema.$ref === "string" &&
    isRefPath(schema.$ref) &&
    resolveRef(schema, fullRoot) === schema
  ) {
    // $ref that failed to resolve → JSON textarea.
    return (
      <JsonFallback
        value={values}
        onChange={(v) => {
          onChange(v as Record<string, unknown>);
        }}
        fieldPath={path}
        errors={errors}
        readOnly={readOnly}
      />
    );
  }

  // ------------------------------------------------------------------
  // Object with properties
  // ------------------------------------------------------------------
  if (hasProperties(effective)) {
    const props_ = effective.properties as Record<
      string,
      Record<string, unknown>
    >;
    const req = requiredSet(effective);
    const propKeys = Object.keys(props_);

    // Extract the nested value at this path, or fall back to values itself
    // when at the root (empty path).
    const nestedValues: Record<string, unknown> =
      path === "" ? values : isObject(values[fieldKey]) ? values[fieldKey] : {};

    function setProperty(key: string, newValue: unknown): void {
      if (path === "") {
        // Root level — rebuild directly from nestedValues + the changed key.
        onChange({ ...values, [key]: newValue });
      } else {
        // Nested — rebuild the nested object, then bubble up.
        const updatedNested = { ...nestedValues, [key]: newValue };
        onChange({ ...values, [fieldKey]: updatedNested });
      }
    }

    const description =
      typeof effective.description === "string" ? effective.description : null;

    // Render one property child (control + required-marker + shadowed chip).
    function renderChild(key: string): ReactElement {
      const propSchema = props_[key] ?? {};
      const childPath = joinPath(path !== "" ? path : undefined, key);
      const isReq = req?.has(key) === true;

      return (
        <div key={key}>
          <SchemaForm
            schema={propSchema}
            rootSchema={fullRoot}
            values={path === "" ? values : { [key]: nestedValues[key] }}
            onChange={(newChildValues) => {
              // newChildValues is { [key]: newValue } — extract and propagate.
              const newVal = newChildValues[key];
              setProperty(key, newVal);
            }}
            errors={errors}
            readOnly={readOnly}
            required={isReq}
            path={childPath}
          />
          {/* Show required marker for the property itself */}
          {isReq && <span className="sr-only">(requis)</span>}
          {/* Shadowed-key warning chip (top-level only, DESIGN §5). */}
          {path === "" &&
            shadowedKeys != null &&
            shadowedKeys.includes(key) && (
              <p className="text-xs text-warning mt-1">
                Écrasée par local.json5 — modification sans effet
              </p>
            )}
        </div>
      );
    }

    // Group consecutive scalar fields into a responsive 2-column grid; composite
    // fields (objects/arrays/dicts) always take a full row. Preserving source
    // order keeps the schema's field ordering intact.
    const groups: { scalar: boolean; keys: string[] }[] = [];
    for (const key of propKeys) {
      const scalar = isScalarSchema(props_[key] ?? {}, fullRoot);
      const last = groups[groups.length - 1];
      if (last?.scalar === scalar) {
        last.keys.push(key);
      } else {
        groups.push({ scalar, keys: [key] });
      }
    }

    // Grouped children, laid out with the scalar/composite grid split.
    const body = (
      <div className="flex flex-col gap-4">
        {description !== null && <SectionDescription text={description} />}
        {groups.map((group, gi) =>
          group.scalar ? (
            <div key={gi} className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {group.keys.map((key) => renderChild(key))}
            </div>
          ) : (
            <div key={gi} className="flex flex-col gap-4">
              {group.keys.map((key) => renderChild(key))}
            </div>
          ),
        )}
      </div>
    );

    // At the file root (empty path) the wrapper object has no meaningful title,
    // so render its children directly — the nested objects become the titled
    // "domain sections". Deeper objects render as a titled, collapsible
    // Accordion section (collapsed by default; nesting preserved).
    if (path === "") {
      return <div className="flex flex-col gap-4">{body}</div>;
    }

    return (
      <Accordion className="rounded-md border border-border">
        <AccordionItem className="border-b-0">
          <AccordionTrigger className="px-3">
            {sectionLabel(fieldKey, effective)}
          </AccordionTrigger>
          <AccordionContent className="px-3">{body}</AccordionContent>
        </AccordionItem>
      </Accordion>
    );
  }

  // ------------------------------------------------------------------
  // Object with additionalProperties
  // ------------------------------------------------------------------
  if (hasAdditionalProperties(effective)) {
    const nestedValues: unknown = path === "" ? values : values[fieldKey];

    return (
      <AdditionalPropertiesField
        schema={effective}
        values={nestedValues}
        onChange={(v) => {
          if (path === "") {
            onChange(v as Record<string, unknown>);
          } else {
            onChange({ ...values, [fieldKey]: v });
          }
        }}
        errors={errors}
        readOnly={readOnly}
        path={path}
        rootSchema={fullRoot}
      />
    );
  }

  // ------------------------------------------------------------------
  // Array
  // ------------------------------------------------------------------
  if (hasItems(effective)) {
    const nestedValues: unknown = path === "" ? values : values[fieldKey];

    if (itemsAreObjects(effective.items as Record<string, unknown>, fullRoot)) {
      return (
        <ObjectArrayField
          schema={effective}
          values={nestedValues}
          onChange={(v) => {
            if (path === "") {
              onChange(v as Record<string, unknown>);
            } else {
              onChange({ ...values, [fieldKey]: v });
            }
          }}
          errors={errors}
          readOnly={readOnly}
          path={path}
          rootSchema={fullRoot}
        />
      );
    }

    return (
      <PrimitiveArrayField
        schema={effective}
        values={nestedValues}
        onChange={(v) => {
          if (path === "") {
            onChange(v as Record<string, unknown>);
          } else {
            onChange({ ...values, [fieldKey]: v });
          }
        }}
        errors={errors}
        readOnly={readOnly}
        path={path}
        rootSchema={fullRoot}
      />
    );
  }

  // ------------------------------------------------------------------
  // Leaf fields
  // ------------------------------------------------------------------

  // Determine the current value for this leaf.
  const currentValue: unknown = path === "" ? undefined : values[fieldKey];

  // --- string + enum --------------------------------------------------
  if (schemaType === "string" && hasEnum(effective)) {
    return (
      <EnumField
        schema={effective}
        value={currentValue}
        onChange={(v) => {
          if (path === "") {
            onChange(v as Record<string, unknown>);
          } else {
            onChange({ ...values, [fieldKey]: v });
          }
        }}
        fieldPath={path}
        fieldKey={fieldKey}
        errors={errors}
        readOnly={readOnly}
        required={required}
      />
    );
  }

  // --- boolean --------------------------------------------------------
  if (schemaType === "boolean") {
    return (
      <BooleanField
        schema={effective}
        value={currentValue}
        onChange={(v) => {
          if (path === "") {
            onChange(v as Record<string, unknown>);
          } else {
            onChange({ ...values, [fieldKey]: v });
          }
        }}
        fieldPath={path}
        fieldKey={fieldKey}
        errors={errors}
        readOnly={readOnly}
        required={required}
      />
    );
  }

  // --- integer / number -----------------------------------------------
  if (schemaType === "integer" || schemaType === "number") {
    return (
      <NumberField
        schema={effective}
        value={currentValue}
        onChange={(v) => {
          if (path === "") {
            onChange(v as Record<string, unknown>);
          } else {
            onChange({ ...values, [fieldKey]: v });
          }
        }}
        fieldPath={path}
        fieldKey={fieldKey}
        errors={errors}
        readOnly={readOnly}
        required={required}
      />
    );
  }

  // --- string (default) -----------------------------------------------
  if (schemaType === "string" || schemaType === undefined) {
    // Undefined type with properties that we didn't catch → treat as string.
    // Also handles the common string case.
    return (
      <StringField
        schema={effective}
        value={currentValue}
        onChange={(v) => {
          if (path === "") {
            onChange(v as Record<string, unknown>);
          } else {
            onChange({ ...values, [fieldKey]: v });
          }
        }}
        fieldPath={path}
        fieldKey={fieldKey}
        errors={errors}
        readOnly={readOnly}
        required={required}
      />
    );
  }

  // --- Fallback: JSON textarea ----------------------------------------
  return (
    <JsonFallback
      value={currentValue}
      onChange={(v) => {
        if (path === "") {
          onChange(v as Record<string, unknown>);
        } else {
          onChange({ ...values, [fieldKey]: v });
        }
      }}
      fieldPath={path}
      errors={errors}
      readOnly={readOnly}
    />
  );
}
