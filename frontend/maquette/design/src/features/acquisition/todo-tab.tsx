// « À traiter » — what only the operator's hand unblocks (ruling 7).
//
// A TAB OF ITS OWN (ruling 10), drawn in the language « En cours » speaks: a pip
// per section, a counter that is its own link, a section with no card not drawn
// at all. Where a card sits is a function of its state: every card here is
// blocked, and its section says what unblocks it. Never an empty screen
// (DOIT-7): with nothing waiting, it says so and says where the rest is.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { mediumCardMarkup } from "./card-markup";
import { slotArrivals } from "./arrival-slots";
import { useAcquisitionQueue } from "../../lib/queue";
import { type QueueCard } from "../../lib/engine-queue";
import { useUiState } from "../../lib/store-access";
import { body, emptyNote, section as sectionClass } from "../../ui/variants";
import { Markup, emptyNoteMarkup, sectionInnerMarkup } from "../../ui/markup";

/**
 * The « À traiter » tab's body.
 *
 * @returns The body.
 */
export function TodoTab(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  if (state.phase !== "ready") {
    return (
      <div className={body()} data-part="surface/body" data-region="acquisition/body">
        {state.phase === "error" ? (
          <SurfaceError subject={t("screens.acquisition.errorNow")} />
        ) : (
          <div className={sectionClass()} data-part="section"><Skeletons count={3} shape="card" /></div>
        )}
      </div>
    );
  }
  const scenario = state.scen === "loaded" ? "loaded" : "";
  const { data: queue } = useAcquisitionQueue(scenario);
  const blocked = [...(queue?.blocked ?? []), ...slotArrivals(queue?.arrivals ?? []).blocked];
  // A STEP THAT CANNOT FINISH is unblocked by a relaunch, never by an identity
  // pick: such a card offers « Relancer » and no « Résoudre ».
  const tunnelErrors = blocked.filter((card) => card.failedStep !== undefined);
  // A MATCH TO CONFIRM is answered on the match itself, never by an identity pick.
  const plexMatches = blocked.filter((card) => card.plexMatch !== undefined);
  const toResolve = blocked.filter((card) => card.failedStep === undefined && card.plexMatch === undefined);
  const section = (pip: string, title: string, cards: QueueCard[], inner: string) =>
    cards.length === 0 ? null : (
      <Markup tag="section"
        className={sectionClass()} data-part="section"
        html={sectionInnerMarkup(pip, title, String(cards.length), inner)}
      />
    );
  return (
    <div className={body()} data-part="surface/body" data-region="acquisition/body">
      {blocked.length === 0 ? (
        <Markup
          className={emptyNote()} data-part="empty-state"
          html={emptyNoteMarkup(t("screens.acquisition.todoEmptyTitle"), t("screens.acquisition.todoEmptyBody"))}
        />
      ) : null}
      {section(
        "danger",
        t("screens.acquisition.todoResolve"),
        toResolve,
        toResolve
          .map((card) => mediumCardMarkup(card, {
            label: t("screens.acquisition.blockedFoot"),
            attributes: { "data-resolution": card.title },
          }))
          .join(""),
      )}
      {section(
        "warning",
        t("screens.acquisition.todoPlexMatch"),
        plexMatches,
        plexMatches
          .map((card) => mediumCardMarkup(card, [
            { label: t("screens.acquisition.plexConfirmFoot"), solid: true, attributes: { "data-plex-confirm": card.title } },
            { label: t("screens.acquisition.plexCorrectFoot"), attributes: { "data-plex-correct": card.title } },
          ]))
          .join(""),
      )}
      {section(
        "danger",
        t("screens.acquisition.todoTunnelError"),
        tunnelErrors,
        tunnelErrors
          .map((card) => mediumCardMarkup(card, {
            label: t("screens.acquisition.todoRequeueFoot"),
            attributes: { "data-journey-requeue": card.title },
          }))
          .join(""),
      )}
    </div>
  );
}
