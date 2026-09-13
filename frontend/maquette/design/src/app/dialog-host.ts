// THE CONFIRMATION'S VERBS, and the seam the dying engine says them through.
//
// `app/panel-host.ts` is the precedent, term for term: a DESCRIPTOR of facts
// crosses and the markup is the component's. What crossed before was an HTML
// STRING — several hundred characters of template with the escaping done by
// hand at every interpolation, and the heading read back out of it afterwards
// so the layer could name itself.
//
// THE WRITE IS FLUSHED SYNCHRONOUSLY, and it is the same subtlety the panel
// host records. A producer closes the sheet and opens a dialog on its NEXT
// line, and both raise the same shared scrim: a commit landing a frame later
// would clear the scrim out from under the dialog. Flushing keeps the ordering
// every caller already relies on.
import { flushSync } from "react-dom";

import { registerLayer, unwindLayer } from "./layers";
import type { DialogDescriptor } from "../ui/dialog/contract";
import { store } from "../lib/store-access";
import { bridge } from "../lib/shell-doors";

declare global {
  interface Window {
    /** The confirmation's verbs, as the engine's producers say them. */
    __dialog?: {
      open: (descriptor: DialogDescriptor) => void;
      close: (pop?: boolean) => void;
      isOpen: () => boolean;
    };
  }
}

/** The confirmation's verbs, filled at install. The harness publishes them as `window.__dialog`. */
export let dialog: Window["__dialog"];

function isOpen(): boolean {
  return store.read().state.dialogOpen === true;
}

function openDialog(descriptor: DialogDescriptor): void {
  // The layer first, the history entry second — `openPanel`'s own order.
  flushSync(() =>
    store.write({ dialogDescriptor: descriptor, dialogOpen: true }),
  );
  try {
    // B-229. D1's third tier reads « Transient: no URL, but Back still closes
    // it », and names a confirmation as its example. This entry is what makes
    // that true: without it a hardware Back popped the entry UNDER the dialog —
    // a page, or the exit guard — with the dialog still up.
    bridge.pushLayer("dialog");
  } catch (error) {
    // Silence would leave the interface showing a dialog with no history entry
    // recording it, which is the disagreement DOIT-10 forbids and which Back
    // would then resolve by leaving the page.
    // ENGLISH, and not in `fr.json`: a console message is a tool message.
    console.error("openDialog: navigation write failed", error);
    window.__navEchec = true;
  }
}

function closeDialog(pop?: boolean): void {
  if (!isOpen()) return;
  flushSync(() => store.write({ dialogOpen: false }));
  // `pop` means the entry is already being popped by the gesture that got us
  // here; otherwise the layer unwinds its own, through the ladder's latch.
  if (!pop) unwindLayer("dialog");
}

export function installDialogHost(): void {
  dialog = { open: openDialog, close: closeDialog, isOpen };
  // ON THE LADDER, as a registration. What Back does with that rung is B-229
  // and lands in its own commit; being ASKABLE is this one's.
  registerLayer("dialog", { isOpen, close: (pop) => closeDialog(pop) });
}
