// design/src/pages/library.tsx
// The fifth migrated PAGE, and the first whose CONTENT the fragment used to
// write after the page was drawn: legacy `viewLibrary()` returned a skeleton —
// an empty `#libitems`, an empty `#libcount` — and `fillLib()` / `libFoot()` /
// `paintLibCount()` filled it as the operator scrolled, `fillLib` replacing the
// element outright (`box.outerHTML = …`). Two worlds writing one container is
// what tore the React root down once already, so the list and its loading move
// here WITH the page rather than leaving a seam behind.
//
// Markup is TRANSPLANTED, not translated. The rows go through `libRowHTML` and
// `tileHTML`, reused VERBATIM: they carry the `data-*` the document-level
// delegation reads (`data-tile`, `data-del`, `data-swipeact`, `data-panel`,
// `data-mediasheet`), and re-deriving that markup here would drift the one thing
// that seam depends on being byte-exact.
//
// WHAT DOES NOT MOVE: the selection bar. `paintSelBar()` creates and removes a
// `.selbar` inside `#device`, a node React never draws — so the legacy owns it
// from creation to removal, and this component only asks for a repaint after it
// renders, exactly as `fillLib` did. Moving it would put a second portal where
// the current arrangement already has one owner.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { useUiState } from "../../lib/store-access";
import { IncompleteLens } from "./incomplete-lens";
import { CountLine, SortLabel } from "./library-count";
import { INCOMPLETE_COUNT, LibraryHead } from "./library-head";
import { LibraryList } from "./library-list";
import { body, countLine, countLineAction, statusDot } from "../../ui/variants";

export function LibraryPage(): ReactElement | null {
  const state = useUiState();
  const { t } = useTranslation();
  // The « incomplets » lens reads its own resource, in its own file. The
  // « récent » lens does NOT: it draws the same `LibraryList`, which is the
  // listing in the source's own order — a second read of the same rows would
  // be a second answer to one question (§13), and `RECENT` is the fixture that
  // arrangement made redundant.

  if (state.libLens === "inc") {
    return (
      <>
        <LibraryHead />
        <div className={countLine()} data-part="count-line" data-region="library/count-line">
          <span className={statusDot({ tone: "warning" })} data-part="status-dot"></span>
          <span>{t("screens.library.incompleteTitle")}</span>
          <b style={{ marginLeft: "auto" }}>{INCOMPLETE_COUNT}</b>
        </div>
        <IncompleteLens />
      </>
    );
  }

  if (state.libLens === "rec") {
    return (
      <>
        <LibraryHead />
        <div className={countLine()} data-part="count-line" data-region="library/count-line">
          <span>{t("screens.library.recentTitle")}</span>
        </div>
        <div className={body()} data-part="surface/body" data-region="library/body">
          <div className="note" data-part="note">
            <b>{t("screens.library.recentNoteLead")}</b>
            {t("screens.library.recentNoteMiddle")}
            <em>{t("screens.library.recentNoteEmphasis")}</em>
            {t("screens.library.recentNoteEnd")}
          </div>
          <LibraryList />
        </div>
      </>
    );
  }

  return (
    <>
      <LibraryHead />
      <div className={countLine()} data-part="count-line" data-region="library/count-line">
        <CountLine />
        <button className={`${countLineAction()} linkbtn`} data-selmode="1">
          {t("screens.library.select")}
        </button>
        <button className={countLineAction()} style={{ marginLeft: 12 }} data-sort="1">
          <SortLabel />
        </button>
      </div>
      <div className={body()} data-part="surface/body" data-region="library/body">
        <div className="note" data-part="note">
          <b>{t("screens.library.mediaNoteLead")}</b>
          {t("screens.library.mediaNoteMiddle")}
          <code>{t("screens.library.mediaNoteRoute")}</code>
          {t("screens.library.mediaNoteEnd")}
        </div>
        <LibraryList />
        <div className="note" data-part="note">
          <b>{t("screens.library.loadingNoteLead")}</b>
          {t("screens.library.loadingNoteMiddle")}
          <code>{t("screens.library.loadingNoteDatabase")}</code>
          {t("screens.library.loadingNoteEnd")}
        </div>
      </div>
    </>
  );
}

