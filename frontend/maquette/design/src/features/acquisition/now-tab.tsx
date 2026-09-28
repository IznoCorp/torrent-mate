import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { mediumCardMarkup } from "./card-markup";
import { inFlightCards } from "./arrival-slots";
import { followOffered } from "./follow-offer";
import { useFollows } from "./queries";
import { useAcquisitionQueue } from "../../lib/queue";
import { useUiState } from "../../lib/store-access";
import { body, emptyNote, section as sectionClass } from "../../ui/variants";
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
  // THE ARRIVALS ARE CARDS HERE (ruling 2), on their way; what is blocked is
  // « À traiter »'s, a tab of its own with its count, and is not repeated here.
  const inflight = queue ? inFlightCards(queue) : [];
  const { data: follows } = useFollows();

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
      {inflight.length > 0 ? (
        <Markup tag="section"
          className={sectionClass()} data-part="section"
          html={sectionInnerMarkup(
            "info",
            t("screens.acquisition.inflight"),
            String(inflight.length),
            // « Suivre », PROPOSED on an arrived series nobody follows (ruling 1).
            inflight.map((card) => mediumCardMarkup(card, followOffered(card, follows ?? []) ? {
              label: t("screens.acquisition.followFoot"),
              attributes: { "data-follow": card.title, "data-follow-ids": JSON.stringify(card.ids) },
            } : undefined)).join(""),
          )}
        />
      ) : null}
    </div>
  );
}
