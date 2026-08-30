// THE FLOATING ACTION BUTTON — one decision point, reading two facts.
//
// A PAGE says whether it has a primary action at all (`actionButton` in the
// navigation table). A MESSAGE on screen says whether that action may be shown
// right now. Written in two places, the second writer erases the first — the
// page's own answer — and the button comes back on a page that never had one.
// That is the engine's own comment on `refreshActionButton`, and it is why this
// component computes the visibility once, from both facts, rather than being
// told to show or hide.
//
// WHY A MESSAGE HIDES IT, and it is a measurement rather than a preference. The
// message and the button are anchored to the same bottom-right corner by
// construction, and the message paints over it: the close target measures 24 by
// 24 and lands INSIDE the button's 52 by 52 box, so the reader aiming at
// « close » is aiming at « add ». Measured on the served copy with
// `elementFromPoint`, not deduced.
//
// AND IT COMES BACK WHEN THE MESSAGE HAS FINISHED LEAVING, not when it starts —
// and ONLY on that path. The message fades out over its own transition; a
// button restored on the first frame of that fade is a target appearing under a
// finger still travelling towards the close it was aiming at. The wait is the
// message's exit duration and nothing else. A page arriving with an action of
// its own waits for nothing: delaying THAT would make the button late on every
// navigation, which is a rendering change with no defect behind it.
import { useEffect, useRef, useState } from "react";
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";

import { icons } from "./icons";
import { useMessagePresent } from "./message-presence";
import { rowFor } from "./navigation";
import { Icon } from "../ui/icon";
import { useUiState } from "../lib/store-access";
import { addAction, addActionDrawing } from "../ui/variants";

// The message's exit duration. It is the one number this component owns, and
// it is the message's, not the button's — they move together or the target
// appears under a finger that is still travelling.
const AFTER_A_MESSAGE_MS = 200;

export function ActionButton(): ReactElement {
  const { t } = useTranslation();
  const state = useUiState();
  const wanted = rowFor(state.page as string | undefined)?.actionButton === true;
  const messageShown = useMessagePresent();

  // Held back only on the message's FALLING edge. `wasShown` is a ref rather
  // than state because it decides whether an effect arms a timer, and a second
  // render is not what should tell it.
  const [heldBack, setHeldBack] = useState(false);
  const wasShown = useRef(messageShown);
  useEffect(() => {
    const leaving = wasShown.current && !messageShown;
    wasShown.current = messageShown;
    if (!leaving) return;
    setHeldBack(true);
    const timer = window.setTimeout(
      () => setHeldBack(false),
      AFTER_A_MESSAGE_MS,
    );
    return () => window.clearTimeout(timer);
  }, [messageShown]);

  return (
    <button
      id="fab"
      data-part="shell/add-action"
      aria-label={t("navigation.actionButtonLabel")}
      className={addAction()}
      hidden={!wanted || messageShown || heldBack}
      // The « ＋ » ALWAYS means « follow »: the mode must never stay stuck from
      // a previous resolution.
      onClick={() =>
        window.__screens.add(String(state.addQ ?? ""), "follow")
      }
    >
      <Icon
        paths={icons.plus}
        strokeWidth={2.4}
        className={addActionDrawing()}
      />
    </button>
  );
}
