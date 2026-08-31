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
import {
  clearRefusedDepartures,
  departAll,
  outboxDepth,
  refusedDepartures,
  subscribeToOutbox,
} from "./outbox";

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
  const waiting = useWaiting();
  const anchor = document.getElementById(HEADER_ANCHOR);
  if (anchor === null) return null;
  return createPortal(
    <span
      className={connectionMark()}
      title={t(`connection.${condition}.title`)}
      data-part="shell/connection-mark"
      data-connection={condition}
      {...(waiting === 0 ? {} : { "data-pending": String(waiting) })}
    >
      <span className={connectionDot({ condition })} />
      <span className="ps-dot__label hidden sm:inline">
        {t(`connection.${condition}.short`)}
      </span>
    </span>,
    anchor,
  );
}

/**
 * Reads how many mutations are waiting to depart.
 *
 * WHY THIS FILE IS WHERE IT IS DRAWN. A mutation issued with the network gone
 * RESOLVES — rejecting would roll it back, and it has not failed — so the
 * operator sees their action land and has no way of knowing it has not left.
 * That is §8 exactly: « un "rien ne se passe" sans raison visible est un
 * mensonge par omission », read from the other end. What is waiting is said
 * here because this is already the one surface that answers « is this screen
 * telling me the truth about the server? ».
 *
 * @returns The number waiting.
 */
function useWaiting(): number {
  return useSyncExternalStore(subscribeToOutbox, outboxDepth);
}

/**
 * Reads how many queued mutations the server refused when they finally left.
 *
 * WHY THIS IS DRAWN AND NOT MERELY RECORDED. A mutation held offline resolved,
 * so the operator watched their action land; if the server then refuses it on
 * the replay, the queue empties and the notice disappears EXACTLY as it does on
 * success. The action is gone and nothing ever said so — which is the same
 * defect as the queue jamming, with the visibility removed instead of the
 * progress. §8: « un "rien ne se passe" sans raison visible est un mensonge par
 * omission. »
 *
 * @returns How many were refused.
 */
function useRefused(): number {
  return useSyncExternalStore(subscribeToOutbox, () => refusedDepartures().length);
}

/**
 * What the notice's one button is, decided ONCE.
 *
 * THE NAME, THE WORDS AND THE ACTION CAME FROM THREE SEPARATE LADDERS, and two
 * of them tested their conditions in a different order. On a lost connection
 * with a refusal recorded and nothing waiting, the button said « Réessayer
 * maintenant » and CLEARED the refusal instead of reconnecting: pressing the
 * reconnect button did not reconnect, and silently discarded the record the
 * repair exists to show. That is the same « lie by suggestion » the previous
 * repair was written for, reintroduced by writing the decision three times.
 *
 * @param condition What the connection is doing.
 * @param owed Whether the condition itself owes the reader an explanation.
 * @param waiting How many mutations are queued.
 * @param refused How many were refused when they finally left.
 * @returns The button's name, its words, and what it does — one decision.
 */
function whatToOffer(
  condition: RelayCondition,
  owed: boolean,
  waiting: number,
  refused: number,
): { name: string; words: string; act: () => void } {
  if (condition === "refused") {
    return {
      name: "signin",
      words: "connection.refused.action",
      act: () => go({ to: SIGN_IN_PATH }),
    };
  }
  // THE CONNECTION FIRST, because a dead socket is what the operator can act on
  // and a queued mutation cannot depart over it anyway.
  if (owed) {
    return {
      name: "retry",
      words: `connection.${condition}.action`,
      act: () => reconnectNow(),
    };
  }
  if (waiting > 0) {
    return { name: "send", words: "connection.send", act: () => void departAll() };
  }
  return {
    name: "acknowledge",
    words: "connection.acknowledge",
    act: () => clearRefusedDepartures(),
  };
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
  const waiting = useWaiting();
  const refused = useRefused();
  const owed = NOTICE_CONDITIONS.includes(condition);
  // SOMETHING WAITING IS ENOUGH ON ITS OWN. A mutation can be held while the
  // stream is perfectly healthy — a request refused by a network the socket
  // survived — and that is the case where saying nothing is worst: the screen
  // looks entirely current and one of the operator's actions has not left.
  if (!owed && waiting === 0 && refused === 0) return null;
  const since = currentSince === null
    ? null
    : new Date(currentSince).toLocaleTimeString("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
      });
  const offer = whatToOffer(condition, owed, waiting, refused);
  return (
    <div
      className={connectionNotice({ condition })}
      role="status"
      data-part="shell/connection-notice"
      data-connection={condition}
      {...(waiting === 0 ? {} : { "data-pending": String(waiting) })}
      {...(refused === 0 ? {} : { "data-refused": String(refused) })}
      {...(currentSince === null ? {} : { "data-since": String(currentSince) })}
    >
      <span>
        {owed ? t(`connection.${condition}.body`) : ""}
        {owed && since !== null ? ` ${t("connection.since", { time: since })}` : ""}
        {waiting === 0 ? "" : `${owed ? " " : ""}${t("connection.waiting", { count: waiting })}`}
        {refused === 0 ? ""
          : `${owed || waiting > 0 ? " " : ""}${t("connection.refusedOnSending", { count: refused })}`}
      </span>
      <button
        type="button"
        className="underline underline-offset-2 font-semibold"
        data-connection-action={offer.name}
        onClick={offer.act}
      >
        {t(offer.words)}
      </button>
    </div>
  );
}
