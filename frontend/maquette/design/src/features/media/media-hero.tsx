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
  failed,
}: {
  title: string;
  sheet: (MediaSheet & MediaSheetFields) | null;
  /** True for a film, false for a series, null while the kind is in flight. */
  isFilm: boolean | null;
  artwork: string | null;
  trailer: Trailer | null;
  /** Whether the sheet's read is still out — a missing part is then a skeleton, never an answer. */
  inFlight: boolean;
  /** Whether the sheet's read FAILED — an absence is then unread, not answered. */
  failed: boolean;
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
                whose kind is in flight. The year, the kind and the runtime are
                three separate answers, and each waits for its own. */}
            {/* NO SHEET AT ALL is not the same as a sheet with fields
                missing, and this line has to keep both. A read that landed on
                nothing — an identifier nobody carries — has no year and no kind
                to wait for, and printing « année inconnue · Série » there
                asserts the KIND of a medium that does not exist. One honest
                sentence covers it, which is what the screen said before this
                line learned its fields. */}
            {sheet ? (
              <>
                {sheet?.y || (inFlight
                  ? <SkeletonLine width="short" />
                  // A FAILURE IS NOT AN ANSWER, here as under the trailer. « année
                  // inconnue » says the year is not known of this medium; after a
                  // 502 what is true is that nobody read it.
                  : t(failed ? "screens.media.yearUnread" : "screens.media.yearUnknown"))}
                {" · "}
                {isFilm === null ? (
                  inFlight
                    ? <SkeletonLine width="short" />
                    // THE KIND KEPT ITS BARE ANSWER between the two twins added
                    // for exactly this: over a failed read the line said
                    // « année non lue · inconnu Genres non lus », one word in
                    // three claiming the kind is unknown of this medium where
                    // the other two say nobody read it.
                    : t(failed ? "screens.media.kindUnread" : "screens.media.unknown")
                ) : isFilm ? (
                  t("common.film")
                ) : (
                  t("common.series")
                )}
                {sheet?.duree ? ` · ${sheet.duree} ${t("screens.media.minutesShort")}` : ""}
              </>
            ) : inFlight ? (
              <SkeletonLine width="half" />
            ) : (
              t("screens.media.metadataUnknown")
            )}{" "}
            {sheet?.g ? (
              <>
                <br />
                {sheet.g}
              </>
            ) : (
              <>
                <br />
                {inFlight
                  ? <SkeletonLine width="short" />
                  : t(failed ? "screens.media.genresUnread" : "screens.media.genresUnknown")}
              </>
            )}{" "}
            {sheet && isFilm === false && sheet.status ? (
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
          ) : inFlight ? (
            // THE RATING IS A PART LIKE THE OTHERS, and drawing nothing for it
            // left the hero one line shorter until the read landed — an absence
            // that is neither an answer nor a wait.
            <SkeletonLine width="short" />
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
        // A SENTENCE THAT SPEAKS FOR THE PROVIDER cannot be printed over a
        // read that never reached it. « Aucune bande-annonce fournie par le
        // provider » is an answer; after a failure the honest word is that
        // nobody knows.
        <p className="noinfo" data-part="no-info">
          {t(failed ? "screens.media.trailerUnread" : "screens.media.noTrailer")}
        </p>
      )}
    </>
  );
}
