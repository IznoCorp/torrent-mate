// THE FRAME, COMPOSED — one element in the root, and one installer beside it.
//
// WHY IT EXISTS RATHER THAN LIVING IN `app/shell.tsx`. The shell is the BOOT:
// the order in which seams, store, cache, relay and root are installed. The
// frame is what is on screen that is not a surface's content — the chrome, the
// layers, the entry. Two subjects, and the shell was already at 380 of
// invariant 6's 400 non-blank lines with none of the frame in it. Every part
// this lot converts joins HERE, so the boot gains a line once instead of a line
// per surface.
//
// IT RENDERS INSIDE THE REACT ROOT, which `app/shell.tsx` re-parents into
// `.device` before the first render — so a layer drawn here resolves its
// `position: absolute` against the phone frame exactly as the engine's own
// markup does, and paints in the document order the stacking already assumes.
import type { ReactElement } from "react";

import { ActionButton } from "./action-button";
import { BottomSlot } from "./bottom-slot";
import { NavigationDrawer } from "./drawer";
import { installAppearance } from "./appearance";
import { installLayerRegistry } from "./layer-registry";
import { DialogLayer } from "./dialog-layer";
import { installDialogHost } from "./dialog-host";
import { MessageLayer } from "./message-layer";
import { installMessagePresence } from "./message-presence";
import { installToastHost } from "./toast-host";
import { TabBar } from "./tab-bar";

/**
 * Everything on screen that is not a surface's content.
 *
 * Rendered once, with the shell, never with a route: the chrome outlives every
 * navigation and a bar mounted per route is a bar that is rebuilt by one.
 */
// Published as this module evaluates, which is before the engine's own boot
// writes anything: the engine imports through `app/shell.tsx`, and the shell
// imports this file with the rest of the frame.
installMessagePresence();
installToastHost();
installLayerRegistry();
installDialogHost();
installAppearance();

export function Frame(): ReactElement {
  return (
    <>
      <ActionButton />
      <BottomSlot />
      <TabBar />
      <NavigationDrawer />
      <DialogLayer />
      <MessageLayer />
    </>
  );
}
