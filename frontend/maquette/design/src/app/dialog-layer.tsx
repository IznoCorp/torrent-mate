// The confirmation layer, subscribed to the store.
//
// Its open state and its descriptor live where `panelOpen` and
// `panelDescriptor` already do — a layer's open state is interface state, and
// it is asked of the store rather than of the DOM so a caller asking in the
// middle of its own task gets the truth rather than what React last painted.
import type { ReactElement } from "react";

import { Dialog } from "../ui/dialog";
import type { DialogDescriptor } from "../ui/dialog/contract";
import { useStoreContent } from "../lib/store-access";

export function DialogLayer(): ReactElement {
  const open = useStoreContent((content) => content.state.dialogOpen === true);
  // The last descriptor stays rendered while closed: the dialog scales out
  // over its own transition, and emptying it on close would blank the
  // confirmation mid-exit — the same reason the sheet keeps its descriptor.
  const descriptor = useStoreContent(
    (content) =>
      (content.state.dialogDescriptor ?? null) as DialogDescriptor | null,
  );
  return (
    <Dialog
      descriptor={descriptor}
      open={open}
      close={() => window.__dialog?.close()}
    />
  );
}
