// What the library holds of a medium: not owned, a film owned, or a series
// with its seasons, aired and owned counts and completeness — and the season
// list beneath.
import { useTranslation } from "react-i18next";
import { useMediaReference, type MediaSheet } from "./reference";
import { SkeletonLine } from "../../ui/state-surfaces";
import { SeasonList } from "./season-list";
import type { CatalogSeason, MediaSheetFields } from "./sheet-fields";
import { factsPanel, keyValueRow, sectionHeading, statusDot } from "../../ui/variants";

export function MediaLibraryFacts({
  sheet,
  isFilm,
  owns,
  ownershipKnown,
  inFlight,
  followed,
  seasons,
  own,
  aired,
  pct,
  catalog,
  catalogEp,
  title,
  seasonsInFlight,
  sheetInFlight,
}: {
  sheet: (MediaSheet & MediaSheetFields) | null;
  /** True for a film, false for a series, null while the kind is unknown. */
  isFilm: boolean | null;
  /** Whether the sheet's read is still out — a wait is drawn only while there is one. */
  inFlight: boolean;
  owns: boolean;
  /**
   * Whether ownership has arrived at all. This block CHOOSES A BRANCH on it —
   * not owned, film owned, series owned — so a default here is not one wrong
   * field but a wrong block: « Possédés 0 », « Complétude 0 % » with a warning
   * pip and a season list of missing episodes, about a medium the reader may
   * not own, replaced by « non » a moment later.
   */
  ownershipKnown: boolean;
  followed: boolean;
  seasons: [number, number | null, number][];
  own: number;
  aired: number;
  pct: number | null;
  catalog: CatalogSeason[];
  catalogEp: number;
  title: string;
  /** Whether the seasons' read is still out — a missing count is then a skeleton, never « inconnu ». */
  seasonsInFlight: boolean;
  /** Whether the SHEET's read is still out — the season list's episode lists come from it. */
  sheetInFlight: boolean;
}) {
  const { baseTitle } = useMediaReference();
  const { t } = useTranslation();
  return (
    <div>
      <h2 className={sectionHeading()} data-part="heading" style={{ marginBottom: "6px" }}>
        {t("screens.media.library")}
      </h2>
      <div className={factsPanel()} data-part="panel">
      {!ownershipKnown ? (
        // WAITING ONLY WHILE THERE IS SOMETHING TO WAIT FOR. Once the read has
        // answered — with nothing, or with a failure — ownership is unknown for
        // good, and four shimmering lines forever say the opposite.
        <>
          <div className={keyValueRow()} data-part="key-value">
            <span>{t("screens.media.inLibrary")}</span>
            <span>
              {inFlight ? <SkeletonLine width="short" /> : t("screens.media.unknownFeminine")}
            </span>
          </div>
          <div className={keyValueRow()} data-part="key-value">
            <span>{t("screens.media.seasons")}</span>
            <span>
              {inFlight ? <SkeletonLine width="half" /> : t("screens.media.unknown")}
            </span>
          </div>
        </>
      ) : (
        !owns ? (
          <>
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.media.inLibrary")}</span>
              <span>
                <span className={statusDot({ tone: "neutral" })} data-part="status-dot"></span>
                {t("screens.media.no")}
              </span>
            </div>
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.media.follow")}</span>
              <span>
                {followed
                  ? t("screens.media.followActive")
                  : t("screens.media.followInactive")}
              </span>
            </div>
            {catalog.length ? (
              <div className={keyValueRow()} data-part="key-value">
                <span>{`${t("screens.media.catalogue")} ${isFilm ? "" : t("screens.media.catalogueKnown")}`}</span>
                <span>
                  {`${catalog.length} ${catalog.length > 1 ? t("screens.media.seasonLowerPlural") : t("screens.media.seasonLower")} · ${catalogEp} ${t("screens.media.episodes")}`}
                </span>
              </div>
            ) : (
              ""
            )}
          </>
        ) : isFilm ? (
          <>
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.media.owned")}</span>
              <span>
                <span className={statusDot({ tone: "success" })} data-part="status-dot"></span>
                {t("screens.media.yes")}
              </span>
            </div>
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.media.file")}</span>
              <span
                style={{
                  fontFamily: "ui-monospace,Menlo,monospace",
                  fontSize: "11px",
                }}
              >
                {`${baseTitle(title)}.${sheet?.y ?? "2026"}.MULTi.1080p.mkv`}
              </span>
            </div>
          </>
        ) : (
          <>
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.media.seasons")}</span>
              <span>{seasons.length || (seasonsInFlight ? <SkeletonLine width="short" /> : t("screens.media.unknown"))}</span>
            </div>
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.media.airedEpisodes")}</span>
              <span>{aired || (seasonsInFlight ? <SkeletonLine width="short" /> : t("screens.media.unknown"))}</span>
            </div>
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.media.ownedPlural")}</span>
              {/* A NUMBER IS AN ASSERTION TOO. `own` is derived from the
                  seasons read, so while that read is out it is zero — « you own
                  none of it », printed between two lines that say they do not
                  know yet. */}
              <span>{seasonsInFlight ? <SkeletonLine width="short" /> : own}</span>
            </div>
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.media.completeness")}</span>
              <span>
                <span
                  className={`pip ${pct === 100 ? "success" : pct === null ? "neutral" : "warning"}`} data-part="status-dot"
                ></span>
                {pct === null
                  ? seasonsInFlight ? <SkeletonLine width="short" /> : t("screens.media.unknownFeminine")
                  : pct + " %"}
              </span>
            </div>
          </>
        )
      )}
      </div>
      <SeasonList
        ownershipKnown={ownershipKnown}
        sheetInFlight={sheetInFlight}
        sheet={sheet}
        seasons={seasons}
        owns={owns}
        catalog={catalog}
        title={title}
      />
    </div>
  );
}
