// The « Incomplets » lens: what is owned and not whole, as tiles or as cards.
// It reads its own resource; the other two lenses draw the listing.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { type IncompleteShow } from "./types";
import { useUiState } from "../../lib/store-access";
import { body, posterGrid, section } from "../../ui/variants";
import { posterArtwork, useEngineDrawing } from "../../lib/engine-drawing";
import { libraryCardMarkup } from "./card-markup";
import { tileMarkup } from "../../ui/tile";
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
  const reference = useEngineDrawing();
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
          className={posterGrid()} data-part="grid"
          html={INCOMPLETE.map((show: IncompleteShow) =>
              tileMarkup({
                title: show.t,
                subtitle: t("screens.library.incompleteEpisodes", {
                  owned: show.o,
                  all: show.a,
                }),
                artwork: posterArtwork(reference.icons, show.poster, show.t),
                // The sheet first: the registry answers the first registered
                // key in attribute order, and a tap opens the medium while the
                // long press opens its panel.
                attributes: { "data-mediasheet": show.t, "data-panel": `media:${show.t}` },
              }),
            ).join("")}
        />
      ) : (
        <Markup
          className={section()} data-part="section"
          html={INCOMPLETE.map((show: IncompleteShow) =>
              libraryCardMarkup({
                t: show.t,
                s: t(
                  show.a - show.o > 1
                    ? "screens.library.incompleteSubMany"
                    : "screens.library.incompleteSubOne",
                  { year: show.y, count: show.a - show.o },
                ),
                f: `${show.o}/${show.a}`,
                chip: ["warning", t("screens.library.incompleteChip")],
                poster: show.poster,
                ids: show.ids,
              }),
            ).join("")}
        />
      )}
    </div>
  );
}
