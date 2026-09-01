// « Découvrir » — the third tab of Acquisition.
// WHAT THIS TAB DRAWS AND NEVER FILLS: `#sugitems`, `#sugload` and the
// deck's `.deckbody`. The suggestion machinery stays the fragment's, and that
// is a measured decision rather than an unfinished one — `advanceDeck` mutates
// the deck's own DOM in place (it inserts a card at the back, decrements every
// `data-depth`, writes an inline transform on the outgoing one and removes it
// 440 ms later), and its own comment says why: a replaced node cannot animate.
// React owning that markup would restore the string it last rendered on the
// next repaint and undo the gesture four rules measure. So the containers are
// React's and their CONTENT is the fragment's: React manages zero children
// there, so neither world removes the other's nodes — the arrangement
// `paintSelBar` already has, one level down.
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { SurfaceError } from "../../ui/state-surfaces";
import { Icon } from "../../ui/icon";
import { useAcquisitionReference } from "./reference";
import { useUiState } from "../../lib/store-access";
import { body, filterZone, liveDot, liveEmphasis, liveStrip, loadFooter, pillBar, pillScroll, section as sectionClass, surfaceError, viewSwitch, viewSwitchButton, viewSwitchWrap } from "../../ui/variants";

// « Découvrir » — what one might want, which is the only surface here that
// asks nothing of the operator: the bar's badge never counts it.
//
// THE CONTAINERS ARE DRAWN HERE AND FILLED BY THE FRAGMENT. `#sugitems`,
// `#sugload` and the deck's `.deckbody` keep their content from `fillSug` /
// `sugFoot` / `refreshDeck`, because the deck's gesture mutates its own DOM in
// place and a replaced node cannot animate. React renders zero children into
// them, so neither world removes the other's nodes.
export function DiscoverTab(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const {
    icons,
    skelCardsInner,
    fillSug,
    sugFoot,
    mountDeck,
    deckHTML,
  } = useAcquisitionReference();

  // THE FRAGMENT FILLS WHAT THIS DRAWS, and it has to be asked AFTER the
  // drawing: `render()` calls the same verbs, but it calls them before React
  // has put the containers in the document, so they find nothing. The deck at
  // rest is filled the same way — its markup was part of the page's own HTML
  // in the legacy, and it is written into the body here.
  useEffect(() => {
    const deckBody = document.querySelector(".deckbody");
    if (state.sugMode === "deck" && state.phase === "ready" && deckBody) {
      // ONLY IF THE PILE IS NOT ALREADY THERE. Rewriting it on every commit
      // destroys the gesture in flight: « Passer » writes the order to the
      // store, which re-renders this component, whose effect would then replace
      // the very nodes `advanceDeck` is animating — and a replaced node cannot
      // animate, which is the whole reason this machinery stayed imperative.
      // Rebuilding a spent pile is `refreshDeck`'s business, and it does it.
      if (!deckBody.querySelector(".deck")) {
        deckBody.innerHTML = deckHTML();
        mountDeck();
      }
      return;
    }
    // AND WHAT THE LEGACY CLEARED BY REWRITING. The deck at rest is written
    // into the body by the line above, and React does not know that node: it
    // was not rendered, so a re-render leaves it in place — the pile stayed at
    // the top of the page under every other state, measured. The legacy got
    // this for free by rewriting `#view` wholesale; here it is said out loud.
    for (const stale of document.querySelectorAll(".body > .deck")) {
      stale.remove();
    }
    if (document.querySelector("#sugitems")) {
      fillSug();
      sugFoot();
    }
  });
  const modes = [
    ["list", icons.list, t("screens.acquisition.modeList")],
    ["poster", icons.grid, t("screens.acquisition.modePosters")],
    ["deck", icons.cards, t("screens.acquisition.modeDeck")],
  ] as const;

  const selector = (
    <div className={filterZone()} data-region="acquisition/filters">
      <div className={pillBar()}>
        <div className={pillScroll()} data-part="pill/list"></div>
        <div className={viewSwitchWrap()}>
          <div className={viewSwitch()} data-part="view/switch">
            {modes.map(([id, paths, label]) => (
              <button
                className={viewSwitchButton()}
                key={id}
                aria-pressed={state.sugMode === id}
                data-sugmode={id}
                aria-label={label}
              >
                <Icon paths={paths} />
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  // The deck at rest is the whole body: no notes, no containers, just the pile
  // the fragment fills.
  if (state.sugMode === "deck" && state.phase === "ready") {
    return (
      <>
        {selector}
        <div className={`${body()} deckbody`} data-part="surface/body"></div>
      </>
    );
  }

  return (
    <>
      {selector}
      <div
        className={`${body()}${state.sugMode === "deck" ? " deckbody" : ""}`}
        data-part="surface/body"
      >
        <div className="note" data-part="note">
          <b>{t("screens.acquisition.discoverNoteLead")}</b>
          {t("screens.acquisition.discoverNoteRest")}
        </div>
        {state.tmdb ? (
          <div className={liveStrip()} data-part="live-activity">
            <span className={liveDot()}></span>
            <span>
              {t("screens.acquisition.liveBefore")}
              <b className={liveEmphasis()}>{t("screens.acquisition.liveSuggestions")}</b>
              {t("screens.acquisition.liveMiddle")}
              <b className={liveEmphasis()}>{t("screens.acquisition.liveOwned")}</b>
              {t("screens.acquisition.liveAfter")}
            </span>
          </div>
        ) : (
          <div
            className={surfaceError()} data-part="surface-error" role="alert"
            style={{
              borderColor:
                "color-mix(in oklab,var(--color-warning) 45%,transparent)",
              background: "color-mix(in oklab,var(--color-warning) 8%,transparent)",
            }}
          >
            <b style={{ color: "var(--color-warning)" }}>
              {t("screens.acquisition.tmdbDisconnected")}
            </b>
            {t("screens.acquisition.tmdbBefore")}
            <b>{t("screens.acquisition.tmdbNotes")}</b>
            {t("screens.acquisition.tmdbMiddle")}
            <br />
            <br />
            {t("screens.acquisition.tmdbAfterBreaks")}
            <b>{t("screens.acquisition.tmdbSimilar")}</b>
            {t("screens.acquisition.tmdbEnd")}
            <button data-tmdb="1">
              {t("screens.acquisition.connectTmdb")}
            </button>
          </div>
        )}
        <div className="note" data-part="note">
          <b>{t("screens.acquisition.callsNoteLead")}</b>
          {t("screens.acquisition.callsNoteBefore")}
          <b>{t("screens.acquisition.callsNoteInner")}</b>
          {t("screens.acquisition.callsNoteAfter")}
        </div>
        <div className="note" data-part="note">
          <b>{t("screens.acquisition.gesturesNoteLead")}</b>
          {t("screens.acquisition.gesturesNoteBefore")}
          <em>{t("screens.acquisition.gesturesNoteInner")}</em>
          {t("screens.acquisition.gesturesNoteAfter")}
        </div>
        {state.phase === "loading" ? (
          <div
            className={sectionClass()} data-part="section"
            dangerouslySetInnerHTML={{ __html: skelCardsInner(4) }}
          />
        ) : state.phase === "error" ? (
          <SurfaceError subject={t("screens.acquisition.errorSuggestions")} />
        ) : null}
        {/* FILLED BY THE FRAGMENT, never by React — see this file's header. */}
        <div id="sugitems" hidden={state.phase !== "ready"}></div>
        <div
          id="sugload"
          className={loadFooter()}
          hidden={state.phase !== "ready" || state.sugMode === "deck"}
        ></div>
        <div className="note" data-part="note">
          <b>{t("screens.acquisition.tmdbMissingNoteLead")}</b>
          {t("screens.acquisition.tmdbMissingNoteRest")}
        </div>
      </div>
    </>
  );
}
