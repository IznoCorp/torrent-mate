// The « Incomplets » lens: what is owned and not whole, as tiles or as cards.
// It reads its own resource; the other two lenses draw the listing.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { useLibraryReference, type IncompleteShow } from "./reference";
import { useLibraryIncomplete } from "./queries";
import { useUiState } from "../../lib/store-access";
import { body, section } from "../../ui/variants";

export function IncompleteLens(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { cardHTML, tileHTML } = useLibraryReference();
  const { data: INCOMPLETE = [] } = useLibraryIncomplete();
  return (
    <div className={body()} data-part="surface/body" data-region="library/body">
      <div className="note" data-part="note">
        <b>{t("screens.library.incompleteNoteLead")}</b>
        {t("screens.library.incompleteNoteMiddle")}
        <code>{t("screens.library.incompleteUnknown")}</code>
        {t("screens.library.incompleteNoteAfterUnknown")}
        <code>{t("screens.library.incompleteInvented")}</code>
        {t("screens.library.incompleteNoteEnd")}
      </div>
      {state.libMode === "grid" ? (
        <div
          className="gallery" data-part="grid"
          dangerouslySetInnerHTML={{
            __html: INCOMPLETE.map((show: IncompleteShow) =>
              tileHTML(
                show,
                t("screens.library.incompleteEpisodes", {
                  owned: show.o,
                  all: show.a,
                }),
              ),
            ).join(""),
          }}
        />
      ) : (
        <div
          className={section()} data-part="section"
          dangerouslySetInnerHTML={{
            __html: INCOMPLETE.map((show: IncompleteShow) =>
              cardHTML({
                t: show.t,
                s: t(
                  show.a - show.o > 1
                    ? "screens.library.incompleteSubMany"
                    : "screens.library.incompleteSubOne",
                  { year: show.y, count: show.a - show.o },
                ),
                f: `${show.o}/${show.a}`,
                chip: ["warning", t("screens.library.incompleteChip")],
              }),
            ).join(""),
          }}
        />
      )}
    </div>
  );
}
