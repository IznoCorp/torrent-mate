/**
 * NumberField — an ``integer`` / ``number`` schema leaf rendered as a numeric
 * ``<Input>``.
 */

import { useId, useState, type ReactElement } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { clientValidate, fieldError } from "../engine";
import { fieldLabel } from "../labels";
import type { LeafProps } from "./types";

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
export function NumberField({
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
