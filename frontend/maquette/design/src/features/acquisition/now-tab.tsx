import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { mediumCardMarkup } from "./card-markup";
import { inFlightCards, slotArrivals } from "./arrival-slots";
import { useAcquisitionQueue, useStaging } from "../../lib/queue";
import { useUiState } from "../../lib/store-access";
import { body, crossReference, crossReferenceLink, crossReferenceStrong, emptyNote, section as sectionClass } from "../../ui/variants";
import { Markup, emptyNoteMarkup, sectionInnerMarkup } from "../../ui/markup";

// « En cours » — what moves, and nothing else: ONE section, « En vol », and
// « rien en cours » when nothing does. What waits to be taken is taken from the
// follow's sheet; what reached the library reads in the Médiathèque's
// « Récents »; what was not found reads on the follow; what waits for the
// operator's hand is « À traiter ».
export function NowTab(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();

  if (state.phase !== "ready") {
    return (
      <div className={body()} data-part="surface/body" data-region="acquisition/body">
        {state.phase === "error" ? (
          <SurfaceError subject={t("screens.acquisition.errorNow")} />
        ) : (
          <div className={sectionClass()} data-part="section"><Skeletons count={4} shape="card" /></div>
        )}
      </div>
    );
  }

  // WHICH WORLD. The prototype carries two and the harness switches between
  // them; the key carries it, so a surface never reads the other one's cards.
  const scenario = state.scen === "loaded" ? "loaded" : "";
  const { data: queue } = useAcquisitionQueue(scenario);
  const { data: staging } = useStaging(scenario);
  // THE ARRIVALS ARE CARDS HERE (ruling 2), on their way; what is blocked is
  // « À traiter »'s, a tab of its own, and read here only for the note below.
  const blocked = [...(queue?.blocked ?? []), ...slotArrivals(queue?.arrivals ?? []).blocked];
  const inflight = queue ? inFlightCards(queue) : [];
  const stuck = staging?.stuck ?? [];

  return (
    <div className={body()} data-part="surface/body" data-region="acquisition/body">
      <div className="note" data-part="note">
        <b>{t("screens.acquisition.nowNoteLead")}</b>
        {t("screens.acquisition.nowNoteRest")}
      </div>
      {inflight.length === 0 ? (
        <Markup
          className={emptyNote()} data-part="empty-state"
          html={emptyNoteMarkup(t("screens.acquisition.nowEmpty"), "")}
        />
      ) : null}
      {stuck.length > 0 ? (
        <button className={crossReference()} data-part="cross-reference" data-go="arr">
          {blocked.length > 0
            ? t("screens.acquisition.crossrefFromAcquisition")
            : ""}
          <b className={crossReferenceStrong()}>{stuck.length}</b>
          {t("screens.acquisition.crossrefMedium")}
          {stuck.length > 1 ? t("screens.acquisition.crossrefPlural") : ""}
          {t("screens.acquisition.crossrefToTreat")}
          {stuck.length > 1
            ? t("screens.acquisition.crossrefEnteredMany")
            : t("screens.acquisition.crossrefEnteredOne")}
          {t("screens.acquisition.crossrefWithoutFollow")}
          <span className={crossReferenceLink()}>{t("screens.acquisition.crossrefLink")}</span>
        </button>
      ) : null}
      {inflight.length > 0 ? (
        <Markup tag="section"
          className={sectionClass()} data-part="section"
          html={sectionInnerMarkup(
            "info",
            t("screens.acquisition.inflight"),
            String(inflight.length),
            inflight.map((card) => mediumCardMarkup(card)).join(""),
          )}
        />
      ) : null}
    </div>
  );
}
