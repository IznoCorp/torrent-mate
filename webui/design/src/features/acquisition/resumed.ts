// The auto-resume, SAID (DECIDED 5 = B of maquette-blocked): a block the engine
// lifts leaves « À traiter » on its own, and while he is looking at that tab the
// existing message says it — « This City Is Ours est reparti », one per lift,
// « 3 acquisitions sont reparties » when one lift frees several cards. On any
// other page nothing is said; the badge drops.
//
// THE ENGINE DECIDES THE LIFT (BK2): nothing here guesses one. Between two
// answers of the queue, a card stopped by an external cause that now stands on
// its way again was resumed by the engine; a card that left for anywhere else —
// abandoned, closed — is not « reparti ».
import { useEffect, useRef } from "react";
import i18next from "i18next";
import { acquisitionKey, inFlightCards, todoCards } from "../../lib/arrival-slots";
import type { QueueCard } from "../../lib/engine-queue";
import type { AcquisitionQueue } from "../../lib/queue";
import { toast } from "../../lib/shell-doors";

/**
 * Whether a card is stopped by a cause the engine lifts on its own.
 *
 * @param card A card of « À traiter ».
 * @returns True for an external block.
 */
function liftsOnItsOwn(card: QueueCard): boolean {
  return (card.ladder ?? []).some((rung) => rung.resumes === "auto");
}

/**
 * Says, on « À traiter », the cards the engine resumed since the last answer.
 *
 * The first answer drawn only sets what is held: arriving on the tab after a
 * lift says nothing, it happened elsewhere.
 *
 * @param queue The queue's answer, once held.
 */
export function useResumedMessage(queue: AcquisitionQueue | undefined): void {
  const held = useRef<Map<string, string> | null>(null);
  useEffect(() => {
    if (queue === undefined) return;
    const blocked = new Map(todoCards(queue).filter(liftsOnItsOwn).map((card) => [acquisitionKey(card), card.title]));
    const before = held.current;
    held.current = blocked;
    if (before === null) return;
    const onTheirWay = new Set(inFlightCards(queue).map(acquisitionKey));
    const resumed = [...before].filter(([key]) => !blocked.has(key) && onTheirWay.has(key));
    if (resumed.length === 0) return;
    toast?.show({
      message: resumed.length === 1
        ? i18next.t("screens.acquisition.resumedOne", { title: resumed[0][1] })
        : i18next.t("screens.acquisition.resumedMany", { count: resumed.length }),
    });
  }, [queue]);
}
