/**
 * TriggerLegend — a tap-accessible popover explaining the run-trigger labels.
 *
 * Renders a ``?`` icon button that opens a popover (Radix DropdownMenu) listing
 * every known trigger with its Badge + one-line French meaning, so the human
 * labels shown in the run tables / detail are decoded in place. Opens on
 * click/tap and closes on click outside — never hover-only (DOIT-9).
 *
 * pipeline-panel Phase 02: converted from an inline chip-paragraph to a
 * popover anchored to the history table header.
 */

import { HelpCircle } from "lucide-react";
import { type ReactElement } from "react";

import { TRIGGER_INFO } from "@/components/pipeline/triggers";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/**
 * TriggerLegend — the trigger-label legend popover.
 *
 * Returns:
 *   A ``?`` icon button that opens a popover listing every known trigger.
 */
export function TriggerLegend(): ReactElement {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="inline-flex size-5 items-center justify-center rounded-full border border-border text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Légende des déclencheurs"
        >
          <HelpCircle className="size-3.5" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        sideOffset={6}
        className="w-72 p-3"
      >
        <p className="mb-2 text-xs font-semibold text-foreground">
          Déclencheurs
        </p>
        <div className="flex flex-col gap-1.5">
          {Object.entries(TRIGGER_INFO).map(([key, info]) => (
            <div
              key={key}
              className="flex items-start gap-2 text-xs"
            >
              <Badge tone={info.tone} dot className="mt-0.5 shrink-0">
                {info.label}
              </Badge>
              <span className="text-muted-foreground">{info.meaning}</span>
            </div>
          ))}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
