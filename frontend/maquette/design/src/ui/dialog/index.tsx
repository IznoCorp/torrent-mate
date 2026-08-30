// THE CONFIRMATION LAYER — `#dlg`, drawn from a descriptor.
//
// It renders at the same id and the same identity class the document declared,
// with `role="dialog"` and `aria-modal="true"` — and it takes its NAME from
// the descriptor's heading rather than by reading back markup it has just
// written. That read existed because the engine handed `openDlg` an HTML
// string and the heading was only discoverable inside it; a dialog does not
// take its name from its content the way a named section does, and an
// `aria-labelledby` id would have to be kept in step by every template that
// opened one.
//
// CLOSED IS A CLASS, NEVER AN ABSENCE: the transition that carries it in and
// out needs both states on the same element, and the engine's `#dlg` likewise
// kept its content after closing.
import type { ReactElement } from "react";

import {
  refuseDialogBlock,
  type DialogBlock,
  type DialogDescriptor,
} from "./contract";
import { Icon } from "../icon";
import { icons } from "../../app/icons";
import {
  dialog,
  dialogActions,
  dialogButton,
  dialogDryRun,
  dialogDryRunDrawing,
  dialogHeading,
  dialogManifest,
  dialogManifestEntry,
  dialogManifestValue,
  dialogParagraph,
  dialogWarning,
} from "../variants";

function Block({ block }: { block: DialogBlock }): ReactElement {
  switch (block.type) {
    case "paragraph":
      return (
        <p className={dialogParagraph()}>
          {block.runs.map((run, at) =>
            run.strong ? <b key={at}>{run.text}</b> : <span key={at}>{run.text}</span>,
          )}
        </p>
      );
    case "dryRun":
      return (
        <div className={dialogDryRun()} data-part="dialog/dry-run">
          <Icon paths={icons.eye} className={dialogDryRunDrawing()} />
          {block.text}
        </div>
      );
    case "manifest":
      return (
        <ul className={dialogManifest()} data-part="dialog/manifest">
          {block.entries.map((entry, at) => (
            <li key={at} className={dialogManifestEntry()}>
              {entry.text}
              <b className={dialogManifestValue()}>{entry.value}</b>
            </li>
          ))}
        </ul>
      );
    case "warning":
      return (
        <div className={dialogWarning()}>
          <b>{block.strong}</b> {block.text}
        </div>
      );
    default:
      return refuseDialogBlock(block);
  }
}

export function Dialog({
  descriptor,
  open,
  close,
}: {
  descriptor: DialogDescriptor | null;
  open: boolean;
  close: () => void;
}): ReactElement {
  return (
    <div
      id="dlg"
      data-part="dialog"
      role="dialog"
      aria-modal="true"
      aria-label={open ? descriptor?.heading : undefined}
      data-open={open || undefined}
      className={dialog({ open })}
    >
      {descriptor ? (
        <>
          <h2 className={dialogHeading()}>{descriptor.heading}</h2>
          {descriptor.body.map((block, at) => (
            <Block key={at} block={block} />
          ))}
          <div className={dialogActions()}>
            {descriptor.actions.map((action, at) => (
              <button
                key={at}
                data-part="dialog/button"
                {...(action.tone === "danger" ? { "data-tone": "danger" } : {})}
                {...(action.target ?? {})}
                className={dialogButton({ tone: action.tone ?? "neutral" })}
                onClick={() => {
                  // THE ORDER IS THE ENGINE'S: close first, act second. A
                  // producer's act may open the next layer on its very next
                  // line, and that layer raises the SAME shared scrim.
                  if (action.dismiss || action.run) close();
                  action.run?.();
                }}
              >
                {action.text}
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
