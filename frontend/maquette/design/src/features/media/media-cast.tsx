// The people of a media sheet: the director or the creator, then the cast
// strip — or the sentence that says the cast is unknown.
import { useTranslation } from "react-i18next";
import { SkeletonLine } from "../../ui/state-surfaces";
import { useMediaReference, type MediaSheet } from "./reference";
import type { MediaSheetFields } from "./sheet-fields";
import { factsPanel, keyValueRow, sectionHeading } from "../../ui/variants";
import { castCaption, castFigure, castList, castPortrait } from "./variants";

export function MediaCast({
  sheet,
  isFilm,
  inFlight,
  failed,
}: {
  sheet: (MediaSheet & MediaSheetFields) | null;
  /** True for a film, false for a series, null while the kind is in flight. */
  isFilm: boolean | null;
  /** Whether the sheet's read FAILED — an absence is then unread, not answered. */
  failed: boolean;
  /** Whether the sheet's read is still out — a missing part is then a skeleton, never an answer. */
  inFlight: boolean;
}) {
  const { CAST, initials } = useMediaReference();
  const { t } = useTranslation();
  return (
    <div>
      <h2 className={sectionHeading()} data-part="heading" style={{ marginBottom: "8px" }}>
        {/* A WAIT THAT NEVER ENDS IS NOT A WAIT. With the read landed on
            nothing — a stale bookmark — the kind is unknown for good, and a
            shimmering line over it says « any moment now » forever, on a screen
            whose body is not even marked busy. The hero's own line answers
            « inconnu » there, and these two must answer the same. */}
        {isFilm === null ? (
          inFlight ? <SkeletonLine width="half" /> : t("screens.media.unknown")
        ) : isFilm ? (
          t("screens.media.castHeadingFilm")
        ) : (
          t("screens.media.castHeadingSeries")
        )}
      </h2>
      <div className={factsPanel()} data-part="panel" style={{ marginBottom: "10px" }}>
        <div className={keyValueRow()} data-part="key-value">
          <span>
            {isFilm === null ? (
              inFlight ? <SkeletonLine width="short" /> : t("screens.media.unknown")
            ) : isFilm ? (
              t("screens.media.director")
            ) : (
              t("screens.media.creator")
            )}
          </span>
          <span>
            {(isFilm === false ? sheet?.crea : isFilm ? sheet?.real : (sheet?.real ?? sheet?.crea)) ??
              (inFlight ? <SkeletonLine width="short" /> : t("screens.media.unknown"))}
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
          // THE LABEL A SCREEN READER HEARS IS THE KIND TOO, and with the
          // kind unknown the honest name is the section's subject rather than
          // a guess at which of the two it is.
          aria-label={
            isFilm === null
              ? t("screens.media.unknown")
              : isFilm
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
      ) : inFlight ? (
        <p className="noinfo"><SkeletonLine width="half" /></p>
      ) : (
        <p className="noinfo" data-part="no-info">
          {t(failed ? "screens.media.castUnread" : "screens.media.castUnknown")}
        </p>
      )}
    </div>
  );
}
