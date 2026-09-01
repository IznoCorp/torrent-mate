// The people of a media sheet: the director or the creator, then the cast
// strip — or the sentence that says the cast is unknown.
import { useTranslation } from "react-i18next";
import { useMediaReference, type MediaSheet } from "./reference";
import type { MediaSheetFields } from "./sheet-fields";
import { factsPanel, keyValueRow, sectionHeading } from "../../ui/variants";
import { castCaption, castFigure, castList, castPortrait } from "./variants";

export function MediaCast({
  sheet,
  isFilm,
}: {
  sheet: (MediaSheet & MediaSheetFields) | null;
  isFilm: boolean;
}) {
  const { CAST, initials } = useMediaReference();
  const { t } = useTranslation();
  return (
    <div>
      <h2 className={sectionHeading()} data-part="heading" style={{ marginBottom: "8px" }}>
        {isFilm
          ? t("screens.media.castHeadingFilm")
          : t("screens.media.castHeadingSeries")}
      </h2>
      <div className={factsPanel()} data-part="panel" style={{ marginBottom: "10px" }}>
        <div className={keyValueRow()} data-part="key-value">
          <span>
            {isFilm
              ? t("screens.media.director")
              : t("screens.media.creator")}
          </span>
          <span>
            {(isFilm ? sheet?.real : sheet?.crea) ??
              t("screens.media.unknown")}
          </span>
        </div>
      </div>
      {sheet?.cast?.length ? (
        <div
          className={castList()}
          data-part="cast"
          data-noswipe=""
          tabIndex={0}
          role="group"
          aria-label={
            isFilm
              ? t("screens.media.castHeadingFilm")
              : t("screens.media.castHeadingSeries")
          }
        >
          {sheet.cast.map((cast) => (
            <figure key={cast.n} className={castFigure()}>
              <span className={castPortrait()} data-part="cast/avatar">
                {CAST[cast.n] ? (
                  <img src={CAST[cast.n]} alt="" loading="lazy" />
                ) : (
                  initials(cast.n)
                )}
              </span>
              <figcaption className={castCaption()}>
                <b>{cast.n}</b>
                <span>{cast.r || t("screens.media.roleUnknown")}</span>
              </figcaption>
            </figure>
          ))}
        </div>
      ) : (
        <p className="noinfo" data-part="no-info">{t("screens.media.castUnknown")}</p>
      )}
    </div>
  );
}
