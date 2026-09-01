// What the library holds of a medium: not owned, a film owned, or a series
// with its seasons, aired and owned counts and completeness — and the season
// list beneath.
import { useTranslation } from "react-i18next";
import { useMediaReference, type MediaSheet } from "./reference";
import { SeasonList } from "./season-list";
import type { CatalogSeason, MediaSheetFields } from "./sheet-fields";
import { factsPanel, keyValueRow, sectionHeading, statusDot } from "../../ui/variants";

export function MediaLibraryFacts({
  sheet,
  isFilm,
  owns,
  followed,
  seasons,
  own,
  aired,
  pct,
  catalog,
  catalogEp,
  title,
}: {
  sheet: (MediaSheet & MediaSheetFields) | null;
  isFilm: boolean;
  owns: boolean;
  followed: boolean;
  seasons: [number, number | null, number][];
  own: number;
  aired: number;
  pct: number | null;
  catalog: CatalogSeason[];
  catalogEp: number;
  title: string;
}) {
  const { baseTitle } = useMediaReference();
  const { t } = useTranslation();
  return (
    <div>
      <h2 className={sectionHeading()} data-part="heading" style={{ marginBottom: "6px" }}>
        {t("screens.media.library")}
      </h2>
      <div className={factsPanel()} data-part="panel">
        {!owns ? (
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
              <span>{seasons.length || t("screens.media.unknown")}</span>
            </div>
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.media.airedEpisodes")}</span>
              <span>{aired || t("screens.media.unknown")}</span>
            </div>
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.media.ownedPlural")}</span>
              <span>{own}</span>
            </div>
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.media.completeness")}</span>
              <span>
                <span
                  className={`pip ${pct === 100 ? "success" : pct === null ? "neutral" : "warning"}`} data-part="status-dot"
                ></span>
                {pct === null
                  ? t("screens.media.unknownFeminine")
                  : pct + " %"}
              </span>
            </div>
          </>
        )}
      </div>
      <SeasonList
        sheet={sheet}
        seasons={seasons}
        owns={owns}
        catalog={catalog}
        title={title}
      />
    </div>
  );
}
