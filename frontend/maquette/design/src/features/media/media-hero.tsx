// The hero of a media sheet — the banner, the title, the metadata line, the
// rating — and the trailer row beneath it, or the sentence that says there is
// none. The element carrying `data-part="hero"` is this one and no other.
import { useTranslation } from "react-i18next";
import { Icon } from "../../ui/icon";
import { SkeletonLine } from "../../ui/state-surfaces";
import { useMediaReference, type MediaSheet, type Trailer } from "./reference";
import type { MediaSheetFields } from "./sheet-fields";
import { heroImage, heroMeta, heroNote, heroText, heroTitle, heroWrap, trailerPlay, trailerRow, trailerSource } from "./variants";

export function MediaHero({
  title,
  sheet,
  isFilm,
  artwork,
  trailer,
  inFlight,
}: {
  title: string;
  sheet: (MediaSheet & MediaSheetFields) | null;
  isFilm: boolean;
  artwork: string | null;
  trailer: Trailer | null;
  /** Whether the sheet's read is still out — a missing part is then a skeleton, never an answer. */
  inFlight: boolean;
}) {
  const { icons } = useMediaReference();
  const { t } = useTranslation();
  return (
    <>
      <div
        className={heroWrap({ poster: Boolean(artwork) })}
        data-part="hero"
        data-no-poster={!artwork || undefined}
      >
        <div
          className={heroImage({ poster: Boolean(artwork) })}
          data-part="hero/background"
          aria-hidden="true"
          style={
            artwork ? { backgroundImage: `url('${artwork}')` } : undefined
          }
        ></div>
        <div className={heroText()} data-part="hero/content">
          <h2 className={heroTitle()} data-part="hero/title">{title.split(" (")[0]}</h2>
          <p className={heroMeta()}>
            {/* FIELD BY FIELD, NEVER BLOCK BY BLOCK, and this line is where the
                difference shows. Gated on the whole sheet being null, a
                placeholder carrying the title and not the year printed « année
                inconnue · Série » — an assertion about the KIND of a medium
                whose kind is in flight, in the wave that forbids exactly that.
                The year, the kind and the runtime are three separate answers,
                and each waits for its own. */}
            {sheet?.y || sheet?.k || !inFlight ? (
              <>
                {sheet?.y || (inFlight ? <SkeletonLine width="short" /> : t("screens.media.yearUnknown"))}
                {" · "}
                {sheet?.k
                  ? isFilm
                    ? t("common.film")
                    : t("common.series")
                  : inFlight
                    ? <SkeletonLine width="short" />
                    : t("common.series")}
                {sheet?.duree ? ` · ${sheet.duree} ${t("screens.media.minutesShort")}` : ""}
              </>
            ) : (
              <SkeletonLine width="half" />
            )}{" "}
            {sheet?.g ? (
              <>
                <br />
                {sheet.g}
              </>
            ) : (
              <>
                <br />
                {inFlight ? <SkeletonLine width="short" /> : t("screens.media.genresUnknown")}
              </>
            )}{" "}
            {sheet && !isFilm && sheet.status ? (
              <>
                <br />
                {t("screens.media.seriesStatus", {
                  // french-ok: the INTERPOLATION placeholder, named by
                // `seriesStatus` in fr.json — renaming this half alone
                // leaves « Série {{statut}} » on screen.
                statut: sheet.status.toLowerCase(),
                })}
              </>
            ) : (
              ""
            )}
          </p>
          {sheet?.note ? (
            <span className={heroNote()}>
              <Icon paths={icons.star} />
              {String(sheet.note).replace(".", ",")}
              <span
                style={{
                  color: "var(--color-muted-foreground)",
                  fontWeight: 400,
                }}
              >
                {" "}
                {t("screens.media.ratingSource")}
              </span>
            </span>
          ) : (
            ""
          )}
        </div>
      </div>

      {trailer ? (
        <a
          className={trailerRow()}
          data-part="media/trailer"
          href={`https://www.youtube.com/watch?v=${trailer.key}`}
          target="_blank"
          rel="noopener"
          data-yt={trailer.key}
        >
          <span className={trailerPlay()}>
            <Icon paths={icons.play} />
          </span>{" "}
          <span>
            {t("screens.media.trailer")}
            <small>{trailer.name}</small>
          </span>{" "}
          <span className={trailerSource()}>
            <Icon paths={icons.ext} />
            YouTube
          </span>
        </a>
      ) : inFlight ? (
        <p className="noinfo"><SkeletonLine width="half" /></p>
      ) : (
        <p className="noinfo" data-part="no-info">{t("screens.media.noTrailer")}</p>
      )}
    </>
  );
}
