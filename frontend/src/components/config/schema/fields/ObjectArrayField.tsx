/**
 * ObjectArrayField — an ``array`` of objects (``$ref`` / inline) rendered as a
 * card list.
 */

import { Plus, X } from "lucide-react";
import { type ReactElement } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import {
  effectiveSchema,
  isObject,
  joinPath,
  removeAtIndex,
  replaceAtIndex,
} from "../engine";
import { fieldLabel } from "../labels";
import { SchemaFormRenderer } from "../Renderer";
import type { CompositeFieldProps } from "./types";

/**
 * Render an array of objects (``$ref`` or inline) as a card list.
 *
 * Each card renders a recursive {@link SchemaFormRenderer} for the object, plus
 * per-card remove.  An add button prepends a new empty object.
 *
 * Args:
 *   schema: The array schema node (must have ``items``).
 *   values: The current array value.
 *   onChange: Called with a new array.
 *   All other props: Forwarded from parent {@link SchemaFormRenderer}.
 *
 * Returns:
 *   The card-list element.
 */
export function ObjectArrayField({
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
  const resolvedItems = effectiveSchema(items, rootSchema);
  const label = fieldLabel(schema, path.split(".").pop() ?? "items");

  function replaceAt(index: number, newValue: unknown): void {
    onChange(replaceAtIndex(arr, index, newValue));
  }

  function removeAt(index: number): void {
    onChange(removeAtIndex(arr, index));
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
              <SchemaFormRenderer
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
