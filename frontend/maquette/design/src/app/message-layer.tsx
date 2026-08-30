// The message layer, subscribed to its host.
//
// It is a component of its own rather than a slice of `app/frame.tsx` because
// what it subscribes to is not the store: the message's own host holds the
// text and the shown flag, so only this layer re-renders when a message comes
// and goes. That is the same reason `app/message-presence.ts` exists — a store
// write between a press and the click that follows destroys the click (B-247).
import { useSyncExternalStore } from "react";
import type { ReactElement } from "react";

import { hideMessage, readMessage, subscribeToMessage } from "./toast-host";
import { Toast } from "../ui/toast";

export function MessageLayer(): ReactElement {
  const state = useSyncExternalStore(subscribeToMessage, readMessage);
  return (
    <Toast
      message={state.message}
      shown={state.shown}
      onClose={hideMessage}
    />
  );
}
