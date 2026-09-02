// The « Incomplets » lens: what is owned and not whole, as tiles or as cards.
// It reads its own resource; the other two lenses draw the listing.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { useLibraryReference, type IncompleteShow } from "./reference";
import { useUiState } from "../../lib/store-access";
import { body, section } from "../../ui/variants";
import { Markup } from "../../ui/markup";

export function IncompleteLens({ rows }: {
  /**
   * What is owned and not whole. It is READ BY THE PAGE, not here, and that is
   * the whole of this prop's reason: a hook moved into a component the page
   * mounts only on this lens is a read that starts when the lens is ENTERED,
   * and the lens then paints its count line over an empty body until it lands.
   * Where the read lives is a behaviour, and a cut is not where a behaviour
   * changes.
   */
  rows: IncompleteShow[];
}): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { cardHTML, tileHTML } = useLibraryReference();
  const INCOMPLETE = rows;
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
        <Markup
          className="gallery" data-part="grid"
          html={INCOMPLETE.map((show: IncompleteShow) =>
              tileHTML(
                show,
                t("screens.library.incompleteEpisodes", {
                  owned: show.o,
                  all: show.a,
                }),
              ),
            ).join("")}
        />
      ) : (
        <Markup
          className={section()} data-part="section"
          html={INCOMPLETE.map((show: IncompleteShow) =>
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
            ).join("")}
        />
      )}
    </div>
  );
}
