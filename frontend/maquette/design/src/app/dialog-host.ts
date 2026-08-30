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

import { registerLayer } from "./layer-registry";
import { refuseDialogBlock, type DialogDescriptor } from "../ui/dialog/contract";

declare global {
  interface Window {
    /** The confirmation's verbs, as the engine's producers say them. */
    __dialog?: {
      open: (descriptor: DialogDescriptor) => void;
      close: () => void;
      isOpen: () => boolean;
    };
    /** The probe that proves the layer REFUSES a block nobody declared. */
    __unknownDialog?: () => void;
  }
}

function isOpen(): boolean {
  return window.__store.read().state.dialogOpen === true;
}

function openDialog(descriptor: DialogDescriptor): void {
  flushSync(() =>
    window.__store.write({ dialogDescriptor: descriptor, dialogOpen: true }),
  );
}

function closeDialog(): void {
  if (!isOpen()) return;
  flushSync(() => window.__store.write({ dialogOpen: false }));
}

export function installDialogHost(): void {
  window.__dialog = { open: openDialog, close: closeDialog, isOpen };
  // ON THE LADDER, as a registration. What Back does with that rung is B-229
  // and lands in its own commit; being ASKABLE is this one's.
  registerLayer("dialog", { isOpen, close: () => closeDialog() });
  // Called as a plain function, never rendered: the dispatcher refuses before
  // it reads anything else, which is what makes the refusal provable from
  // outside.
  window.__unknownDialog = () =>
    refuseDialogBlock({ type: "ceci-n-existe-pas" });
}
