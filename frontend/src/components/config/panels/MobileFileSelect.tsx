/**
 * MobileFileSelect — the mobile-only (< md) config file dropdown.
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
  /** Select a file. */
  readonly onSelect: (name: string) => void;
}

/**
 * MobileFileSelect — a top dropdown that replaces the 240px sidebar below the
 * ``md`` breakpoint so the editor stays usable at 375px.
 *
 * Args:
 *   props: {@link MobileFileSelectProps}.
 *
 * Returns:
 *   The mobile file selector element.
 */
export function MobileFileSelect({
  files,
  selectedFile,
  dirtyFileNames,
  onSelect,
}: MobileFileSelectProps): ReactElement {
  return (
    <div className="flex flex-col gap-1.5 md:hidden">
      <Label htmlFor="config-file-mobile-select">Fichier</Label>
      <Select
        {...(selectedFile !== null ? { value: selectedFile } : {})}
        onValueChange={onSelect}
      >
        <SelectTrigger id="config-file-mobile-select" aria-label="Fichier">
          <SelectValue placeholder="Sélectionner un fichier…" />
        </SelectTrigger>
        <SelectContent>
          {files.map((f) => (
            <SelectItem key={f.name} value={f.name}>
              {f.name}
              {dirtyFileNames.has(f.name) ? " •" : ""}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
