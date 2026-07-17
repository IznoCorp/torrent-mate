/**
 * Config page — visual configuration editor (TorrentMateUI S4 — config-editor).
 *
 * A thin page shell: {@link useConfigEditor} owns the load / dirty / save /
 * validate / restart machine, and this component wires that state to the
 * presentation panels — the {@link FileList} sidebar, the mobile file selector,
 * the {@link ConfigFilePanel} editor, the restart / staging banners, the
 * {@link SecretsTab} section, and the conflict / restart dialogs.
 */

import { type ReactElement } from "react";

import { ConfigFilePanel } from "@/components/config/panels/ConfigFilePanel";
import { ConflictDialog } from "@/components/config/panels/ConflictDialog";
import { MobileFileSelect } from "@/components/config/panels/MobileFileSelect";
import { RestartConfirmDialog } from "@/components/config/panels/RestartConfirmDialog";
import { RestartRequiredBanner } from "@/components/config/panels/RestartRequiredBanner";
import { StalledLoadRetry } from "@/components/config/panels/StalledLoadRetry";
import { FileList } from "@/components/config/FileList";
import { SecretsTab } from "@/components/config/SecretsTab";
import { StagingBanner } from "@/components/StagingBanner";
import { useConfigEditor } from "@/hooks/useConfigEditor";

/**
 * Config — the authenticated config editor route (``/config``).
 *
 * Returns:
 *   The config page element.
 */
export default function Config(): ReactElement {
  const editor = useConfigEditor();

  // ---- Loading state -------------------------------------------------------
  if (editor.isLoading) {
    return (
      <section className="mx-auto flex max-w-5xl flex-col gap-4">
        <h1 className="text-xl font-semibold tracking-tight">Configuration</h1>
        <p className="text-sm text-muted-foreground">Chargement…</p>
        <StalledLoadRetry onRetry={editor.refetchAll} />
      </section>
    );
  }

  // ---- Error state ---------------------------------------------------------
  if (editor.isError) {
    return (
      <section className="mx-auto flex max-w-5xl flex-col gap-4">
        <h1 className="text-xl font-semibold tracking-tight">Configuration</h1>
        <p className="text-sm text-danger" role="alert">
          Impossible de charger la configuration. Vérifiez que le backend est
          accessible.
        </p>
      </section>
    );
  }

  // ---- Render --------------------------------------------------------------
  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Configuration</h1>

      {/* Staging read-only banner */}
      {editor.isStaging && <StagingBanner />}
      {editor.readOnly && (
        <div
          className="rounded-md border border-warning bg-warning/10 px-4 py-3 text-sm"
          role="alert"
        >
          Mode lecture seule — les modifications sont désactivées sur cette
          instance.
        </div>
      )}

      {/* Restart required banner */}
      {editor.restartRequired && (
        <RestartRequiredBanner
          readOnly={editor.readOnly}
          restartConfigured={editor.restartConfigured}
          staleFiles={editor.staleFiles}
          restartPending={editor.restartPending}
          onRestart={editor.openRestartConfirm}
        />
      )}

      {/* Mobile-only file selector — the 240px sidebar is hidden < md, so a
          top dropdown keeps the editor usable at 375px. */}
      <MobileFileSelect
        files={editor.files}
        selectedFile={editor.selectedFile}
        dirtyFileNames={editor.dirtyFileNames}
        onSelect={editor.handleSelectFile}
      />

      {/* Two-panel layout: FileList (sidebar) + SchemaForm editor */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-[240px_1fr]">
        {/* Left panel: file list (hidden < md — replaced by the mobile Select) */}
        <div className="hidden rounded-md border border-border p-2 md:block">
          <FileList
            dirtyFiles={editor.dirtyFileNames}
            selected={editor.selectedFile}
            onSelect={editor.handleSelectFile}
          />
        </div>

        {/* Right panel: form or placeholder */}
        <ConfigFilePanel
          selectedFile={editor.selectedFile}
          fileLoading={editor.fileLoading}
          fileError={editor.fileError}
          readOnly={editor.readOnly}
          validatePending={editor.validatePending}
          savePending={editor.savePending}
          isDirty={editor.isDirty}
          onValidate={() => {
            void editor.handleValidate();
          }}
          onSave={() => {
            void editor.handleSave();
          }}
          schema={editor.fileSchema}
          rootSchema={editor.rootSchema}
          values={editor.currentValues}
          errors={editor.formErrors}
          shadowedKeys={editor.shadowedKeys}
          onChange={editor.onFormChange}
        />
      </div>

      {/* Secrets section */}
      <div className="rounded-md border border-border p-4">
        <SecretsTab readOnly={editor.readOnly} />
      </div>

      {/* Conflict dialog */}
      <ConflictDialog
        open={editor.showConflict}
        onClose={editor.closeConflict}
        onReload={editor.handleReloadFile}
      />

      {/* Restart confirmation dialog */}
      <RestartConfirmDialog
        open={editor.showRestartConfirm}
        onClose={editor.closeRestartConfirm}
        onConfirm={() => {
          void editor.handleRestart();
        }}
      />
    </section>
  );
}
