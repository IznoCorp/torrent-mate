/**
 * ConfigFilePanel — the right-hand config editor panel (header + actions +
 * {@link SchemaForm}), with placeholder / loading / error states.
 */

import { type ReactElement } from "react";

import { SchemaForm } from "@/components/config/SchemaForm";
import { EmptyState } from "@/components/ds/EmptyState";
import { Button } from "@/components/ui/button";

/** Props for {@link ConfigFilePanel}. */
interface ConfigFilePanelProps {
  /** Currently selected file name, or null (placeholder). */
  readonly selectedFile: string | null;
  /** ``true`` while the selected file content is loading. */
  readonly fileLoading: boolean;
  /** ``true`` when the selected file content errored. */
  readonly fileError: boolean;
  /** Read-only instance — disables the action buttons + form. */
  readonly readOnly: boolean;
  /** ``true`` while a validate request is in flight. */
  readonly validatePending: boolean;
  /** ``true`` while a save request is in flight. */
  readonly savePending: boolean;
  /** ``true`` when the selected file has unsaved edits. */
  readonly isDirty: boolean;
  /** Validate the candidate values. */
  readonly onValidate: () => void;
  /** Persist the dirty values. */
  readonly onSave: () => void;
  /** The sub-schema restricted to the selected file's owned keys. */
  readonly schema: Record<string, unknown>;
  /** The full root schema (carries ``$defs``). */
  readonly rootSchema: Record<string, unknown> | undefined;
  /** Current form values. */
  readonly values: Record<string, unknown>;
  /** Server validation errors keyed by dot-joined field path. */
  readonly errors: Record<string, string>;
  /** Keys shadowed by ``local.json5``. */
  readonly shadowedKeys: string[];
  /** Record an edit into the dirty buffer. */
  readonly onChange: (newValues: Record<string, unknown>) => void;
}

/**
 * ConfigFilePanel — renders the selected file's editor, or a placeholder /
 * loading / error message when no editable form is available.
 *
 * Args:
 *   props: {@link ConfigFilePanelProps}.
 *
 * Returns:
 *   The right-panel element.
 */
export function ConfigFilePanel({
  selectedFile,
  fileLoading,
  fileError,
  readOnly,
  validatePending,
  savePending,
  isDirty,
  onValidate,
  onSave,
  schema,
  rootSchema,
  values,
  errors,
  shadowedKeys,
  onChange,
}: ConfigFilePanelProps): ReactElement {
  return (
    <div className="rounded-md border border-border p-4">
      {selectedFile === null ? (
        <EmptyState
          title="Aucun fichier disponible"
          description="La configuration ne contient aucun fichier éditable."
        />
      ) : fileLoading ? (
        <p className="text-sm text-muted-foreground">Chargement du fichier…</p>
      ) : fileError ? (
        <p className="text-sm text-danger" role="alert">
          Erreur lors du chargement de &quot;{selectedFile}&quot;.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">{selectedFile}</h2>

            {/* Action buttons */}
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={readOnly || validatePending}
                onClick={onValidate}
              >
                Valider
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={readOnly || !isDirty || savePending}
                onClick={onSave}
              >
                {savePending ? "Enregistrement…" : "Enregistrer"}
              </Button>
            </div>
          </div>

          {/* SchemaForm */}
          <SchemaForm
            schema={schema}
            rootSchema={rootSchema ?? schema}
            values={values}
            onChange={onChange}
            errors={errors}
            readOnly={readOnly}
            shadowedKeys={shadowedKeys}
          />
        </div>
      )}
    </div>
  );
}
