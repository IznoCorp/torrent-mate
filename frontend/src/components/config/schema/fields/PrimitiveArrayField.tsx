/**
 * PrimitiveArrayField — an ``array`` of primitives rendered as removable rows.
 */

import { Plus, X } from "lucide-react";
import { type ReactElement } from "react";

import { Button } from "@/components/ui/button";

import { joinPath, removeAtIndex, replaceAtIndex } from "../engine";
import { fieldLabel } from "../labels";
import { SchemaFormRenderer } from "../Renderer";
import type { CompositeFieldProps } from "./types";

/**
 * Render an array of primitives as a list of rows, each with a remove button
 * plus an add button at the bottom.
 *
 * Args:
 *   schema: The array schema node (must have ``items``).
 *   values: The current array value (treated as ``unknown[]``).
 *   onChange: Called with a new array.
 *   All other props: Forwarded from parent {@link SchemaFormRenderer}.
 *
 * Returns:
 *   The list editor element.
 */
export function PrimitiveArrayField({
  schema,
  values,
  onChange,
  errors,
  readOnly,
  path,
  rootSchema,
}: CompositeFieldProps): ReactElement {
  const arr: unknown[] = Array.isArray(values) ? values : [];
  const items = schema.items as Record<string, unknown>;
  const label = fieldLabel(schema, path.split(".").pop() ?? "items");

  function replaceAt(index: number, newValue: unknown): void {
    onChange(replaceAtIndex(arr, index, newValue));
  }

  function removeAt(index: number): void {
    onChange(removeAtIndex(arr, index));
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
            <SchemaFormRenderer
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
