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
  /* WHERE FOCUS LANDS WHEN THE DIALOG OPENS, and it is the WAY OUT.
     `app/focus.ts` moves focus into a layer that opens: it asks for the
     layer's own named entry, `[autofocus]`, and falls back to the first
     control the reader would reach anyway. A confirmation that names none puts
     focus on its first button, which is the ACT: on the restart confirmation
     that handed a keyboard's or a switch control's next Enter the
     household-wide restart the dialog exists to prevent.

     So the way out names itself, and no producer has to remember to: the first
     action that dismisses is the entry. A dialog offering none — the dry run
     and the real run, where both buttons act — keeps the default, because
     inventing a way out that the descriptor does not offer would be worse than
     the first-button rule it replaces. */
  const entryAt = descriptor
    ? descriptor.actions.findIndex((action) => action.dismiss)
    : -1;
  // A `Record<string, string>`, the way `action.target` is: an attribute NAME
  // React does not know is a name TypeScript does not know either, and a
  // literal spread into JSX is checked for it. The same door the descriptor's
  // own `data-*` come through.
  const namedEntry: Record<string, string> = { autofocus: "" };
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
            {/* THE WAY OUT IS NAMED, and `data-dialog-dismiss` is that name. It
                was `id="dlgcancel"` — an id the engine's producer invented and
                two rules selected — and an id on a control a DESCRIPTOR may
                repeat is a contract that breaks the second time a dialog offers
                two ways out. It is written so a false state omits the
                attribute, which is what every boolean state attribute here
                does.

                IT IS NOT `data-dismiss`, and the qualifier is not decoration:
                the engine's own delegation reads `closest.dataset.dismiss` and
                calls `dismissSug(Number(…))` on it. An empty value is falsy so
                the collision was inert — and would have become `dismissSug(0)`
                the first time anyone gave this attribute a value. Found by a
                reader of the seams. */}
            {descriptor.actions.map((action, at) => (
              <button
                key={at}
                data-part="dialog/button"
                {...(action.tone === "danger" ? { "data-tone": "danger" } : {})}
                {...(action.dismiss ? { "data-dialog-dismiss": "" } : {})}
                {...(at === entryAt ? namedEntry : {})}
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
