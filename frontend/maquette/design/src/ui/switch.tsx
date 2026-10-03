// A switch: one control that turns one thing on or off, whatever it turns.
//
// ONE ELEMENT, WRITTEN ONCE. The drawing was already one (`toggleSwitch`), but
// the element around it — its role, its checked state, its accessible name —
// was written out by each form that offered a switch, and a copy is where the
// next difference hides. The knob is the drawing's `::after`: no child.
//
// IT KNOWS NO DOMAIN. What it turns and how a press is handled are the
// caller's: a press is either the caller's handler or a `data-*` attribute the
// caller's delegated listener reads, and the part a rule reads is written by
// the caller under the attribute's own name.
import type { ReactElement } from "react";
import { toggleSwitch } from "./variants";

/**
 * A switch, drawn checked or not.
 *
 * @param props.checked Whether what it turns is on.
 * @param props.label Its accessible name — what it turns.
 * @param props.onClick The press, when the caller handles it here.
 * @param props.disabled Whether it only shows its state — drawn, never pressed.
 * @param props.data-part The switch's part, for the rules that read it — written at the
 *   call site under the attribute's own name, so the markup guard reads the value
 *   where it is chosen.
 * @returns The switch.
 */
export function Switch({ checked, label, onClick, disabled, ...attributes }: {
  /** Whether what it turns is on. */
  checked: boolean;
  /** Its accessible name. */
  label: string;
  /** The press, when the caller handles it here. */
  onClick?: () => void;
  /** Whether it only shows its state. */
  disabled?: boolean;
  /** The name a rule reads the switch by — the caller's, as every part is. */
  "data-part"?: string;
} & { [attribute: `data-${string}`]: string | undefined }): ReactElement {
  return (
    <button
      className={toggleSwitch()}
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      {...attributes}
    />
  );
}
