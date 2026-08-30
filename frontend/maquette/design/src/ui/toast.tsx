// THE MESSAGE — the interface's one general-purpose « something happened »
// channel, and §8's own surface: « un "rien ne se passe" sans raison visible
// est un mensonge par omission ».
//
// IT IS RENDERED ALWAYS, and that is the mechanism rather than a convenience.
// `role="status"` with `aria-live="polite"` announces what appears INSIDE a
// region that was already in the document; a live region inserted together
// with its content announces nothing at all. The engine's markup was in
// `index.html` from the first parse for exactly that reason, and only
// `#toastmsg` was ever written. Shown is a class here, never an absence — the
// same shape `ui/sheet.tsx` takes for the same reason on a different property.
//
// THE UNDO IS A REAL BUTTON. It was an `innerHTML` string with an inline
// style, injected beside the escaped message — the one write of
// `SURVEY.md` § 1.1's nineteen that a formatter could have made invisible to
// the inventory command. It is a child now, and its `id` stays `#toastundo`
// because rules select it.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";

import { Icon } from "./icon";
import { icons } from "../app/icons";
import { messageClose, messageHost, messageUndo } from "./variants";

export type Message = {
  /** What happened, in the reader's own words. */
  message: string;
  /** What undoes it, where the act was a gesture and a gesture can be wrong. */
  undo?: () => void;
};

export function Toast({
  message,
  shown,
  onClose,
}: {
  // The last message stays rendered while the host is hidden: the message
  // fades out over its own transition, and emptying it on close would blank
  // the text mid-exit — the same reason the sheet keeps its descriptor.
  message: Message | null;
  shown: boolean;
  onClose: () => void;
}): ReactElement {
  const { t } = useTranslation();
  return (
    <div
      id="toast"
      role="status"
      aria-live="polite"
      data-shown={shown || undefined}
      className={messageHost({ shown })}
    >
      <span id="toastmsg">
        {message?.message ?? ""}
        {message?.undo ? (
          <>
            {" "}
            <button
              id="toastundo"
              className={messageUndo()}
              onClick={(event) => {
                event.stopPropagation();
                onClose();
                message.undo?.();
              }}
            >
              {t("message.undo")}
            </button>
          </>
        ) : null}
      </span>
      <button
        id="toastx"
        className={messageClose()}
        aria-label={t("message.close")}
        onClick={onClose}
      >
        <Icon paths={icons.x} className="w-[14px] h-[14px]" />
      </button>
    </div>
  );
}
