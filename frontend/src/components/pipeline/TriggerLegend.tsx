/**
 * TriggerLegend — a tap-accessible disclosure explaining the run-trigger labels.
 *
 * Renders a ``?`` icon button that opens an inline disclosure panel listing every
 * known trigger with its Badge + one-line French meaning, so the human labels
 * shown in the run tables / detail are decoded in place. Opens on click/tap and
 * closes on click outside or a second button press — never hover-only (DOIT-9).
 *
 * Uses an accessible ``button[aria-expanded]`` + conditionally rendered region
 * pattern (no ``role="menu"`` — this is a legend, not a menu).
 * ``@radix-ui/react-popover`` is not in the project dependency tree, so the
 * disclosure is built from primitives (pipeline-panel review cycle 1, C1).
 */

import { HelpCircle } from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactElement,
} from "react";

import { TRIGGER_INFO } from "@/components/pipeline/triggers";
import { Badge } from "@/components/ui/badge";

/**
 * TriggerLegend — the trigger-label legend disclosure.
 *
 * Returns:
 *   A ``?`` icon button that opens an inline legend panel.
 */
export function TriggerLegend(): ReactElement {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLSpanElement>(null);

  // Close on outside click (mousedown so it fires before a click-to-reopen on
  // the trigger itself would race).
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        containerRef.current !== null &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => {
      document.removeEventListener("mousedown", handler);
    };
  }, [open]);

  const toggle = useCallback(() => {
    setOpen((prev) => !prev);
  }, []);

  return (
    <span ref={containerRef} className="relative inline-flex">
      <button
        type="button"
        className="inline-flex size-5 items-center justify-center rounded-full border border-border text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        aria-label="Légende des déclencheurs"
        aria-expanded={open}
        onClick={toggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle();
          }
        }}
      >
        <HelpCircle className="size-3.5" aria-hidden="true" />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1.5 w-72 rounded-md border border-border bg-popover p-3 shadow-md">
          <p className="mb-2 text-xs font-semibold text-foreground">
            Déclencheurs
          </p>
          <div className="flex flex-col gap-1.5">
            {Object.entries(TRIGGER_INFO).map(([key, info]) => (
              <div key={key} className="flex items-start gap-2 text-xs">
                <Badge tone={info.tone} dot className="mt-0.5 shrink-0">
                  {info.label}
                </Badge>
                <span className="text-muted-foreground">{info.meaning}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </span>
  );
}
