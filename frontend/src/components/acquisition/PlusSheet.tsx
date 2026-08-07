/**
 * PlusSheet — Veille et Obligations in a slide-in drawer.
 *
 * Moves the existing WatcherPanel and ObligationsPanel into a Sheet so they
 * remain reachable without occupying a tab. The ranking profiles moved to
 * the Config page. Neither panel is redesigned here — out of scope (spec §14).
 */

import { type ReactElement } from "react";

import { ObligationsPanel } from "@/components/acquisition/ObligationsPanel";
import { WatcherPanel } from "@/components/acquisition/WatcherPanel";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

/** Props for {@link PlusSheet}. */
export interface PlusSheetProps {
  /** Whether the sheet is visible. */
  readonly open: boolean;
  /** Callback to close (or open) the sheet. */
  readonly onOpenChange: (open: boolean) => void;
}

/**
 * PlusSheet — secondary acquisition surface (Watcher + Obligations).
 *
 * Args:
 *   props: {@link PlusSheetProps} — open state + close callback.
 *
 * Returns:
 *   The sheet element.
 */
export function PlusSheet({
  open,
  onOpenChange,
}: PlusSheetProps): ReactElement {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>Veille et obligations</SheetTitle>
          <SheetDescription>
            État du watcher et obligations de partage. Les profils de
            classement sont maintenant dans la page Configuration.
          </SheetDescription>
        </SheetHeader>
        <div className="mt-6 flex flex-col gap-6">
          <WatcherPanel />
          <ObligationsPanel />
        </div>
      </SheetContent>
    </Sheet>
  );
}
