import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { offeredFeet } from "./act-rights";
import { useRights } from "../../lib/account";
import { mediumCardMarkup } from "./card-markup";
import { inFlightCards } from "../../lib/arrival-slots";
import { followOffered } from "./follow-offer";
import { useFollows } from "./queries";
import { useAcquisitionQueue } from "../../lib/queue";
import { useUiState } from "../../lib/store-access";
import { body, emptyNote, section as sectionClass } from "../../ui/variants";
import { Markup, emptyNoteMarkup, sectionInnerMarkup } from "../../ui/markup";
import { NOW_SEARCH_KEY, NowFilters, nowFilterInForce, nowSortInForce } from "./now-filters";
import { orderNow } from "./now-order";

// « En cours » — what moves, and nothing else: ONE section, « En vol », and
// « rien en cours » when nothing does. What waits to be taken is taken from the
// follow's sheet; what reached the library reads in the Médiathèque's
// « Récents »; what was not found reads on the follow; what waits for the
// operator's hand is « À traiter ».
//
// THE ZONE IS THE TAB'S SIBLING, BEFORE ITS BODY, whatever the read says: the
// filter and sort zone keeps its place from tab to tab (`acquisition-zone.tsx`).
export function NowTab(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  // EVERY HOOK BEFORE THE PLACEHOLDER'S RETURN. Called after it, the loaded body
  // rendered two hooks more than the pass before, and React logged #310 on the
  // console each time a non-ready state gave way to a loaded one (B-320).
  //
  // WHICH WORLD. The prototype carries two and the harness switches between
  // them; the key carries it, so a surface never reads the other one's cards.
  const scenario = state.scen === "loaded" ? "loaded" : "";
  const { data: queue, error: queueError, isError } = useAcquisitionQueue(scenario);
  // REFUSED AND HOLDING NOTHING: a refused REFETCH keeps the cache's data (`isError` stays true), and that data stays drawn.
  const queueRefused = isError && queue === undefined;
  const { data: follows } = useFollows();
  // THE ACTS ARE THE ACCOUNT'S (§ 17): a card it may only read draws no foot.
  const rights = useRights();

  // A REFUSED READ IS SAID WHATEVER THE PHASE: only the harness sets the error phase, so a real refusal
  // would otherwise leave the loading face.
  if (state.phase !== "ready" || queueRefused) {
    return (
      <>
        <NowFilters />
        <div
          className={body()}
          data-part="surface/body"
          data-region="acquisition/body"
        >
          {state.phase === "error" || queueRefused ? (
            <SurfaceError subject={t("screens.acquisition.errorNow")} failure={queueError ?? undefined} />
          ) : (
            <div className={sectionClass()} data-part="section">
              <Skeletons count={4} shape="card" />
            </div>
          )}
        </div>
      </>
    );
  }

  // THE ARRIVALS ARE CARDS HERE (ruling 2), on their way; what is blocked is
  // « À traiter »'s, a tab of its own with its count, and is not repeated here.
  const onTheirWay = queue ? inFlightCards(queue) : [];
  // THE ONE DERIVATION of the list, the pill's count and its panel's: the filter and the sort in force, the search applied.
  const inflight = orderNow(onTheirWay, nowFilterInForce(state), nowSortInForce(state), String(state[NOW_SEARCH_KEY] ?? ""));

  return (
    <>
      <NowFilters shown={inflight.length} />
      <div
        className={body()}
        data-part="surface/body"
        data-region="acquisition/body"
      >
        <div className="note" data-part="note">
          <b>{t("screens.acquisition.nowNoteLead")}</b>
          {t("screens.acquisition.nowNoteRest")}
        </div>
        {inflight.length === 0 ? (
          <Markup
            className={emptyNote()}
            data-part="empty-state"
            html={emptyNoteMarkup(t(onTheirWay.length === 0 ? "screens.acquisition.nowEmpty" : "screens.acquisition.nowFilterEmpty"), "")}
          />
        ) : null}
        {inflight.length > 0 ? (
          <Markup
            tag="section"
            className={sectionClass()}
            data-part="section"
            html={sectionInnerMarkup(
              "info",
              t("screens.acquisition.inflight"),
              String(inflight.length),
              // « Suivre », PROPOSED on an arrived series nobody follows (ruling 1).
              inflight
                .map((card) =>
                  mediumCardMarkup(
                    card,
                    offeredFeet(
                      followOffered(card, follows ?? [])
                        ? {
                            label: t("screens.acquisition.followFoot"),
                            attributes: {
                              "data-follow": card.title,
                              "data-follow-ids": JSON.stringify(card.ids),
                            },
                          }
                        : undefined,
                      card,
                      rights,
                    ),
                  ),
                )
                .join(""),
            )}
          />
        ) : null}
      </div>
    </>
  );
}
