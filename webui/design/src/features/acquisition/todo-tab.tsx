// « À traiter » — every block, in the app or elsewhere (Q7 of 2026-10-01).
//
// A TAB OF ITS OWN (ruling 10), ONE FLAT LIST (DECIDED 1 of maquette-blocked,
// amending ruling 10's sections): no section says what unblocks a card — its
// cause line does — and the one-pill filter and sort stand above it, the
// order by urgency by default (`todo-order.ts`). Never an empty screen
// (DOIT-7): with nothing blocked, it says so and says where the rest is; a
// filter that keeps nothing says so in its own words.
//
// WHAT HE SET ASIDE IS LAST, AND FOLDED (ruling 16): « Mis de côté » is not
// forgotten — its files are still on the machine — but it waits for nobody's
// hand but his, when he chooses; so it closes the tab, shut, and counts neither
// in the tab's number nor in the bar's badge.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { offeredFeet } from "./act-rights";
import { useRights } from "../../lib/account";
import { blockDoor, mediumCardMarkup } from "./card-markup";
import { closureFoot } from "./closure-markup";
import { setAsideCards, todoCards } from "../../lib/arrival-slots";
import { causeOf, orderTodo } from "./todo-order";
import { TodoPills, todoFilterInForce, todoSortInForce } from "./todo-pills";
import { useResumedMessage } from "./resumed";
import { Disclosure } from "../../ui/disclosure";
import { useAcquisitionQueue, useStaging } from "../../lib/queue";
import { type QueueCard } from "../../lib/engine-queue";
import { useUiState } from "../../lib/store-access";
import { body, emptyNote, foldedCards, section as sectionClass } from "../../ui/variants";
import { Markup, emptyNoteMarkup, sectionInnerMarkup } from "../../ui/markup";

/**
 * The « À traiter » tab's body.
 *
 * @returns The body.
 */
export function TodoTab(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  // EVERY HOOK BEFORE THE PLACEHOLDER'S RETURN — `NowTab`'s reason (B-320).
  const scenario = state.scen === "loaded" ? "loaded" : "";
  const { data: queue, error: queueError, isError } = useAcquisitionQueue(scenario);
  // REFUSED AND HOLDING NOTHING — `NowTab`'s reason.
  const queueRefused = isError && queue === undefined;
  // THE STAGING READ IS OBSERVED HERE because the panels this tab opens derive
  // their act from it (`queueNow().stuck`): a folder the read does not hold is
  // offered its journey instead of « Résoudre ». An unobserved answer is not
  // read at all on a cold load.
  useStaging(scenario);
  // THE ACTS ARE THE ACCOUNT'S (§ 17): a card it may only read draws no foot.
  const rights = useRights();
  // A BLOCK THE ENGINE LIFTS while he looks at this tab is said (DECIDED 5).
  useResumedMessage(queue);
  // A REFUSED READ IS SAID WHATEVER THE PHASE — `NowTab`'s reason.
  if (state.phase !== "ready" || queueRefused) {
    return (
      <div
        className={body()}
        data-part="surface/body"
        data-region="acquisition/body"
      >
        {state.phase === "error" || queueRefused ? (
          <SurfaceError subject={t("screens.acquisition.errorTodo")} failure={queueError ?? undefined} />
        ) : (
          <div className={sectionClass()} data-part="section">
            <Skeletons count={3} shape="card" />
          </div>
        )}
      </div>
    );
  }
  const blocked = queue ? todoCards(queue) : [];
  const setAside = queue ? setAsideCards(queue) : [];
  const filter = todoFilterInForce(state);
  const drawn = orderTodo(blocked, filter, todoSortInForce(state));
  // EACH CARD OFFERS WHAT UNBLOCKS IT, by its cause — never by a section.
  const feet = (card: QueueCard) => {
    const cause = causeOf(card);
    // A STEP THAT CANNOT FINISH is unblocked by a relaunch, never by an identity
    // pick: such a card offers « Relancer » and no « Résoudre ».
    if (cause === "step")
      return offeredFeet([
        { label: t("screens.acquisition.todoRequeueFoot"), attributes: { "data-journey-requeue": card.title } },
        { label: t("screens.acquisition.abandonFoot"), attributes: { "data-journey-abandon": card.title } },
      ], card, rights);
    // A MATCH TO CONFIRM is answered on the match itself, never by an identity pick.
    if (cause === "plex")
      return offeredFeet([
        { label: t("screens.acquisition.plexConfirmFoot"), solid: true, attributes: { "data-plex-confirm": card.title } },
        { label: t("screens.acquisition.plexCorrectFoot"), attributes: { "data-plex-correct": card.title } },
      ], card, rights);
    // A CLOSED TUNNEL leads to its sheet; « Marquer comme vu » is in its panel
    // (DECIDED 2), never a « × » on the card.
    if (cause === "closed") return closureFoot(card);
    if (cause === "resolve")
      return offeredFeet({ label: t("screens.acquisition.blockedFoot"), attributes: { "data-resolution": card.title } },
        card, rights);
    // AN EXTERNAL BLOCK'S FOOT HOLDS ITS DOOR ALONE (DECIDED 6), where its
    // cause is settled; « Abandonner » stays in its panel.
    return blockDoor(card, rights);
  };
  return (
    <div
      className={body()}
      data-part="surface/body"
      data-region="acquisition/body"
    >
      {blocked.length === 0 ? (
        <Markup
          className={emptyNote()}
          data-part="empty-state"
          html={emptyNoteMarkup(
            t("screens.acquisition.todoEmptyTitle"),
            t("screens.acquisition.todoEmptyBody"),
          )}
        />
      ) : (
        <>
          <TodoPills shown={drawn.length} />
          {drawn.length === 0 ? (
            <Markup
              className={emptyNote()}
              data-part="empty-state"
              html={emptyNoteMarkup(t("screens.acquisition.todoFilterEmpty"), "")}
            />
          ) : (
            <Markup
              tag="section"
              className={sectionClass()}
              data-part="section"
              html={drawn.map((card) => mediumCardMarkup(card, feet(card))).join("")}
            />
          )}
        </>
      )}
      {setAside.length === 0 ? null : (
        <section className={sectionClass()} data-part="section/set-aside">
          <Disclosure
            summary={
              <Markup
                html={sectionInnerMarkup(
                  "waiting",
                  t("screens.acquisition.todoSetAside"),
                  String(setAside.length),
                  "",
                )}
              />
            }
          >
            <Markup
              className={foldedCards()}
              html={setAside
                .map((card) =>
                  mediumCardMarkup(
                    card,
                    offeredFeet(
                      [
                        {
                          label: t("screens.acquisition.blockedFoot"),
                          attributes: { "data-resolution": card.title },
                        },
                        {
                          label: t("screens.acquisition.deleteFoot"),
                          attributes: { "data-staging-delete": card.title },
                        },
                      ],
                      card,
                      rights,
                    ),
                  ),
                )
                .join("")}
            />
          </Disclosure>
        </section>
      )}
    </div>
  );
}
