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
 * order; a blank, colliding or invalid key reverts (never merges two entries)
 * and explains the refusal in a per-row alert, cleared on the next keystroke.
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

  // CONFIG-10 (ticket 250): per-row rename-refusal explanations, keyed by the
  // CURRENT object key. A refused rename reverts (never merges two entries)
  // but must say WHY; editing that row's key input clears its message.
  const [keyErrors, setKeyErrors] = useState<Record<string, string>>({});

  function clearKeyError(key: string): void {
    setKeyErrors((prev) => {
      if (!Object.hasOwn(prev, key)) return prev;
      const next = { ...prev };
      // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
      delete next[key];
      return next;
    });
  }

  function setEntry(key: string, newValue: unknown): void {
    onChange({ ...obj, [key]: newValue });
  }

  /**
   * Commit a key rename (blur/Enter), preserving row order.
   *
   * A blank, invalid or colliding new key reverts to the current key — a
   * rename must never merge two entries — and records a per-row explanation
   * for the refusal (cleared when the user edits that row's key again).
   */
  function commitKeyRename(oldKey: string, rawNewKey: string): void {
    setKeyDrafts((prev) => {
      const next = { ...prev };
      // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
      delete next[oldKey];
      return next;
    });
    const newKey = rawNewKey.trim();
    if (newKey === oldKey) {
      clearKeyError(oldKey);
      return;
    }
    if (newKey === "") {
      setKeyErrors((prev) => ({
        ...prev,
        [oldKey]: "Renommage annulé : clé vide",
      }));
      return;
    }
    // "__proto__" can never become a dict key: the computed assignment
    // `renamed["__proto__"] = v` below would invoke the inherited prototype
    // setter instead of creating an own property, silently losing the entry.
    if (newKey === "__proto__") {
      setKeyErrors((prev) => ({
        ...prev,
        [oldKey]: "Renommage annulé : clé invalide",
      }));
      return;
    }
    // Object.hasOwn, not `in`: `in` walks the prototype chain and would
    // refuse legitimate keys such as `toString` as phantom collisions.
    if (Object.hasOwn(obj, newKey)) {
      setKeyErrors((prev) => ({
        ...prev,
        [oldKey]: "Renommage annulé : clé déjà utilisée",
      }));
      return;
    }
    clearKeyError(oldKey);
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
    // Drop any pending refusal message so it cannot resurface on a future
    // entry that reuses the removed key.
    clearKeyError(key);
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

      {entries.map(([k, v], idx) => {
        const rowPath = joinPath(path, k);
        const keyError = keyErrors[k];
        return (
          // CONFIG-10 (ticket 250): rows are keyed by entry index, not by the
          // dict key — a committed rename changes the key, and a key-based row
          // would remount, dropping focus and detaching the remove button
          // mid-click. Index identity is deliberate and safe here because
          // renames preserve entry order and every REACHABLE input is
          // controlled (key drafts/errors live in maps keyed by dict key; the
          // scalar value Input reads straight from the object). Known
          // limitation: the nested SchemaFormRenderer branch below is NOT
          // fully controlled — its descendants (NumberField/StringField
          // clientErr, JsonFallback draft) hold internal state that would
          // migrate across rows on a middle-row removal under index keys. That
          // branch is unreachable with the current config schema (no
          // inline-object additionalProperties — all $refs) and would need
          // stable synthetic row ids before it ever becomes reachable.
          <div key={idx} className="flex items-start gap-2">
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
                  // A new keystroke supersedes a previous rename refusal.
                  clearKeyError(k);
                }}
                onBlur={(e) => {
                  commitKeyRename(k, e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    // Commit directly instead of blur(): a successful rename
                    // re-renders the row and blur() would strand focus on
                    // document.body; committing inline keeps the caret in
                    // this key input. Tab-out still commits via onBlur.
                    commitKeyRename(k, e.currentTarget.value);
                  }
                }}
              />
              {keyError !== undefined && (
                <p className="mb-1 text-sm text-danger" role="alert">
                  {keyError}
                </p>
              )}
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
