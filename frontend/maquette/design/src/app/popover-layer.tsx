// The popover layer, subscribed to its host.
import { useSyncExternalStore } from "react";
import type { ReactElement } from "react";

import { readPopover, subscribeToPopover } from "./popover-host";
import { Popover } from "../ui/popover";

export function PopoverLayer(): ReactElement | null {
  const state = useSyncExternalStore(subscribeToPopover, readPopover);
  return <Popover anchor={state.anchor} content={state.content} />;
}
