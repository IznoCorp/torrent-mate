/**
 * SchemaFormRenderer — the recursive JSON Schema → shadcn control dispatcher.
 *
 * This is the engine's rendering half: it resolves a schema node (via
 * {@link effectiveSchema}) and dispatches to the field kit based on the node
 * ``type``. Nested objects and arrays recurse back into
 * {@link SchemaFormRenderer}. The pure schema logic lives in ``./engine``; the
 * per-primitive controls live in ``./fields``.
 *
 * The public {@link SchemaForm} wrapper (``../SchemaForm``) is a thin re-export
 * of this component.
 */

import { type ReactElement } from "react";

import {
  effectiveSchema,
  hasAdditionalProperties,
  hasEnum,
  hasItems,
  hasProperties,
  isObject,
  isRefPath,
  isScalarSchema,
  itemsAreObjects,
  joinPath,
  requiredSet,
  resolveRef,
  type SchemaType,
} from "./engine";
import { sectionLabel } from "./labels";
import type { SchemaFormProps } from "./types";
import { AdditionalPropertiesField } from "./fields/AdditionalPropertiesField";
import { BooleanField } from "./fields/BooleanField";
import { EnumField } from "./fields/EnumField";
import { JsonFallback } from "./fields/JsonFallback";
import { NumberField } from "./fields/NumberField";
import { ObjectArrayField } from "./fields/ObjectArrayField";
import { PrimitiveArrayField } from "./fields/PrimitiveArrayField";
import { SectionDescription } from "./fields/SectionDescription";
import { StringField } from "./fields/StringField";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

// ---------------------------------------------------------------------------
// SchemaFormRenderer — recursive dispatcher
// ---------------------------------------------------------------------------

/**
 * SchemaFormRenderer — recursive JSON Schema → form control renderer.
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
export function SchemaFormRenderer({
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
          <SchemaFormRenderer
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
