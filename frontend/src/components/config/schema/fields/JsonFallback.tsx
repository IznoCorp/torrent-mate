/**
 * JsonFallback — the JSON ``<textarea>`` escape hatch for unresolvable schemas.
 */

import { useId, useState, type ReactElement, type ChangeEvent } from "react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

import { fieldError } from "../engine";

/**
 * Fallback renderer for unresolvable schemas (unknown ``$ref``, complex
 * unions, free-form dicts).
 *
 * Renders a ``<textarea>`` with ``JSON.parse`` validation on blur:
 * - Invalid JSON → inline error shown, ``onChange`` is NOT called.
 * - Valid JSON → ``onChange`` is called with the parsed value.
 *
 * This is the **only** place in the component tree allowed to hold raw
 * ``unknown`` values — the textarea draft is local state, not pushed upward
 * until it is valid JSON.
 *
 * Args:
 *   value: The current value (rendered as pretty-printed JSON).
 *   onChange: Called with the parsed value on successful blur validation.
 *   fieldPath: Dot-joined field path for error lookup.
 *   errors: Server error map.
 *   readOnly: Whether the textarea is disabled.
 *
 * Returns:
 *   The textarea element.
 */
export function JsonFallback({
  value,
  onChange,
  fieldPath,
  errors,
  readOnly,
}: {
  readonly value: unknown;
  readonly onChange: (v: unknown) => void;
  readonly fieldPath: string;
  readonly errors: Record<string, string>;
  readonly readOnly: boolean;
}): ReactElement {
  const id = useId();
  const text =
    value !== undefined && value !== null ? JSON.stringify(value, null, 2) : "";
  const [draft, setDraft] = useState(text);
  const [parseErr, setParseErr] = useState<string | null>(null);
  const er = fieldError(errors, fieldPath);

  function handleBlur(): void {
    if (draft.trim() === "") {
      setParseErr(null);
      onChange(undefined);
      return;
    }
    try {
      const parsed: unknown = JSON.parse(draft);
      setParseErr(null);
      onChange(parsed);
    } catch (e: unknown) {
      setParseErr(e instanceof Error ? e.message : "JSON invalide");
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>JSON</Label>
      <textarea
        id={id}
        className={cn(
          "border-input placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 flex min-h-[120px] w-full rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50 font-mono",
          (er !== null || parseErr !== null) && "border-destructive",
        )}
        aria-invalid={er !== null || parseErr !== null ? true : undefined}
        disabled={readOnly}
        value={draft}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => {
          setDraft(e.target.value);
          // Clear parse error while the user is editing.
          if (parseErr !== null) setParseErr(null);
        }}
        onBlur={handleBlur}
        rows={6}
        spellCheck={false}
      />
      {parseErr !== null && (
        <p className="text-sm text-danger" role="alert">
          {parseErr}
        </p>
      )}
      {er !== null && (
        <p className="text-sm text-danger" role="alert">
          {er}
        </p>
      )}
    </div>
  );
}
