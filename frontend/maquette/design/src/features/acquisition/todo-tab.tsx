// « À traiter » — what only the operator's hand unblocks (ruling 7).
//
// A TAB OF ITS OWN (ruling 10), drawn in the language « En cours » speaks: a pip
// per section, a counter that is its own link, a section with no card not drawn
// at all. Where a card sits is a function of its state: every card here is
// blocked, and its section says what unblocks it. Never an empty screen
// (DOIT-7): with nothing waiting, it says so and says where the rest is.
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
import { mediumCardMarkup } from "./card-markup";
import { setAsideCards, todoCards } from "../../lib/arrival-slots";
import { Disclosure } from "../../ui/disclosure";
import { useAcquisitionQueue, useStaging } from "../../lib/queue";
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
  // THE ACTS ARE THE ACCOUNT'S (§ 17): a card it may only read draws no foot.
  const rights = useRights();
  if (state.phase !== "ready") {
    return (
      <div className={body()} data-part="surface/body" data-region="acquisition/body">
        {state.phase === "error" ? (
          <SurfaceError subject={t("screens.acquisition.errorTodo")} />
        ) : (
          <div className={sectionClass()} data-part="section"><Skeletons count={3} shape="card" /></div>
        )}
      </div>
    );
  }
  const scenario = state.scen === "loaded" ? "loaded" : "";
  const { data: queue } = useAcquisitionQueue(scenario);
  // THE STAGING READ IS OBSERVED HERE because the panels this tab opens derive
  // their act from it (`queueNow().stuck`): a folder the read does not hold is
  // offered its journey instead of « Résoudre ». An unobserved answer is not
  // read at all on a cold load.
  useStaging(scenario);
  const blocked = queue ? todoCards(queue) : [];
  const setAside = queue ? setAsideCards(queue) : [];
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
          .map((card) => mediumCardMarkup(card, offeredFeet({
            label: t("screens.acquisition.blockedFoot"),
            attributes: { "data-resolution": card.title },
          }, card, rights)))
          .join(""),
      )}
      {section(
        "warning",
        t("screens.acquisition.todoPlexMatch"),
        plexMatches,
        plexMatches
          .map((card) => mediumCardMarkup(card, offeredFeet([
            { label: t("screens.acquisition.plexConfirmFoot"), solid: true, attributes: { "data-plex-confirm": card.title } },
            { label: t("screens.acquisition.plexCorrectFoot"), attributes: { "data-plex-correct": card.title } },
          ], card, rights)))
          .join(""),
      )}
      {section(
        "danger",
        t("screens.acquisition.todoTunnelError"),
        tunnelErrors,
        tunnelErrors
          .map((card) => mediumCardMarkup(card, offeredFeet([
            { label: t("screens.acquisition.todoRequeueFoot"), attributes: { "data-journey-requeue": card.title } },
            { label: t("screens.acquisition.abandonFoot"), attributes: { "data-journey-abandon": card.title } },
          ], card, rights)))
          .join(""),
      )}
      {setAside.length === 0 ? null : (
        <section className={sectionClass()} data-part="section/set-aside">
          <Disclosure summary={<Markup html={sectionInnerMarkup("waiting", t("screens.acquisition.todoSetAside"), String(setAside.length), "")} />}>
            <Markup
              html={setAside
                .map((card) => mediumCardMarkup(card, offeredFeet([
                  { label: t("screens.acquisition.blockedFoot"), attributes: { "data-resolution": card.title } },
                  { label: t("screens.acquisition.deleteFoot"), attributes: { "data-staging-delete": card.title } },
                ], card, rights)))
                .join("")}
            />
          </Disclosure>
        </section>
      )}
    </div>
  );
}
