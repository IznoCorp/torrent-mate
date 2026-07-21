/**
 * AdditionalPropertiesField — an object with ``additionalProperties`` rendered
 * as a key/value row editor.
 */

import { Plus, X } from "lucide-react";
import { type ReactElement } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { fieldError, isObject, joinPath } from "../engine";
import { fieldLabel } from "../labels";
import { SchemaFormRenderer } from "../Renderer";
import type { CompositeFieldProps } from "./types";

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
 *   All other props: Forwarded from parent {@link SchemaFormRenderer}.
 *
 * Returns:
 *   The key/value editor element.
 */
export function AdditionalPropertiesField({
  schema,
  values,
  onChange,
  errors,
  readOnly,
  path,
  rootSchema,
}: CompositeFieldProps): ReactElement {
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
                <SchemaFormRenderer
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
