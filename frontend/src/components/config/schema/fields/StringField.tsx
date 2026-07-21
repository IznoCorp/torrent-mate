/**
 * StringField — a ``string`` schema leaf rendered as a text ``<Input>``.
 */

import { useId, useState, type ReactElement } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

import { clientValidate, fieldError } from "../engine";
import { fieldLabel, isPathLike } from "../labels";
import type { LeafProps } from "./types";

/**
 * Render a ``string`` field as a text ``<Input>``.
 *
 * Args:
 *   props: {@link LeafProps}.
 *
 * Returns:
 *   The input element.
 */
export function StringField({
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
