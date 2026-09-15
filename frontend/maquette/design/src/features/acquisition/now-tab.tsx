import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { mediumCardMarkup } from "./card-markup";
import { useAcquisitionQueue, useStaging } from "../../lib/queue";
import { type QueueCard } from "../../lib/engine-queue";
import { useUiState } from "../../lib/store-access";
import { body, crossReference, crossReferenceLink, crossReferenceStrong, emptyNote, section as sectionClass } from "../../ui/variants";
import { Markup, emptyNoteMarkup, sectionInnerMarkup } from "../../ui/markup";

// « En cours » — five sections of urgency, one coloured pip each, and a counter
// that IS its own link. The page's own note calls this the language reference
// for the three other pages.
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
  const takeable = queue?.takeable ?? [];
  const blocked = queue?.blocked ?? [];
  const inflight = queue?.inFlight ?? [];
  const notfound = queue?.notFound ?? [];
  const doneToday = queue?.doneToday ?? [];
  const stuck = staging?.stuck ?? [];
  const nothing =
    takeable.length +
      blocked.length +
      inflight.length +
      notfound.length +
      doneToday.length ===
    0;

  const section = (
    pip: string,
    title: string,
    cards: QueueCard[],
    inner: string,
    note?: string,
  ) =>
    cards.length === 0 || inner === "" ? null : (
      <Markup tag="section"
        className={sectionClass()} data-part="section"
        html={sectionInnerMarkup(pip, title, String(cards.length), inner, note)}
      />
    );

  return (
    <div className={body()} data-part="surface/body" data-region="acquisition/body">
      <div className="note" data-part="note">
        <b>{t("screens.acquisition.nowNoteLead")}</b>
        {t("screens.acquisition.nowNoteRest")}
      </div>
      {nothing ? (
        <Markup
          className={emptyNote()} data-part="empty-state"
          html={emptyNoteMarkup(
              t("screens.acquisition.nowEmptyTitle"),
              `${t("screens.acquisition.nowEmptyBodyBefore")}<b>${t("screens.acquisition.nowEmptyBodyCount")}</b>${t("screens.acquisition.nowEmptyBodyAfter")}`,
            )}
        />
      ) : null}
      {section(
        "warning",
        t("screens.acquisition.takeable"),
        takeable,
        takeable
          .map((card) =>
            mediumCardMarkup(card, {
              label: t("screens.acquisition.takeableFoot"),
              solid: true,
              attributes: { "data-take": card.title },
            }),
          )
          .join(""),
      )}
      {section(
        "danger",
        t("screens.acquisition.blocked"),
        blocked,
        blocked
          .map((card) =>
            mediumCardMarkup(card, {
              label: t("screens.acquisition.blockedFoot"),
              attributes: { "data-resolution": card.title },
            }),
          )
          .join(""),
      )}
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
      {section(
        "info",
        t("screens.acquisition.inflight"),
        inflight,
        inflight.map((card) => mediumCardMarkup(card)).join(""),
      )}
      {section(
        "waiting",
        t("screens.acquisition.notfound"),
        notfound,
        notfound.map((card) => mediumCardMarkup(card)).join(""),
        `<b>${t("screens.acquisition.notfoundNoteLead")}</b>${t("screens.acquisition.notfoundNoteRest")}`,
      )}
      {section(
        "success",
        t("screens.acquisition.doneToday"),
        doneToday,
        doneToday.map((card) => mediumCardMarkup(card)).join(""),
      )}
    </div>
  );
}
