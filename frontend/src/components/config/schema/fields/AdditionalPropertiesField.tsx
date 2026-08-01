/**
 * AdditionalPropertiesField — an object with ``additionalProperties`` rendered
 * as a key/value row editor.
 */

import { Plus, X } from "lucide-react";
import { useState, type ReactElement } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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
 * Key renames commit on blur/Enter (CONFIG-10, ticket 250) and preserve row
 * order; a blank or colliding key silently reverts (never merges two entries).
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

  // CONFIG-10 (ticket 250): per-row key drafts, keyed by the CURRENT object
  // key. Typing edits the draft only; the rename commits on blur/Enter so the
  // row identity (and input focus) survives every keystroke.
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({});

  function setEntry(key: string, newValue: unknown): void {
    onChange({ ...obj, [key]: newValue });
  }

  /**
   * Commit a key rename (blur/Enter), preserving row order.
   *
   * A blank, unchanged or colliding new key reverts to the current key —
   * a rename must never silently merge two entries.
   */
  function commitKeyRename(oldKey: string, rawNewKey: string): void {
    setKeyDrafts((prev) => {
      const next = { ...prev };
      // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
      delete next[oldKey];
      return next;
    });
    const newKey = rawNewKey.trim();
    if (newKey === "" || newKey === oldKey || newKey in obj) return;
    const renamed: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(obj)) {
      renamed[k === oldKey ? newKey : k] = v;
    }
    onChange(renamed);
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
              {/* CONFIG-10: the key is EDITABLE, as the field docstring promises
                  — renames commit on blur/Enter. X7: a dict key is a machine
                  token — mono, not prose. */}
              <Input
                type="text"
                aria-label={`Clé ${k}`}
                disabled={readOnly}
                className="mb-1 h-8 font-mono text-xs"
                value={keyDrafts[k] ?? k}
                onChange={(e) => {
                  const draft = e.target.value;
                  setKeyDrafts((prev) => ({ ...prev, [k]: draft }));
                }}
                onBlur={(e) => {
                  commitKeyRename(k, e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    e.currentTarget.blur();
                  }
                }}
              />
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
                // X4: 44px touch target on mobile, compact on desktop.
                className="mt-5 min-h-11 min-w-11 shrink-0 md:min-h-8 md:min-w-8"
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
          // X4: 44px touch target on mobile, compact on desktop.
          className="min-h-11 self-start md:min-h-8"
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
