// The obligation's OUTCOME, as a block of the torrent's panel — the in-app message.
//
// THE NOTICE OF THE APPLICATION, in the outcome's tone: good news for an
// obligation met, information for one released. It leads the panel, above the
// facts, because it is what the push sent the reader there to read (the
// operator, 2026-10-03: « des messages in-app sur le torrent en question »).
import type { ReactElement } from "react";
import { registerBlock } from "../../ui/panel/contract";
import { SurfaceError } from "../../ui/state-surfaces";
import type { OutcomeMessage } from "./obligation-outcome";

declare module "../../ui/panel/contract" {
  interface PanelBlockMap {
    obligationOutcome: { message: OutcomeMessage };
  }
}

/**
 * The message: its lead in bold, then its why.
 *
 * @param props.block The block, carrying the message.
 * @returns The block.
 */
function ObligationOutcomeBlock({ block }: { block: { message: OutcomeMessage } }): ReactElement {
  const { message } = block;
  return (
    <div data-part="torrents/obligation-outcome" data-outcome={message.outcome} data-reason={message.reason}>
      <SurfaceError tone={message.tone} part="torrents/obligation-message">
        <b>{message.lead}</b>
        {message.why}
      </SurfaceError>
    </div>
  );
}

registerBlock("obligationOutcome", (block) => <ObligationOutcomeBlock block={block} />);
