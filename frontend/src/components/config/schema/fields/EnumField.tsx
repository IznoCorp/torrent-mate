/**
 * EnumField — a ``string`` + ``enum`` schema leaf rendered as a ``<Select>``.
 */

import { useId, type ReactElement } from "react";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { fieldError } from "../engine";
import { fieldLabel } from "../labels";
import type { LeafProps } from "./types";

/**
 * Render a ``string`` + ``enum`` field as a ``<Select>``.
 *
 * Args:
 *   props: {@link LeafProps}.
 *
 * Returns:
 *   The select element.
 */
export function EnumField({
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
