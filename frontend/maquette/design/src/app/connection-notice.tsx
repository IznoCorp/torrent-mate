// What the interface says about its own connection.
//
// §8 OF THE CONSTITUTION IS THIS FILE. « Un "rien ne se passe" sans raison
// visible est un mensonge par omission. » The worst defect this lot can ship is
// not a lost event — it is a screen that looks current and is not, and that is
// exactly what the header used to do: it carried « Connecté » as a literal,
// beside a green dot, with no connection anywhere in the prototype.
//
// IT KNOWS NO DOMAIN (invariants 7 and 10). It reads a condition and draws it.
// It could not name a media item, a pipeline run or a query key.
//
// TWO PARTS, BECAUSE THEY ANSWER TWO QUESTIONS. The dot in the header answers
// « is this screen live? » at a glance, and it is the element the maquette
// already had — the operator has validated it, so it is made TRUTHFUL rather
// than replaced. The notice below the header answers « then what should I
// do? », and it appears only when there is something to say: a bar that was
// always there would be chrome, and chrome is what a reader learns to stop
// seeing.
import type { ReactElement } from "react";
import { useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import { SIGN_IN_PATH } from "../lib/addresses";
import { go } from "../lib/navigate";
import {
  readCondition,
  subscribeToCondition,
  type RelayCondition,
} from "../lib/relay-condition";
import { reconnectNow } from "../lib/relay";
import { connectionDot, connectionMark, connectionNotice } from "../ui/variants";

/** Where the header keeps its indicator. `display: contents`, so it adds no box. */
const HEADER_ANCHOR = "connection";

/**
 * Reads the connection, and re-renders when it changes.
 *
 * `useSyncExternalStore` and NOT a `useEffect` (invariant 5): the relay is
 * installed at boot and outlives every component, so a subscription that came
 * and went with a mount would be a second lifetime nobody asked for.
 *
 * @returns What the connection is doing.
 */
function useConnection() {
  return useSyncExternalStore(subscribeToCondition, readCondition);
}

/**
 * The header's indicator: one dot, and the word for what it means.
 *
 * @returns The dot, portalled into the header the shell already draws.
 */
export function ConnectionMark(): ReactElement | null {
  const { t } = useTranslation();
  const { condition } = useConnection();
  const anchor = document.getElementById(HEADER_ANCHOR);
  if (anchor === null) return null;
  return createPortal(
    <span
      className={connectionMark()}
      title={t(`connection.${condition}.title`)}
      data-part="shell/connection-mark"
      data-connection={condition}
    >
      <span className={connectionDot({ condition })} />
      <span className="ps-dot__label hidden sm:inline">
        {t(`connection.${condition}.short`)}
      </span>
    </span>,
    anchor,
  );
}

/** The conditions that owe the reader more than a word. */
const NOTICE_CONDITIONS: readonly RelayCondition[] = ["lost", "refused"];

/**
 * The notice: what is wrong, since when, and what to do about it.
 *
 * `data-since` CARRIES THE INSTANT THE COPY WAS DERIVED FROM, so a rule can
 * check the DERIVATION rather than the rendering. A time formatted to the
 * minute cannot distinguish `new Date(currentSince)` from `new Date()` inside a
 * test that runs in one second — and what was really wrong was drift, not
 * substitution: the instant was written at the handshake, so the notice
 * announced the session's start as the age of the data.
 *
 * SINCE WHEN IS THE PART THAT MATTERS. « Reconnexion… » tells a reader to wait;
 * « les informations datent de 14:32 » tells them what they are looking at.
 * NE-DOIT-PAS-5 asks for the real reason, never a code — so `refused` says the
 * session is over, and offers the way back rather than a number.
 *
 * @returns The bar, or nothing at all while the connection is good.
 */
export function ConnectionNotice(): ReactElement | null {
  const { t } = useTranslation();
  const { condition, currentSince } = useConnection();
  if (!NOTICE_CONDITIONS.includes(condition)) return null;
  const since = currentSince === null
    ? null
    : new Date(currentSince).toLocaleTimeString("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
      });
  return (
    <div
      className={connectionNotice({ condition })}
      role="status"
      data-part="shell/connection-notice"
      data-connection={condition}
      {...(currentSince === null ? {} : { "data-since": String(currentSince) })}
    >
      <span>
        {t(`connection.${condition}.body`)}
        {since === null ? "" : ` ${t("connection.since", { time: since })}`}
      </span>
      <button
        type="button"
        className="underline underline-offset-2 font-semibold"
        data-connection-action={condition === "refused" ? "signin" : "retry"}
        onClick={() => {
          if (condition === "refused") go({ to: SIGN_IN_PATH });
          else reconnectNow();
        }}
      >
        {t(`connection.${condition}.action`)}
      </button>
    </div>
  );
}
