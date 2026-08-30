// THE DRAWER'S BOX — the layer itself, and nothing about what is in it.
//
// It renders `<aside id="drawer">` at the same id and the same identity class
// the engine's markup carried, so `app/focus.ts` still finds it by
// `data-open`, `app/drawer-gesture.ts` still attaches to it, and the rules
// that select it still measure it. Only the owner moved.
//
// CLOSED IS A CLASS, NEVER AN ABSENCE. The transform that carries the panel in
// and out needs both states on the same element, and the engine's `<aside>`
// likewise stayed in the document with its content after closing.
import type { ReactElement, ReactNode } from "react";

import { drawer } from "./variants";

export function Drawer({
  open,
  label,
  children,
}: {
  open: boolean;
  /** « Menu ». NOT « Navigation principale »: the tab bar already carries that
   *  name, and two landmarks answering to one name make a screen reader's
   *  landmark list a guessing game. */
  label: string;
  children: ReactNode;
}): ReactElement {
  return (
    <aside
      id="drawer"
      aria-label={label}
      data-open={open || undefined}
      className={drawer({ open })}
    >
      {children}
    </aside>
  );
}
