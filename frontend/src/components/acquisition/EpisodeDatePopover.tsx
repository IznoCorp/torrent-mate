/**
 * EpisodeDatePopover — click a matrix chip to see its air date (#10).
 *
 * The completeness matrix lives inside the mobile shell, whose anti-scroll guard
 * clamps every ancestor: an inline popover would be clipped. So the panel is
 * rendered through a portal to ``document.body`` — outside the clamped subtree —
 * and positioned against the trigger's viewport rect.
 *
 * Content is French and human (NE-DOIT-PAS-4): « Diffusé le {date} » for an
 * aired episode, « Sortie prévue le {date} » for an announced one — never the
 * raw ISO token. Keyboard-accessible: the trigger is a real button (Enter /
 * Space toggles), Escape closes and returns focus to it, and a click outside or
 * a scroll dismisses it.
 */

import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import type { EpisodeState } from "@/components/acquisition/meta";
import { formatAirDate } from "@/lib/format";

/** Props for {@link EpisodeDatePopover}. */
export interface EpisodeDatePopoverProps {
  /** The episode's state — ``"announced"`` selects the « Sortie prévue » wording. */
  readonly state: EpisodeState;
  /** ISO ``YYYY-MM-DD`` air date, or ``null`` when the provider gave none. */
  readonly airDate: string | null | undefined;
  /** Accessible name for the trigger (e.g. « E3 — Annoncé »). */
  readonly triggerLabel: string;
  /** Native hover tooltip for the trigger — the desktop fallback for the click popover. */
  readonly hoverTitle?: string;
  /** The chip rendered as the clickable trigger. */
  readonly children: ReactNode;
}

/** The French sentence for a chip's air date, or a graceful unknown-date line. */
function dateSentence(
  state: EpisodeState,
  airDate: string | null | undefined,
): string {
  const formatted = formatAirDate(airDate);
  if (formatted === null) {
    return "Date de diffusion inconnue.";
  }
  return state === "announced"
    ? `Sortie prévue le ${formatted}`
    : `Diffusé le ${formatted}`;
}

/**
 * EpisodeDatePopover — a portalled, keyboard-accessible date popover on a chip.
 *
 * Args:
 *   state: The episode state (drives past/future wording).
 *   airDate: The ISO air date.
 *   triggerLabel: Accessible name for the trigger button.
 *   children: The chip element shown as the trigger.
 *
 * Returns:
 *   The trigger button; the panel mounts to ``document.body`` while open.
 */
export function EpisodeDatePopover({
  state,
  airDate,
  triggerLabel,
  hoverTitle,
  children,
}: EpisodeDatePopoverProps): ReactElement {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number }>({
    top: 0,
    left: 0,
  });
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  const close = useCallback(() => {
    setOpen(false);
    triggerRef.current?.focus();
  }, []);

  // Position the portalled panel against the trigger's viewport rect, clamped
  // so it never spills off the right edge (a chip near the screen edge on a
  // 390 px phone would otherwise push the panel out of view).
  useLayoutEffect(() => {
    if (!open || triggerRef.current === null) {
      return;
    }
    const rect = triggerRef.current.getBoundingClientRect();
    const width = 220;
    const left = Math.min(rect.left, window.innerWidth - width - 8);
    setCoords({ top: rect.bottom + 6, left: Math.max(8, left) });
  }, [open]);

  // Focus the panel on open (screen-reader announces the dialog); dismiss on
  // Escape, on a pointer outside, and on any scroll (the fixed panel would
  // otherwise float away from its now-moved trigger).
  useEffect(() => {
    if (!open) {
      return;
    }
    panelRef.current?.focus();
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        close();
      }
    };
    const onPointer = (e: PointerEvent): void => {
      const t = e.target as Node;
      if (
        panelRef.current?.contains(t) !== true &&
        triggerRef.current?.contains(t) !== true
      ) {
        setOpen(false);
      }
    };
    const onScroll = (): void => {
      setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open, close]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        aria-label={triggerLabel}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        {...(hoverTitle != null ? { title: hoverTitle } : {})}
        onClick={() => {
          setOpen((v) => !v);
        }}
        className="inline-flex cursor-pointer rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {children}
      </button>
      {open &&
        createPortal(
          <div
            ref={panelRef}
            id={panelId}
            role="dialog"
            aria-label={triggerLabel}
            tabIndex={-1}
            style={{ top: coords.top, left: coords.left }}
            className="fixed z-50 w-[220px] rounded-md border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md focus-visible:outline-none"
          >
            {dateSentence(state, airDate)}
          </div>,
          document.body,
        )}
    </>
  );
}
