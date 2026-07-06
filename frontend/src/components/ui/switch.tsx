import * as React from "react";

import { cn } from "@/lib/utils";
import { switchThumbVariants, switchTrackVariants } from "./switch-variants";

/** Props for {@link Switch}. */
export interface SwitchProps extends Omit<
  React.ButtonHTMLAttributes<HTMLButtonElement>,
  "role" | "onChange" | "value" | "children"
> {
  /** Whether the switch is in the on position. */
  checked: boolean;
  /** Called when the user toggles the switch. */
  onCheckedChange: (checked: boolean) => void;
  /** Colour tone. @default "primary" */
  tone?: "primary" | "success";
}

/**
 * Switch — a boolean toggle styled on TorrentMate tokens (design-system
 * ``components/core/Switch``).
 *
 * Hand-rolled ``<button role="switch">`` with a sliding thumb — no radix
 * dependency. Controlled via ``checked`` / ``onCheckedChange`` like a checkbox.
 * The ``tone`` prop selects between the primary and success signal palettes;
 * ``disabled`` dims the control and blocks interaction.
 *
 * The track is 38×22 px (DS contract) wrapped in padding for a ≥44 px hit area.
 * ``prefers-reduced-motion`` is respected via the ``motion-reduce:`` utility.
 *
 * Args:
 *   checked: Whether the switch is on.
 *   onCheckedChange: Toggle callback receiving the new boolean value.
 *   tone: Colour tone (default ``"primary"``).
 *   disabled: Whether the switch is non-interactive.
 *
 * Returns:
 *   The switch element.
 */
export function Switch({
  checked,
  onCheckedChange,
  tone = "primary",
  disabled = false,
  className,
  ...rest
}: SwitchProps): React.JSX.Element {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => { onCheckedChange(!checked); }}
      className={cn(
        // Button reset + ≥44 px hit area (22 px track + 3 px padding each side
        // gives a 28 px box, so add 8 px of invisible padding via min-size).
        "inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full p-0",
        // Focus ring from DS tokens.
        "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-[color-mix(in_oklch,var(--ring)_35%,transparent)]",
        // Disabled state.
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...rest}
    >
      <span className={switchTrackVariants({ checked, tone })}>
        <span className={switchThumbVariants({ checked, tone })} />
      </span>
    </button>
  );
}
