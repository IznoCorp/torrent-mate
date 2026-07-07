/**
 * FileList — sidebar list of config files with badges.
 *
 * Renders every config file as a selectable row with:
 * - Owned keys as muted chips.
 * - A "restart" badge when any owned key has ``restart_impact=true``.
 * - A "stale" badge when the file is in ``status.stale_files``.
 * - A "shadowed" badge when ``shadowed_keys`` is non-empty.
 * - A dirty dot when the parent page has unsaved edits for this file.
 */

import type { ReactElement } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  useConfigFiles,
  useConfigSchema,
  useConfigStatus,
} from "@/hooks/useConfig";

/** Props for {@link FileList}. */
export interface FileListProps {
  /** Files with unsaved local edits (basename → set membership). */
  readonly dirtyFiles: Set<string>;
  /** Currently selected file basename, or ``null`` when nothing is selected. */
  readonly selected: string | null;
  /** Called when the user clicks a file row. */
  readonly onSelect: (name: string) => void;
}

/**
 * FileList — selectable sidebar list of config overlays.
 *
 * Args:
 *   props: {@link FileListProps}.
 *
 * Returns:
 *   The file list element, or a loading / error fallback.
 */
export function FileList({
  dirtyFiles,
  selected,
  onSelect,
}: FileListProps): ReactElement {
  const files = useConfigFiles();
  const schema = useConfigSchema();
  const status = useConfigStatus();

  // Loading / error states.
  if (files.isLoading || schema.isLoading || status.isLoading) {
    return (
      <div className="text-sm text-muted-foreground py-4">
        Chargement des fichiers…
      </div>
    );
  }

  if (files.isError || schema.isError || status.isError) {
    return (
      <div className="text-sm text-[var(--danger)] py-4" role="alert">
        Erreur lors du chargement des fichiers.
      </div>
    );
  }

  const fileList = files.data?.files ?? [];
  const restartImpact = schema.data?.restart_impact ?? {};
  const staleSet = new Set(status.data?.stale_files ?? []);

  return (
    <nav
      className="flex flex-col gap-0.5"
      aria-label="Fichiers de configuration"
    >
      {fileList.map((file) => {
        const isSelected = selected === file.name;
        const isDirty = dirtyFiles.has(file.name);
        const isStale = staleSet.has(file.name);
        const hasShadowed = file.shadowed_keys.length > 0;
        const hasRestart = file.owned_keys.some(
          (k) => restartImpact[k] === true,
        );

        return (
          <button
            key={file.name}
            type="button"
            className={cn(
              "flex flex-col gap-1 rounded-md px-3 py-2 text-left w-full",
              "hover:bg-accent hover:text-accent-foreground transition-colors",
              isSelected && "bg-accent text-accent-foreground font-medium",
            )}
            aria-current={isSelected ? "page" : undefined}
            onClick={() => {
              onSelect(file.name);
            }}
          >
            <div className="flex items-center gap-2">
              {/* Dirty dot */}
              {isDirty && (
                <span
                  className="size-2 shrink-0 rounded-full bg-[var(--warning)]"
                  aria-label="Modifications non enregistrées"
                />
              )}

              <span className="text-sm truncate">{file.name}</span>

              {/* Badges */}
              {hasRestart && (
                <Badge tone="warning" mono>
                  restart
                </Badge>
              )}
              {isStale && (
                <Badge tone="info" mono>
                  stale
                </Badge>
              )}
              {hasShadowed && (
                <Badge tone="neutral" mono>
                  shadowed
                </Badge>
              )}
            </div>

            {/* Owned keys as muted chips */}
            {file.owned_keys.length > 0 && (
              <div className="flex flex-wrap gap-1 pl-4">
                {file.owned_keys.map((key) => (
                  <Badge key={key} tone="neutral" className="text-[0.65rem]">
                    {key}
                  </Badge>
                ))}
              </div>
            )}
          </button>
        );
      })}

      {fileList.length === 0 && (
        <p className="text-sm text-muted-foreground py-4">
          Aucun fichier de configuration trouvé.
        </p>
      )}
    </nav>
  );
}
