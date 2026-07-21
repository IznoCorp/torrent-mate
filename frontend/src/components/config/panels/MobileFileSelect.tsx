/**
 * MobileFileSelect — the mobile-only (< md) config section dropdown.
 */

import { type ReactElement } from "react";

import type { FileInfo } from "@/api/config";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/** Props for {@link MobileFileSelect}. */
interface MobileFileSelectProps {
  /** The config files listing. */
  readonly files: FileInfo[];
  /** Currently selected file name, or null. */
  readonly selectedFile: string | null;
  /** Names of files with unsaved edits (bullet marker). */
  readonly dirtyFileNames: Set<string>;
  /** Active panel — mirrors the desktop tab bar (systeme-hub 3.1). */
  readonly leftTab: "files" | "secrets";
  /** Select a file. */
  readonly onSelect: (name: string) => void;
  /** Switch to the Secrets panel (the appended ``Secrets`` option). */
  readonly onSelectSecrets: () => void;
}

/**
 * MobileFileSelect — a top dropdown that replaces the 240px sidebar below the
 * ``md`` breakpoint so the editor and the Secrets panel stay usable at 375px.
 *
 * Args:
 *   props: {@link MobileFileSelectProps}.
 *
 * Returns:
 *   The mobile section selector element.
 */
export function MobileFileSelect({
  files,
  selectedFile,
  dirtyFileNames,
  leftTab,
  onSelect,
  onSelectSecrets,
}: MobileFileSelectProps): ReactElement {
  return (
    <div className="flex flex-col gap-1.5 md:hidden">
      <Label htmlFor="config-file-mobile-select">
        {leftTab === "secrets" ? "Secrets" : "Fichier"}
      </Label>
      <Select
        {...(selectedFile !== null && leftTab === "files"
          ? { value: selectedFile }
          : {})}
        onValueChange={(value: string) => {
          if (value === "__secrets__") {
            onSelectSecrets();
          } else {
            onSelect(value);
          }
        }}
      >
        <SelectTrigger id="config-file-mobile-select" aria-label="Section">
          <SelectValue
            placeholder={
              leftTab === "secrets" ? "Secrets" : "Sélectionner un fichier…"
            }
          />
        </SelectTrigger>
        <SelectContent>
          {files.map((f) => (
            <SelectItem key={f.name} value={f.name}>
              {f.name}
              {dirtyFileNames.has(f.name) ? " •" : ""}
            </SelectItem>
          ))}
          <SelectItem
            value="__secrets__"
            className="border-t border-border mt-1 pt-1"
          >
            Secrets
          </SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
