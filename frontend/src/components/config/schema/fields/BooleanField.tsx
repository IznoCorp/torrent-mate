/**
 * BooleanField — a ``boolean`` schema leaf rendered as a ``<Switch>``.
 */

import { useId, type ReactElement } from "react";

import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

import { fieldError } from "../engine";
import { fieldLabel } from "../labels";
import type { LeafProps } from "./types";

/**
 * Render a ``boolean`` field as a ``<Switch>``.
 *
 * Args:
 *   props: {@link LeafProps}.
 *
 * Returns:
 *   The switch element.
 */
export function BooleanField({
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
