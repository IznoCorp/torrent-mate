/**
 * Config page — visual configuration editor (TorrentMateUI S4 — config-editor).
 *
 * A thin page shell: {@link useConfigEditor} owns the load / dirty / save /
 * validate / restart machine, and this component wires that state to the
 * presentation panels behind a Fichiers / Secrets tab bar — the
 * {@link FileList} sidebar, the mobile section selector, the
 * {@link ConfigFilePanel} editor, the restart / staging banners, the
 * {@link SecretsTab} sibling panel (no more scroll-to-find, G2/E3), and the
 * conflict / restart dialogs.
 */

import { type ReactElement } from "react";

import { ConfigFilePanel } from "@/components/config/panels/ConfigFilePanel";
import { ConflictDialog } from "@/components/config/panels/ConflictDialog";
import { MobileFileSelect } from "@/components/config/panels/MobileFileSelect";
import { RestartConfirmDialog } from "@/components/config/panels/RestartConfirmDialog";
import { RestartRequiredBanner } from "@/components/config/panels/RestartRequiredBanner";
import { StalledLoadRetry } from "@/components/config/panels/StalledLoadRetry";
import { FileList } from "@/components/config/FileList";
import { RankingPanel } from "@/components/config/RankingPanel";
import { SecretsTab } from "@/components/config/SecretsTab";
import { PageHeader } from "@/components/ds/PageHeader";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useConfigEditor } from "@/hooks/useConfigEditor";
import { handleTablistKeyDown } from "@/lib/tablist";
import { cn } from "@/lib/utils";

/** The desktop tab bar entries (Fichiers / Secrets), in display order. */
const CONFIG_TABS = [
  { id: "files", label: "Fichiers" },
  { id: "secrets", label: "Secrets" },
  // Ranking profiles used to sit on the acquisition page. They are settings —
  // read rarely, changed rarely — and they were crowding a surface whose job is
  // to answer "what needs me now". Their home is here.
  { id: "ranking", label: "Classement" },
] as const;

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
        <PageHeader title="Configuration" />
        {/* X8 — layout-shaped Skeleton (sidebar + panel), not bare text. */}
        <div
          className="grid grid-cols-1 gap-4 md:grid-cols-[240px_1fr]"
          aria-busy="true"
        >
          <Skeleton className="hidden h-64 md:block" />
          <Skeleton className="h-64 w-full" />
        </div>
        <StalledLoadRetry onRetry={editor.refetchAll} />
      </section>
    );
  }

  // ---- Error state ---------------------------------------------------------
  if (editor.isError) {
    return (
      <section className="mx-auto flex max-w-5xl flex-col gap-4">
        <PageHeader title="Configuration" />
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
      <PageHeader title="Configuration" />

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

      {/* Mobile-only section selector — the 240px sidebar is hidden < md, so a
          top dropdown keeps the editor and Secrets usable at 375px. */}
      <MobileFileSelect
        files={editor.files}
        selectedFile={editor.selectedFile}
        dirtyFileNames={editor.dirtyFileNames}
        leftTab={editor.leftTab}
        onSelect={editor.handleSelectFile}
        onSelectSecrets={editor.handleSelectSecrets}
        onSelectClassement={() => {
          editor.setLeftTab("ranking");
        }}
      />

      {/* Desktop tab bar — visible only on md+; mobile uses the dropdown above.
          ACQUISITION-7 (ticket 250): full WAI-ARIA tablist wiring — roving
          tabIndex + arrow-key navigation + tab/panel linkage. */}
      <div
        className="hidden md:flex gap-0.5 rounded-lg bg-muted p-1 w-fit"
        role="tablist"
        aria-label="Section"
        onKeyDown={(e) => {
          handleTablistKeyDown(
            e,
            CONFIG_TABS.map((t) => t.id),
            editor.leftTab,
            editor.setLeftTab,
            (id) => `config-tab-${id}`,
          );
        }}
      >
        {CONFIG_TABS.map((tab) => (
          <button
            key={tab.id}
            id={`config-tab-${tab.id}`}
            role="tab"
            aria-selected={editor.leftTab === tab.id}
            aria-controls="config-tabpanel"
            tabIndex={editor.leftTab === tab.id ? 0 : -1}
            type="button"
            onClick={() => {
              editor.setLeftTab(tab.id);
            }}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              editor.leftTab === tab.id
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Files tab: two-panel layout (FileList sidebar + SchemaForm editor). */}
      {editor.leftTab === "files" && (
        <div
          id="config-tabpanel"
          role="tabpanel"
          aria-labelledby="config-tab-files"
          className="grid grid-cols-1 gap-4 md:grid-cols-[240px_1fr]"
        >
          {/* Left panel: file list (hidden < md — replaced by the mobile
              Select). X6: DS Card instead of a hand-rolled bordered div. */}
          <Card className="hidden gap-0 p-2 md:block">
            <FileList
              dirtyFiles={editor.dirtyFileNames}
              selected={editor.selectedFile}
              onSelect={editor.handleSelectFile}
            />
          </Card>

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
      )}

      {/* Secrets tab (sibling of the file list — no more scroll-to-find,
          G2/E3). X6: DS Card instead of a hand-rolled bordered div. */}
      {editor.leftTab === "ranking" && (
        <Card
          id="config-tabpanel"
          role="tabpanel"
          aria-labelledby="config-tab-ranking"
          className="gap-0 p-4"
        >
          <RankingPanel />
        </Card>
      )}

      {editor.leftTab === "secrets" && (
        <Card
          id="config-tabpanel"
          role="tabpanel"
          aria-labelledby="config-tab-secrets"
          className="gap-0 p-4"
        >
          <SecretsTab readOnly={editor.readOnly} />
        </Card>
      )}

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
