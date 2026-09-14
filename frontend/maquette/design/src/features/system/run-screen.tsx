// One passage, at its own address.
//
// WHAT IT IS TODAY: the address exists and names the run, so a row in the list
// leads somewhere real. What a reader needs to see of a passage — its steps
// with their counts, its reasons, its raw output folded away — is the screen's
// subject and is drawn by the phase that owns it.
import { useParams } from "@tanstack/react-router";
import type { ReactElement } from "react";

/**
 * The run screen.
 *
 * @returns The passage's own surface.
 */
export function RunScreen(): ReactElement {
  const { runUid } = useParams({ from: "/run/$runUid" });
  return (
    <div data-part="run" data-region="run/body">
      <span data-part="run/identifier">{runUid}</span>
    </div>
  );
}
